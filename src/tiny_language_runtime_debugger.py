"""Debugger primitives for TinyLanguage runtime execution.

This module isolates the stepping, breakpoint, and snapshot plumbing used by
the interpreter runtime. Keeping these helpers here keeps the core runtime
implementation focused on evaluation semantics while still offering rich
debugger hooks for the CLI, LSP, and DAP integrations.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from tiny_errors import SourcePos, StackFrame


@dataclass
class ScopeSnapshot:
    """Captured locals/types for a single environment frame."""

    values: Dict[str, object]
    types: Dict[str, str]


@dataclass
class DebugSnapshot:
    """Point-in-time debugger view of execution state."""

    pos: SourcePos
    namespace: Optional[str]
    call_stack: Tuple[StackFrame, ...]
    scopes: List[ScopeSnapshot]


@dataclass
class StepRequest:
    """Describe a pending step command and its target depth."""

    mode: str
    depth: int


class Debugger:
    """Lightweight, synchronous debugger controller for stepping and breakpoints."""

    VALID_COMMANDS = {"continue", "step_in", "step_over", "step_out", "pause"}

    def __init__(
        self,
        on_pause: Optional[Callable[[DebugSnapshot], str]] = None,
        *,
        mirror_stdout: bool = True,
    ):
        self.breakpoints: Dict[Optional[str], Set[int]] = defaultdict(set)
        self.on_pause = on_pause
        self.command_queue: deque[str] = deque()
        self.snapshots: List[DebugSnapshot] = []
        self.pending_step: Optional[StepRequest] = None
        self.last_location: Optional[Tuple[Optional[str], int]] = None
        self.force_pause: bool = False
        # When False, the runtime will avoid mirroring program output to
        # ``stdout`` while debugging. This is useful for DAP transports that use
        # stdout for the protocol stream and expect program output to be emitted
        # via explicit ``output`` events instead of direct writes.
        self.mirror_stdout = mirror_stdout

    def set_breakpoints(self, namespace: Optional[str], lines: Set[int]) -> None:
        """Register breakpoints for a namespace (or ``None`` for the active module)."""

        self.breakpoints[namespace] = set(lines)

    def enqueue_commands(self, *commands: str) -> None:
        """Queue debugger commands to run in order as pauses are hit."""

        for cmd in commands:
            self._validate_command(cmd)
            self.command_queue.append(cmd)

    def request_pause(self) -> None:
        """Force the debugger to pause at the next opportunity."""

        self.force_pause = True

    def should_pause(self, pos: SourcePos, namespace: Optional[str], depth: int) -> bool:
        location = (namespace, pos.line)
        if self.force_pause:
            return True
        if pos.line in self.breakpoints.get(namespace, set()) or pos.line in self.breakpoints.get(None, set()):
            return True
        return self._matches_step(location, depth)

    def handle_pause(self, snapshot: DebugSnapshot, depth: int) -> None:
        """Record a pause snapshot and update stepping state."""

        self.snapshots.append(snapshot)
        self.last_location = (snapshot.namespace, snapshot.pos.line)
        # Clear any pending forced pause now that we've yielded control.
        self.force_pause = False
        command = self._next_command(snapshot)
        self.pending_step = self._step_for_command(command, depth)

    def _next_command(self, snapshot: DebugSnapshot) -> str:
        if self.on_pause is not None:
            command = self.on_pause(snapshot)
        elif self.command_queue:
            command = self.command_queue.popleft()
        else:
            command = "continue"
        self._validate_command(command)
        return command

    def _validate_command(self, command: str) -> None:
        if command not in self.VALID_COMMANDS:
            raise ValueError(f"invalid debugger command {command!r}; expected one of {sorted(self.VALID_COMMANDS)}")

    def _step_for_command(self, command: str, depth: int) -> Optional[StepRequest]:
        if command == "continue":
            return None
        if command == "step_in":
            return StepRequest("step_in", depth)
        if command == "step_over":
            return StepRequest("step_over", depth)
        if command == "step_out":
            return StepRequest("step_out", max(0, depth - 1))
        return None

    def _matches_step(self, location: Tuple[Optional[str], int], depth: int) -> bool:
        if self.pending_step is None:
            return False
        if self.pending_step.mode == "step_in":
            return location != self.last_location
        if self.pending_step.mode == "step_over":
            return depth <= self.pending_step.depth and location != self.last_location
        if self.pending_step.mode == "step_out":
            return depth <= self.pending_step.depth and location != self.last_location
        return False
