"""Runtime helpers: module resolution, heap management, and async utilities.

This segment contains the import mechanics, concurrency primitives, and the core
runtime container used by the evaluator. Docstrings focus on public-facing
behaviors so integrators can navigate the stitched module without reading the
entire implementation.
"""

import logging
import time

from collections import defaultdict, deque

# ----- Runtime -----


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        super().__init__()
        self.value = value


@dataclass
class ScopeSnapshot:
    values: Dict[str, Any]
    types: Dict[str, str]


@dataclass
class DebugSnapshot:
    pos: SourcePos
    namespace: Optional[str]
    call_stack: Tuple[StackFrame, ...]
    scopes: List[ScopeSnapshot]


@dataclass
class StepRequest:
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
        # Track whether the pause was explicitly requested (e.g. pause-on-entry)
        # so session resets can preserve intentional pauses while clearing stale
        # state such as previous step requests.
        self._requested_pause: bool = False
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
        self._requested_pause = True

    def reset_session(self) -> None:
        """Clear transient state between program runs while keeping breakpoints."""

        self.snapshots.clear()
        self.pending_step = None
        self.last_location = None
        # Preserve explicit pause requests (e.g. pause-on-entry) while clearing
        # any stale pause flags inherited from previous runs.
        self.force_pause = self._requested_pause
        # Pause requests should apply only to the next run. After carrying the
        # request into ``force_pause`` for the new session, clear the flag so a
        # single pause-on-entry request does not force every subsequent run to
        # halt immediately.
        self._requested_pause = False

    def should_pause(self, pos: SourcePos, namespace: Optional[str], depth: int) -> bool:
        location = (namespace, pos.line)
        if self.force_pause:
            return True
        if pos.line in self.breakpoints.get(namespace, set()) or pos.line in self.breakpoints.get(None, set()):
            return True
        return self._matches_step(location, depth)

    def handle_pause(self, snapshot: DebugSnapshot, depth: int) -> None:
        self.snapshots.append(snapshot)
        self.last_location = (snapshot.namespace, snapshot.pos.line)
        # Clear any pending forced pause now that we've yielded control.
        self.force_pause = False
        self._requested_pause = False
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


@dataclass
class BaseView:
    obj: Dict[str, Any]
    class_name: str


@dataclass
class NamespaceRef:
    runtime: "Runtime"
    name: str


def _import_binding_name(module: str, alias: Optional[str]) -> str:
    if alias:
        return alias
    stripped = module.lstrip(".") or module
    return stripped.split(".")[-1]


class ModuleResolver:
    """Locate and load TinyLanguage modules from configurable search roots.

    The resolver accepts optional search paths (including the ``TINYPATH``
    environment variable) and memoizes successfully loaded modules so repeated
    imports are cheap. It also guards against circular imports by tracking the
    current resolution stack.
    """

    def __init__(self, search_paths: Optional[List[Path]] = None):
        env_paths = os.environ.get("TINYPATH", "")
        configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
        default_roots = [Path.cwd(), Path(__file__).parent]
        self.search_paths: List[Path] = search_paths or configured_paths + default_roots
        self.cache: Dict[Path, NamespaceRef] = {}
        self._in_progress: List[Path] = []

    def _resolve_name(self, raw: str, caller_namespace: Optional[str], pos: Optional[SourcePos]) -> str:
        """Normalize relative import names against the caller's namespace.

        A leading dot sequence (e.g. ``.foo`` or ``..bar.baz``) is expanded using
        the caller's module namespace. Errors include source span information to
        aid diagnostics in the parser and linter.
        """
        leading = len(raw) - len(raw.lstrip("."))
        if leading == 0:
            return raw
        if not caller_namespace:
            raise TinyLangError(
                format_error("", pos or SourcePos.origin(), "relative import outside a module", code="E008"),
                pos or SourcePos.origin(),
                code="E008",
            )
        base = caller_namespace.split(".")
        if leading > len(base):
            raise TinyLangError(
                format_error(
                    "",
                    pos or SourcePos.origin(),
                    "relative import traverses beyond module root",
                    code="E008",
                ),
                pos or SourcePos.origin(),
                code="E008",
            )
        trimmed = base[: len(base) - leading]
        remainder = raw.lstrip(".")
        if remainder:
            trimmed.append(remainder)
        return ".".join(part for part in trimmed if part)

    def _candidate_paths(self, module_name: str, caller_path: Optional[Path]) -> List[Path]:
        """Return possible filesystem paths for a module name.

        The search order starts next to the caller's module (for relative
        imports) before falling back to configured search roots. Each candidate
        mirrors Python's ``pkg.subpkg.module`` to ``pkg/subpkg/module.tiny``
        translation.
        """
        rel_path = Path(*module_name.split("."))
        candidates: List[Path] = []
        roots: List[Path] = []
        if caller_path:
            roots.append(caller_path.parent)
        roots.extend(self.search_paths)
        for root in roots:
            candidates.append((root / rel_path).with_suffix(".tiny"))
        return candidates

    def import_module(
        self,
        name: str,
        runtime: "Runtime",
        *,
        caller_namespace: Optional[str],
        caller_path: Optional[Path],
        pos: Optional[SourcePos] = None,
    ) -> NamespaceRef:
        """Import a module, executing it if necessary and caching the namespace."""
        resolved_name = self._resolve_name(name, caller_namespace, pos)
        for candidate in self._candidate_paths(resolved_name, caller_path):
            resolved_path = candidate.resolve()
            if resolved_path in self.cache:
                return self.cache[resolved_path]
            if resolved_path.exists():
                if resolved_path in self._in_progress:
                    raise TinyLangError(
                        format_error(
                            "",
                            pos or SourcePos.origin(),
                            f"circular import involving {resolved_path}",
                            code="E008",
                        ),
                        pos or SourcePos.origin(),
                        code="E008",
                    )
                self._in_progress.append(resolved_path)
                try:
                    module_env = Environment(parent=None, namespace=resolved_name, runtime=runtime)
                    compile_and_run(
                        resolved_path.read_text(encoding="utf-8"),
                        env=module_env,
                        runtime=runtime,
                        module_namespace=resolved_name,
                        module_path=resolved_path,
                        module_resolver=self,
                    )
                    ns_ref = NamespaceRef(runtime, resolved_name)
                    self.cache[resolved_path] = ns_ref
                    return ns_ref
                finally:
                    self._in_progress.remove(resolved_path)
        raise TinyLangError(
            format_error(
                "", pos or SourcePos.origin(), f"module '{name}' not found on search path", code="E008"
            ),
            pos or SourcePos.origin(),
            code="E008",
        )


@dataclass
class SpawnHandle:
    thread: threading.Thread
    done: threading.Event
    cancelled: threading.Event
    result: Any = None
    error: Optional[BaseException] = None


@dataclass
class CancellationToken:
    """Coordinated cancellation primitive shared across spawned tasks."""

    cancelled: threading.Event = field(default_factory=threading.Event)
    reason: Optional[str] = None
    _linked: List[SpawnHandle] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def cancel(self, reason: Optional[str] = None) -> bool:
        """Mark the token as cancelled and propagate to linked handles."""
        with self._lock:
            already = self.cancelled.is_set()
            if already:
                return False
            self.reason = reason
            self.cancelled.set()
            for handle in list(self._linked):
                handle.cancelled.set()
            return True

    def link_handle(self, handle: SpawnHandle) -> bool:
        """Link a spawn handle so it reacts to future cancellations."""
        with self._lock:
            if handle in self._linked:
                return False
            if self.cancelled.is_set():
                handle.cancelled.set()
                return False
            self._linked.append(handle)
            return True


class Runtime:
    def __init__(self, source: str):
        self._lock = threading.RLock()
        self.heap: Dict[int, List[Any]] = {}
        self.allocations: Dict[int, int] = {}
        self.freed_allocations: Dict[int, int] = {}
        self.freed_ptrs: Set[int] = set()
        self.heap_cell_types: Dict[int, Dict[int, str]] = {}
        self.ptr_tags: Dict[int, str] = {}
        self.ops: Dict[Tuple[str, Optional[str], Optional[str]], Any] = {}
        self.methods: Dict[Tuple[str, str], MethodDef] = {}
        self.types: Dict[str, Dict[str, Any]] = {}
        self.variant_to_type: Dict[str, str] = {}
        self.next_ptr = 1
        self.output: List[str] = []
        self.functions: Dict[str, Fn] = {}
        self.native_functions: Dict[str, Callable[..., Any]] = {}
        self.global_env: Optional["Environment"] = None
        self.error_messages: List[str] = []
        self.source = source
        self.source_map: Dict[Optional[str], str] = {None: source}
        self.namespace_envs: Dict[str, "Environment"] = {}
        self.module_resolver: ModuleResolver = ModuleResolver()
        self.current_module_path: Optional[Path] = None
        self.current_module_namespace: Optional[str] = None
        self.call_stack: List[StackFrame] = []
        self.debugger: Optional[Debugger] = None
        self.stream_output: bool = True
        self.streamed_output: bool = False
        self.trace_log_path: Optional[str] = os.environ.get("TINYLANG_TRACE_LOG")
        self.trace_every_statement: bool = os.environ.get("TINYLANG_TRACE_EVERY_STATEMENT", "0") == "1"
        self.trace_heartbeat_secs: float = float(os.environ.get("TINYLANG_TRACE_HEARTBEAT_SECS", "1.0"))
        self.trace_to_stdout: bool = os.environ.get("TINYLANG_TRACE_STDOUT", "0") not in {"0", "", "false", "False"}
        self._trace_logger: Optional[logging.Logger] = None
        self._last_trace_time: float = 0.0
        self._last_trace_location: Optional[Tuple[Optional[str], int]] = None
        if self.trace_log_path:
            self._setup_trace_logger()

    @staticmethod
    def _qualify_name(name: str, namespace: Optional[str]) -> str:
        return f"{namespace}.{name}" if namespace else name

    def _source_for_namespace(self, namespace: Optional[str]) -> str:
        with self._lock:
            if namespace in self.source_map:
                return self.source_map[namespace]
        return self.source

    def _format_stacktrace(self, stack: Sequence[StackFrame]) -> str:
        if not stack:
            return ""
        lines = ["Stack trace:"]
        for frame in reversed(stack):
            lines.append(f"  at {frame.qualified_name} (line {frame.pos.line}, col {frame.pos.col})")
        return "\n".join(lines)

    def _setup_trace_logger(self) -> None:
        Path(self.trace_log_path).parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"tiny_language.trace.{id(self)}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.handlers.clear()
        handler = logging.FileHandler(self.trace_log_path, mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        if self.trace_to_stdout:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(stream_handler)
        self._trace_logger = logger

    def _log_trace(self, node: IR, env: "Environment", namespace: Optional[str]) -> None:
        if self._trace_logger is None:
            return
        now = time.time()
        pos = getattr(node, "pos", SourcePos.origin()) or SourcePos.origin()
        location = (namespace, pos.line)
        should_log = self.trace_every_statement or now - self._last_trace_time >= self.trace_heartbeat_secs
        if not should_log and location == self._last_trace_location:
            return
        self._last_trace_time = now if should_log else self._last_trace_time
        self._last_trace_location = location
        stack_overview = " > ".join(frame.qualified_name for frame in self.call_stack) or "<root>"
        scope_keys = ", ".join(sorted(getattr(env, "values", {}).keys()))
        self._trace_logger.debug(
            "executing %s at %s:%d (col %d); depth=%d; stack=%s; env=%s",
            node.__class__.__name__,
            namespace or "<module>",
            pos.line,
            getattr(pos, "col", 0),
            len(self.call_stack),
            stack_overview,
            scope_keys,
        )

    def _capture_scopes(self, env: "Environment") -> List[ScopeSnapshot]:
        scopes: List[ScopeSnapshot] = []
        current: Optional["Environment"] = env
        while current:
            scopes.append(ScopeSnapshot(values=dict(current.values), types=dict(current.types)))
            current = current.parent
        return scopes

    def _maybe_pause(self, node: IR, env: "Environment", namespace: Optional[str]) -> None:
        self._log_trace(node, env, namespace)
        if self.debugger is None:
            return
        pos = getattr(node, "pos", SourcePos.origin()) or SourcePos.origin()
        depth = len(self.call_stack)
        if self.debugger.should_pause(pos, namespace, depth):
            snapshot = DebugSnapshot(
                pos=pos,
                namespace=namespace,
                call_stack=tuple(self.call_stack),
                scopes=self._capture_scopes(env),
            )
            if self._trace_logger is not None:
                self._trace_logger.debug(
                    "pause at %s:%d; depth=%d; pending_step=%s; breakpoints=%s",
                    namespace or "<module>",
                    pos.line,
                    depth,
                    getattr(self.debugger, "pending_step", None),
                    self.debugger.breakpoints,
                )
            self.debugger.handle_pause(snapshot, depth)

    def _record_error(
        self,
        msg: str,
        pos: Optional[SourcePos] = None,
        *,
        code: str = "E000",
        hint: Optional[str] = None,
        formatted: Optional[str] = None,
    ) -> None:
        if formatted is None:
            source = self._source_for_namespace(self.current_module_namespace if pos is not None else None)
            base = format_error(source, pos, msg, code=code, hint=hint) if pos is not None else msg
            stack_part = self._format_stacktrace(self.call_stack)
            formatted = f"{base}\n{stack_part}" if stack_part else base
        with self._lock:
            # Only keep the most recent runtime error so `errorMessage` reflects
            # the latest failure instead of accumulating older ones.
            self.error_messages = [formatted]

    def _error(
        self,
        msg: str,
        pos: SourcePos,
        *,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        candidates: Optional[List[str]] = None,
        ) -> TinyLangError:
        derived_code, derived_hint = _classify_error(msg, candidates)
        code = code or derived_code
        hint = hint or derived_hint
        source = self._source_for_namespace(self.current_module_namespace)
        formatted = format_error(source, pos, msg, code=code, hint=hint)
        stack = tuple(self.call_stack)
        if stack:
            formatted = f"{formatted}\n{self._format_stacktrace(stack)}"
        self._record_error(msg, pos, code=code, hint=hint, formatted=formatted)
        return TinyLangError(formatted, pos, code=code, hint=hint, stack=stack)

    def _ensure_error_has_stack(self, err: TinyLangError) -> TinyLangError:
        if err.stack:
            return err
        stack = tuple(self.call_stack)
        if not stack:
            return err
        err.stack = stack
        err.message = f"{err.message}\n{self._format_stacktrace(stack)}"
        return err

    @staticmethod
    def _error_value(err: TinyLangError) -> Dict[str, Any]:
        stack_strings = [
            f"{frame.qualified_name} (line {frame.pos.line}, col {frame.pos.col})" for frame in err.stack
        ]
        return {
            "__tag__": "Error",
            "code": err.code,
            "message": str(err),
            "hint": err.hint,
            "stack": stack_strings,
        }

    @property
    def error_message(self) -> Optional[str]:
        with self._lock:
            if not self.error_messages:
                return None
            return self.error_messages[-1]

    # heap helpers
    def __new(self, n: int) -> int:
        if n < 0:
            raise RuntimeError("alloc error: negative size")
        with self._lock:
            p = self.next_ptr
            self.next_ptr += 1
            self.heap[p] = [0 for _ in range(int(n))]
            self.allocations[p] = int(n)
            self.freed_allocations.pop(p, None)
            self.heap_cell_types[p] = {}
            self.freed_ptrs.discard(p)
            return p

    @staticmethod
    def _pointer_label(p: Any) -> str:
        type_name = type(p).__name__
        if isinstance(p, (int, float)) and str(p).isnumeric():
            return str(int(p))
        return f"{p!r} ({type_name})"

    def _resolve_ptr(self, p: Any, pos: Optional[SourcePos], *, op: str) -> Tuple[Optional[int], Optional[List[Any]]]:
        """Validate and resolve a heap pointer for the requested operation.

        Returns a tuple of `(pointer, cells)` where either entry may be `None` if
        validation failed and an error was recorded.
        """

        try:
            ip = int(p)
        except Exception:
            message = f"heap {op} error: pointer {self._pointer_label(p)} is not numeric"
            self._record_error(message, pos)
            return None, None

        if isinstance(p, float) and not p.is_integer():
            message = f"heap {op} error: pointer {self._pointer_label(p)} is not an integer pointer"
            self._record_error(message, pos)
            return None, None

        if ip < 1:
            message = (
                f"heap {op} error: pointer {ip} is invalid (must refer to a live positive allocation)"
            )
            self._record_error(message, pos)
            return None, None

        with self._lock:
            if ip in self.freed_ptrs:
                size_part = self.freed_allocations.get(ip)
                size_hint = f" (size {size_part})" if size_part is not None else ""
                message = f"heap {op} error: pointer {ip} was already freed{size_hint}"
                self._record_error(message, pos)
                return None, None
            try:
                cells = self.heap[ip]
            except KeyError:
                live = sorted(self.heap.keys())
                freed = sorted(self.freed_ptrs)
                details: List[str] = []
                if live:
                    details.append(f"live: {live}")
                if freed:
                    details.append(f"freed: {freed}")
                context = f" ({'; '.join(details)})" if details else ""
                message = f"heap {op} error: unknown pointer {ip}{context}"
                self._record_error(message, pos)
                return None, None
            return ip, cells

    def _parse_heap_index(self, i: Any, pos: Optional[SourcePos]) -> Optional[int]:
        """Parse an index argument and record helpful errors when invalid."""

        try:
            idx = int(i)
        except Exception:
            message = f"heap access error: index {i!r} is not numeric"
            self._record_error(message, pos)
            return None

        if isinstance(i, float) and not i.is_integer():
            message = f"heap access error: index {self._pointer_label(i)} is not an integer index"
            self._record_error(message, pos)
            return None

        return idx

    def delete(self, p: Any, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        ip, _ = self._resolve_ptr(p, pos, op="delete")
        if ip is None:
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": self.error_message or ""}}

        with self._lock:
            self.heap.pop(ip, None)
            self.heap_cell_types.pop(ip, None)
            self.ptr_tags.pop(ip, None)
            size = self.allocations.pop(ip, None)
            if size is not None:
                self.freed_allocations[ip] = size
            self.freed_ptrs.add(ip)
        return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}

    def heap_get(self, p: Any, i: Any, *, pos: Optional[SourcePos] = None) -> Any:
        idx = self._parse_heap_index(i, pos)
        if idx is None:
            return None

        ip, cells = self._resolve_ptr(p, pos, op="access")
        if ip is None or cells is None:
            return None

        size = len(cells)
        if idx < 0 or idx >= size:
            range_hint = "empty allocation" if size == 0 else f"valid indices: 0..{size - 1}"
            self._record_error(
                f"heap access error: index {idx} out of range for pointer {ip} (size {size}; {range_hint})",
                pos,
            )
            return None
        return cells[idx]

    def heap_set(self, p: Any, i: Any, v: Any, *, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        idx = self._parse_heap_index(i, pos)
        if idx is None:
            msg = self.error_message or ""
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": msg}}

        ip, cells = self._resolve_ptr(p, pos, op="access")
        if ip is None or cells is None:
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": self.error_message or ""}}

        size = len(cells)
        if idx < 0 or idx >= size:
            range_hint = "empty allocation" if size == 0 else f"valid indices: 0..{size - 1}"
            message = f"heap access error: index {idx} out of range for pointer {ip} (size {size}; {range_hint})"
            self._record_error(message, pos)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": message}}

        with self._lock:
            expected = self.heap_cell_types.get(ip, {}).get(idx)
            actual = self._value_type_name(v)
            if expected is not None and expected != actual:
                message = f"heap type mismatch at {ip}[{idx}]: expected {expected} but got {actual}"
                self._record_error(message, pos, code="E014")
                return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": message}}
            self.heap[ip][idx] = v
            self.heap_cell_types.setdefault(ip, {})[idx] = actual
        return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}

    def heap_leak_report(self) -> Dict[str, Any]:
        """Summarize live heap allocations for leak tracking in tests."""

        with self._lock:
            live = {ptr: len(cells) for ptr, cells in self.heap.items()}
            leak_count = len(live)
            return {
                "live": live,
                "count": leak_count,
                "total_cells": sum(live.values()),
                "allocations": dict(self.allocations),
                "freed_sizes": dict(self.freed_allocations),
                "freed": sorted(self.freed_ptrs),
                "freed_count": len(self.freed_ptrs),
                "has_leaks": leak_count > 0,
            }

    def tag(self, p: Any, typ: Any, *, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        try:
            with self._lock:
                self.ptr_tags[int(p)] = str(typ)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            self._record_error(str(e), pos)
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def __get_tag(self, v: Any) -> Optional[str]:
        if isinstance(v, dict) and "__tag__" in v:
            return v["__tag__"]
        if isinstance(v, BaseView):
            return v.class_name
        try:
            iv = int(v)
            with self._lock:
                if iv in self.ptr_tags:
                    return self.ptr_tags[iv]
        except Exception:
            pass
        return None

    def _value_type_name(self, value: Any) -> Optional[str]:
        if isinstance(value, dict) and "__type__" in value:
            return str(value.get("__type__"))
        tag = self.__get_tag(value)
        if tag:
            return tag
        if value is None:
            return "Null"
        if isinstance(value, bool):
            return "Bool"
        if isinstance(value, int) and not isinstance(value, bool):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "string"
        return type(value).__name__

    def _infer_type_name(self, value: Any) -> str:
        """Return a broad type label for variables defined without annotations.

        The runtime already tracks concrete types (e.g., distinguishing `int` from
        `float`) for annotated parameters and return values. For unannotated
        variables we allow a simple inference step so that numeric values start out
        as the general "number" type, making later `int`/`float` updates valid
        without counting as type changes. Other values keep their concrete name.
        """

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return "number"
        return self._value_type_name(value) or type(value).__name__

    def _check_assignment_type(
        self, env: "Environment", name: str, value: Any, pos: SourcePos, *, local_only: bool = False
    ) -> None:
        expected = env.type_of(name, local_only=local_only)
        if expected is None:
            return
        if not self._type_matches(expected, value):
            actual = self._value_type_name(value) or type(value).__name__
            raise self._error(
                f"type change for variable {name}: expected {expected} but got {actual}",
                pos,
                code="E014",
                hint="Use a new variable or cast explicitly if a different type is required.",
            )

    def _type_matches(self, expected: str, value: Any) -> bool:
        actual = self._value_type_name(value)
        if actual is None:
            return False
        expected_norm = expected.strip()
        optional = expected_norm.endswith("?")
        base_expected = expected_norm[:-1].strip() if optional else expected_norm
        actual_norm = actual.strip() if isinstance(actual, str) else str(actual)
        if optional and actual_norm.lower() == "null":
            return True
        if base_expected == actual_norm or base_expected.lower() == actual_norm.lower():
            return True
        if base_expected.lower() == "number" and actual_norm.lower() in {"number", "int", "float"}:
            return True
        if base_expected.lower() == "string" and actual_norm.lower() == "string":
            return True
        if base_expected.lower() in {"bool", "boolean"} and actual_norm.lower() in {"bool", "boolean"}:
            return True
        if base_expected == "Null" and value is None:
            return True
        if optional and actual_norm.lower() != "null":
            return self._type_matches(base_expected, value)
        return False

    def _enforce_annotation(self, expected: str, value: Any, *, label: str, pos: SourcePos) -> None:
        if not self._type_matches(expected, value):
            actual = self._value_type_name(value) or type(value).__name__
            raise self._error(
                f"type mismatch for {label}: expected {expected} but got {actual}",
                pos,
                code="E009",
                hint="Adjust the type annotation (use '?' to allow Null) or pass a compatible value to satisfy the hint.",
            )

    def _enforce_inferred_return(self, owner: Any, value: Any, *, label: str, pos: SourcePos) -> None:
        expected = getattr(owner, "inferred_return_type", None)
        inferred = self._infer_type_name(value)
        if expected is None:
            owner.inferred_return_type = inferred
            return
        if self._type_matches(expected, value):
            return
        actual = self._value_type_name(value) or type(value).__name__
        raise self._error(
            f"inferred return type for {label} changed: expected {expected} but got {actual}",
            pos,
            code="E014",
            hint="Add an explicit return type annotation or keep return values consistent to avoid implicit type changes.",
        )

    @staticmethod
    def _number_fields(val: Any) -> Optional[Dict[str, Any]]:
        if isinstance(val, dict) and val.get("__tag__") == "Number":
            return val.get("__fields__", {}).get("Number")
        return None

    @staticmethod
    def _make_number(value: Any, error: str) -> Dict[str, Any]:
        return {"__tag__": "Number", "__fields__": {"Number": {"value": value, "error": error}}}

    @staticmethod
    def _intervall_fields(val: Any) -> Optional[Dict[str, Any]]:
        if isinstance(val, dict) and val.get("__tag__") == "NumberIntervall":
            return val.get("__fields__", {}).get("NumberIntervall")
        return None

    @staticmethod
    def _make_intervall(lower: Any, upper: Any, error: str) -> Dict[str, Any]:
        return {
            "__tag__": "NumberIntervall",
            "__fields__": {"NumberIntervall": {"lower": lower, "upper": upper, "error": error}},
        }

    def _number_to_intervall(self, value: Any) -> Optional[Dict[str, Any]]:
        fields = self._number_fields(value)
        if fields is None:
            return None
        err = fields.get("error", "normal") or "normal"
        if err in {"plus_infinity", "minus_infinity", "any_number"}:
            return self._make_intervall(0, 0, err)
        lower = fields.get("value", 0)
        upper = fields.get("value", 0)
        return self._make_intervall(lower, upper, "normal")

    def _coerce_to_number(self, val: Any) -> Any:
        if val is None:
            return self._make_number(0, "normal")
        if self.__get_tag(val) == "Number":
            return val
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return self._make_number(val, "normal")
        return val

    def _coerce_to_intervall(self, val: Any) -> Any:
        if val is None:
            return self._make_intervall(0, 0, "normal")
        if self.__get_tag(val) == "NumberIntervall":
            return val
        from_number = self._number_to_intervall(val)
        if from_number is not None:
            return from_number
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return self._make_intervall(val, val, "normal")
        return val

    def _coerce_numeric_operands(
        self, op: str, a: Any, b: Any, ta: Optional[str], tb: Optional[str]
    ) -> Tuple[Any, Any]:
        arithmetic_ops = {"+", "-", "*", "/", "^"}
        if op not in arithmetic_ops:
            return a, b
        if ta == "NumberIntervall" or tb == "NumberIntervall":
            return self._coerce_to_intervall(a), self._coerce_to_intervall(b)
        if ta == "Number" or tb == "Number":
            return self._coerce_to_number(a), self._coerce_to_number(b)
        return a, b

    def _number_binop(self, op: str, a: Any, b: Any) -> Any:
        fields_a = self._number_fields(a)
        fields_b = self._number_fields(b)
        if fields_a is None or fields_b is None:
            return None

        val_a = fields_a.get("value", 0)
        val_b = fields_b.get("value", 0)
        err_a = fields_a.get("error", "normal") or "normal"
        err_b = fields_b.get("error", "normal") or "normal"

        def mk(err: str, value: Any = 0) -> Dict[str, Any]:
            return self._make_number(value, err)

        def overflow(v: float) -> Optional[str]:
            limit = 1e21
            if v > limit:
                return "plus_infinity"
            if v < -limit:
                return "minus_infinity"
            return None

        if op == "^":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a != "normal" or err_b != "normal":
                return mk("any_number")
            if not isinstance(val_b, (int, float)):
                return mk("any_number")
            if isinstance(val_b, float):
                if not val_b.is_integer():
                    return mk("any_number")
                val_b = int(val_b)
            try:
                res = val_a**val_b
            except Exception:
                return mk("any_number")
            ov = overflow(res)
            if ov:
                return mk(ov)
            rounded = False
            if isinstance(res, float):
                rounded = not res.is_integer()
                if not rounded:
                    res = int(res)
            return mk("rounded" if rounded else "normal", res)

        if op == "+":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a == "minus_infinity" and err_b == "normal" and val_b > 0:
                return mk("any_number")
            if err_b == "minus_infinity" and err_a == "normal" and val_a > 0:
                return mk("any_number")
            if err_a == "plus_infinity" or err_b == "plus_infinity":
                return mk("plus_infinity")
            if err_a == "minus_infinity" or err_b == "minus_infinity":
                return mk("minus_infinity")
            res = val_a + val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "-":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a == "plus_infinity" and err_b == "normal" and val_b > 0:
                return mk("any_number")
            if err_a == "plus_infinity" or err_b == "minus_infinity":
                return mk("plus_infinity")
            if err_a == "minus_infinity" or err_b == "plus_infinity":
                return mk("minus_infinity")
            res = val_a - val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "*":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a in {"plus_infinity", "minus_infinity"} and err_b in {"plus_infinity", "minus_infinity"}:
                sign = 1
                if err_a == "minus_infinity":
                    sign *= -1
                if err_b == "minus_infinity":
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            if err_a in {"plus_infinity", "minus_infinity"}:
                if val_b == 0:
                    return mk("any_number")
                sign = -1 if err_a == "minus_infinity" else 1
                if val_b < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            if err_b in {"plus_infinity", "minus_infinity"}:
                if val_a == 0:
                    return mk("any_number")
                sign = -1 if err_b == "minus_infinity" else 1
                if val_a < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            res = val_a * val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "/":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_b in {"plus_infinity", "minus_infinity"} and err_a == "normal":
                return mk("normal", 0)
            if err_b == "normal" and val_b == 0:
                if err_a == "plus_infinity":
                    return mk("plus_infinity")
                if err_a == "minus_infinity":
                    return mk("minus_infinity")
                if val_a > 0:
                    return mk("plus_infinity")
                if val_a < 0:
                    return mk("minus_infinity")
                return mk("any_number")
            if err_a in {"plus_infinity", "minus_infinity"}:
                if err_b in {"plus_infinity", "minus_infinity"}:
                    return mk("any_number")
                sign = -1 if err_a == "minus_infinity" else 1
                if err_b == "normal" and val_b < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            res = val_a / val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            rounded = False
            if isinstance(res, float):
                rounded = not res.is_integer()
                if not rounded:
                    res = int(res)
            return mk("rounded" if rounded else "normal", res)

        return None

    def _number_power(self, base: Any, exponent: Any) -> Any:
        fields_a = self._number_fields(base)
        fields_b = self._number_fields(exponent)
        if fields_a is None or fields_b is None:
            return None

        val_a = fields_a.get("value", 0)
        val_b = fields_b.get("value", 0)
        err_a = fields_a.get("error", "normal") or "normal"
        err_b = fields_b.get("error", "normal") or "normal"

        def mk(err: str, value: Any = 0) -> Dict[str, Any]:
            return self._make_number(value, err)

        def overflow(v: float) -> Optional[str]:
            limit = 1e21
            if v > limit:
                return "plus_infinity"
            if v < -limit:
                return "minus_infinity"
            return None

        if err_a == "any_number" or err_b == "any_number":
            return mk("any_number")
        if err_a != "normal" or err_b != "normal":
            return mk("any_number")
        try:
            res = val_a**val_b
        except Exception:
            return mk("any_number")
        ov = overflow(res)
        if ov:
            return mk(ov)
        rounded = False
        if isinstance(res, float):
            rounded = not res.is_integer()
            if not rounded:
                res = int(res)
        return mk("rounded" if rounded else "normal", res)

    def __binop(self, op: str, a: Any, b: Any) -> Any:
        if a is None:
            a = 0
        if b is None:
            b = 0
        ta = self.__get_tag(a)
        tb = self.__get_tag(b)
        a, b = self._coerce_numeric_operands(op, a, b, ta, tb)
        ta = self.__get_tag(a)
        tb = self.__get_tag(b)
        num_res = self._number_binop(op, a, b)
        if num_res is not None:
            return num_res
        key = (op, ta, tb)
        with self._lock:
            impl = self.ops.get(key)
        if impl:
            return impl(a, b)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b
        if op == "^":
            if isinstance(b, float):
                if not b.is_integer():
                    raise RuntimeError("exponent for ^ must be an integer")
                b = int(b)
            elif not isinstance(b, int):
                raise RuntimeError("exponent for ^ must be an integer")
            return a**b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        raise RuntimeError(f"unsupported op {op}")

    def field_get(self, obj: Any, key: str, *, pos: Optional[SourcePos] = None) -> Any:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        if isinstance(target_obj, NamespaceRef):
            env = self.namespace_envs.get(target_obj.name)
            if env and env.contains(key):
                return env.get(key)
            qualified = self._qualify_name(key, target_obj.name)
            with self._lock:
                if qualified in self.functions:
                    return NamespaceRef(self, qualified)
            self._record_error(f"unknown field {key}", pos)
            return None
        if isinstance(target_obj, dict) and "__fields__" in target_obj:
            try:
                fmap = self._resolve_field_storage(
                    target_obj, key, owner_hint, target_obj["__tag__"], allow_write=False
                )
                return fmap[key]
            except Exception as err:  # noqa: BLE001
                self._record_error(str(err), pos)
                return None
        try:
            return target_obj[str(key)]
        except Exception:
            self._record_error(f"unknown field {key}", pos)
            return None

    def field_set(self, obj: Any, key: str, val: Any) -> None:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        if isinstance(target_obj, dict) and "__fields__" in target_obj:
            fmap = self._resolve_field_storage(target_obj, key, owner_hint, target_obj["__tag__"], allow_write=True)
            fmap[key] = val
            return
        target_obj[str(key)] = val

    def register_type(
        self,
        name: str,
        fields: Optional[List[Tuple[str, str]]] = None,
        variants: Optional[List[TypeVariant]] = None,
    ) -> None:
        variant_map: Dict[str, Dict[str, str]] = {}
        if variants:
            variant_map = {v.name: dict(v.fields) for v in variants}
        elif fields is not None:
            variant_map[name] = dict(fields)
        with self._lock:
            for vname in variant_map:
                self.variant_to_type[vname] = name
            self.types[str(name)] = {
                "kind": "sum" if variants else "product",
                "fields": variant_map.get(name, {}),
                "variants": variant_map,
            }

        def _register_constructor(target_name: str, field_defs: Dict[str, str]) -> None:
            field_order = list(field_defs.keys())

            def _ctor(*args: Any) -> Dict[str, Any]:
                if len(args) != len(field_order):
                    raise RuntimeError(
                        f"{target_name} expects {len(field_order)} argument(s); got {len(args)}"
                    )
                init = dict(zip(field_order, args))
                return self.instantiate_variant(target_name, init, type_name=name)

            self.register_native(target_name, _ctor)

        if variants:
            for vname, fields_map in variant_map.items():
                _register_constructor(vname, fields_map)
        elif fields is not None:
            _register_constructor(name, variant_map.get(name, {}))

    def _type_variants(self, name: str) -> Optional[Dict[str, Dict[str, str]]]:
        with self._lock:
            tinfo = self.types.get(name)
        if not tinfo:
            return None
        variants = tinfo.get("variants")
        if variants:
            return variants
        if tinfo.get("fields") is not None:
            return {name: tinfo.get("fields", {})}
        return None

    def instantiate_variant(
        self, variant: str, init: Dict[str, Any], *, type_name: Optional[str] = None, pos: Optional[SourcePos] = None
    ) -> Dict[str, Any]:
        inferred_type = type_name or self.variant_to_type.get(variant)
        if inferred_type is None:
            raise self._error(f"unknown variant {variant}", pos)
        variants = self._type_variants(inferred_type)
        if not variants or variant not in variants:
            raise self._error(f"variant {variant} not allowed for type {inferred_type}", pos)
        expected_fields = variants.get(variant, {})
        missing = [f for f in expected_fields if f not in init]
        extra = [f for f in init if f not in expected_fields]
        if missing:
            raise self._error(f"missing field(s) for variant {variant}: {', '.join(missing)}", pos)
        if extra:
            raise self._error(f"unknown field(s) for variant {variant}: {', '.join(extra)}", pos)
        value: Dict[str, Any] = {"__tag__": variant, "__type__": inferred_type}
        value.update(init)
        return value

    def register_class(self, name: str, fields: List[Tuple[str, str]], bases: Optional[List[str]] = None) -> None:
        base_list = list(bases) if bases is not None else []
        with self._lock:
            existing = self.types.get(name)
            if existing:
                if existing.get("kind") != "class":
                    raise RuntimeError(f"type {name} already defined and is not a class")
                existing["fields"].update(dict(fields))
                if bases is not None:
                    existing["bases"] = base_list
                return
            self.types[str(name)] = {"kind": "class", "fields": dict(fields), "bases": base_list}

    def register_method(self, md: MethodDef) -> None:
        with self._lock:
            self.methods[(md.class_name, md.name)] = md

    def register_native(self, name: str, func: Callable[..., Any], namespace: Optional[str] = None) -> None:
        qualified = self._qualify_name(name, namespace)
        with self._lock:
            self.native_functions[qualified] = func

    def register_operator(self, opdef: OpDef, env: "Environment") -> None:
        def impl(a_val: Any, b_val: Any) -> Any:
            op_env = Environment(parent=env, namespace=env.namespace, runtime=self)
            op_env.define(opdef.a_name, a_val, opdef.pos)
            op_env.define(opdef.b_name, b_val, opdef.pos)
            res = self.eval_block(opdef.body, op_env, env.namespace)
            if isinstance(res, ReturnSignal):
                return res.value
            return res

        with self._lock:
            self.ops[(opdef.op, opdef.a_type, opdef.b_type)] = impl

    def class_mro(self, name: str) -> List[str]:
        with self._lock:
            info = self.types.get(name)
            if info is None or info.get("kind") != "class":
                raise RuntimeError(f"unknown class {name}")
            bases = list(info.get("bases", []))
        mro: List[str] = [name]
        for base in bases:
            with self._lock:
                if base not in self.types:
                    raise RuntimeError(f"unknown base class {base} for {name}")
            for ancestor in self.class_mro(base):
                if ancestor not in mro:
                    mro.append(ancestor)
        return mro

    @staticmethod
    def _split_field_name(fname: str) -> Tuple[Optional[str], str]:
        if "." in fname:
            owner, rest = fname.split(".", 1)
            return owner, rest
        return None, fname

    def instantiate_class(self, name: str, init: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            info = self.types.get(name)
            if info is None or info.get("kind") != "class":
                raise RuntimeError(f"unknown class {name}")
        mro = self.class_mro(name)
        obj: Dict[str, Any] = {"__tag__": name, "__fields__": {}}
        for cls in mro:
            with self._lock:
                finfo = self.types.get(cls)
                if finfo is None or finfo.get("kind") != "class":
                    raise RuntimeError(f"unknown class {cls}")
            obj["__fields__"][cls] = {fname: None for fname in finfo["fields"]}

        for raw_name, val in init.items():
            owner_hint, fname = self._split_field_name(raw_name)
            fmap = self._resolve_field_storage(obj, fname, owner_hint, name)
            fmap[fname] = val
        return obj

    def eval_match(self, m: Match, value: Any, env: "Environment") -> Any:
        tag = self.__get_tag(value)
        if tag is None:
            raise self._error("match target is not tagged", m.pos)

        type_name = None
        if isinstance(value, dict):
            type_name = value.get("__type__") or self.variant_to_type.get(tag)
        else:
            type_name = self.variant_to_type.get(tag)

        variants: Optional[Dict[str, Dict[str, str]]] = None
        expected: Optional[Set[str]] = None
        if type_name:
            variants = self._type_variants(str(type_name))
            if variants:
                expected = set(variants.keys())

        seen: Set[str] = set()
        has_wildcard = False
        for case in m.cases:
            if isinstance(case.pattern, WildcardPattern):
                has_wildcard = True
            elif isinstance(case.pattern, VariantPattern):
                if case.pattern.variant in seen:
                    raise self._error(f"duplicate case {case.pattern.variant}", case.pattern.pos)
                seen.add(case.pattern.variant)
                if expected is not None and case.pattern.variant not in expected:
                    missing_case = case.pattern.variant
                    raise self._error(
                        f"unknown case(s) for sum type {type_name}: {missing_case} (unexpected case {missing_case} for type {type_name})",
                        case.pattern.pos,
                    )

        if expected is not None and not has_wildcard:
            missing = expected - seen
            if missing:
                missing_list = ", ".join(sorted(missing))
                raise self._error(
                    f"non-exhaustive match for {type_name}: missing {missing_list} (missing cases: {missing_list})",
                    m.pos,
                    hint="Add the missing branches or a trailing '_' catch-all case.",
                )

        for case in m.cases:
            pattern = case.pattern
            if isinstance(pattern, WildcardPattern):
                branch_env = Environment(parent=env, namespace=env.namespace, runtime=self)
                if pattern.name:
                    branch_env.define(pattern.name, value, pattern.pos)
                return self.eval_expr(case.body, branch_env)

            if isinstance(pattern, VariantPattern) and pattern.variant == tag:
                branch_env = Environment(parent=env, namespace=env.namespace, runtime=self)
                if pattern.positional_bindings:
                    # Map positional bindings onto the declared variant fields so
                    # ``case Circle(r) =>`` can bind ``r`` to the first field of
                    # ``Circle`` without requiring explicit ``field: value``
                    # syntax in the pattern.
                    field_order: List[str] = []
                    if variants and pattern.variant in variants:
                        field_order = list(variants[pattern.variant].keys())
                    elif isinstance(value, dict):
                        field_order = [k for k in value.keys() if k not in {"__tag__", "__type__"}]
                    if not field_order:
                        raise self._error(
                            f"cannot bind positional pattern for {pattern.variant} without type information",
                            pattern.pos,
                        )
                    if len(pattern.positional_bindings) > len(field_order):
                        raise self._error(
                            f"positional pattern for {pattern.variant} has too many fields",
                            pattern.pos,
                        )
                    for idx, bind in enumerate(pattern.positional_bindings):
                        if not bind:
                            continue
                        fname = field_order[idx]
                        if not isinstance(value, dict) or fname not in value:
                            raise self._error(f"field {fname} missing for variant {pattern.variant}", pattern.pos)
                        branch_env.define(bind, value[fname], pattern.pos)
                for fname, bind in pattern.bindings.items():
                    if not isinstance(value, dict) or fname not in value:
                        raise self._error(f"field {fname} missing for variant {pattern.variant}", pattern.pos)
                    if bind:
                        branch_env.define(bind, value[fname], pattern.pos)
                return self.eval_expr(case.body, branch_env)

        raise self._error(f"non-exhaustive match for tag {tag}", m.pos)

    def _resolve_function(self, name: str, env: "Environment") -> Tuple[Optional[str], Optional[Fn]]:
        with self._lock:
            fn = self.functions.get(name)
        if fn is not None:
            return name, fn
        if "." not in name and env.namespace:
            qualified = self._qualify_name(name, env.namespace)
            with self._lock:
                fn = self.functions.get(qualified)
            if fn is not None:
                return qualified, fn
        return None, None

    def _invoke_native(self, qualified_name: str, args: List[Any]) -> Tuple[bool, Any]:
        with self._lock:
            native = self.native_functions.get(qualified_name)
        if native is None:
            return False, None
        return True, native(*args)

    def _invoke_function(self, fn: Fn, args: List[Any]) -> Any:
        call_env = Environment(parent=self.global_env, namespace=fn.namespace, runtime=self)
        for param, arg in zip(fn.params, args):
            if param.type:
                self._enforce_annotation(param.type, arg, label=f"parameter {param.name} in function {fn.name}", pos=fn.pos)
            call_env.define(param.name, arg, fn.pos)
        frame = StackFrame(fn.name, fn.namespace, fn.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = fn.namespace or prev_namespace
        try:
            res = self.eval_block(fn.body, call_env, fn.namespace)
            if isinstance(res, ReturnSignal):
                value = res.value
                if fn.return_type:
                    self._enforce_annotation(fn.return_type, value, label=f"return value for function {fn.name}", pos=fn.pos)
                else:
                    self._enforce_inferred_return(fn, value, label=f"function {fn.name}", pos=fn.pos)
                return value
            if fn.return_type:
                self._enforce_annotation(fn.return_type, res, label=f"return value for function {fn.name}", pos=fn.pos)
            else:
                self._enforce_inferred_return(fn, res, label=f"function {fn.name}", pos=fn.pos)
            return res
        except TinyLangError as err:
            raise self._ensure_error_has_stack(err) from err
        finally:
            self.call_stack.pop()
            self.current_module_namespace = prev_namespace

    def _run_spawn(self, fn: Fn, args: List[Any], handle: SpawnHandle) -> None:
        try:
            if handle.cancelled.is_set():
                handle.error = RuntimeError("spawn cancelled")
                return
            result = self._invoke_function(fn, args)
            if handle.cancelled.is_set():
                handle.error = RuntimeError("spawn cancelled")
            else:
                handle.result = result
        except Exception as exc:  # noqa: BLE001
            handle.error = exc
        finally:
            handle.done.set()

    def _start_task(self, fn: Fn, args: List[Any]) -> SpawnHandle:
        done = threading.Event()
        cancelled = threading.Event()
        placeholder_thread = threading.Thread(target=lambda: None)
        handle = SpawnHandle(thread=placeholder_thread, done=done, cancelled=cancelled)

        def run_task() -> None:
            self._run_spawn(fn, args, handle)

        worker = threading.Thread(target=run_task)
        handle.thread = worker
        worker.start()
        return handle

    def _join_status(self, handle: SpawnHandle, *, done: bool) -> Dict[str, Any]:
        return {
            "__tag__": "JoinStatus",
            "done": done,
            "cancelled": handle.cancelled.is_set(),
            "error": str(handle.error) if handle.error else None,
            "result": None if handle.error or not done or handle.cancelled.is_set() else handle.result,
        }

    def cancel_handle(self, handle: Any) -> bool:
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("cancel expects a spawn handle")
        already = handle.cancelled.is_set()
        handle.cancelled.set()
        return not already

    def make_cancellation_token(self) -> CancellationToken:
        return CancellationToken()

    def cancel_token(self, token: Any, reason: Optional[str] = None) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("cancel_token expects a cancellation token")
        return token.cancel(reason)

    def token_cancelled(self, token: Any) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("token_cancelled expects a cancellation token")
        return token.cancelled.is_set()

    def token_reason(self, token: Any) -> Optional[str]:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("token_reason expects a cancellation token")
        return token.reason

    def link_token(self, token: Any, handle: Any) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("link_token expects a cancellation token")
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("link_token expects a spawn handle")
        return token.link_handle(handle)

    def join_handle(
        self,
        handle: Any,
        *,
        timeout_ms: Optional[float] = None,
        cancel_on_timeout: bool = False,
        want_status: bool = False,
    ) -> Any:
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("join expects a spawn handle")

        timeout = None if timeout_ms is None else max(0.0, timeout_ms / 1000.0)
        finished = handle.done.wait(timeout)
        if not finished:
            if cancel_on_timeout:
                self.cancel_handle(handle)
            if want_status:
                return self._join_status(handle, done=False)
            return None

        handle.thread.join()
        if handle.cancelled.is_set():
            if want_status:
                return self._join_status(handle, done=True)
            raise handle.error or RuntimeError("join cancelled")
        if handle.error:
            if want_status:
                return self._join_status(handle, done=True)
            raise handle.error
        if want_status:
            return self._join_status(handle, done=True)
        return handle.result

    def _resolve_field_storage(
        self,
        obj: Dict[str, Any],
        fname: str,
        owner_hint: Optional[str],
        current_class: str,
        *,
        allow_write: bool = True,
    ) -> Dict[str, Any]:
        if "__fields__" not in obj:
            raise RuntimeError("field access on non-class value")

        def lookup_mro(start_class: str) -> List[str]:
            return self.class_mro(start_class)

        mro = lookup_mro(owner_hint or current_class)
        matches: List[Tuple[str, Dict[str, Any]]] = []

        for cls in mro:
            fmap = obj["__fields__"].get(cls, {})
            if fname in fmap:
                matches.append((cls, fmap))

        if owner_hint:
            for cls, fmap in matches:
                if cls == owner_hint:
                    return fmap
            raise RuntimeError(f"unknown field {fname} for base class {owner_hint}")

        if matches:
            primary_class = current_class
            for cls, fmap in matches:
                if cls == primary_class:
                    return fmap

        if len(matches) == 1:
            return matches[0][1]
        if len(matches) > 1:
            action = "assign" if allow_write else "access"
            raise RuntimeError(
                f"ambiguous field {fname} during {action}; please qualify with a base class name"
            )
        raise RuntimeError(f"unknown field {fname} for class {current_class}")

    def find_method(self, start_class: str, name: str) -> Optional[MethodDef]:
        for cls in self.class_mro(start_class):
            with self._lock:
                md = self.methods.get((cls, name))
            if md:
                return md
        return None

    def call_method(self, obj: Any, name: str, args: List[Any]) -> Any:
        if isinstance(obj, NamespaceRef):
            qualified_name = self._qualify_name(name, obj.name)
            invoked, native_res = self._invoke_native(qualified_name, args)
            if invoked:
                return native_res
            fn = self.functions.get(qualified_name)
            if fn is None:
                raise RuntimeError(f"unknown function {qualified_name}")
            return self._invoke_function(fn, args)
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        start_class = obj.class_name if isinstance(obj, BaseView) else self.__get_tag(target_obj)
        cname = self.__get_tag(target_obj)
        if start_class is None or cname is None:
            raise RuntimeError("method call on untagged value")
        md = self.find_method(start_class, name)
        if md is None:
            raise RuntimeError(f"no method {name} for class {start_class}")
        env = Environment(parent=None, runtime=self)
        self_value: Any = target_obj
        if md.class_name != cname:
            self_value = BaseView(target_obj, md.class_name)
        env.define(md.params[0].name, self_value, md.pos)  # self
        for base in self.class_mro(cname)[1:]:
            env.define(base, BaseView(target_obj, base), md.pos)
        for param, arg in zip(md.params[1:], args):
            if param.type:
                self._enforce_annotation(param.type, arg, label=f"parameter {param.name} in method {md.class_name}.{md.name}", pos=md.pos)
            env.define(param.name, arg, md.pos)
        frame = StackFrame(f"{md.class_name}.{md.name}", md.namespace, md.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = md.namespace or prev_namespace
        try:
            res = self.eval_block(md.body, env)
            if isinstance(res, ReturnSignal):
                value = res.value
                if md.return_type:
                    self._enforce_annotation(md.return_type, value, label=f"return value for method {md.class_name}.{md.name}", pos=md.pos)
                else:
                    self._enforce_inferred_return(md, value, label=f"method {md.class_name}.{md.name}", pos=md.pos)
                return value
            if md.return_type:
                self._enforce_annotation(md.return_type, res, label=f"return value for method {md.class_name}.{md.name}", pos=md.pos)
            else:
                self._enforce_inferred_return(md, res, label=f"method {md.class_name}.{md.name}", pos=md.pos)
            return res
        except TinyLangError as err:
            raise self._ensure_error_has_stack(err) from err
        finally:
            self.call_stack.pop()
            self.current_module_namespace = prev_namespace

    def type_field_type(self, tname: str, fname: str) -> Optional[str]:
        with self._lock:
            t = self.types.get(tname)
        if t is None:
            return None
        owner_hint, field_name = self._split_field_name(fname)
        if t.get("kind") == "class":
            targets: List[str] = []
            if owner_hint:
                targets.append(owner_hint)
            else:
                targets.append(tname)
                targets.extend(self.class_mro(tname)[1:])
            hits = []
            for cls in targets:
                info = self.types.get(cls)
                if info and field_name in info.get("fields", {}):
                    hits.append(info["fields"][field_name])
                    if owner_hint:
                        break
                    if cls == tname:
                        return info["fields"][field_name]
            if len(hits) == 1:
                return hits[0]
            return None
        variants = t.get("variants") or ({tname: t.get("fields", {})} if t.get("fields") is not None else {})
        if owner_hint:
            return variants.get(owner_hint, {}).get(field_name)
        if len(variants) == 1:
            return next(iter(variants.values())).get(field_name)
        hits = [fields.get(field_name) for fields in variants.values() if field_name in fields]
        if len(hits) == 1:
            return hits[0]
        return None

    @staticmethod
    def format_value(val: Any) -> str:
        if isinstance(val, dict) and val.get("__tag__") == "Number":
            fields = val.get("__fields__", {}).get("Number", {})
            err = fields.get("error")
            if err in {"plus_infinity", "minus_infinity", "any_number"}:
                return str(err)
            if "value" in fields:
                value = fields.get("value")
                if err == "rounded":
                    return f"{value} (rounded)"
                return str(value)
        if isinstance(val, dict) and val.get("__tag__") == "NumberIntervall":
            fields = val.get("__fields__", {}).get("NumberIntervall", {})
            err = fields.get("error")
            if err in {"plus_infinity", "minus_infinity", "any_number"}:
                return str(err)
            if err == "upper_bound_is_plus_infinity":
                lower = fields.get("lower")
                return f"[{lower}, infinity]"
            if err == "lower_bound_is_minus_infinity":
                upper = fields.get("upper")
                return f"[-infinity, {upper}]"
            if err == "wrapped_interval":
                lower = fields.get("lower")
                upper = fields.get("upper")
                return f"[{lower}, {upper}]"
            if "lower" in fields and "upper" in fields:
                lower = fields.get("lower")
                upper = fields.get("upper")
                center = (lower + upper) / 2
                radius = (upper - lower) / 2

                def _format_float(val: float) -> str:
                    abs_val = abs(val)
                    if abs_val >= 1e-9:
                        rounded = round(val, 12)
                        if abs(rounded - val) <= abs_val * 1e-12:
                            val = rounded
                    return str(val)

                return f"{_format_float(center)} +/- {_format_float(radius)}"
        if isinstance(val, bool):
            return "true" if val else "false"
        if val is None:
            return "Null"
        return str(val)

    @staticmethod
    def _is_truthy(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, str):
            return len(val) > 0
        try:
            return bool(val)
        except Exception:
            return True

    
