from __future__ import annotations

import json
import math
import random
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from tiny_language import Environment, NamespaceRef, Runtime


class _StdLibRegistrar:
    def __init__(self, runtime: "Runtime", env: "Environment", namespace_ref_cls: type):
        self.runtime = runtime
        self.env = env
        self.namespace_ref_cls = namespace_ref_cls

    def install(self) -> None:
        self._ensure_namespace("Math")
        self._ensure_namespace("String")
        self._ensure_namespace("Collections")
        self._ensure_namespace("Map")
        self._ensure_namespace("Set")
        self._ensure_namespace("Deque")
        self._ensure_namespace("Random")
        self._ensure_namespace("File")
        self._ensure_namespace("JSON")
        self._ensure_namespace("Async")

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

        self.runtime.register_native("split", self._string_split, namespace="String")
        self.runtime.register_native("join", self._string_join, namespace="String")
        self.runtime.register_native("contains", self._string_contains, namespace="String")
        self.runtime.register_native("upper", self._string_upper, namespace="String")
        self.runtime.register_native("lower", self._string_lower, namespace="String")
        self.runtime.register_native("trim", self._string_trim, namespace="String")
        self.runtime.register_native("repeat", self._string_repeat, namespace="String")

        self.runtime.register_native("len", self._collections_len, namespace="Collections")
        self.runtime.register_native("push", self._collections_push, namespace="Collections")
        self.runtime.register_native("pop", self._collections_pop, namespace="Collections")
        self.runtime.register_native("slice", self._collections_slice, namespace="Collections")
        self.runtime.register_native("contains", self._collections_contains, namespace="Collections")

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

        self.runtime.register_native("new", self._set_new, namespace="Set")
        self.runtime.register_native("from_list", self._set_from_list, namespace="Set")
        self.runtime.register_native("len", self._set_len, namespace="Set")
        self.runtime.register_native("add", self._set_add, namespace="Set")
        self.runtime.register_native("delete", self._set_delete, namespace="Set")
        self.runtime.register_native("has", self._set_has, namespace="Set")
        self.runtime.register_native("to_list", self._set_to_list, namespace="Set")

        self.runtime.register_native("new", self._deque_new, namespace="Deque")
        self.runtime.register_native("len", self._deque_len, namespace="Deque")
        self.runtime.register_native("push_left", self._deque_push_left, namespace="Deque")
        self.runtime.register_native("push_right", self._deque_push_right, namespace="Deque")
        self.runtime.register_native("pop_left", self._deque_pop_left, namespace="Deque")
        self.runtime.register_native("pop_right", self._deque_pop_right, namespace="Deque")
        self.runtime.register_native("peek_left", self._deque_peek_left, namespace="Deque")
        self.runtime.register_native("peek_right", self._deque_peek_right, namespace="Deque")
        self.runtime.register_native("to_list", self._deque_to_list, namespace="Deque")

        self.runtime.register_native("random", self._random_random, namespace="Random")
        self.runtime.register_native("randint", self._random_randint, namespace="Random")
        self.runtime.register_native("choice", self._random_choice, namespace="Random")
        self.runtime.register_native("shuffle", self._random_shuffle, namespace="Random")

        self.runtime.register_native("read", self._file_read, namespace="File")
        self.runtime.register_native("write", self._file_write, namespace="File")
        self.runtime.register_native("exists", self._file_exists, namespace="File")
        self.runtime.register_native("remove", self._file_remove, namespace="File")

        self.runtime.register_native("parse", self._json_parse, namespace="JSON")
        self.runtime.register_native("stringify", self._json_stringify, namespace="JSON")

        self.runtime.register_native("token", self._async_token, namespace="Async")
        self.runtime.register_native("cancel", self._async_cancel, namespace="Async")
        self.runtime.register_native("is_cancelled", self._async_is_cancelled, namespace="Async")
        self.runtime.register_native("reason", self._async_reason, namespace="Async")
        self.runtime.register_native("link", self._async_link, namespace="Async")

    def _ensure_namespace(self, name: str) -> None:
        if name not in self.env.values:
            self.env.values[name] = self.namespace_ref_cls(self.runtime, name)

    def _to_pointer(self, values: Iterable[Any]) -> int:
        items = list(values)
        ptr = self.runtime._Runtime__new(len(items))  # noqa: SLF001 - accessing private helper is intentional
        for idx, value in enumerate(items):
            self.runtime.heap_set(ptr, idx, value)
        return ptr

    def _alloc_heap(self, value: Any) -> int:
        ptr = self.runtime._Runtime__new(0)  # noqa: SLF001 - intentional reuse of private helper
        with self.runtime._lock:  # type: ignore[attr-defined]
            self.runtime.heap[ptr] = value
        return ptr

    def _resolve_sequence(self, target: Any) -> List[Any]:
        if isinstance(target, int) and target in self.runtime.heap:
            return self.runtime.heap[target]
        if isinstance(target, list):
            return target
        raise RuntimeError("collections operation expects a heap pointer or list")

    def _resolve_map(self, target: Any) -> Dict[Any, Any]:
        if isinstance(target, int) and target in self.runtime.heap:
            maybe = self.runtime.heap[target]
            if isinstance(maybe, dict):
                return maybe
        if isinstance(target, dict):
            return target
        raise RuntimeError("map operation expects a heap pointer or dict")

    def _resolve_set(self, target: Any) -> set:
        if isinstance(target, int) and target in self.runtime.heap:
            maybe = self.runtime.heap[target]
            if isinstance(maybe, set):
                return maybe
        if isinstance(target, set):
            return target
        raise RuntimeError("set operation expects a heap pointer or set")

    def _resolve_deque(self, target: Any) -> deque:
        if isinstance(target, int) and target in self.runtime.heap:
            maybe = self.runtime.heap[target]
            if isinstance(maybe, deque):
                return maybe
        if isinstance(target, deque):
            return target
        raise RuntimeError("deque operation expects a heap pointer or deque")

    def _resolve_number(self, value: Any) -> tuple[Any, str | None]:
        fields = self.runtime._number_fields(value)  # noqa: SLF001 - internal helper reuse
        if fields is not None:
            return fields.get("value", 0), fields.get("error", "normal") or "normal"
        return value, None

    def _resolve_intervall(self, value: Any) -> tuple[Any, Any, str | None] | None:
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
            val = num_fields.get("value", 0)
            return val, val, "normal"

        if isinstance(value, (int, float)):
            return value, value, "normal"

        return None

    def _math_abs(self, value: Any) -> Any:
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
            res = round(num_fields.get("value", 0), places) if places is not None else round(num_fields.get("value", 0))
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return round(value, places) if places is not None else round(value)

    def _math_floor(self, value: Any) -> Any:
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

    def _string_split(self, text: Any, sep: Any) -> int:
        return self._to_pointer(str(text).split(str(sep)))

    def _string_join(self, items: Any, sep: Any) -> str:
        seq = self._resolve_sequence(items)
        return str(sep).join(str(item) for item in seq)

    def _string_contains(self, text: Any, needle: Any) -> bool:
        return str(needle) in str(text)

    def _string_upper(self, text: Any) -> str:
        return str(text).upper()

    def _string_lower(self, text: Any) -> str:
        return str(text).lower()

    def _string_trim(self, text: Any) -> str:
        return str(text).strip()

    def _string_repeat(self, text: Any, count: Any) -> str:
        try:
            times = int(count)
        except Exception:
            raise RuntimeError("repeat expects an integer count")
        if times < 0:
            raise RuntimeError("repeat count must be non-negative")
        return str(text) * times

    def _collections_len(self, target: Any) -> int:
        try:
            if isinstance(target, int) and target in self.runtime.heap:
                return len(self.runtime.heap[target])
            return len(target)  # type: ignore[arg-type]
        except Exception:
            raise RuntimeError("len expects a sized value")

    def _collections_push(self, target: Any, value: Any) -> int:
        seq = self._resolve_sequence(target)
        seq.append(value)
        return len(seq)

    def _collections_pop(self, target: Any) -> Any:
        seq = self._resolve_sequence(target)
        if not seq:
            raise RuntimeError("pop from empty collection")
        return seq.pop()

    def _collections_slice(self, target: Any, start: Any, end: Any) -> int:
        seq = self._resolve_sequence(target)
        try:
            start_idx = int(start)
            end_idx = int(end)
        except Exception:
            raise RuntimeError("slice expects integer start and end")
        return self._to_pointer(seq[start_idx:end_idx])

    def _collections_contains(self, target: Any, value: Any) -> bool:
        seq = self._resolve_sequence(target)
        return value in seq

    def _map_new(self) -> int:
        return self._alloc_heap({})

    def _map_from_entries(self, entries: Any) -> int:
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

    def _random_random(self) -> float:
        return random.random()

    def _random_randint(self, lower: Any, upper: Any) -> int:
        try:
            lo = int(lower)
            hi = int(upper)
        except Exception:
            raise RuntimeError("randint expects integer bounds")
        return random.randint(lo, hi)

    def _random_choice(self, values: Any) -> Any:
        seq = self._resolve_sequence(values)
        if not seq:
            raise RuntimeError("choice expects a non-empty sequence")
        return random.choice(seq)

    def _random_shuffle(self, values: Any) -> int:
        seq = self._resolve_sequence(values)
        random.shuffle(seq)
        return len(seq)

    def _coerce_path(self, path: Any) -> Path:
        path_str = str(path)
        # Normalize platform-specific separators that may appear inside TinyLanguage
        # string literals (especially on Windows where backslashes are common and can
        # be interpreted as escape sequences by editors).
        path_str = path_str.replace("\\", "/")
        return Path(path_str)

    def _file_read(self, path: Any) -> str:
        text_path = self._coerce_path(path)
        if not text_path.exists():
            raise RuntimeError(f"file does not exist: {text_path}")
        return text_path.read_text(encoding="utf-8")

    def _file_write(self, path: Any, content: Any) -> bool:
        text_path = self._coerce_path(path)
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(str(content), encoding="utf-8")
        return True

    def _file_exists(self, path: Any) -> bool:
        return self._coerce_path(path).exists()

    def _file_remove(self, path: Any) -> bool:
        text_path = self._coerce_path(path)
        if not text_path.exists():
            return False
        text_path.unlink()
        return True

    def _json_parse(self, text: Any) -> Any:
        try:
            loaded = json.loads(str(text))
        except Exception as exc:
            raise RuntimeError(f"invalid json: {exc}")
        return self._json_to_value(loaded)

    def _json_to_value(self, data: Any) -> Any:
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

    def _async_token(self) -> Any:
        return self.runtime.make_cancellation_token()

    def _async_cancel(self, token: Any, reason: Any | None = None) -> bool:
        text = None if reason is None else str(reason)
        return self.runtime.cancel_token(token, text)

    def _async_is_cancelled(self, token: Any) -> bool:
        return self.runtime.token_cancelled(token)

    def _async_reason(self, token: Any) -> Any:
        return self.runtime.token_reason(token)

    def _async_link(self, token: Any, handle: Any) -> bool:
        return self.runtime.link_token(token, handle)


def register_stdlib(
    runtime: "Runtime", env: "Environment", namespace_ref_cls: type | None = None
) -> None:
    if namespace_ref_cls is None:
        from tiny_language import NamespaceRef  # Imported lazily to avoid circular imports

        namespace_ref_cls = NamespaceRef

    _StdLibRegistrar(runtime, env, namespace_ref_cls).install()
