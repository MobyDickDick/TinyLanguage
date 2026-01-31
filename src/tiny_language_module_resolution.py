"""Shared helpers for resolving TinyLanguage module imports across backends."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from tiny_errors import SourcePos, SourceSpan, TinyLangError


@dataclass(frozen=True)
class ModuleResolutionConfig:
    """Configuration for locating TinyLanguage modules on disk."""

    search_paths: List[Path]
    stdlib_root: Path

    @classmethod
    def from_search_paths(cls, search_paths: Optional[List[Path]] = None) -> "ModuleResolutionConfig":
        """Build configuration using ``TINYPATH`` and sensible defaults."""
        env_paths = os.environ.get("TINYPATH", "")
        configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
        default_roots = [Path.cwd(), Path(__file__).parent]
        stdlib_root = Path(__file__).resolve().parents[1] / "stdlib"
        return cls(search_paths or configured_paths + default_roots, stdlib_root)


def resolve_module_name(raw: str, caller_namespace: Optional[str], pos: Optional[Any]) -> str:
    """Normalize relative import names against the caller's namespace."""
    pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
    leading = len(raw) - len(raw.lstrip("."))
    if leading == 0:
        return raw
    if not caller_namespace:
        raise TinyLangError(
            "relative import outside a module",
            pos_for_error or SourcePos.origin(),
            code="E008",
            span=pos if isinstance(pos, SourceSpan) else None,
        )
    base = caller_namespace.split(".")
    if leading > len(base):
        raise TinyLangError(
            "relative import traverses beyond module root",
            pos_for_error or SourcePos.origin(),
            code="E008",
            span=pos if isinstance(pos, SourceSpan) else None,
        )
    trimmed = base[: len(base) - leading]
    remainder = raw.lstrip(".")
    if remainder:
        trimmed.append(remainder)
    return ".".join(part for part in trimmed if part)


def candidate_module_paths(
    module_name: str,
    *,
    caller_path: Optional[Path],
    search_paths: List[Path],
    stdlib_root: Path,
) -> List[Path]:
    """Return possible filesystem paths for a module name."""
    candidates: List[Path] = []
    roots: List[Path] = []
    if module_name.startswith("stdlib."):
        rel_path = Path(*module_name.split(".")[1:])
        if stdlib_root.exists():
            roots.append(stdlib_root)
    else:
        rel_path = Path(*module_name.split("."))
        if caller_path:
            roots.append(caller_path.parent)
        roots.extend(search_paths)
    for root in roots:
        candidates.append((root / rel_path).with_suffix(".tiny"))
    return candidates
