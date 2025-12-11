#!/usr/bin/env python3
"""Minimal Debug Adapter Protocol server for TinyLanguage.

The adapter runs the TinyLanguage interpreter in the same process using the
built-in debugger hooks. It supports a single thread, breakpoints, and basic
stepping so that the VS Code extension can provide a real debugging experience
instead of the previous terminal-based prototype.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import inspect
import bdb
import io
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT.parent / "src"
sys.path.insert(0, str(SRC_ROOT))

from tiny_language import Debugger, compile_and_run


@dataclass
class VariableHandle:
    label: str
    values: Dict[str, Any] = field(default_factory=dict)


class DAPServer:
    def __init__(self) -> None:
        self._seq = 0
        self._lock = threading.Lock()
        self._paused_snapshot = None
        self._command_queue: "queue.Queue[str]" = queue.Queue()
        self._breakpoints: Dict[str, List[int]] = {}
        self._thread: Optional[threading.Thread] = None
        self._program: Optional[Path] = None
        self._launch_args: Dict[str, Any] = {}
        self._namespace: Optional[str] = None
        self._launch_received = False
        self._configuration_done = False
        self._variable_handles: Dict[int, VariableHandle] = {}
        self._next_handle = 1
        self._log_lock = threading.Lock()
        self._log_handle = self._open_log_file()
        self._log_to_stderr = os.environ.get("TINYLANGUAGE_DAP_STDERR", "0") == "1"
        self._log("TinyLanguage debug adapter started (hello world)")
        self._initialized_sent = False
        self._last_client_message = time.monotonic()
        self._last_client_command: Optional[str] = None
        self._session_started_at = self._last_client_message
        self._shutdown = False
        self._watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
        self._watchdog_warning_sent = False
        self._python_mode = False

    def _open_log_file(self):
        log_path = os.environ.get("TINYLANGUAGE_DAP_LOG")
        if not log_path:
            return None
        try:
            path = Path(log_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            return path.open("a", encoding="utf-8")
        except OSError as exc:  # pragma: no cover - logging opt-in
            print(f"Failed to open debug log file {log_path}: {exc}", file=sys.stderr)
            return None

    def _log(self, message: str) -> None:
        timestamp = datetime.utcnow().isoformat() + "Z"
        if not self._log_handle:
            if self._log_to_stderr:
                print(f"[{timestamp}] {message}", file=sys.stderr)
            return
        with self._log_lock:
            self._log_handle.write(f"[{timestamp}] {message}\n")
            self._log_handle.flush()
            if self._log_to_stderr:
                print(f"[{timestamp}] {message}", file=sys.stderr)

    # ----- DAP plumbing -----
    def _read_message(self) -> Optional[Dict[str, Any]]:
        """Read a single DAP message from stdin."""

        header = b""
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            # Some clients terminate headers with "\n" instead of "\r\n". Treat any
            # blank line (after stripping whitespace) as the separator so the
            # adapter does not hang waiting for an exact CRLF match.
            if line.strip() == b"":
                break
            header += line

        headers = header.decode("utf-8").split("\r\n")
        length = 0
        for entry in headers:
            if entry.lower().startswith("content-length"):
                length = int(entry.split(":", 1)[1].strip())

        body = sys.stdin.buffer.read(length)
        if not body:
            return None

        message = json.loads(body.decode("utf-8"))
        self._log(f"<-- {message}")
        self._last_client_message = time.monotonic()
        self._last_client_command = message.get("command")
        return message

    def _send(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload)
        message = f"Content-Length: {len(data)}\r\n\r\n{data}"
        self._log(f"--> {payload}")
        sys.stdout.write(message)
        sys.stdout.flush()

    def _next_seq(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    # ----- TinyLanguage helpers -----
    def _namespace_for_path(self, path: Path) -> str:
        try:
            rel = path.resolve().relative_to(Path.cwd())
            return ".".join(rel.with_suffix("").parts)
        except Exception:
            return path.stem

    def _debugger(self):
        def on_pause(snapshot):
            self._paused_snapshot = snapshot
            self._log("Paused at breakpoint")
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "stopped",
                "body": {"reason": "breakpoint", "threadId": 1},
            })
            return self._wait_for_command()

        dbg = Debugger(on_pause=on_pause)
        for path, lines in self._breakpoints.items():
            namespace = self._namespace_for_path(Path(path)) if path else self._namespace
            dbg.set_breakpoints(namespace, set(lines))
        return dbg

    def _python_debugger(self, program: Path):
        server = self

        class _PythonDebugger(bdb.Bdb):
            def user_line(self, frame):  # pragma: no cover - exercised via VS Code
                filename = Path(frame.f_code.co_filename).resolve()
                if filename != program.resolve():
                    return
                server._paused_snapshot = {
                    "python": True,
                    "frame": frame,
                    "stack": inspect.getouterframes(frame),
                }
                server._log("Paused in Python program")
                server._send(
                    {
                        "type": "event",
                        "seq": server._next_seq(),
                        "event": "stopped",
                        "body": {"reason": "breakpoint", "threadId": 1},
                    }
                )
                command = server._wait_for_command()
                if command == "step_over":
                    self.set_next(frame)
                elif command == "step_in":
                    self.set_step()
                elif command == "step_out":
                    self.set_return(frame)
                else:
                    self.set_continue()

        dbg = _PythonDebugger()
        for path, lines in self._breakpoints.items():
            resolved = Path(path).resolve()
            for line in lines:
                try:
                    dbg.set_break(str(resolved), line)
                except Exception as exc:  # pragma: no cover - depends on source
                    self._log(f"Failed to set Python breakpoint at {resolved}:{line}: {exc}")
        return dbg

    def _wait_for_command(self) -> str:
        timeout = float(os.environ.get("TINYLANGUAGE_DAP_PAUSE_TIMEOUT", "30"))
        deadline = None if timeout <= 0 else time.monotonic() + timeout
        command = None
        while command is None:
            remaining = None if deadline is None else max(0.1, deadline - time.monotonic())
            try:
                command = self._command_queue.get(timeout=remaining)
            except queue.Empty:
                if deadline is None:
                    self._log("Still waiting for client command while paused")
                    continue
                if time.monotonic() >= deadline:
                    command = "continue"
                    self._log("No client command received while paused; continuing automatically after timeout")
                else:
                    self._log("Still waiting for client command while paused")
        self._log(f"Dequeued command from client: {command}")
        return command

    def _run_program(self, program: Path) -> None:
        self._log(f"Starting program run: {program}")
        try:
            source = program.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - I/O failure
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "output",
                "body": {"category": "stderr", "output": f"Failed to read program: {exc}\n"},
            })
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "terminated",
                "body": {},
            })
            return
        self._namespace = self._namespace_for_path(program)
        debugger = self._debugger()
        try:
            output = compile_and_run(
                source,
                module_namespace=self._namespace,
                module_path=program,
                debugger=debugger,
            )
        except Exception as exc:  # pragma: no cover - surfaced via output event
            self._log(f"Runtime error: {exc}")
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "output",
                "body": {"category": "stderr", "output": f"Runtime error: {exc}\n"},
            })
        else:
            if output:
                rendered = output if output.endswith("\n") else output + "\n"
                self._send({
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "output",
                    "body": {"category": "stdout", "output": rendered},
                })
        self._send({
            "type": "event",
            "seq": self._next_seq(),
            "event": "terminated",
            "body": {},
        })

    def _run_python_program(self, program: Path) -> None:
        self._log(f"Starting Python program run: {program}")
        self._namespace = str(program)
        debugger = self._python_debugger(program)
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        try:
            with open(program, "r", encoding="utf-8") as handle:
                code = handle.read()
        except Exception as exc:  # pragma: no cover - I/O failure
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "output",
                    "body": {"category": "stderr", "output": f"Failed to read program: {exc}\n"},
                }
            )
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "terminated",
                    "body": {},
                }
            )
            return

        try:
            compiled = compile(code, str(program), "exec")
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                debugger.runctx(compiled, {}, {})
        except SystemExit:
            pass
        except Exception as exc:  # pragma: no cover - runtime failure
            stderr_buffer.write(f"Exception in Python program: {exc}\n")
        stdout_value = stdout_buffer.getvalue()
        stderr_value = stderr_buffer.getvalue()
        if stdout_value:
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "output",
                    "body": {"category": "stdout", "output": stdout_value},
                }
            )
        if stderr_value:
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "output",
                    "body": {"category": "stderr", "output": stderr_value},
                }
            )
        self._send(
            {
                "type": "event",
                "seq": self._next_seq(),
                "event": "terminated",
                "body": {},
            }
        )

    # ----- Request handlers -----
    def _start_program_thread(self, trigger: str) -> None:
        if self._thread and self._thread.is_alive():
            self._log(f"Start skipped; program already running (trigger={trigger})")
            return
        if not self._program:
            self._log(f"Start skipped; no program set yet (trigger={trigger})")
            return
        if trigger == "launch" and not self._configuration_done:
            self._log("Launch received before configurationDone; starting anyway")
        self._log(f"Starting program thread (trigger={trigger})")
        target = self._run_python_program if self._python_mode else self._run_program
        self._thread = threading.Thread(target=target, args=(self._program,), daemon=True)
        self._thread.start()

    def handle_initialize(self, request: Dict[str, Any]) -> None:
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "initialize",
            "success": True,
            "body": {
                "supportsConfigurationDoneRequest": True,
                "supportsSetVariable": False,
            },
        }
        self._send(response)
        self._send({"type": "event", "seq": self._next_seq(), "event": "initialized"})
        self._initialized_sent = True
        if not self._watchdog_thread.is_alive():
            self._watchdog_thread.start()

    def handle_set_breakpoints(self, request: Dict[str, Any]) -> None:
        args = request.get("arguments", {})
        source = args.get("source", {})
        path = source.get("path")
        verified: List[Dict[str, Any]] = []
        if path:
            lines = [bp.get("line") for bp in args.get("breakpoints", []) if bp.get("line")]
            self._breakpoints[path] = lines
            self._log(f"Updated breakpoints for {path}: {lines}")
            verified = [{"verified": True, "line": line} for line in lines]
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "setBreakpoints",
            "success": True,
            "body": {"breakpoints": verified},
        }
        self._send(response)

    def handle_set_exception_breakpoints(self, request: Dict[str, Any]) -> None:
        # TinyLanguage does not currently differentiate exception types, but the
        # VS Code client always sends this request during configuration. Reply
        # with an empty set of breakpoints so the session can proceed.
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "setExceptionBreakpoints",
            "success": True,
            "body": {"breakpoints": []},
        }
        self._send(response)

    def handle_launch(self, request: Dict[str, Any]) -> None:
        args = request.get("arguments", {})
        program = args.get("program")
        self._python_mode = bool(args.get("pythonMode"))
        if not program:
            message = "Launch request is missing required 'program' path"
            self._log(message)
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "output",
                    "body": {"category": "stderr", "output": message + "\n"},
                }
            )
            response = {
                "type": "response",
                "seq": self._next_seq(),
                "request_seq": request.get("seq", 0),
                "command": "launch",
                "success": False,
                "message": message,
                "body": {},
            }
            self._send(response)
            return
        self._launch_received = True
        self._launch_args = args
        self._program = Path(program)
        self._log(f"Launch request for {self._program}")
        self._start_program_thread("launch")
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "launch",
            "success": True,
            "body": {},
        }
        self._send(response)

    def handle_configuration_done(self, request: Dict[str, Any]) -> None:
        self._configuration_done = True
        self._start_program_thread("configurationDone")
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "configurationDone",
            "success": True,
            "body": {},
        }
        self._send(response)

    def handle_threads(self, request: Dict[str, Any]) -> None:
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "threads",
            "success": True,
            "body": {"threads": [{"id": 1, "name": "Main Thread"}]},
        }
        self._send(response)

    def _frame_path(self) -> Optional[str]:
        return str(self._program) if self._program else None

    def handle_stack_trace(self, request: Dict[str, Any]) -> None:
        frames = []
        if self._paused_snapshot:
            if isinstance(self._paused_snapshot, dict) and self._paused_snapshot.get("python"):
                stack = self._paused_snapshot.get("stack") or []
                for idx, frame_info in enumerate(stack):
                    frames.append(
                        {
                            "id": idx + 1,
                            "name": frame_info.function,
                            "line": frame_info.lineno,
                            "column": 1,
                            "source": {"path": frame_info.filename},
                        }
                    )
            else:
                for idx, frame in enumerate(reversed(self._paused_snapshot.call_stack)):
                    frames.append({
                        "id": idx + 1,
                        "name": frame.qualified_name,
                        "line": frame.pos.line,
                        "column": frame.pos.col,
                        "source": {"path": self._frame_path()},
                    })
                frames.append({
                    "id": len(frames) + 1,
                    "name": "<current>",
                    "line": self._paused_snapshot.pos.line,
                    "column": self._paused_snapshot.pos.col,
                    "source": {"path": self._frame_path()},
                })
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "stackTrace",
            "success": True,
            "body": {"stackFrames": frames},
        }
        self._send(response)

    def handle_scopes(self, request: Dict[str, Any]) -> None:
        scopes = []
        if self._paused_snapshot:
            if isinstance(self._paused_snapshot, dict) and self._paused_snapshot.get("python"):
                frame = self._paused_snapshot.get("frame")
                if frame:
                    values = {**frame.f_globals, **frame.f_locals}
                    handle_id = self._next_handle
                    self._next_handle += 1
                    self._variable_handles[handle_id] = VariableHandle(
                        label="python_frame", values=values
                    )
                    scopes.append({
                        "name": "Python Frame",
                        "variablesReference": handle_id,
                        "expensive": False,
                    })
            else:
                for idx, scope in enumerate(self._paused_snapshot.scopes):
                    handle_id = self._next_handle
                    self._next_handle += 1
                    self._variable_handles[handle_id] = VariableHandle(
                        label=f"scope_{idx}", values=scope.values
                    )
                    scopes.append({
                        "name": f"Scope {idx}",
                        "variablesReference": handle_id,
                        "expensive": False,
                    })
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "scopes",
            "success": True,
            "body": {"scopes": scopes},
        }
        self._send(response)

    def handle_variables(self, request: Dict[str, Any]) -> None:
        args = request.get("arguments", {})
        handle_id = args.get("variablesReference")
        handle = self._variable_handles.get(handle_id)
        variables = []
        if handle:
            for name, value in handle.values.items():
                variables.append({
                    "name": name,
                    "value": repr(value),
                    "variablesReference": 0,
                })
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "variables",
            "success": True,
            "body": {"variables": variables},
        }
        self._send(response)

    def _handle_unknown(self, request: Dict[str, Any]) -> None:
        # Respond to unexpected requests so the client does not hang waiting for
        # a reply. Unknown commands are logged for easier diagnostics.
        command = request.get("command", "<unknown>")
        self._log(f"Received unsupported request: {command}")
        if request.get("type") == "request":
            response = {
                "type": "response",
                "seq": self._next_seq(),
                "request_seq": request.get("seq", 0),
                "command": command,
                "success": False,
                "message": f"Unsupported request: {command}",
            }
            self._send(response)

    def _watchdog(self) -> None:
        # If the client never sends configuration or launch requests after the
        # initialize handshake, provide a clear failure signal instead of
        # letting the adapter sit idle forever.
        while not self._shutdown:
            time.sleep(0.5)
            if not self._initialized_sent:
                continue
            if self._launch_received or self._configuration_done:
                break
            idle = time.monotonic() - self._last_client_message
            if idle > 3.0 and not self._watchdog_warning_sent:
                last_cmd = self._last_client_command or "<none>"
                elapsed = time.monotonic() - self._session_started_at
                log_hint = " set TINYLANGUAGE_DAP_LOG=/tmp/tiny_dap.log" if not self._log_handle else ""
                stderr_hint = " and TINYLANGUAGE_DAP_STDERR=1" if not self._log_to_stderr else ""
                warning = (
                    "No launch/configuration requests received. "
                    "VS Code should send 'launch' after 'initialize'; if it did not, "
                    "ensure a TinyLanguage launch.json entry exists or use the "
                    "'TinyLanguage: Launch active file (prototype)' command." +
                    (" Enable adapter logging with" + log_hint + stderr_hint if (log_hint or stderr_hint) else "") +
                    f" Last client command: {last_cmd}; idle for {idle:.1f}s (session {elapsed:.1f}s)."
                )
                self._log(warning)
                self._send(
                    {
                        "type": "event",
                        "seq": self._next_seq(),
                        "event": "output",
                        "body": {"category": "stderr", "output": warning + "\n"},
                    }
                )
                self._watchdog_warning_sent = True

    def _enqueue(self, command: str) -> None:
        self._command_queue.put(command)
        self._log(f"Enqueued command: {command}")
        response = {
            "type": "event",
            "seq": self._next_seq(),
            "event": "continued",
            "body": {"threadId": 1},
        }
        self._send(response)

    def handle_continue(self, request: Dict[str, Any], command: str = "continue") -> None:
        self._enqueue(command)
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": request["command"],
            "success": True,
            "body": {"allThreadsContinued": True},
        }
        self._send(response)

    def handle_disconnect(self, request: Dict[str, Any]) -> None:
        if self._thread and self._thread.is_alive():
            self._enqueue("continue")
            self._thread.join(timeout=1)
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "disconnect",
            "success": True,
            "body": {},
        }
        self._send(response)

    # ----- Main loop -----
    def run(self) -> None:
        handlers = {
            "initialize": self.handle_initialize,
            "setBreakpoints": self.handle_set_breakpoints,
            "setExceptionBreakpoints": self.handle_set_exception_breakpoints,
            "launch": self.handle_launch,
            "configurationDone": self.handle_configuration_done,
            "threads": self.handle_threads,
            "stackTrace": self.handle_stack_trace,
            "scopes": self.handle_scopes,
            "variables": self.handle_variables,
            "continue": self.handle_continue,
            "next": lambda req: self.handle_continue(req, "step_over"),
            "stepIn": lambda req: self.handle_continue(req, "step_in"),
            "stepOut": lambda req: self.handle_continue(req, "step_out"),
            "disconnect": self.handle_disconnect,
        }
        self._log("Debug adapter started")
        while True:
            message = self._read_message()
            if message is None or self._shutdown:
                self._log("No more messages; shutting down")
                break
            command = message.get("command")
            if command in handlers:
                handlers[command](message)
            else:
                self._handle_unknown(message)


def _self_test() -> None:
    try:
        module_path = inspect.getfile(compile_and_run)
    except Exception:  # pragma: no cover - diagnostic guardrail
        module_path = "<unknown>"

    details = {
        "python": sys.executable,
        "adapter": str(Path(__file__).resolve()),
        "cwd": str(Path.cwd()),
        "src_root": str(SRC_ROOT),
        "src_root_exists": SRC_ROOT.exists(),
        "tiny_language_module": module_path,
        "sys_path_sample": sys.path[:5],
        "tiny_language_loaded": Debugger is not None and compile_and_run is not None,
    }
    print(json.dumps(details, indent=2))


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        try:
            _self_test()
        except Exception as exc:  # pragma: no cover - diagnostic path
            print(f"Self-test failed: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            DAPServer().run()
        except KeyboardInterrupt:  # pragma: no cover - graceful shutdown
            pass
