"""Runtime helpers: module resolution, heap management, and async utilities.

This segment contains the import mechanics, concurrency primitives, and the core
runtime container used by the evaluator. Docstrings focus on public-facing
behaviors so integrators can navigate the stitched module without reading the
entire implementation.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from collections import deque
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from tiny_errors import SourcePos, SourceSpan, StackFrame, TinyLangError, _line_info, format_error
from tiny_language_error_codes import classify_error
from tiny_language_ast import Fn, IR, Match, MethodDef, OpDef, Param, TypeVariant, VariantPattern, WildcardPattern
from tiny_language_runtime_debugger import DebugSnapshot, Debugger, ScopeSnapshot, StepRequest
from tiny_language_runtime_environment import Environment
from tiny_language_runtime_modules import ModuleResolver, NamespaceRef, _import_binding_name

# ----- Runtime -----

LOGGER = logging.getLogger(__name__)


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        super().__init__()
        self.value = value


class _SpawnCancelled(Exception):
    """Stop a worker after its spawn handle has been cancelled."""


@dataclass
class ParameterBinding:
    name: str
    original: Any
    escaped: bool
    copied: bool


ParamKey = Tuple[str, int]


@dataclass
class BaseView:
    obj: Dict[str, Any]
    class_name: str


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
            remaining: List[SpawnHandle] = []
            for handle in list(self._linked):
                if handle.done.is_set():
                    continue
                handle.cancelled.set()
                remaining.append(handle)
            self._linked = remaining
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


@dataclass
class TaskScope:
    """Track spawned handles that must resolve before exiting a task block."""

    handles: List[SpawnHandle] = field(default_factory=list)

    def add_handle(self, handle: SpawnHandle) -> None:
        if handle not in self.handles:
            self.handles.append(handle)


@dataclass
class _ParsedType:
    name: str
    args: List["_ParsedType"]
    optional: bool = False


class Runtime:
    """Interpreter runtime state and helpers for executing TinyLanguage code."""

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
        env_copy_flag = os.environ.get("TINYLANG_COPY_ON_CALL", "").strip().lower()
        self.copy_on_call: bool = env_copy_flag in {"1", "true", "yes", "on"}
        self._parameter_binding_stack: threading.local = threading.local()
        self._spawn_context: threading.local = threading.local()
        self.trace_log_path: Optional[str] = os.environ.get("TINYLANG_TRACE_LOG")
        self.trace_every_statement: bool = os.environ.get("TINYLANG_TRACE_EVERY_STATEMENT", "0") == "1"
        self.trace_heartbeat_secs: float = float(os.environ.get("TINYLANG_TRACE_HEARTBEAT_SECS", "1.0"))
        self.trace_to_stdout: bool = os.environ.get("TINYLANG_TRACE_STDOUT", "0") not in {"0", "", "false", "False"}
        self._trace_logger: Optional[logging.Logger] = None
        self._last_trace_time: float = 0.0
        self._last_trace_location: Optional[Tuple[Optional[str], int]] = None
        self._last_emitted_output_idx: int = 0
        self._task_scopes: List[TaskScope] = []
        self.task_scope_timeout_ms: float = float(os.environ.get("TINYLANG_TASK_SCOPE_TIMEOUT_MS", "50"))
        heap_debug_flag = os.environ.get("TINYLANG_HEAP_DEBUG", "").strip().lower()
        self.heap_debug: bool = heap_debug_flag in {"1", "true", "yes", "on"}
        if self.trace_log_path:
            self._setup_trace_logger()

    def _binding_stack(self) -> List[Dict[ParamKey, ParameterBinding]]:
        stack = getattr(self._parameter_binding_stack, "stack", None)
        if stack is None:
            stack = []
            self._parameter_binding_stack.stack = stack
        return stack

    def _raise_if_spawn_cancelled(self) -> None:
        """Cooperatively stop the current worker at statement boundaries."""
        cancelled = getattr(self._spawn_context, "cancelled", None)
        if cancelled is not None and cancelled.is_set():
            raise _SpawnCancelled()

    def _push_task_scope(self) -> TaskScope:
        scope = TaskScope()
        self._task_scopes.append(scope)
        return scope

    def _pop_task_scope(self) -> None:
        if not self._task_scopes:
            return
        scope = self._task_scopes.pop()
        for handle in scope.handles:
            self.join_handle(handle, timeout_ms=self.task_scope_timeout_ms, cancel_on_timeout=True)

    def _register_task_handle(self, handle: SpawnHandle) -> None:
        if self._task_scopes:
            self._task_scopes[-1].add_handle(handle)

    def _push_parameter_scope(self, bindings: Dict[ParamKey, ParameterBinding]) -> None:
        self._binding_stack().append(bindings)

    def _pop_parameter_scope(self) -> None:
        stack = self._binding_stack()
        if stack:
            stack.pop()

    def _binding_key(self, value: Any) -> Optional[ParamKey]:
        if isinstance(value, BaseView):
            return self._binding_key(value.obj)
        if self._is_heap_pointer(value):
            return ("ptr", int(value))
        if isinstance(value, dict):
            return ("obj", id(value))
        if isinstance(value, list):
            return ("list", id(value))
        return None

    def _is_heap_pointer(self, value: Any) -> bool:
        if isinstance(value, bool):
            return False
        try:
            iv = int(value)
        except Exception:
            return False
        if isinstance(value, float) and not value.is_integer():
            return False
        with self._lock:
            return iv in self.heap

    def _is_mutable_argument(self, value: Any) -> bool:
        if self._is_heap_pointer(value):
            return True
        if isinstance(value, BaseView):
            return self._is_mutable_argument(value.obj)
        if isinstance(value, (dict, list)):
            return True
        return False

    def _deep_copy_value(
        self,
        value: Any,
        *,
        memo: Optional[Dict[int, Any]] = None,
        ptr_memo: Optional[Dict[int, Any]] = None,
        protected_keys: Optional[Set[ParamKey]] = None,
    ) -> Any:
        memo = memo or {}
        ptr_memo = ptr_memo or {}
        if protected_keys is not None:
            key = self._binding_key(value)
            if key:
                protected_keys.add(key)

        if isinstance(value, BaseView):
            copied_obj = self._deep_copy_value(value.obj, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys)
            return BaseView(copied_obj, value.class_name)

        if self._is_heap_pointer(value):
            ip = int(value)
            if ip in ptr_memo:
                return ptr_memo[ip]
            with self._lock:
                cells = list(self.heap.get(ip, []))
                cell_types = dict(self.heap_cell_types.get(ip, {}))
                tag = self.ptr_tags.get(ip)
            new_ptr = self.__new(len(cells))
            ptr_memo[ip] = new_ptr
            for idx, cell in enumerate(cells):
                copied_cell = self._deep_copy_value(
                    cell, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys
                )
                self.heap_set(new_ptr, idx, copied_cell)
                if idx in cell_types:
                    with self._lock:
                        self.heap_cell_types.setdefault(new_ptr, {})[idx] = cell_types[idx]
            if tag:
                with self._lock:
                    self.ptr_tags[new_ptr] = tag
            return new_ptr

        if isinstance(value, dict):
            obj_id = id(value)
            if obj_id in memo:
                return memo[obj_id]
            copied: Dict[str, Any] = {}
            memo[obj_id] = copied
            for key, val in value.items():
                if key == "__fields__" and isinstance(val, dict):
                    copied_fields: Dict[str, Dict[str, Any]] = {}
                    copied[key] = copied_fields
                    for cls, fmap in val.items():
                        copied_fields[cls] = {
                            fname: self._deep_copy_value(fval, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys)
                            for fname, fval in fmap.items()
                        }
                else:
                    copied[key] = self._deep_copy_value(
                        val, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys
                    )
            return copied

        if isinstance(value, list):
            list_id = id(value)
            if list_id in memo:
                return memo[list_id]
            copied_list: List[Any] = []
            memo[list_id] = copied_list
            copied_list.extend(
                self._deep_copy_value(item, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys)
                for item in value
            )
            return copied_list

        if isinstance(value, tuple):
            return tuple(
                self._deep_copy_value(item, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys)
                for item in value
            )

        return value

    def _lookup_protected_binding(self, target: Any) -> Optional[ParameterBinding]:
        key = self._binding_key(target)
        if key is None:
            return None
        for scope in reversed(self._binding_stack()):
            binding = scope.get(key)
            if binding:
                return binding
        return None

    def _guard_protected_mutation(self, target: Any, pos: Optional[Any]) -> None:
        if not self.copy_on_call:
            return
        binding = self._lookup_protected_binding(target)
        if binding is None or binding.escaped:
            return
        raise self._error(
            f"mutation of protected parameter {binding.name} is not allowed while copy-on-call is enabled",
            pos or SourcePos.origin(),
            hint="Return the argument or disable --copy-on-call to mutate caller-owned data.",
        )

    def _bind_parameters_to_env(
        self,
        params: List[Param],
        args: List[Any],
        env: "Environment",
        *,
        escaped_params: Set[str],
        pos: SourcePos,
        type_label: str,
        force_escaped: Optional[Set[str]] = None,
    ) -> Dict[ParamKey, ParameterBinding]:
        bindings: Dict[ParamKey, ParameterBinding] = {}
        memo: Dict[int, Any] = {}
        ptr_memo: Dict[int, Any] = {}
        forced = force_escaped or set()
        for param, arg in zip(params, args):
            if param.type:
                self._enforce_annotation(param.type, arg, label=f"parameter {param.name} in {type_label}", pos=pos)
            should_escape = param.name in escaped_params or param.name in forced
            is_mutable = self._is_mutable_argument(arg)
            protected_keys: Set[ParamKey] = set()
            bound_val = arg
            if self.copy_on_call and is_mutable and not should_escape:
                bound_val = self._deep_copy_value(
                    arg, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys
                )
            env.define(param.name, bound_val, pos)
            if self.copy_on_call and is_mutable and not should_escape:
                for key in protected_keys:
                    bindings[key] = ParameterBinding(param.name, arg, escaped=False, copied=bound_val is not arg)
        return bindings

    def flush_streams(self) -> None:
        """Flush any mirrored stdout streams when streaming is enabled."""

        with self._lock:
            import sys

            mirror_stdout = bool(getattr(self.debugger, "mirror_stdout", False))
            if self.stream_output or mirror_stdout or self.trace_to_stdout:
                sys.stdout.flush()

            self._emit_output_to_debugger()

    def _emit_output_to_debugger(self) -> None:
        handler = getattr(self.debugger, "on_output", None)
        if handler is None:
            return

        new_output = "".join(self.output[self._last_emitted_output_idx :])
        if not new_output:
            return

        self._last_emitted_output_idx = len(self.output)
        handler(new_output)

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

    @staticmethod
    def _pos_and_span(location: Optional[Any], span_override: Optional[SourceSpan] = None) -> Tuple[Optional[SourcePos], Optional[SourceSpan]]:
        resolved_span = span_override
        if resolved_span is None:
            if isinstance(location, SourceSpan):
                resolved_span = location
            elif location is not None:
                resolved_span = getattr(location, "span", None)
        if isinstance(location, SourcePos):
            resolved_pos = location
        elif location is not None:
            resolved_pos = getattr(location, "pos", None)
        else:
            resolved_pos = None
        if resolved_pos is None and resolved_span is not None:
            resolved_pos = resolved_span.start
        return resolved_pos, resolved_span

    @staticmethod
    def _format_location(
        pos: Optional[SourcePos], span: Optional[SourceSpan]
    ) -> Optional[Union[SourcePos, SourceSpan]]:
        if span is not None and span.start != span.stop:
            return span
        if pos is not None:
            return pos
        if span is not None:
            return span.start
        return pos

    def _record_error(
        self,
        msg: str,
        pos: Optional[Any] = None,
        *,
        code: str = "E000",
        hint: Optional[str] = None,
        formatted: Optional[str] = None,
        span: Optional[SourceSpan] = None,
    ) -> None:
        resolved_pos, resolved_span = self._pos_and_span(pos, span)
        location = self._format_location(resolved_pos, resolved_span)
        if formatted is None:
            source = self._source_for_namespace(self.current_module_namespace if location is not None else None)
            base = format_error(source, location, msg, code=code, hint=hint) if location is not None else msg
            stack_part = self._format_stacktrace(self.call_stack)
            formatted = f"{base}\n{stack_part}" if stack_part else base
        with self._lock:
            # Only keep the most recent runtime error so `errorMessage` reflects
            # the latest failure instead of accumulating older ones.
            self.error_messages = [formatted]

    def _error(
        self,
        msg: str,
        pos: Any,
        *,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        candidates: Optional[List[str]] = None,
        span: Optional[SourceSpan] = None,
        ) -> TinyLangError:
        resolved_pos, resolved_span = self._pos_and_span(pos, span)
        location = self._format_location(resolved_pos, resolved_span) or resolved_pos or SourcePos.origin()
        derived_code, derived_hint = classify_error(msg, candidates)
        code = code or derived_code
        hint = hint or derived_hint
        source = self._source_for_namespace(self.current_module_namespace)
        formatted = format_error(source, location, msg, code=code, hint=hint)
        stack = tuple(self.call_stack)
        if stack:
            formatted = f"{formatted}\n{self._format_stacktrace(stack)}"
        self._record_error(msg, resolved_pos, code=code, hint=hint, formatted=formatted, span=resolved_span)
        return TinyLangError(formatted, resolved_pos or SourcePos.origin(), code=code, hint=hint, stack=stack, span=resolved_span)

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

    def heap_new(self, values: List[Any]) -> int:
        """Allocate and initialize cells for generated-backend ``new`` literals."""

        pointer = self.__new(len(values))
        with self._lock:
            self.heap[pointer][:] = values
        return pointer

    @staticmethod
    def _pointer_label(p: Any) -> str:
        type_name = type(p).__name__
        if isinstance(p, (int, float)) and str(p).isnumeric():
            return str(int(p))
        return f"{p!r} ({type_name})"

    def _heap_debug_suffix(
        self,
        *,
        pointer: Optional[Any] = None,
        index: Optional[Any] = None,
        size: Optional[int] = None,
    ) -> str:
        if not self.heap_debug:
            return ""
        parts: List[str] = []
        if pointer is not None:
            parts.append(f"pointer={self._pointer_label(pointer)}")
            try:
                tag = self.ptr_tags.get(int(pointer))
            except Exception:
                tag = None
            if tag:
                parts.append(f"tag={tag}")
        if index is not None:
            parts.append(f"index={index!r}")
        if size is not None:
            parts.append(f"size={size}")
        parts.append(f"module={self.current_module_namespace or '<main>'}")
        with self._lock:
            live = sorted(self.heap.keys())
            freed = sorted(self.freed_ptrs)
        if live:
            parts.append(f"live={live}")
        if freed:
            parts.append(f"freed={freed}")
        return f" [debug: {', '.join(parts)}]"

    def _resolve_ptr(self, p: Any, pos: Optional[Any], *, op: str) -> Tuple[Optional[int], Optional[List[Any]]]:
        """Validate and resolve a heap pointer for the requested operation.

        Returns a tuple of `(pointer, cells)` where either entry may be `None` if
        validation failed and an error was recorded.
        """

        if isinstance(p, bool):
            message = (
                f"heap {op} error: pointer {self._pointer_label(p)} is not numeric"
                f"{self._heap_debug_suffix(pointer=p)}"
            )
            self._record_error(message, pos)
            return None, None

        try:
            ip = int(p)
        except Exception:
            message = (
                f"heap {op} error: pointer {self._pointer_label(p)} is not numeric"
                f"{self._heap_debug_suffix(pointer=p)}"
            )
            self._record_error(message, pos)
            return None, None

        if isinstance(p, float) and not p.is_integer():
            message = (
                f"heap {op} error: pointer {self._pointer_label(p)} is not an integer pointer"
                f"{self._heap_debug_suffix(pointer=p)}"
            )
            self._record_error(message, pos)
            return None, None

        if ip < 1:
            message = (
                f"heap {op} error: pointer {ip} is invalid (must refer to a live positive allocation)"
                f"{self._heap_debug_suffix(pointer=ip)}"
            )
            self._record_error(message, pos)
            return None, None

        with self._lock:
            if ip in self.freed_ptrs:
                size_part = self.freed_allocations.get(ip)
                size_hint = f" (size {size_part})" if size_part is not None else ""
                message = (
                    f"heap {op} error: pointer {ip} was already freed{size_hint}"
                    f"{self._heap_debug_suffix(pointer=ip, size=size_part)}"
                )
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
                message = (
                    f"heap {op} error: unknown pointer {ip}{context}"
                    f"{self._heap_debug_suffix(pointer=ip)}"
                )
                self._record_error(message, pos)
                return None, None
            return ip, cells

    def _parse_heap_index(self, i: Any, pos: Optional[Any]) -> Optional[int]:
        """Parse an index argument and record helpful errors when invalid."""

        if isinstance(i, bool):
            message = (
                "heap access error: index "
                f"{self._pointer_label(i)} is not numeric{self._heap_debug_suffix(index=i)}"
            )
            self._record_error(message, pos)
            return None

        try:
            idx = int(i)
        except Exception:
            message = f"heap access error: index {i!r} is not numeric{self._heap_debug_suffix(index=i)}"
            self._record_error(message, pos)
            return None

        if isinstance(i, float) and not i.is_integer():
            message = (
                "heap access error: index "
                f"{self._pointer_label(i)} is not an integer index{self._heap_debug_suffix(index=i)}"
            )
            self._record_error(message, pos)
            return None

        return idx

    def delete(self, p: Any, pos: Optional[Any] = None) -> Dict[str, Any]:
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

    def heap_get(self, p: Any, i: Any, *, pos: Optional[Any] = None) -> Any:
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
                "heap access error: index "
                f"{idx} out of range for pointer {ip} (size {size}; {range_hint})"
                f"{self._heap_debug_suffix(pointer=ip, index=idx, size=size)}",
                pos,
            )
            return None
        return cells[idx]

    def heap_set(self, p: Any, i: Any, v: Any, *, pos: Optional[Any] = None) -> Dict[str, Any]:
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
            message = (
                "heap access error: index "
                f"{idx} out of range for pointer {ip} (size {size}; {range_hint})"
                f"{self._heap_debug_suffix(pointer=ip, index=idx, size=size)}"
            )
            self._record_error(message, pos)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": message}}

        self._guard_protected_mutation(ip, pos)

        with self._lock:
            expected = self.heap_cell_types.get(ip, {}).get(idx)
            actual = self._value_type_name(v)
            if expected is not None and expected != actual:
                message = (
                    f"heap type mismatch at {ip}[{idx}]: expected {expected} but got {actual}"
                    f"{self._heap_debug_suffix(pointer=ip, index=idx)}"
                )
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

    def tag(self, p: Any, typ: Any, *, pos: Optional[Any] = None) -> Dict[str, Any]:
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
        """Return a type label for variables defined without annotations."""
        return self._value_type_name(value) or type(value).__name__

    @staticmethod
    def _normalize_numeric_type(type_name: str) -> str:
        normalized = type_name.strip()
        lowered = normalized.lower()
        if lowered == "int":
            return "int"
        if lowered == "float":
            return "float"
        return type_name

    def _check_assignment_type(
        self, env: "Environment", name: str, value: Any, pos: Any, *, local_only: bool = False
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

    def _parse_type_expression(self, type_name: str) -> Optional[_ParsedType]:
        text = type_name.strip()
        if not text:
            return None
        idx = 0

        def skip_ws() -> None:
            nonlocal idx
            while idx < len(text) and text[idx].isspace():
                idx += 1

        def parse_expr() -> Optional[_ParsedType]:
            nonlocal idx
            skip_ws()
            start = idx
            while idx < len(text) and (text[idx].isalnum() or text[idx] in "._"):
                idx += 1
            if start == idx:
                return None
            name = text[start:idx]
            skip_ws()
            args: List[_ParsedType] = []
            if idx < len(text) and text[idx] == "[":
                idx += 1
                skip_ws()
                if idx < len(text) and text[idx] == "]":
                    idx += 1
                else:
                    while True:
                        arg = parse_expr()
                        if arg is None:
                            return None
                        args.append(arg)
                        skip_ws()
                        if idx < len(text) and text[idx] == ",":
                            idx += 1
                            continue
                        if idx < len(text) and text[idx] == "]":
                            idx += 1
                            break
                        return None
            skip_ws()
            optional = False
            if idx < len(text) and text[idx] == "?":
                optional = True
                idx += 1
            skip_ws()
            return _ParsedType(name=name, args=args, optional=optional)

        parsed = parse_expr()
        skip_ws()
        if parsed is None or idx != len(text):
            return None
        return parsed

    @staticmethod
    def _render_type_expression(expr: _ParsedType) -> str:
        rendered = expr.name
        if expr.args:
            rendered = f"{rendered}[{', '.join(Runtime._render_type_expression(arg) for arg in expr.args)}]"
        if expr.optional:
            rendered = f"{rendered}?"
        return rendered

    @staticmethod
    def _type_name_matches(expected: str, actual: str) -> bool:
        if expected.lower() == actual.lower():
            return True
        if expected.lower() == "number" and actual.lower() in {"number", "int", "float"}:
            return True
        if expected.lower() == "string" and actual.lower() == "string":
            return True
        if expected.lower() in {"bool", "boolean"} and actual.lower() in {"bool", "boolean"}:
            return True
        return False

    def _is_list_value(self, value: Any) -> bool:
        if isinstance(value, list):
            return True
        if self._is_heap_pointer(value):
            return True
        tag = self.__get_tag(value)
        return tag in {"PyList", "List"}

    @staticmethod
    def _is_map_value(value: Any) -> bool:
        return isinstance(value, dict) and "__tag__" not in value and "__type__" not in value

    @staticmethod
    def _is_set_value(value: Any) -> bool:
        return isinstance(value, set)

    @staticmethod
    def _is_deque_value(value: Any) -> bool:
        return isinstance(value, deque)

    def _iter_list_values(self, value: Any) -> List[Any]:
        if isinstance(value, list):
            return list(value)
        if self._is_heap_pointer(value):
            with self._lock:
                return list(self.heap.get(int(value), []))
        return []

    def _container_type_matches(self, expected: _ParsedType, value: Any) -> bool:
        expected_name = expected.name.lower()
        if expected_name == "list":
            if not self._is_list_value(value):
                return False
            if not expected.args:
                return True
            element = self._render_type_expression(expected.args[0])
            for item in self._iter_list_values(value):
                if not self._type_matches(element, item):
                    return False
            return True
        if expected_name == "set":
            if not self._is_set_value(value):
                return False
            if not expected.args:
                return True
            element = self._render_type_expression(expected.args[0])
            return all(self._type_matches(element, item) for item in value)
        if expected_name == "deque":
            if not self._is_deque_value(value):
                return False
            if not expected.args:
                return True
            element = self._render_type_expression(expected.args[0])
            return all(self._type_matches(element, item) for item in value)
        if expected_name == "map":
            if not self._is_map_value(value):
                return False
            if not expected.args:
                return True
            if len(expected.args) != 2:
                return False
            key_type = self._render_type_expression(expected.args[0])
            value_type = self._render_type_expression(expected.args[1])
            return all(self._type_matches(key_type, k) and self._type_matches(value_type, v) for k, v in value.items())
        return False

    def _type_matches(self, expected: str, value: Any) -> bool:
        expected_norm = expected.strip()
        expected_expr = self._parse_type_expression(expected_norm)
        if expected_expr and expected_expr.name.lower() == "any":
            return True
        if expected_expr and expected_expr.optional:
            if value is None:
                return True
            expected_expr = _ParsedType(name=expected_expr.name, args=expected_expr.args, optional=False)
        if expected_expr and expected_expr.name.lower() in {"list", "set", "deque", "map"}:
            return self._container_type_matches(expected_expr, value)
        actual = self._value_type_name(value)
        if actual is None:
            return False
        actual_norm = actual.strip() if isinstance(actual, str) else str(actual)
        if expected_expr:
            return self._type_name_matches(expected_expr.name, actual_norm)
        if expected_norm.lower() == "any":
            return True
        optional = expected_norm.endswith("?")
        base_expected = expected_norm[:-1].strip() if optional else expected_norm
        if optional and actual_norm.lower() == "null":
            return True
        if self._type_name_matches(base_expected, actual_norm):
            return True
        if base_expected == "Null" and value is None:
            return True
        if optional and actual_norm.lower() != "null":
            return self._type_matches(base_expected, value)
        return False

    def _enforce_annotation(self, expected: str, value: Any, *, label: str, pos: Any) -> None:
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
        inferred = self._normalize_numeric_type(self._infer_type_name(value))
        if expected is None:
            owner.inferred_return_type = inferred
            return
        expected_norm = self._normalize_numeric_type(expected)
        if expected_norm != expected:
            owner.inferred_return_type = expected_norm
        if self._type_matches(expected_norm, value):
            return
        actual = self._value_type_name(value) or type(value).__name__
        raise self._error(
            f"inferred return type for {label} changed: expected {expected_norm} but got {actual}",
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
                if not val_b.is_integer() and val_a < 0:
                    return mk("any_number")
                if val_b.is_integer():
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
            if isinstance(val_b, float) and not val_b.is_integer() and val_a < 0:
                return mk("any_number")
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
                if not b.is_integer() and a < 0:
                    raise RuntimeError("fractional exponent for ^ requires a non-negative base")
                if b.is_integer():
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

    def field_get(self, obj: Any, key: str, *, pos: Optional[Any] = None) -> Any:
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

    def field_set(self, obj: Any, key: str, val: Any, *, pos: Optional[Any] = None) -> None:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        self._guard_protected_mutation(target_obj, pos)
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
        self, variant: str, init: Dict[str, Any], *, type_name: Optional[str] = None, pos: Optional[Any] = None
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
            raise self._error("match target is not tagged", m)

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
                    raise self._error(f"duplicate case {case.pattern.variant}", case.pattern)
                seen.add(case.pattern.variant)
                if expected is not None and case.pattern.variant not in expected:
                    missing_case = case.pattern.variant
                    raise self._error(
                        f"unknown case(s) for sum type {type_name}: {missing_case} (unexpected case {missing_case} for type {type_name})",
                        case.pattern,
                    )

        if expected is not None and not has_wildcard:
            missing = expected - seen
            if missing:
                missing_list = ", ".join(sorted(missing))
                raise self._error(
                    f"non-exhaustive match for {type_name}: missing {missing_list} (missing cases: {missing_list})",
                    m,
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
                            pattern,
                        )
                    if len(pattern.positional_bindings) > len(field_order):
                        raise self._error(
                            f"positional pattern for {pattern.variant} has too many fields",
                            pattern,
                        )
                    for idx, bind in enumerate(pattern.positional_bindings):
                        if not bind:
                            continue
                        fname = field_order[idx]
                        if not isinstance(value, dict) or fname not in value:
                            raise self._error(f"field {fname} missing for variant {pattern.variant}", pattern)
                        branch_env.define(bind, value[fname], pattern.pos)
                for fname, bind in pattern.bindings.items():
                    if not isinstance(value, dict) or fname not in value:
                        raise self._error(f"field {fname} missing for variant {pattern.variant}", pattern)
                    if bind:
                        branch_env.define(bind, value[fname], pattern.pos)
                return self.eval_expr(case.body, branch_env)

        raise self._error(f"non-exhaustive match for tag {tag}", m)

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
        parent_env = self.global_env
        if fn.namespace and fn.namespace in self.namespace_envs:
            parent_env = self.namespace_envs[fn.namespace]
        call_env = Environment(parent=parent_env, namespace=fn.namespace, runtime=self)
        param_bindings = self._bind_parameters_to_env(
            fn.params,
            args,
            call_env,
            escaped_params=getattr(fn, "return_param_names", set()),
            pos=fn.pos,
            type_label=f"function {fn.name}",
        )
        frame = StackFrame(fn.name, fn.namespace, fn.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = fn.namespace or prev_namespace
        self._push_parameter_scope(param_bindings)
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
            self._pop_parameter_scope()
            self.call_stack.pop()
            self.current_module_namespace = prev_namespace

    def _run_spawn(self, fn: Fn, args: List[Any], handle: SpawnHandle) -> None:
        try:
            self._spawn_context.cancelled = handle.cancelled
            if handle.cancelled.is_set():
                raise _SpawnCancelled()
            result = self._invoke_function(fn, args)
            if handle.cancelled.is_set():
                handle.error = RuntimeError("spawn cancelled")
            else:
                handle.result = result
        except _SpawnCancelled:
            handle.error = RuntimeError("spawn cancelled")
        except Exception as exc:  # noqa: BLE001
            handle.error = exc
        finally:
            self._spawn_context.cancelled = None
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
        self._register_task_handle(handle)
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
        if handle.done.is_set():
            return False
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
        env = Environment(parent=self.global_env, runtime=self)
        self_value: Any = target_obj
        if md.class_name != cname:
            self_value = BaseView(target_obj, md.class_name)
        method_args = [self_value] + args
        forced_escape = {md.params[0].name} if md.params else set()
        param_bindings = self._bind_parameters_to_env(
            md.params,
            method_args,
            env,
            escaped_params=getattr(md, "return_param_names", set()),
            pos=md.pos,
            type_label=f"method {md.class_name}.{md.name}",
            force_escaped=forced_escape,
        )
        for base in self.class_mro(cname)[1:]:
            env.define(base, BaseView(target_obj, base), md.pos)
        frame = StackFrame(f"{md.class_name}.{md.name}", md.namespace, md.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = md.namespace or prev_namespace
        self._push_parameter_scope(param_bindings)
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
            self._pop_parameter_scope()
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


def compile_and_run(*args: Any, **kwargs: Any) -> str:
    """Proxy to the public API compile helper to preserve legacy imports."""

    import importlib.util

    if importlib.util.find_spec("tiny_language_stitched"):
        from tiny_language_stitched import compile_and_run as stitched_compile_and_run

        return stitched_compile_and_run(*args, **kwargs)

    from tiny_language_api import compile_and_run as api_compile_and_run

    return api_compile_and_run(*args, **kwargs)
    
