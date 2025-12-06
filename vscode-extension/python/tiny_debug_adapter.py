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
        self._namespace: Optional[str] = None
        self._variable_handles: Dict[int, VariableHandle] = {}
        self._next_handle = 1

    # ----- DAP plumbing -----
    def _read_message(self) -> Optional[Dict[str, Any]]:
        header = b""
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            if line == b"\r\n":
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
        return json.loads(body.decode("utf-8"))

    def _send(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload)
        message = f"Content-Length: {len(data)}\r\n\r\n{data}"
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
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "stopped",
                "body": {"reason": "breakpoint", "threadId": 1},
            })
            try:
                command = self._command_queue.get(timeout=60.0)
            except queue.Empty:
                command = "continue"
            return command

        dbg = Debugger(on_pause=on_pause)
        for _, lines in self._breakpoints.items():
            dbg.set_breakpoints(None, set(lines))
        return dbg

    def _run_program(self, program: Path) -> None:
        try:
            source = program.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - I/O failure
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "output",
                "body": {"category": "stderr", "output": f"Failed to read program: {exc}\n"},
            })
            return
        debugger = self._debugger()
        self._namespace = self._namespace_for_path(program)
        try:
            compile_and_run(source, module_namespace=self._namespace, module_path=program, debugger=debugger)
        except Exception as exc:  # pragma: no cover - surfaced via output event
            self._send({
                "type": "event",
                "seq": self._next_seq(),
                "event": "output",
                "body": {"category": "stderr", "output": f"Runtime error: {exc}\n"},
            })
        self._send({
            "type": "event",
            "seq": self._next_seq(),
            "event": "terminated",
            "body": {},
        })

    # ----- Request handlers -----
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

    def handle_set_breakpoints(self, request: Dict[str, Any]) -> None:
        args = request.get("arguments", {})
        source = args.get("source", {})
        path = source.get("path")
        verified: List[Dict[str, Any]] = []
        if path:
            lines = [bp.get("line") for bp in args.get("breakpoints", []) if bp.get("line")]
            self._breakpoints[path] = lines
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

    def handle_launch(self, request: Dict[str, Any]) -> None:
        args = request.get("arguments", {})
        program = args.get("program")
        self._program = Path(program) if program else None
        response = {
            "type": "response",
            "seq": self._next_seq(),
            "request_seq": request["seq"],
            "command": "launch",
            "success": True,
            "body": {},
        }
        self._send(response)
        if self._program:
            self._thread = threading.Thread(target=self._run_program, args=(self._program,), daemon=True)
            self._thread.start()

    def handle_configuration_done(self, request: Dict[str, Any]) -> None:
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

    def _enqueue(self, command: str) -> None:
        self._command_queue.put(command)
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
        while True:
            message = self._read_message()
            if message is None:
                break
            command = message.get("command")
            if command in handlers:
                handlers[command](message)


def _self_test() -> None:
    details = {
        "python": sys.executable,
        "adapter": str(Path(__file__).resolve()),
        "cwd": str(Path.cwd()),
        "src_root": str(SRC_ROOT),
        "src_root_exists": SRC_ROOT.exists(),
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
        sys.exit(0)

    server = DAPServer()
    server.run()
