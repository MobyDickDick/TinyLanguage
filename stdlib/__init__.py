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
        self.runtime.register_native("pow", self._math_pow, namespace="Math")
        self.runtime.register_native("sqrt", self._math_sqrt, namespace="Math")

        self.runtime.register_native("split", self._string_split, namespace="String")
        self.runtime.register_native("join", self._string_join, namespace="String")
        self.runtime.register_native("contains", self._string_contains, namespace="String")

        self.runtime.register_native("len", self._collections_len, namespace="Collections")
        self.runtime.register_native("push", self._collections_push, namespace="Collections")
        self.runtime.register_native("pop", self._collections_pop, namespace="Collections")

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

    def _math_abs(self, value: Any) -> Any:
        fields = self.runtime._number_fields(value)  # noqa: SLF001 - internal helper reuse
        if fields is not None:
            err = fields.get("error", "normal") or "normal"
            val = fields.get("value", 0)
            return self.runtime._make_number(abs(val), err)  # noqa: SLF001
        return abs(value)

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

    def _string_split(self, text: Any, sep: Any) -> int:
        return self._to_pointer(str(text).split(str(sep)))

    def _string_join(self, items: Any, sep: Any) -> str:
        seq = self._resolve_sequence(items)
        return str(sep).join(str(item) for item in seq)

    def _string_contains(self, text: Any, needle: Any) -> bool:
        return str(needle) in str(text)

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


def register_stdlib(
    runtime: "Runtime", env: "Environment", namespace_ref_cls: type | None = None
) -> None:
    if namespace_ref_cls is None:
        from tiny_language import NamespaceRef  # Imported lazily to avoid circular imports

        namespace_ref_cls = NamespaceRef

    _StdLibRegistrar(runtime, env, namespace_ref_cls).install()
