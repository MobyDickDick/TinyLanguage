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
import tempfile
import inspect
import bdb
import io
import importlib.util
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
import socket
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT.parent / "src"
if SRC_ROOT.exists():
    sys.path.insert(0, str(SRC_ROOT))

# These globals are populated by _load_tiny_language().
Debugger = None
compile_and_run = None


def _load_module_from_path(path: Path):
    """Attempt to load the TinyLanguage module from an explicit file path."""

    if not path.exists():
        return None

    spec = importlib.util.spec_from_file_location("tiny_language", path)
    if not spec or not spec.loader:  # pragma: no cover - defensive guardrail
        return None

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # pragma: no cover - import failure
        return None
    return module


def _load_tiny_language() -> None:
    """Populate Debugger/compile_and_run with a best-effort runtime import."""

    global Debugger, compile_and_run

    runtime_hint = os.environ.get("TINYLANGUAGE_RUNTIME")
    candidates = []
    if runtime_hint:
        hint_path = Path(runtime_hint)
        # Accept either a direct file path or a directory containing the runtime.
        if hint_path.is_dir():
            candidates.append(hint_path / "tiny_language.py")
            candidates.append(hint_path / "tiny_language_stitched.py")
        else:
            candidates.append(hint_path)
    if SRC_ROOT.exists():
        candidates.append(SRC_ROOT / "tiny_language.py")
        candidates.append(SRC_ROOT / "tiny_language_stitched.py")

    module = None
    for candidate in candidates:
        module = _load_module_from_path(candidate)
        if module:
            break

    if module is None:
        try:
            module = __import__("tiny_language")
        except Exception as exc:  # pragma: no cover - diagnostic guardrail
            message = (
                "TinyLanguage runtime could not be loaded. Set tinylanguage.runtimePath "
                "to a valid tiny_language.py or install the extension from the repository. "
                f"Last error: {exc}"
            )
            raise ImportError(message) from exc

    Debugger = getattr(module, "Debugger", None)
    compile_and_run = getattr(module, "compile_and_run", None)


_load_tiny_language()


def _env_var_truthy(name: str) -> bool:
    """Return True when the environment variable is set to a truthy value."""

    value = os.environ.get(name)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    return normalized in {"1", "true", "yes", "on"}


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
        self._log_to_stderr = _env_var_truthy("TINYLANGUAGE_DAP_STDERR")
        log_requested = os.environ.get("TINYLANGUAGE_DAP_LOG")
        self._log_handle = self._open_log_file()
        # If the user explicitly requested logging but the file could not be
        # opened, fall back to stderr so logs are not silently dropped. This
        # avoids "blocked" sessions where no diagnostics are recorded because
        # the configured path was invalid or unwritable.
        if log_requested and not self._log_handle:
            self._log_to_stderr = True
        self._log("TinyLanguage debug adapter started (hello world)")
        self._initialized_sent = False
        self._last_client_message = time.monotonic()
        self._last_client_command: Optional[str] = None
        self._session_started_at = self._last_client_message
        self._shutdown = False
        self._watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
        self._watchdog_warning_sent = False
        self._python_mode = False
        self._process_event_sent = False
        self._thread_event_sent = False
        self._debugger_instance = None
        self._pause_requested = False
        self._streaming_output = False
        self._console_pipe: Optional[Path] = None
        self._reader = sys.stdin.buffer
        self._writer = sys.stdout.buffer
        self._transport = "stdio"
        self._tcp_server: Optional[socket.socket] = None
        self._tcp_client: Optional[socket.socket] = None
        self._tcp_host: Optional[str] = None
        self._tcp_port: Optional[int] = None
        self._configure_transport()
        # Start the watchdog immediately so that we can surface handshake issues
        # (e.g., VS Code never sending an initialize request) instead of
        # blocking forever with no diagnostics.
        self._watchdog_thread.start()

    def _emit_warning(self, message: str) -> None:
        """Log a warning and surface it to the client output stream."""

        self._log(message)
        self._send(
            {
                "type": "event",
                "seq": self._next_seq(),
                "event": "output",
                "body": {"category": "stderr", "output": message + "\n"},
            }
        )

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
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self._log_handle:
            if self._log_to_stderr:
                print(f"[{timestamp}] {message}", file=sys.stderr)
            return
        with self._log_lock:
            self._log_handle.write(f"[{timestamp}] {message}\n")
            self._log_handle.flush()
            if self._log_to_stderr:
                print(f"[{timestamp}] {message}", file=sys.stderr)

    def _configure_transport(self) -> None:
        """Initialize the DAP transport (stdio by default, TCP when requested)."""

        port_value = os.environ.get("TINYLANGUAGE_DAP_TCP_PORT")
        if not port_value:
            self._transport = "stdio"
            self._reader = sys.stdin.buffer
            self._writer = sys.stdout.buffer
            return

        try:
            port = int(str(port_value).strip())
        except ValueError:
            self._emit_warning(f"Invalid TINYLANGUAGE_DAP_TCP_PORT value: {port_value!r}")
            self._transport = "stdio"
            self._reader = sys.stdin.buffer
            self._writer = sys.stdout.buffer
            return

        host = os.environ.get("TINYLANGUAGE_DAP_TCP_HOST", "127.0.0.1")
        try:
            self._tcp_server = socket.create_server((host, port), backlog=1)
        except Exception as exc:  # pragma: no cover - socket binding failure
            self._emit_warning(f"Failed to bind debug adapter TCP server on {host}:{port}: {exc}")
            self._transport = "stdio"
            self._reader = sys.stdin.buffer
            self._writer = sys.stdout.buffer
            return

        self._tcp_server.settimeout(15)
        bound_host, bound_port = self._tcp_server.getsockname()
        self._tcp_host = str(bound_host)
        self._tcp_port = int(bound_port)
        self._transport = "tcp"
        self._reader = None
        self._writer = None
        self._log(f"Debug adapter listening on TCP {self._tcp_host}:{self._tcp_port}")

    def _await_client(self) -> bool:
        """Accept a TCP client when the transport uses sockets."""

        if self._transport != "tcp":
            return True
        if self._tcp_client:
            return True
        if self._tcp_server is None:
            self._emit_warning("TCP transport requested but no server socket is available")
            return False
        try:
            self._log("Waiting for VS Code to connect to the debug adapter socket")
            client, addr = self._tcp_server.accept()
        except socket.timeout:
            self._emit_warning("Timed out waiting for VS Code to connect to the debug adapter socket")
            return False
        except Exception as exc:  # pragma: no cover - unexpected accept failure
            self._emit_warning(f"Failed to accept debug adapter client: {exc}")
            return False
        self._tcp_client = client
        self._reader = client.makefile("rb")
        self._writer = client.makefile("wb")
        self._log(f"VS Code connected from {addr}")
        return True

    def _close_transport(self) -> None:
        """Tear down any active transport connections."""

        try:
            if self._reader and self._reader is not sys.stdin.buffer:
                self._reader.close()
        finally:
            self._reader = None

        try:
            if self._writer and self._writer is not sys.stdout.buffer:
                self._writer.close()
        finally:
            self._writer = None

        if self._tcp_client:
            try:
                self._tcp_client.close()
            finally:
                self._tcp_client = None
        if self._tcp_server:
            try:
                self._tcp_server.close()
            finally:
                self._tcp_server = None

    # ----- DAP plumbing -----
    def _read_message(self) -> Optional[Dict[str, Any]]:
        """Read a single DAP message from the configured transport."""

        if self._reader is None:
            return None

        header = b""
        while True:
            line = self._reader.readline()
            if not line:
                return None
            # Some clients terminate headers with "\n" instead of "\r\n". Treat any
            # blank line (after stripping whitespace) as the separator so the
            # adapter does not hang waiting for an exact CRLF match.
            if line.strip() == b"":
                break
            header += line

        length = 0
        for entry in header.decode("utf-8").splitlines():
            if ":" not in entry:
                continue
            key, value = entry.split(":", 1)
            if key.lower() == "content-length":
                try:
                    length = int(value.strip())
                except ValueError:
                    self._log(f"Invalid Content-Length header: {entry!r}")
                    return None

        if length <= 0:
            self._log("Missing or zero Content-Length header in incoming message")
            return None

        body = self._reader.read(length)
        if not body:
            return None

        message = json.loads(body.decode("utf-8"))
        self._log(f"<-- {message}")
        self._last_client_message = time.monotonic()
        self._last_client_command = message.get("command")
        return message

    def _send(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload)
        message = f"Content-Length: {len(data)}\r\n\r\n{data}".encode("utf-8")
        self._log(f"--> {payload}")
        if self._writer is None:
            return
        self._writer.write(message)
        self._writer.flush()

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
            reason = "pause" if self._pause_requested else "breakpoint"
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "stopped",
                "body": {"reason": reason, "threadId": 1},
            })
            self._pause_requested = False
            return self._wait_for_command()

        dbg = Debugger(on_pause=on_pause, mirror_stdout=False)
        dbg.on_output = lambda text: self._send(
            {
                "type": "event",
                "seq": self._next_seq(),
                "event": "output",
                "body": {"category": "stdout", "output": text},
            }
        )
        self._streaming_output = True
        self._debugger_instance = dbg
        self._sync_all_breakpoints()
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
                reason = "pause" if server._pause_requested else "breakpoint"
                server._send(
                    {
                        "type": "event",
                        "seq": server._next_seq(),
                        "event": "stopped",
                        "body": {"reason": reason, "threadId": 1},
                    }
                )
                server._pause_requested = False
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
        self._debugger_instance = dbg
        self._sync_all_breakpoints()
        return dbg

    def _apply_breakpoints(self, path: Optional[str], lines: List[int]) -> None:
        debugger = self._debugger_instance
        if debugger is None:
            return

        # Python-mode debugging uses the standard library bdb hooks.
        if isinstance(debugger, bdb.Bdb):
            if not path:
                return
            resolved = Path(path).resolve()
            try:
                debugger.clear_all_file_breaks(str(resolved))
            except Exception as exc:  # pragma: no cover - depends on source
                self._log(f"Failed to clear Python breakpoints for {resolved}: {exc}")
            for line in lines:
                try:
                    debugger.set_break(str(resolved), line)
                except Exception as exc:  # pragma: no cover - depends on source
                    self._log(f"Failed to set Python breakpoint at {resolved}:{line}: {exc}")
            return

        namespace = self._namespace_for_path(Path(path)) if path else self._namespace
        try:
            debugger.set_breakpoints(namespace, set(lines))
        except Exception as exc:  # pragma: no cover - defensive guardrail
            self._log(f"Failed to set breakpoints for {path or '<module>'}: {exc}")

    def _sync_all_breakpoints(self) -> None:
        if not self._debugger_instance:
            return
        for path, lines in self._breakpoints.items():
            self._apply_breakpoints(path, lines)

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
                    self._clear_breakpoints_after_timeout()
                else:
                    self._log("Still waiting for client command while paused")
        self._log(f"Dequeued command from client: {command}")
        return command

    def _clear_breakpoints_after_timeout(self) -> None:
        """Drop all configured breakpoints after a pause timeout.

        When no client commands arrive before ``TINYLANGUAGE_DAP_PAUSE_TIMEOUT``
        elapses, the adapter auto-continues. Clearing breakpoints in that
        situation prevents the runtime from immediately pausing again on the
        next loop iteration, which would otherwise make headless runs appear
        stuck even though a timeout was reached.
        """

        if not self._breakpoints:
            return

        self._log("Clearing breakpoints after pause timeout")
        paths = list(self._breakpoints.keys())
        for path in paths:
            self._breakpoints[path] = []
            self._apply_breakpoints(path, [])

    def _maybe_setup_console_pipe(self) -> None:
        """Create a named pipe for Console.read_line if requested/possible.

        Stdin/stdout carry DAP traffic, so interactive input would collide with the
        protocol stream. When running on POSIX, expose a FIFO path via
        TINYLANGUAGE_DAP_STDIN_PIPE so users can write input from a terminal
        (e.g., ``cat > /tmp/...``) while the debugger stays attached.
        """

        if self._console_pipe or os.environ.get("TINYLANGUAGE_DAP_STDIN_PIPE"):
            # A pipe was already provided or created earlier in the session.
            existing = os.environ.get("TINYLANGUAGE_DAP_STDIN_PIPE")
            if existing:
                self._console_pipe = Path(existing)
            return

        if os.name == "nt":  # pragma: no cover - FIFO not available on Windows
            self._log("Console pipe request skipped: named pipes via mkfifo require POSIX")
            return

        pipe_dir = Path(tempfile.gettempdir()) / f"tiny_dap_console_{os.getpid()}"
        pipe_dir.mkdir(parents=True, exist_ok=True)
        pipe_path = pipe_dir / "stdin.fifo"
        try:
            os.mkfifo(pipe_path)
        except FileExistsError:
            pass
        except OSError as exc:  # pragma: no cover - FIFO creation failure
            self._log(f"Failed to create console pipe {pipe_path}: {exc}")
            return

        self._console_pipe = pipe_path
        os.environ["TINYLANGUAGE_DAP_STDIN_PIPE"] = str(pipe_path)
        self._send(
            {
                "type": "event",
                "seq": self._next_seq(),
                "event": "output",
                "body": {
                    "category": "console",
                    "output": (
                        f"TinyLanguage console input is available via FIFO: {pipe_path}\n"
                        "Write lines into this pipe from a terminal (e.g., `cat > "
                        f"{pipe_path}`) to satisfy Console.read_line while debugging.\n"
                    ),
                },
            }
        )
        self._log(f"Console pipe ready at {pipe_path}")

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
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "exited",
                    "body": {"exitCode": 1},
                }
            )
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "terminated",
                "body": {},
            })
            return
        self._namespace = self._namespace_for_path(program)
        self._streaming_output = False
        debugger = self._debugger()
        if self._transport == "stdio":
            self._maybe_setup_console_pipe()
        previous_stdin_guard = os.environ.get("TINYLANGUAGE_DAP_DISABLE_STDIN")
        if self._transport == "stdio":
            os.environ["TINYLANGUAGE_DAP_DISABLE_STDIN"] = "1"
        try:
            output = compile_and_run(
                source,
                module_namespace=self._namespace,
                module_path=program,
                debugger=debugger,
                stream_output=False,
            )
        except Exception as exc:  # pragma: no cover - surfaced via output event
            self._log(f"Runtime error: {exc}")
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "output",
                "body": {"category": "stderr", "output": f"Runtime error: {exc}\n"},
            })
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "exited",
                    "body": {"exitCode": 1},
                }
            )
        else:
            if output and not self._streaming_output:
                rendered = output if output.endswith("\n") else output + "\n"
                self._send({
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "output",
                    "body": {"category": "stdout", "output": rendered},
                })
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "exited",
                    "body": {"exitCode": 0},
                }
            )
        finally:
            if self._transport == "stdio":
                if previous_stdin_guard is None:
                    os.environ.pop("TINYLANGUAGE_DAP_DISABLE_STDIN", None)
                else:
                    os.environ["TINYLANGUAGE_DAP_DISABLE_STDIN"] = previous_stdin_guard
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
            code_obj = sys.exc_info()[1]
            try:
                exit_code = int(code_obj.code)
            except Exception:
                exit_code = 0
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "exited",
                    "body": {"exitCode": exit_code},
                }
            )
        except Exception as exc:  # pragma: no cover - runtime failure
            stderr_buffer.write(f"Exception in Python program: {exc}\n")
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "exited",
                    "body": {"exitCode": 1},
                }
            )
        else:
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "exited",
                    "body": {"exitCode": 0},
                }
            )
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
        if not self._launch_received:
            self._log(f"Start skipped; launch not received yet (trigger={trigger})")
            return
        if not self._configuration_done:
            self._log(f"Start deferred; waiting for configurationDone (trigger={trigger})")
            return
        if not self._program:
            self._log(f"Start skipped; no program set yet (trigger={trigger})")
            return
        self._log(f"Starting program thread (trigger={trigger})")
        target = self._run_python_program if self._python_mode else self._run_program
        self._thread = threading.Thread(target=target, args=(self._program,), daemon=True)
        self._thread.start()
        if not self._thread_event_sent:
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "thread",
                    "body": {"reason": "started", "threadId": 1},
                }
            )
            self._thread_event_sent = True

    def handle_initialize(self, request: Dict[str, Any]) -> None:
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "initialize",
            "success": True,
            "body": {
                "supportsConfigurationDoneRequest": True,
                "supportsPauseRequest": True,
                "supportsSetVariable": False,
            },
        }
        self._send(response)
        self._send({"type": "event", "seq": self._next_seq(), "event": "initialized"})
        self._initialized_sent = True

    def handle_set_breakpoints(self, request: Dict[str, Any]) -> None:
        args = request.get("arguments", {})
        source = args.get("source", {})
        path = source.get("path")
        verified: List[Dict[str, Any]] = []
        if path:
            lines = [bp.get("line") for bp in args.get("breakpoints", []) if bp.get("line")]
            self._breakpoints[path] = lines
            self._log(f"Updated breakpoints for {path}: {lines}")
            self._apply_breakpoints(path, lines)
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
        if not self._process_event_sent:
            try:
                name = self._program.name
                cwd = str(self._program.parent)
            except Exception:
                name = str(self._program)
                cwd = None
            self._send(
                {
                    "type": "event",
                    "seq": self._next_seq(),
                    "event": "process",
                    "body": {
                        "name": name,
                        "systemProcessId": os.getpid(),
                        "isLocalProcess": True,
                        "startMethod": "launch",
                        "cwd": cwd,
                    },
                }
            )
            self._process_event_sent = True
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

    def handle_evaluate(self, request: Dict[str, Any]) -> None:
        args = request.get("arguments", {})
        expr = args.get("expression", "")
        result: Optional[str] = None
        if self._paused_snapshot:
            if isinstance(self._paused_snapshot, dict) and self._paused_snapshot.get("python"):
                frame = self._paused_snapshot.get("frame")
                if frame:
                    values = {**frame.f_globals, **frame.f_locals}
                    try:
                        result = repr(eval(expr, values, values))  # noqa: S307 - trusted pause context
                    except Exception as exc:  # pragma: no cover - depends on expression
                        result = f"Evaluation error: {exc}"
            else:
                for scope in self._paused_snapshot.scopes:
                    if expr in scope.values:
                        result = repr(scope.values[expr])
                        break
                if result is None:
                    result = "<unknown>"
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request.get("seq", 0),
            "command": "evaluate",
            "success": True,
            "body": {"result": result or "<not paused>", "variablesReference": 0},
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
            idle = time.monotonic() - self._last_client_message

            # If the client never initiates the DAP handshake, emit a warning so
            # the user understands why the session appears stuck.
            if not self._initialized_sent and idle > 3.0 and not self._watchdog_warning_sent:
                elapsed = time.monotonic() - self._session_started_at
                log_hint = " set TINYLANGUAGE_DAP_LOG=/tmp/tiny_dap.log" if not self._log_handle else ""
                stderr_hint = " and TINYLANGUAGE_DAP_STDERR=1" if not self._log_to_stderr else ""
                warning = (
                    "No messages received from VS Code (waiting for 'initialize'). "
                    "If the session does not start, verify the TinyLanguage debug configuration is selected" +
                    (" and enable adapter logging with" + log_hint + stderr_hint if (log_hint or stderr_hint) else "") +
                    f". Idle for {idle:.1f}s (session {elapsed:.1f}s)."
                )
                self._emit_warning(warning)
                self._watchdog_warning_sent = True
                continue

            if not self._initialized_sent:
                continue
            if self._configuration_done:
                break

            if self._launch_received and not self._configuration_done:
                if idle > 3.0 and not self._watchdog_warning_sent:
                    last_cmd = self._last_client_command or "<none>"
                    elapsed = time.monotonic() - self._session_started_at
                    log_hint = " set TINYLANGUAGE_DAP_LOG=/tmp/tiny_dap.log" if not self._log_handle else ""
                    stderr_hint = " and TINYLANGUAGE_DAP_STDERR=1" if not self._log_to_stderr else ""
                    warning = (
                        "Launch received but no configurationDone request. "
                        "VS Code should send 'configurationDone' after setting breakpoints; "
                        "if it did not, verify the TinyLanguage debug configuration is selected." +
                        (" Enable adapter logging with" + log_hint + stderr_hint if (log_hint or stderr_hint) else "") +
                        f" Last client command: {last_cmd}; idle for {idle:.1f}s (session {elapsed:.1f}s)."
                    )
                    self._emit_warning(warning)
                    # Force the launch to start so the user is not stuck even if
                    # the client failed to send configurationDone.
                    self._configuration_done = True
                    self._start_program_thread("watchdog")
                    self._watchdog_warning_sent = True
                continue

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
                self._emit_warning(warning)
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

    def handle_pause(self, request: Dict[str, Any]) -> None:
        self._pause_requested = True
        debugger = self._debugger_instance
        if debugger is not None:
            request_pause = getattr(debugger, "request_pause", None)
            if callable(request_pause):
                request_pause()
            elif hasattr(debugger, "set_step"):
                debugger.set_step()
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "pause",
            "success": True,
            "body": {},
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
        self._shutdown = True
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
            "evaluate": self.handle_evaluate,
            "continue": self.handle_continue,
            "pause": self.handle_pause,
            "next": lambda req: self.handle_continue(req, "step_over"),
            "stepIn": lambda req: self.handle_continue(req, "step_in"),
            "stepOut": lambda req: self.handle_continue(req, "step_out"),
            "disconnect": self.handle_disconnect,
        }
        self._log("Debug adapter started")
        if not self._await_client():
            self._log("Shutting down: no client connection established")
            self._close_transport()
            return
        while True:
            if self._shutdown:
                self._log("Shutdown requested; shutting down")
                break
            message = self._read_message()
            if message is None:
                self._log("No more messages; shutting down")
                break
            command = message.get("command")
            if command in handlers:
                handlers[command](message)
            else:
                self._handle_unknown(message)
        self._close_transport()


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
