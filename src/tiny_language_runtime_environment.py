"""Runtime environment storage for TinyLanguage evaluation scopes."""

from typing import Any, Dict, Optional, Union

from tiny_errors import SourcePos, SourceSpan


class Environment:
    """Lexical scope storage for values and inferred types."""

    def __init__(
        self, parent: Optional["Environment"], namespace: Optional[str] = None, runtime: Optional["Runtime"] = None
    ):
        self.parent = parent  # Outer lexical scope (if any)
        self.namespace = namespace  # Module/namespace name for namespacing lookups
        self.runtime = runtime or (parent.runtime if parent else None)
        self.values: Dict[str, Any] = {}  # Local symbol table
        self.types: Dict[str, str] = {}

    @staticmethod
    def _fallback_type_name(value: Any) -> str:
        if isinstance(value, dict) and "__type__" in value:
            return str(value.get("__type__"))
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

    @staticmethod
    def _normalize_numeric_type(type_name: str) -> str:
        normalized = type_name.strip()
        lowered = normalized.lower()
        if lowered in {"int", "float"}:
            return "number"
        return type_name

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise RuntimeError(f"unknown variable {name}")

    def define(self, name: str, value: Any, pos: Union[SourcePos, SourceSpan]) -> None:
        if self.runtime:
            inferred = self.runtime._infer_type_name(value)
            self.types[name] = self._normalize_numeric_type(inferred)
        else:
            self.types[name] = self._fallback_type_name(value)
        self.values[name] = value

    def assign(self, name: str, value: Any, pos: Union[SourcePos, SourceSpan]) -> None:
        if name in self.values:
            if self.runtime:
                self.runtime._check_assignment_type(self, name, value, pos, local_only=True)
                inferred = self.runtime._infer_type_name(value)
                self.types[name] = self._normalize_numeric_type(inferred)
            else:
                self.types[name] = self._fallback_type_name(value)
            self.values[name] = value
        elif self.parent is not None:
            self.parent.assign(name, value, pos)
        else:
            self.define(name, value, pos)

    def set(self, name: str, value: Any) -> None:
        """Compatibility setter used by generated Python backend code.

        This mirrors assignment semantics: update an existing binding in the
        nearest lexical scope, or define a new binding if the name is not
        present yet.
        """

        self.assign(name, value, SourcePos.origin())

    def contains(self, name: str) -> bool:
        if name in self.values:
            return True
        if self.parent is not None:
            return self.parent.contains(name)
        return False

    def type_of(self, name: str, *, local_only: bool = False) -> Optional[str]:
        if name in self.types:
            return self.types[name]
        if not local_only and self.parent is not None:
            return self.parent.type_of(name)
        return None

    def all_names(self) -> list[str]:
        names = list(self.values.keys())
        if self.parent:
            names.extend(self.parent.all_names())
        return names
