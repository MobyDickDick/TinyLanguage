"""
stdlib_registry.py — TinyLanguage standard library registration (native runtime)

This module wires TinyLanguage “stdlib namespaces” (e.g. `Math`, `String`, `Map`)
to their Python implementations inside the TinyLanguage runtime.

High-level responsibilities
---------------------------
1) **Namespace bootstrapping**
   Ensures stdlib namespaces exist in the TinyLanguage environment, so Tiny code
   can call e.g. `Math.abs(...)` or `JSON.parse(...)`.

2) **Native function registration**
   Registers Python callables as “native” Tiny functions via
   `runtime.register_native(name, func, namespace=...)`.

3) **Native type registration**
   Registers runtime “types” implemented as tagged dicts (ADTs / variants).
   This file defines and registers a `Result` type with `Ok` and `Err` variants.

4) **Bridging / interop**
   Provides a controlled Python interop surface under the `Python.*` namespace,
   including:
   - module import with allowlists
   - attribute calls with optional timeouts
   - conversions between Tiny values and Python host values

Security notes (Python interop)
-------------------------------
Python interop is intentionally restricted:
- Certain Python modules are denied completely (see `_BANNED_PYTHON_MODULES`).
- Calls are gated by an explicit allowlist of attribute names.
- Optional timeouts are supported (via worker threads).

Implementation notes
--------------------
- This module relies on several *internal* runtime helpers
  (`_Runtime__new`, `_number_fields`, `_intervall_fields`, ...). Those accesses
  are intentional to keep the stdlib fast and avoid duplicating logic.
- Collections may be represented either as Python objects **or** as Tiny heap
  pointers (integers indexing `runtime.heap`). Helper `_resolve_*` methods
  normalize those cases.

The public entry point is `register_stdlib(runtime, env, ...)`.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import random
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple

from tiny_errors import SourcePos

# ---------------------------------------------------------------------------
# Python interop: module denylist
# ---------------------------------------------------------------------------
# This is a coarse safety mechanism to avoid obvious “escape hatches”.
# Interop still requires an allowlist of attributes, but we deny these modules
# outright because they commonly enable process execution, networking, or low-
# level memory access.
_BANNED_PYTHON_MODULES = {
    "subprocess",
    "socket",
    "multiprocessing",
    "ctypes",
    "ssl",
    "sys",
}


# ---------------------------------------------------------------------------
# Runtime type helper
# ---------------------------------------------------------------------------


@dataclass
class _Variant:
    """Descriptor for a runtime “variant” (an ADT constructor).

    The runtime uses these descriptors when registering Tiny types like:

        type Result { Ok { value: any }; Err { ... } }

    Attributes
    ----------
    name:
        Variant tag name (e.g. "Ok", "Err").
    fields:
        List of (field_name, type_annotation_string) pairs.
    """

    name: str
    fields: List[Tuple[str, str]]


# ---------------------------------------------------------------------------
# Async: channel primitive (used by Async namespace)
# ---------------------------------------------------------------------------


class _Channel:
    """A bounded FIFO channel with blocking send/recv operations.

    This is a minimal concurrency primitive intended for TinyLanguage async demos.

    Semantics
    ---------
    - `capacity <= 0` behaves like a channel with capacity 0 (rendezvous-style),
      i.e. `send` blocks until a receiver consumes the value.
    - `send(value)` returns False if the channel was closed before the send.
    - `recv()` blocks until a value is available or the channel is closed.
      If closed and empty, returns `None`.
    - `close()` wakes all waiters and returns True if it closed successfully,
      False if it was already closed.

    Thread-safety
    -------------
    Uses a lock and two conditions:
    - `not_empty` for receivers waiting on values
    - `not_full` for senders waiting on capacity
    """

    def __init__(self, capacity: int):
        self.capacity = max(0, int(capacity))
        self.buffer: deque[Any] = deque()
        self.closed = False
        self.lock = threading.Lock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)

    def send(self, value: Any) -> bool:
        """Send a value to the channel, blocking if the buffer is full.

        Returns
        -------
        bool
            True if the value was enqueued, False if the channel is closed.
        """
        with self.not_full:
            while len(self.buffer) >= self.capacity and not self.closed:
                self.not_full.wait()
            if self.closed:
                return False
            self.buffer.append(value)
            self.not_empty.notify()
            return True

    def recv(self) -> Any:
        """Receive a value from the channel, blocking if empty.

        Returns
        -------
        Any
            The next buffered value, or None if the channel is closed and empty.
        """
        with self.not_empty:
            while not self.buffer and not self.closed:
                self.not_empty.wait()
            if not self.buffer:
                return None
            value = self.buffer.popleft()
            self.not_full.notify()
            return value

    def close(self) -> bool:
        """Close the channel and wake up all waiting senders/receivers."""
        with self.lock:
            already = self.closed
            self.closed = True
            self.not_empty.notify_all()
            self.not_full.notify_all()
            return not already


if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from tiny_language import Environment, NamespaceRef, Runtime


# ---------------------------------------------------------------------------
# Stdlib registration helper
# ---------------------------------------------------------------------------


class _StdLibRegistrar:
    """Registers all stdlib namespaces, types, and native functions.

    Instances capture:
    - the runtime implementation (`Runtime`)
    - the current environment (`Environment`)
    - the `NamespaceRef` class used by the language to reference namespaces

    The main workflow is: `_StdLibRegistrar(...).install()`.
    """

    def __init__(self, runtime: "Runtime", env: "Environment", namespace_ref_cls: type):
        self.runtime = runtime
        self.env = env
        self.namespace_ref_cls = namespace_ref_cls

        # Python interop state:
        # - maps "Python.<module>" -> allowed attribute names
        self._python_namespaces: Dict[str, set[str]] = {}
        # - heap pointers created to represent Python lists/tuples (identity tracking)
        self._python_pointers: set[int] = set()
        # - integers that should be treated as scalar ints, not heap pointers
        self._python_scalar_ints: set[int] = set()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def install(self) -> None:
        """Install namespaces, types, and all native functions into the runtime."""
        # Ensure namespaces exist in the Tiny environment.
        self._ensure_namespace("Math")
        self._ensure_namespace("String")
        self._ensure_namespace("Collections")
        self._ensure_namespace("Map")
        self._ensure_namespace("Set")
        self._ensure_namespace("Deque")
        self._ensure_namespace("Random")
        self._ensure_namespace("Console")
        self._ensure_namespace("File")
        self._ensure_namespace("JSON")
        self._ensure_namespace("Async")
        self._ensure_namespace("Result")
        self._ensure_namespace("Python")

        # Register the `Result` ADT at runtime.
        self.runtime.register_type(
            "Result",
            variants=[
                _Variant("Ok", [("value", "any")]),
                _Variant(
                    "Err",
                    [("code", "string?"), ("message", "string"), ("hint", "string?"), ("stack", "any")],
                ),
            ],
        )

        # ---------------------------- Math ---------------------------------
        self.runtime.register_native("abs", self._math_abs, namespace="Math")
        self.runtime.register_native("max", self._math_max, namespace="Math")
        self.runtime.register_native("min", self._math_min, namespace="Math")
        self.runtime.register_native("pow", self._math_pow, namespace="Math")
        self.runtime.register_native("clamp", self._math_clamp, namespace="Math")
        self.runtime.register_native("sqrt", self._math_sqrt, namespace="Math")
        self.runtime.register_native("round", self._math_round, namespace="Math")
        self.runtime.register_native("floor", self._math_floor, namespace="Math")
        self.runtime.register_native("ceil", self._math_ceil, namespace="Math")
        self.runtime.register_native("sign", self._math_sign, namespace="Math")

        # --------------------------- String --------------------------------
        self.runtime.register_native("split", self._string_split, namespace="String")
        self.runtime.register_native("join", self._string_join, namespace="String")
        self.runtime.register_native("contains", self._string_contains, namespace="String")
        self.runtime.register_native("upper", self._string_upper, namespace="String")
        self.runtime.register_native("lower", self._string_lower, namespace="String")
        self.runtime.register_native("trim", self._string_trim, namespace="String")
        self.runtime.register_native("repeat", self._string_repeat, namespace="String")
        self.runtime.register_native("replace", self._string_replace, namespace="String")
        self.runtime.register_native("starts_with", self._string_starts_with, namespace="String")
        self.runtime.register_native("ends_with", self._string_ends_with, namespace="String")
        self.runtime.register_native("is_digit", self._string_is_digit, namespace="String")

        # ------------------------- Collections ------------------------------
        # Generic helpers for sequences (heap list pointers or Python lists).
        self.runtime.register_native("len", self._collections_len, namespace="Collections")
        self.runtime.register_native("push", self._collections_push, namespace="Collections")
        self.runtime.register_native("pop", self._collections_pop, namespace="Collections")
        self.runtime.register_native("slice", self._collections_slice, namespace="Collections")
        self.runtime.register_native("contains", self._collections_contains, namespace="Collections")

        # ----------------------------- Map ---------------------------------
        self.runtime.register_native("new", self._map_new, namespace="Map")
        self.runtime.register_native("from_entries", self._map_from_entries, namespace="Map")
        self.runtime.register_native("len", self._map_len, namespace="Map")
        self.runtime.register_native("get", self._map_get, namespace="Map")
        self.runtime.register_native("set", self._map_set, namespace="Map")
        self.runtime.register_native("delete", self._map_delete, namespace="Map")
        self.runtime.register_native("has", self._map_has, namespace="Map")
        self.runtime.register_native("keys", self._map_keys, namespace="Map")
        self.runtime.register_native("values", self._map_values, namespace="Map")
        self.runtime.register_native("entries", self._map_entries, namespace="Map")

        # ----------------------------- Set ---------------------------------
        self.runtime.register_native("new", self._set_new, namespace="Set")
        self.runtime.register_native("from_list", self._set_from_list, namespace="Set")
        self.runtime.register_native("len", self._set_len, namespace="Set")
        self.runtime.register_native("add", self._set_add, namespace="Set")
        self.runtime.register_native("delete", self._set_delete, namespace="Set")
        self.runtime.register_native("has", self._set_has, namespace="Set")
        self.runtime.register_native("to_list", self._set_to_list, namespace="Set")

        # ---------------------------- Deque --------------------------------
        self.runtime.register_native("new", self._deque_new, namespace="Deque")
        self.runtime.register_native("len", self._deque_len, namespace="Deque")
        self.runtime.register_native("push_left", self._deque_push_left, namespace="Deque")
        self.runtime.register_native("push_right", self._deque_push_right, namespace="Deque")
        self.runtime.register_native("pop_left", self._deque_pop_left, namespace="Deque")
        self.runtime.register_native("pop_right", self._deque_pop_right, namespace="Deque")
        self.runtime.register_native("peek_left", self._deque_peek_left, namespace="Deque")
        self.runtime.register_native("peek_right", self._deque_peek_right, namespace="Deque")
        self.runtime.register_native("to_list", self._deque_to_list, namespace="Deque")

        # --------------------------- Random --------------------------------
        self.runtime.register_native("random", self._random_random, namespace="Random")
        self.runtime.register_native("randint", self._random_randint, namespace="Random")
        self.runtime.register_native("choice", self._random_choice, namespace="Random")
        self.runtime.register_native("shuffle", self._random_shuffle, namespace="Random")

        # --------------------------- Console -------------------------------
        self.runtime.register_native("read_line", self._console_read_line, namespace="Console")

        # ----------------------------- File --------------------------------
        self.runtime.register_native("read", self._file_read, namespace="File")
        self.runtime.register_native("write", self._file_write, namespace="File")
        self.runtime.register_native("exists", self._file_exists, namespace="File")
        self.runtime.register_native("remove", self._file_remove, namespace="File")

        # ----------------------------- JSON --------------------------------
        self.runtime.register_native("parse", self._json_parse, namespace="JSON")
        self.runtime.register_native("stringify", self._json_stringify, namespace="JSON")

        # ----------------------------- Async -------------------------------
        self.runtime.register_native("token", self._async_token, namespace="Async")
        self.runtime.register_native("cancel", self._async_cancel, namespace="Async")
        self.runtime.register_native("is_cancelled", self._async_is_cancelled, namespace="Async")
        self.runtime.register_native("reason", self._async_reason, namespace="Async")
        self.runtime.register_native("link", self._async_link, namespace="Async")
        self.runtime.register_native("channel", self._async_channel, namespace="Async")
        self.runtime.register_native("send", self._async_send, namespace="Async")
        self.runtime.register_native("recv", self._async_recv, namespace="Async")
        self.runtime.register_native("close", self._async_close, namespace="Async")

        # ---------------------------- Result --------------------------------
        self.runtime.register_native("ok", self._result_ok, namespace="Result")
        self.runtime.register_native("err", self._result_err, namespace="Result")
        self.runtime.register_native("is_ok", self._result_is_ok, namespace="Result")
        self.runtime.register_native("is_err", self._result_is_err, namespace="Result")
        self.runtime.register_native("unwrap_or", self._result_unwrap_or, namespace="Result")

        # ---------------------------- Python --------------------------------
        self.runtime.register_native("import_module", self._python_import_module, namespace="Python")
        self.runtime.register_native("call", self._python_call, namespace="Python")
        self.runtime.register_native("fn", self._python_fn, namespace="Python")

    # -----------------------------------------------------------------------
    # Namespace helpers / runtime heap helpers
    # -----------------------------------------------------------------------

    def _ensure_namespace(self, name: str) -> None:
        """Ensure `name` is defined in the environment as a namespace reference."""
        if name not in self.env.values:
            self.env.define(name, self.namespace_ref_cls(self.runtime, name), SourcePos.origin())

    def _to_pointer(self, values: Iterable[Any]) -> int:
        """Allocate a Tiny heap list pointer containing `values`."""
        items = list(values)
        ptr = self.runtime._Runtime__new(len(items))  # noqa: SLF001 - accessing private helper is intentional
        for idx, value in enumerate(items):
            self.runtime.heap_set(ptr, idx, value)
        return ptr

    def _alloc_heap(self, value: Any) -> int:
        """Store an arbitrary Python object on the Tiny heap and return its pointer."""
        ptr = self.runtime._Runtime__new(0)  # noqa: SLF001 - intentional reuse of private helper
        with self.runtime._lock:  # type: ignore[attr-defined]
            self.runtime.heap[ptr] = value
        return ptr

    # -----------------------------------------------------------------------
    # Value normalization helpers (heap pointer OR native Python object)
    # -----------------------------------------------------------------------

    def _resolve_sequence(self, target: Any) -> List[Any]:
        """Resolve a Tiny “sequence” either from heap pointer or Python list."""
        if isinstance(target, int) and target in self.runtime.heap:
            return self.runtime.heap[target]
        if isinstance(target, list):
            return target
        raise RuntimeError("collections operation expects a heap pointer or list")

    def _resolve_map(self, target: Any) -> Dict[Any, Any]:
        """Resolve a map either from heap pointer or Python dict."""
        if isinstance(target, int) and target in self.runtime.heap:
            maybe = self.runtime.heap[target]
            if isinstance(maybe, dict):
                return maybe
        if isinstance(target, dict):
            return target
        raise RuntimeError("map operation expects a heap pointer or dict")

    def _resolve_set(self, target: Any) -> set:
        """Resolve a set either from heap pointer or Python set."""
        if isinstance(target, int) and target in self.runtime.heap:
            maybe = self.runtime.heap[target]
            if isinstance(maybe, set):
                return maybe
        if isinstance(target, set):
            return target
        raise RuntimeError("set operation expects a heap pointer or set")

    def _resolve_deque(self, target: Any) -> deque:
        """Resolve a deque either from heap pointer or `collections.deque`."""
        if isinstance(target, int) and target in self.runtime.heap:
            maybe = self.runtime.heap[target]
            if isinstance(maybe, deque):
                return maybe
        if isinstance(target, deque):
            return target
        raise RuntimeError("deque operation expects a heap pointer or deque")

    # -----------------------------------------------------------------------
    # Numeric / interval helpers
    # -----------------------------------------------------------------------

    def _resolve_number(self, value: Any) -> tuple[Any, str | None]:
        """Normalize Tiny 'number objects' to (value, error_tag) if present."""
        fields = self.runtime._number_fields(value)  # noqa: SLF001 - internal helper reuse
        if fields is not None:
            return fields.get("value", 0), fields.get("error", "normal") or "normal"
        return value, None

    def _resolve_intervall(self, value: Any) -> tuple[Any, Any, str | None] | None:
        """Normalize Tiny interval objects to (lower, upper, error_tag).

        Note: method name uses the project’s existing spelling `intervall`
        to match runtime/internal naming.
        """
        fields = self.runtime._intervall_fields(value)  # noqa: SLF001 - internal helper reuse
        if fields is not None:
            return (
                fields.get("lower", 0),
                fields.get("upper", 0),
                fields.get("error", "normal") or "normal",
            )

        num_fields = self.runtime._number_fields(value)  # noqa: SLF001 - internal helper reuse
        if num_fields is not None:
            err = num_fields.get("error", "normal") or "normal"
            if err in {"plus_infinity", "minus_infinity", "any_number"}:
                return 0, 0, err
            return None

        return None

    # -----------------------------------------------------------------------
    # Math namespace
    # -----------------------------------------------------------------------
    # Many operations support either plain Python numbers OR Tiny “number/interval”
    # objects. When a Tiny wrapper exists, these methods attempt to preserve the
    # wrapper and propagate error tags.

    def _math_abs(self, value: Any) -> Any:
        """Absolute value with interval support."""
        interval = self._resolve_intervall(value)
        if interval is not None:
            lower, upper, err = interval
            if err != "normal":
                return self.runtime._make_intervall(lower, upper, err)  # noqa: SLF001

            if lower > upper:
                return self.runtime._make_intervall(lower, upper, "wrapped_interval")  # noqa: SLF001

            candidates = [abs(lower), abs(upper)]
            if lower <= 0 <= upper:
                lo, hi = 0, max(candidates)
            else:
                lo, hi = min(candidates), max(candidates)
            return self.runtime._make_intervall(lo, hi, "normal")  # noqa: SLF001

        fields = self.runtime._number_fields(value)  # noqa: SLF001 - internal helper reuse
        if fields is not None:
            err = fields.get("error", "normal") or "normal"
            val = fields.get("value", 0)
            return self.runtime._make_number(abs(val), err)  # noqa: SLF001
        return abs(value)

    def _math_max(self, left: Any, right: Any) -> Any:
        """Maximum of two values, supporting intervals and error propagation."""
        left_interval = self._resolve_intervall(left)
        right_interval = self._resolve_intervall(right)

        if left_interval is not None or right_interval is not None:
            if left_interval is not None and right_interval is not None:
                l_lo, l_hi, l_err = left_interval
                r_lo, r_hi, r_err = right_interval
                err = l_err or r_err or "normal"
                if l_err != "normal" or r_err != "normal":
                    return self.runtime._make_intervall(0, 0, err)  # noqa: SLF001

                return self.runtime._make_intervall(max(l_lo, r_lo), max(l_hi, r_hi), err)  # noqa: SLF001

            interval_value = left_interval or right_interval
            other = right if left_interval is not None else left
            lo, hi, err = interval_value
            if err != "normal":
                return self.runtime._make_intervall(0, 0, err)  # noqa: SLF001
            try:
                return self.runtime._make_intervall(max(lo, other), max(hi, other), "normal")  # noqa: SLF001
            except Exception:
                return self.runtime._make_intervall(0, 0, "any_number")  # noqa: SLF001

        l_val, l_err = self._resolve_number(left)
        r_val, r_err = self._resolve_number(right)

        res = max(l_val, r_val)
        err = l_err or r_err or "normal"
        if l_err or r_err:
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return res

    def _math_min(self, left: Any, right: Any) -> Any:
        """Minimum of two values, supporting intervals and error propagation."""
        left_interval = self._resolve_intervall(left)
        right_interval = self._resolve_intervall(right)

        if left_interval is not None or right_interval is not None:
            if left_interval is not None and right_interval is not None:
                l_lo, l_hi, l_err = left_interval
                r_lo, r_hi, r_err = right_interval
                err = l_err or r_err or "normal"
                if l_err != "normal" or r_err != "normal":
                    return self.runtime._make_intervall(0, 0, err)  # noqa: SLF001

                return self.runtime._make_intervall(min(l_lo, r_lo), min(l_hi, r_hi), err)  # noqa: SLF001

            interval_value = left_interval or right_interval
            other = right if left_interval is not None else left
            lo, hi, err = interval_value
            if err != "normal":
                return self.runtime._make_intervall(0, 0, err)  # noqa: SLF001
            try:
                return self.runtime._make_intervall(min(lo, other), min(hi, other), "normal")  # noqa: SLF001
            except Exception:
                return self.runtime._make_intervall(0, 0, "any_number")  # noqa: SLF001

        l_val, l_err = self._resolve_number(left)
        r_val, r_err = self._resolve_number(right)

        res = min(l_val, r_val)
        err = l_err or r_err or "normal"
        if l_err or r_err:
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return res

    def _math_pow(self, base: Any, exponent: Any) -> Any:
        """Exponentiation with interval support and Tiny number wrappers."""
        base_interval = self._resolve_intervall(base)
        exp_interval = self._resolve_intervall(exponent)

        if base_interval is not None or exp_interval is not None:
            if base_interval is None or exp_interval is None:
                return self.runtime._make_intervall(0, 0, "any_number")  # noqa: SLF001

            b_lo, b_hi, b_err = base_interval
            e_lo, e_hi, e_err = exp_interval
            if b_err != "normal" or e_err != "normal":
                return self.runtime._make_intervall(0, 0, b_err or e_err)  # noqa: SLF001

            try:
                candidates = [
                    math.pow(b_lo, e_lo),
                    math.pow(b_lo, e_hi),
                    math.pow(b_hi, e_lo),
                    math.pow(b_hi, e_hi),
                ]
                lo = min(candidates)
                hi = max(candidates)
            except Exception:
                return self.runtime._make_intervall(0, 0, "any_number")  # noqa: SLF001

            return self.runtime._make_intervall(lo, hi, "normal")  # noqa: SLF001

        num_res = self.runtime._number_power(base, exponent)  # noqa: SLF001
        if num_res is not None:
            return num_res
        res = math.pow(base, exponent)
        if isinstance(res, float) and res.is_integer():
            res = int(res)
        return res

    def _math_sqrt(self, value: Any) -> Any:
        """Square root with interval support and error propagation."""
        interval = self._resolve_intervall(value)
        if interval is not None:
            lower, upper, err = interval
            if err != "normal":
                return self.runtime._make_intervall(lower, upper, err)  # noqa: SLF001
            if lower < 0:
                return self.runtime._make_intervall(lower, upper, "any_number")  # noqa: SLF001
            try:
                lo = math.sqrt(lower)
                hi = math.sqrt(upper)
                if lo > hi:
                    lo, hi = hi, lo
            except Exception:
                return self.runtime._make_intervall(0, 0, "any_number")  # noqa: SLF001
            return self.runtime._make_intervall(lo, hi, "normal")  # noqa: SLF001

        fields = self.runtime._number_fields(value)  # noqa: SLF001
        if fields is not None:
            err = fields.get("error", "normal") or "normal"
            res = math.sqrt(fields.get("value", 0))
            if isinstance(res, float) and res.is_integer():
                res = int(res)
            return self.runtime._make_number(res, err)  # noqa: SLF001
        res = math.sqrt(value)
        if isinstance(res, float) and res.is_integer():
            res = int(res)
        return res

    def _math_round(self, value: Any, digits: Any | None = None) -> Any:
        """Round a number or interval; `digits` (if present) must be an int."""
        num_fields = self.runtime._number_fields(value)  # noqa: SLF001
        places = None
        if digits is not None:
            try:
                places = int(digits)
            except Exception:
                raise RuntimeError("round expects an optional integer for digits")
        interval = self._resolve_intervall(value)
        if interval is not None:
            lower, upper, err = interval
            if err != "normal":
                return self.runtime._make_intervall(lower, upper, err)  # noqa: SLF001
            try:
                lo = round(lower, places) if places is not None else round(lower)
                hi = round(upper, places) if places is not None else round(upper)
            except Exception:
                return self.runtime._make_intervall(0, 0, "any_number")  # noqa: SLF001
            if lo > hi:
                lo, hi = hi, lo
            return self.runtime._make_intervall(lo, hi, "normal")  # noqa: SLF001
        if num_fields is not None:
            err = num_fields.get("error", "normal") or "normal"
            res = (
                round(num_fields.get("value", 0), places)
                if places is not None
                else round(num_fields.get("value", 0))
            )
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return round(value, places) if places is not None else round(value)

    def _math_floor(self, value: Any) -> Any:
        """Floor with interval and Tiny wrapper support."""
        interval = self._resolve_intervall(value)
        if interval is not None:
            lower, upper, err = interval
            if err != "normal":
                return self.runtime._make_intervall(lower, upper, err)  # noqa: SLF001
            return self.runtime._make_intervall(math.floor(lower), math.floor(upper), "normal")  # noqa: SLF001
        fields = self.runtime._number_fields(value)  # noqa: SLF001
        if fields is not None:
            err = fields.get("error", "normal") or "normal"
            res = math.floor(fields.get("value", 0))
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return math.floor(value)

    def _math_ceil(self, value: Any) -> Any:
        """Ceil with interval and Tiny wrapper support."""
        interval = self._resolve_intervall(value)
        if interval is not None:
            lower, upper, err = interval
            if err != "normal":
                return self.runtime._make_intervall(lower, upper, err)  # noqa: SLF001
            return self.runtime._make_intervall(math.ceil(lower), math.ceil(upper), "normal")  # noqa: SLF001
        fields = self.runtime._number_fields(value)  # noqa: SLF001
        if fields is not None:
            err = fields.get("error", "normal") or "normal"
            res = math.ceil(fields.get("value", 0))
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return math.ceil(value)

    def _math_sign(self, value: Any) -> Any:
        """Sign function; may return an uncertain/any_number wrapper for intervals."""
        interval = self._resolve_intervall(value)
        if interval is not None:
            lower, upper, err = interval
            if err != "normal":
                return self.runtime._make_number(0, err)  # noqa: SLF001
            if lower > 0 and upper > 0:
                return 1
            if lower < 0 and upper < 0:
                return -1
            return self.runtime._make_number(0, "any_number")  # noqa: SLF001
        val, _err = self._resolve_number(value)
        if val > 0:
            return 1
        if val < 0:
            return -1
        return 0

    def _math_clamp(self, value: Any, lower: Any, upper: Any) -> Any:
        """Clamp `value` into [lower, upper], supporting intervals."""
        interval_val = self._resolve_intervall(value)
        interval_lower = self._resolve_intervall(lower)
        interval_upper = self._resolve_intervall(upper)

        if interval_val is not None or interval_lower is not None or interval_upper is not None:
            val_lo, val_hi, val_err = interval_val or (0, 0, "normal")
            low_lo, low_hi, low_err = interval_lower or (0, 0, "normal")
            up_lo, up_hi, up_err = interval_upper or (0, 0, "normal")

            err = val_err or low_err or up_err or "normal"
            if err != "normal":
                return self.runtime._make_intervall(0, 0, err)  # noqa: SLF001

            try:
                lower_bound = max(low_lo, min(val_lo, up_hi))
                upper_bound = max(low_hi, min(val_hi, up_lo))
            except Exception:
                return self.runtime._make_intervall(0, 0, "any_number")  # noqa: SLF001

            if lower_bound > upper_bound:
                lower_bound, upper_bound = upper_bound, lower_bound

            return self.runtime._make_intervall(lower_bound, upper_bound, "normal")  # noqa: SLF001

        v_val, v_err = self._resolve_number(value)
        lower_val, lower_err = self._resolve_number(lower)
        upper_val, upper_err = self._resolve_number(upper)

        res = max(lower_val, min(v_val, upper_val))
        err = v_err or lower_err or upper_err or "normal"
        if v_err or lower_err or upper_err:
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return res

    # -----------------------------------------------------------------------
    # String namespace
    # -----------------------------------------------------------------------

    def _string_split(self, text: Any, sep: Any) -> int:
        """Split `text` by `sep` and return a Tiny heap list pointer of strings."""
        return self._to_pointer(str(text).split(str(sep)))

    def _string_join(self, items: Any, sep: Any) -> str:
        """Join a sequence with a separator."""
        seq = self._resolve_sequence(items)
        return str(sep).join(str(item) for item in seq)

    def _string_contains(self, text: Any, needle: Any) -> bool:
        """Substring check."""
        return str(needle) in str(text)

    def _string_upper(self, text: Any) -> str:
        return str(text).upper()

    def _string_lower(self, text: Any) -> str:
        return str(text).lower()

    def _string_trim(self, text: Any) -> str:
        return str(text).strip()

    def _string_repeat(self, text: Any, count: Any) -> str:
        """Repeat a string `count` times; count must be a non-negative integer."""
        try:
            times = int(count)
        except Exception:
            raise RuntimeError("repeat expects an integer count")
        if times < 0:
            raise RuntimeError("repeat count must be non-negative")
        return str(text) * times

    def _string_replace(self, text: Any, old: Any, new: Any) -> str:
        """Replace occurrences of `old` in `text` with `new`."""
        return str(text).replace(str(old), str(new))

    def _string_starts_with(self, text: Any, prefix: Any) -> bool:
        """Return True if text starts with prefix."""
        return str(text).startswith(str(prefix))

    def _string_ends_with(self, text: Any, suffix: Any) -> bool:
        """Return True if text ends with suffix."""
        return str(text).endswith(str(suffix))

    def _string_is_digit(self, text: Any) -> bool:
        """Return True if text contains only digit characters."""
        return str(text).isdigit()

    # -----------------------------------------------------------------------
    # Collections namespace
    # -----------------------------------------------------------------------

    def _collections_len(self, target: Any) -> int:
        """Return length for heap pointers or Python sized objects."""
        try:
            if isinstance(target, int) and target in self.runtime.heap:
                return len(self.runtime.heap[target])
            return len(target)  # type: ignore[arg-type]
        except Exception:
            raise RuntimeError("len expects a sized value")

    def _collections_push(self, target: Any, value: Any) -> int:
        """Append to a sequence; returns the new length."""
        seq = self._resolve_sequence(target)
        seq.append(value)
        return len(seq)

    def _collections_pop(self, target: Any) -> Any:
        """Pop from end; raises on empty."""
        seq = self._resolve_sequence(target)
        if not seq:
            raise RuntimeError("pop from empty collection")
        return seq.pop()

    def _collections_slice(self, target: Any, start: Any, end: Any) -> int:
        """Slice a sequence and return a new heap list pointer."""
        seq = self._resolve_sequence(target)
        try:
            start_idx = int(start)
            end_idx = int(end)
        except Exception:
            raise RuntimeError("slice expects integer start and end")
        return self._to_pointer(seq[start_idx:end_idx])

    def _collections_contains(self, target: Any, value: Any) -> bool:
        """Membership test for sequences."""
        seq = self._resolve_sequence(target)
        return value in seq

    # -----------------------------------------------------------------------
    # Map / Set / Deque namespaces
    # -----------------------------------------------------------------------
    # These provide heap-friendly wrappers around Python dict/set/deque.

    def _map_new(self) -> int:
        return self._alloc_heap({})

    def _map_from_entries(self, entries: Any) -> int:
        """Build a map from a list of `[key, value]` pairs."""
        seq = self._resolve_sequence(entries)
        result: Dict[Any, Any] = {}
        for pair in seq:
            pair_val = pair
            if isinstance(pair, int) and pair in self.runtime.heap:
                pair_val = self.runtime.heap[pair]
            if not isinstance(pair_val, (list, tuple)) or len(pair_val) != 2:
                raise RuntimeError("from_entries expects [key, value] pairs")
            key, val = pair_val
            result[key] = val
        return self._alloc_heap(result)

    def _map_len(self, target: Any) -> int:
        return len(self._resolve_map(target))

    def _map_get(self, target: Any, key: Any, default: Any | None = None) -> Any:
        return self._resolve_map(target).get(key, default)

    def _map_set(self, target: Any, key: Any, value: Any) -> Any:
        m = self._resolve_map(target)
        m[key] = value
        return value

    def _map_delete(self, target: Any, key: Any) -> bool:
        m = self._resolve_map(target)
        if key in m:
            del m[key]
            return True
        return False

    def _map_has(self, target: Any, key: Any) -> bool:
        return key in self._resolve_map(target)

    def _map_keys(self, target: Any) -> int:
        return self._to_pointer(self._resolve_map(target).keys())

    def _map_values(self, target: Any) -> int:
        return self._to_pointer(self._resolve_map(target).values())

    def _map_entries(self, target: Any) -> int:
        items = [[k, v] for k, v in self._resolve_map(target).items()]
        return self._to_pointer(items)

    def _set_new(self) -> int:
        return self._alloc_heap(set())

    def _set_from_list(self, values: Any) -> int:
        seq = self._resolve_sequence(values)
        return self._alloc_heap(set(seq))

    def _set_len(self, target: Any) -> int:
        return len(self._resolve_set(target))

    def _set_add(self, target: Any, value: Any) -> bool:
        s = self._resolve_set(target)
        before = len(s)
        s.add(value)
        return len(s) > before

    def _set_delete(self, target: Any, value: Any) -> bool:
        s = self._resolve_set(target)
        if value in s:
            s.remove(value)
            return True
        return False

    def _set_has(self, target: Any, value: Any) -> bool:
        return value in self._resolve_set(target)

    def _set_to_list(self, target: Any) -> int:
        return self._to_pointer(list(self._resolve_set(target)))

    def _deque_new(self, values: Any | None = None) -> int:
        """Create a deque, optionally from an existing sequence."""
        if values is None:
            return self._alloc_heap(deque())
        seq = self._resolve_sequence(values)
        return self._alloc_heap(deque(seq))

    def _deque_len(self, target: Any) -> int:
        return len(self._resolve_deque(target))

    def _deque_push_left(self, target: Any, value: Any) -> int:
        dq = self._resolve_deque(target)
        dq.appendleft(value)
        return len(dq)

    def _deque_push_right(self, target: Any, value: Any) -> int:
        dq = self._resolve_deque(target)
        dq.append(value)
        return len(dq)

    def _deque_pop_left(self, target: Any) -> Any:
        dq = self._resolve_deque(target)
        if not dq:
            raise RuntimeError("pop from empty deque")
        return dq.popleft()

    def _deque_pop_right(self, target: Any) -> Any:
        dq = self._resolve_deque(target)
        if not dq:
            raise RuntimeError("pop from empty deque")
        return dq.pop()

    def _deque_peek_left(self, target: Any) -> Any:
        dq = self._resolve_deque(target)
        if not dq:
            raise RuntimeError("peek from empty deque")
        return dq[0]

    def _deque_peek_right(self, target: Any) -> Any:
        dq = self._resolve_deque(target)
        if not dq:
            raise RuntimeError("peek from empty deque")
        return dq[-1]

    def _deque_to_list(self, target: Any) -> int:
        return self._to_pointer(list(self._resolve_deque(target)))

    # -----------------------------------------------------------------------
    # Random namespace
    # -----------------------------------------------------------------------

    def _random_random(self) -> float:
        """Return a uniform float in [0.0, 1.0)."""
        return random.random()

    def _random_randint(self, lower: Any, upper: Any) -> int:
        """Return an integer N such that lower <= N <= upper."""
        try:
            lo = int(lower)
            hi = int(upper)
        except Exception:
            raise RuntimeError("randint expects integer bounds")
        return random.randint(lo, hi)

    def _random_choice(self, values: Any) -> Any:
        """Choose one element uniformly from a non-empty sequence."""
        seq = self._resolve_sequence(values)
        if not seq:
            raise RuntimeError("choice expects a non-empty sequence")
        return random.choice(seq)

    def _random_shuffle(self, values: Any) -> int:
        """Shuffle a sequence in-place; returns the length."""
        seq = self._resolve_sequence(values)
        random.shuffle(seq)
        return len(seq)

    # -----------------------------------------------------------------------
    # Console namespace
    # -----------------------------------------------------------------------

    def _console_read_line(self, prompt: Any | None = None) -> str:
        """Read one line from stdin (or debug adapter pipe).

        Debug adapter integration
        -------------------------
        When running under the TinyLanguage debug adapter, stdin/stdout may be
        reserved for the protocol stream. In that case:
        - If `TINYLANGUAGE_DAP_STDIN_PIPE` is set, read from that FIFO path.
        - Otherwise, if `TINYLANGUAGE_DAP_DISABLE_STDIN` is set and
          `TINYLANGUAGE_DAP_ALLOW_STDIN` is *not* set, deny reads.
        """
        pipe_path = os.environ.get("TINYLANGUAGE_DAP_STDIN_PIPE")
        if pipe_path:
            try:
                with open(pipe_path, "r", encoding="utf-8") as handle:
                    line = handle.readline()
            except FileNotFoundError:
                raise RuntimeError(
                    f"Console.read_line pipe does not exist: {pipe_path}. "
                    "Re-run the debugger or recreate the FIFO."
                )
            except Exception as exc:  # pragma: no cover - unexpected FIFO error
                raise RuntimeError(f"Console.read_line failed to read pipe {pipe_path}: {exc}")
            if line == "":
                return ""
            return line.rstrip("\n")

        if os.environ.get("TINYLANGUAGE_DAP_DISABLE_STDIN") and not os.environ.get("TINYLANGUAGE_DAP_ALLOW_STDIN"):
            raise RuntimeError(
                "Console.read_line is disabled while running under the TinyLanguage debug adapter "
                "because stdin/stdout carry the protocol stream. Run the program from a terminal or "
                "set TINYLANGUAGE_DAP_ALLOW_STDIN=1 to bypass this guard (not recommended)."
            )
        try:
            return input("" if prompt is None else str(prompt))
        except EOFError:
            return ""

    # -----------------------------------------------------------------------
    # File namespace
    # -----------------------------------------------------------------------

    def _coerce_path(self, path: Any) -> Path:
        """Convert Tiny string path to a `Path`, normalizing separators."""
        path_str = str(path)
        # Normalize platform-specific separators that may appear inside TinyLanguage
        # string literals (especially on Windows where backslashes are common and can
        # be interpreted as escape sequences by editors).
        path_str = path_str.replace("\\", "/")
        return Path(path_str)

    def _file_read(self, path: Any) -> str:
        """Read UTF-8 text from a file path."""
        text_path = self._coerce_path(path)
        if not text_path.exists():
            raise RuntimeError(f"file does not exist: {text_path}")
        return text_path.read_text(encoding="utf-8")

    def _file_write(self, path: Any, content: Any) -> bool:
        """Write UTF-8 text to a file path, creating parent directories."""
        text_path = self._coerce_path(path)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(str(content), encoding="utf-8")
        return True

    def _file_exists(self, path: Any) -> bool:
        """Return True iff the path exists."""
        return self._coerce_path(path).exists()

    def _file_remove(self, path: Any) -> bool:
        """Remove a file if it exists; returns False if it did not exist."""
        text_path = self._coerce_path(path)
        if not text_path.exists():
            return False
        text_path.unlink()
        return True

    # -----------------------------------------------------------------------
    # JSON namespace
    # -----------------------------------------------------------------------

    def _json_parse(self, text: Any) -> Any:
        """Parse JSON and convert it into Tiny-friendly values."""
        try:
            loaded = json.loads(str(text))
        except Exception as exc:
            raise RuntimeError(f"invalid json: {exc}")
        return self._json_to_value(loaded)

    def _json_to_value(self, data: Any) -> Any:
        """Recursively map decoded JSON to Tiny values."""
        if isinstance(data, dict):
            return {k: self._json_to_value(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._json_to_value(item) for item in data]
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        raise RuntimeError(f"unsupported json value: {data!r}")

    def _json_stringify(self, value: Any) -> str:
        """Serialize Tiny values (including heap pointers) to JSON."""
        def convert(val: Any) -> Any:
            if isinstance(val, bool):
                return val
            num_fields = self.runtime._number_fields(val)  # noqa: SLF001
            if num_fields is not None:
                return num_fields.get("value", 0)
            if isinstance(val, int) and val in self.runtime.heap:
                obj = self.runtime.heap[val]
                if isinstance(obj, list):
                    return [convert(item) for item in obj]
                if isinstance(obj, dict):
                    return {str(k): convert(v) for k, v in obj.items()}
                if isinstance(obj, (deque, set)):
                    return [convert(item) for item in list(obj)]
            if isinstance(val, list):
                return [convert(item) for item in val]
            if isinstance(val, dict):
                return {str(k): convert(v) for k, v in val.items()}
            if isinstance(val, deque):
                return [convert(item) for item in list(val)]
            if isinstance(val, set):
                return [convert(item) for item in sorted(val, key=str)]
            if val is None:
                return None
            if isinstance(val, (str, int, float, bool)):
                return val
            raise RuntimeError(f"value of type {type(val).__name__} cannot be stringified to JSON")

        return json.dumps(convert(value))

    # -----------------------------------------------------------------------
    # Async namespace (tokens, cancellation, channels)
    # -----------------------------------------------------------------------

    def _async_token(self) -> Any:
        """Create a new cancellation token."""
        return self.runtime.make_cancellation_token()

    def _async_cancel(self, token: Any, reason: Any | None = None) -> bool:
        """Cancel a token with an optional reason string."""
        text = None if reason is None else str(reason)
        return self.runtime.cancel_token(token, text)

    def _async_is_cancelled(self, token: Any) -> bool:
        return self.runtime.token_cancelled(token)

    def _async_reason(self, token: Any) -> Any:
        return self.runtime.token_reason(token)

    def _async_link(self, token: Any, handle: Any) -> bool:
        """Link a token to a task handle so cancellation can propagate."""
        return self.runtime.link_token(token, handle)

    def _async_channel(self, capacity: Any) -> _Channel:
        """Create a bounded channel with integer capacity."""
        try:
            cap = int(capacity)
        except Exception:
            raise RuntimeError("channel expects an integer capacity")
        return _Channel(cap)

    def _async_send(self, chan: Any, value: Any) -> bool:
        if not isinstance(chan, _Channel):
            raise RuntimeError("send expects a channel")
        return chan.send(value)

    def _async_recv(self, chan: Any) -> Any:
        if not isinstance(chan, _Channel):
            raise RuntimeError("recv expects a channel")
        return chan.recv()

    def _async_close(self, chan: Any) -> bool:
        if not isinstance(chan, _Channel):
            raise RuntimeError("close expects a channel")
        return chan.close()

    # -----------------------------------------------------------------------
    # Result namespace (ADTs)
    # -----------------------------------------------------------------------

    def _result_ok(self, value: Any) -> Dict[str, Any]:
        """Construct Result.Ok(value)."""
        return self.runtime.instantiate_variant("Ok", {"value": value}, type_name="Result")

    def _result_err(self, value: Any, code: Any | None = None) -> Dict[str, Any]:
        """Construct Result.Err(...) from various error-shaped inputs."""
        if hasattr(value, "__class__") and value.__class__.__name__ == "TinyLangError":
            err_obj = self.runtime._error_value(value)
        elif isinstance(value, dict) and value.get("__tag__") == "Error":
            err_obj = {
                "code": value.get("code"),
                "message": value.get("message") or value.get("msg"),
                "hint": value.get("hint"),
                "stack": value.get("stack", []),
            }
        else:
            err_obj = {"code": code or "E000", "message": str(value), "hint": None, "stack": []}
        return self.runtime.instantiate_variant("Err", err_obj, type_name="Result")

    def _result_is_ok(self, value: Any) -> bool:
        return isinstance(value, dict) and value.get("__type__") == "Result" and value.get("__tag__") == "Ok"

    def _result_is_err(self, value: Any) -> bool:
        return isinstance(value, dict) and value.get("__type__") == "Result" and value.get("__tag__") == "Err"

    def _result_unwrap_or(self, value: Any, default: Any) -> Any:
        """Return Ok.value or the provided default if Err."""
        if self._result_is_ok(value):
            return value.get("value")
        if self._result_is_err(value):
            return default
        return value

    # -----------------------------------------------------------------------
    # Python interop helpers (Python namespace)
    # -----------------------------------------------------------------------

    def _python_import_module(self, module: str, allow: Any | None = None) -> "NamespaceRef":
        """Import a Python module and expose selected attributes into `Python.<module>`.

        Parameters
        ----------
        module:
            Module name, e.g. `"math"` or `"math.trunc"`.
        allow:
            Optional allowlist:
              - list/sequence of attribute names
              - dict with key `"allow"` containing a list/sequence
              - heap pointer to a list

        Returns
        -------
        NamespaceRef
            Reference to the created Tiny namespace, e.g. `Python.math`.
        """
        module_name = str(module)
        self._python_ensure_module_allowed(module_name)
        allowed = self._python_normalize_allowlist(allow)
        py_module = importlib.import_module(module_name)
        namespace = f"Python.{module_name}"

        existing = self._python_namespaces.get(namespace, set())
        requested = set(allowed)
        missing = requested - existing

        self._python_namespaces[namespace] = existing | requested

        # Lazily create a namespace environment so constants can be accessed as fields.
        from tiny_language import Environment  # Imported lazily to avoid circular imports

        env = self.runtime.namespace_envs.get(namespace)
        if env is None:
            env = Environment(parent=None, namespace=namespace, runtime=self.runtime)
            self.runtime.namespace_envs[namespace] = env

        for name in missing:
            attr = getattr(py_module, name, None)
            if callable(attr):
                self.runtime.register_native(name, self._python_make_callable(py_module, name), namespace=namespace)
            else:
                env.define(name, self._python_from_host(attr), SourcePos.origin())

        return self.namespace_ref_cls(self.runtime, namespace)

    def _python_call(self, module: str, attr: str, args: Any | None = None, opts: Any | None = None) -> Any:
        """Call a Python function under allowlist control.

        Parameters
        ----------
        module:
            Python module name.
        attr:
            Attribute name (function name).
        args:
            Either:
              - None
              - list
              - heap pointer to list
              - single value (wrapped into a single argument)
        opts:
            Optional dict with:
              - "allow": allowlist override for this call
              - "timeout_ms": integer timeout in milliseconds

        Returns
        -------
        Any
            Result converted back into a Tiny value.
        """
        module_name = str(module)
        self._python_ensure_module_allowed(module_name)
        allowed_attrs = self._python_resolve_allowlist(module_name, opts)
        if allowed_attrs is None:
            allowed_attrs = set()
        timeout_ms = self._python_normalize_timeout(opts)

        py_module = importlib.import_module(module_name)
        attr_name = str(attr)
        if attr_name not in allowed_attrs:
            raise RuntimeError(f"[PYDENY] attribute {attr_name} not allowed")

        func = getattr(py_module, attr_name, None)
        if not callable(func):
            raise RuntimeError(f"[PYERR] attribute {attr_name} is not callable")

        arg_list = self._python_normalize_args(args)
        py_args = [self._python_to_host(val) for val in arg_list]
        result: Dict[str, Any] = {}
        error: Dict[str, BaseException] = {}

        def _invoke() -> None:
            try:
                result["value"] = func(*py_args)
            except Exception as exc:  # noqa: BLE001
                error["exc"] = exc

        if timeout_ms is None:
            _invoke()
        else:
            thread = threading.Thread(target=_invoke, daemon=True)
            thread.start()
            thread.join(timeout_ms / 1000.0)
            if thread.is_alive():
                raise RuntimeError(f"[PYTIMEOUT] {module_name}.{attr_name} exceeded {timeout_ms} ms")
        if error:
            raise RuntimeError(f"[PYERR] {error['exc']}")
        return self._python_from_host(result.get("value"))

    def _python_fn(self, module: str, attr: str, opts: Any | None = None) -> str:
        """Register a Python callable as a Tiny native function.

        This is a convenience wrapper around `Python.call` that registers a named
        Tiny function (optionally aliased) directly on the root runtime.

        Parameters
        ----------
        module:
            Python module name.
        attr:
            Attribute name inside the module.
        opts:
            Optional dict:
              - "allow": allowlist override
              - "as": name to register the function under in Tiny

        Returns
        -------
        str
            The registered name (alias).
        """
        alias = attr
        if isinstance(opts, dict) and "as" in opts:
            alias = str(opts["as"])

        module_name = str(module)
        self._python_ensure_module_allowed(module_name)
        allowed_attrs = self._python_resolve_allowlist(module_name, opts)
        if allowed_attrs is None:
            allowed_attrs = set()
        py_module = importlib.import_module(module_name)
        attr_name = str(attr)
        if attr_name not in allowed_attrs:
            raise RuntimeError(f"[PYDENY] attribute {attr_name} not allowed")

        func = getattr(py_module, attr_name, None)
        if not callable(func):
            raise RuntimeError(f"[PYERR] attribute {attr_name} is not callable")

        self.runtime.register_native(alias, self._python_make_callable(py_module, attr_name))
        return alias

    def _python_make_callable(self, module: Any, attr: str):
        """Wrap a Python callable so args/results are converted across the boundary."""
        def _callable(*args: Any) -> Any:
            py_args = [self._python_to_host(val) for val in args]
            func = getattr(module, attr)
            return self._python_from_host(func(*py_args))

        return _callable

    def _python_normalize_allowlist(self, value: Any | None) -> list[str]:
        """Normalize allowlist input into a list[str]."""
        allow_source = value
        if isinstance(value, dict):
            allow_source = value.get("allow")
        if allow_source is None:
            return []
        if isinstance(allow_source, int) and allow_source in self.runtime.heap:
            allow_source = self.runtime.heap[allow_source]
        try:
            return [str(v) for v in list(allow_source)]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("[PYERR] allowlist must be iterable") from exc

    def _python_normalize_timeout(self, opts: Any | None) -> int | None:
        """Extract timeout_ms from options dict (milliseconds)."""
        if not isinstance(opts, dict):
            return None
        if "timeout_ms" not in opts:
            return None
        try:
            timeout = int(opts["timeout_ms"])
        except Exception:  # noqa: BLE001
            raise RuntimeError("[PYERR] timeout_ms must be an integer")
        if timeout < 0:
            raise RuntimeError("[PYERR] timeout_ms must be non-negative")
        return timeout

    def _python_ensure_module_allowed(self, module: str) -> None:
        """Denylist enforcement for Python modules."""
        base = module.split(".")[0]
        if base in _BANNED_PYTHON_MODULES or module in _BANNED_PYTHON_MODULES:
            raise RuntimeError(f"[PYSEC] module {module} denied")

    def _python_resolve_allowlist(self, module: str, opts: Any | None) -> set[str] | None:
        """Resolve allowlist either from call options or stored namespace state."""
        if isinstance(opts, dict) and "allow" in opts:
            return set(self._python_normalize_allowlist(opts))
        if opts is not None and not isinstance(opts, dict):
            return set(self._python_normalize_allowlist(opts))
        return self._python_namespaces.get(f"Python.{module}")

    def _python_normalize_args(self, args: Any | None) -> list[Any]:
        """Normalize call arguments for Python calls."""
        if args is None:
            return []
        if isinstance(args, int) and args in self.runtime.heap:
            seq = self.runtime.heap[args]
            if isinstance(seq, list):
                return list(seq)
        if isinstance(args, list):
            return args
        return [args]

    def _python_to_host(self, value: Any, _seen: set[int] | None = None) -> Any:
        """Convert Tiny values (including heap pointers) into Python values.

        Cycle handling:
        - Uses a `seen` set keyed by `id(obj)` to avoid infinite recursion when
          converting self-referential structures.
        """
        seen = _seen or set()

        def _mark(obj: Any) -> bool:
            try:
                obj_id = id(obj)
            except Exception:  # noqa: BLE001
                return False
            if obj_id in seen:
                return True
            seen.add(obj_id)
            return False

        if isinstance(value, bool):
            return value
        if isinstance(value, (str, float)) or value is None:
            return value
        if isinstance(value, int) and value in self._python_scalar_ints:
            return value
        if isinstance(value, int) and value in self._python_pointers:
            stored = self.runtime.heap[value]
            if _mark(stored):
                return stored
            if isinstance(stored, list):
                return [self._python_to_host(v, seen) for v in stored]
            if isinstance(stored, dict):
                return {k: self._python_to_host(v, seen) for k, v in stored.items()}
            if isinstance(stored, set):
                return {self._python_to_host(v, seen) for v in stored}
            return stored
        if isinstance(value, dict) and "__fields__" in value:
            if _mark(value):
                return value
            return {k: self._python_to_host(v, seen) for k, v in value.get("__fields__", {}).items()}
        if isinstance(value, list):
            if _mark(value):
                return value
            return [self._python_to_host(v, seen) for v in value]
        if isinstance(value, dict):
            if _mark(value):
                return value
            return {k: self._python_to_host(v, seen) for k, v in value.items()}
        return value

    def _python_from_host(self, value: Any) -> Any:
        """Convert Python values into Tiny values.

        - Lists/tuples are turned into heap lists (pointer ints).
        - Dicts/sets/deques are converted recursively.
        - Other objects become an opaque proxy dict.
        """
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            converted: List[Any] = []
            for v in value:
                converted_val = self._python_from_host(v)
                if isinstance(v, int) and not isinstance(v, bool):
                    self._python_scalar_ints.add(v)
                converted.append(converted_val)
            with self.runtime._lock:  # type: ignore[attr-defined]
                if getattr(self.runtime, "next_ptr", 0) < 100000:
                    self.runtime.next_ptr = 100000
            ptr = self._to_pointer(converted)
            self._python_pointers.add(ptr)
            self.runtime.ptr_tags[ptr] = "PyList"
            return ptr
        if isinstance(value, tuple):
            converted: List[Any] = []
            for v in list(value):
                converted_val = self._python_from_host(v)
                if isinstance(v, int) and not isinstance(v, bool):
                    self._python_scalar_ints.add(v)
                converted.append(converted_val)
            with self.runtime._lock:  # type: ignore[attr-defined]
                if getattr(self.runtime, "next_ptr", 0) < 100000:
                    self.runtime.next_ptr = 100000
            ptr = self._to_pointer(converted)
            self._python_pointers.add(ptr)
            self.runtime.ptr_tags[ptr] = "PyList"
            return ptr
        if isinstance(value, dict):
            return {k: self._python_from_host(v) for k, v in value.items()}
        if isinstance(value, set):
            return {self._python_from_host(v) for v in value}
        if isinstance(value, deque):
            return deque(self._python_from_host(v) for v in value)
        # Fallback to an opaque proxy with identity semantics.
        return {"__py_object__": repr(value)}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def register_stdlib(
    runtime: "Runtime", env: "Environment", namespace_ref_cls: type | None = None
) -> None:
    """Register the TinyLanguage standard library into the given runtime/env.

    Parameters
    ----------
    runtime:
        The TinyLanguage runtime instance responsible for native registration,
        heap management, namespaces, and type instantiation.
    env:
        The top-level environment for the program execution (global scope).
    namespace_ref_cls:
        Optional `NamespaceRef` class. If not provided, imported lazily from
        `tiny_language` to avoid circular imports.
    """
    if namespace_ref_cls is None:
        from tiny_language import NamespaceRef  # Imported lazily to avoid circular imports

        namespace_ref_cls = NamespaceRef

    _StdLibRegistrar(runtime, env, namespace_ref_cls).install()
