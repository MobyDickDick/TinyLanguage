from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Iterable, List

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

        self.runtime.register_native("abs", self._math_abs, namespace="Math")
        self.runtime.register_native("max", self._math_max, namespace="Math")
        self.runtime.register_native("min", self._math_min, namespace="Math")
        self.runtime.register_native("pow", self._math_pow, namespace="Math")
        self.runtime.register_native("clamp", self._math_clamp, namespace="Math")
        self.runtime.register_native("sqrt", self._math_sqrt, namespace="Math")

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

    def _ensure_namespace(self, name: str) -> None:
        if name not in self.env.values:
            self.env.values[name] = self.namespace_ref_cls(self.runtime, name)

    def _to_pointer(self, values: Iterable[Any]) -> int:
        items = list(values)
        ptr = self.runtime._Runtime__new(len(items))  # noqa: SLF001 - accessing private helper is intentional
        for idx, value in enumerate(items):
            self.runtime.heap_set(ptr, idx, value)
        return ptr

    def _resolve_sequence(self, target: Any) -> List[Any]:
        if isinstance(target, int) and target in self.runtime.heap:
            return self.runtime.heap[target]
        if isinstance(target, list):
            return target
        raise RuntimeError("collections operation expects a heap pointer or list")

    def _resolve_number(self, value: Any) -> tuple[Any, str | None]:
        fields = self.runtime._number_fields(value)  # noqa: SLF001 - internal helper reuse
        if fields is not None:
            return fields.get("value", 0), fields.get("error", "normal") or "normal"
        return value, None

    def _math_abs(self, value: Any) -> Any:
        fields = self.runtime._number_fields(value)  # noqa: SLF001 - internal helper reuse
        if fields is not None:
            err = fields.get("error", "normal") or "normal"
            val = fields.get("value", 0)
            return self.runtime._make_number(abs(val), err)  # noqa: SLF001
        return abs(value)

    def _math_max(self, left: Any, right: Any) -> Any:
        l_val, l_err = self._resolve_number(left)
        r_val, r_err = self._resolve_number(right)

        res = max(l_val, r_val)
        err = l_err or r_err or "normal"
        if l_err or r_err:
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return res

    def _math_min(self, left: Any, right: Any) -> Any:
        l_val, l_err = self._resolve_number(left)
        r_val, r_err = self._resolve_number(right)

        res = min(l_val, r_val)
        err = l_err or r_err or "normal"
        if l_err or r_err:
            return self.runtime._make_number(res, err)  # noqa: SLF001
        return res

    def _math_pow(self, base: Any, exponent: Any) -> Any:
        num_res = self.runtime._number_power(base, exponent)  # noqa: SLF001
        if num_res is not None:
            return num_res
        res = math.pow(base, exponent)
        if isinstance(res, float) and res.is_integer():
            res = int(res)
        return res

    def _math_sqrt(self, value: Any) -> Any:
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

    def _math_clamp(self, value: Any, lower: Any, upper: Any) -> Any:
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


def register_stdlib(
    runtime: "Runtime", env: "Environment", namespace_ref_cls: type | None = None
) -> None:
    if namespace_ref_cls is None:
        from tiny_language import NamespaceRef  # Imported lazily to avoid circular imports

        namespace_ref_cls = NamespaceRef

    _StdLibRegistrar(runtime, env, namespace_ref_cls).install()
