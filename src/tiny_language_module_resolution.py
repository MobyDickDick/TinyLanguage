"""Shared helpers for resolving TinyLanguage module imports across backends."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urlparse

from tiny_errors import SourcePos, SourceSpan, TinyLangError

if importlib.util.find_spec("tomllib"):
    import tomllib
else:
    import tomli as tomllib


@dataclass(frozen=True)
class ModuleResolutionConfig:
    """Configuration for locating TinyLanguage modules on disk."""

    search_paths: List[Path]
    stdlib_root: Path
    project_root: Optional[Path]

    @classmethod
    def from_search_paths(
        cls,
        search_paths: Optional[List[Path]] = None,
        *,
        start_path: Optional[Path] = None,
    ) -> "ModuleResolutionConfig":
        """Build configuration using ``TINYPATH`` and sensible defaults."""
        env_paths = os.environ.get("TINYPATH", "")
        configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
        default_roots = [Path.cwd(), Path(__file__).parent]
        stdlib_root = Path(__file__).resolve().parents[1] / "stdlib"
        roots = search_paths or configured_paths + default_roots
        project_root = _find_project_root(start_path or Path.cwd())
        return cls(roots, stdlib_root, project_root)


def _find_project_root(start_path: Path) -> Optional[Path]:
    current = start_path if start_path.is_dir() else start_path.parent
    for candidate in [current, *current.parents]:
        if (candidate / "tiny.toml").is_file():
            return candidate
        if (candidate / "tiny.lock").is_file():
            return candidate
        if (candidate / "vendor").is_dir():
            return candidate
    return None


def _lockfile_entries(lock_path: Path) -> list[dict[str, Any]]:
    if not lock_path.is_file():
        return []
    lock_data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        entries.extend(lock_data.get(section, []))
    return entries


def _registry_host(registry: Optional[str]) -> str:
    if not registry:
        return "registry"
    parsed = urlparse(registry)
    host = parsed.netloc or parsed.path
    host = host.strip("/").replace(":", "_")
    return host or "registry"


def _pkg_module_rel_paths(parts: list[str]) -> list[Path]:
    if not parts:
        return []
    if len(parts) == 1:
        package_name = parts[0]
        return [Path("__init__"), Path(package_name)]
    return [Path(*parts[1:])]


def _package_roots_for(
    package_name: str,
    *,
    project_root: Optional[Path],
) -> list[Path]:
    if not project_root:
        return []
    lock_path = project_root / "tiny.lock"
    entries = _lockfile_entries(lock_path)
    vendor_root = project_root / "vendor"
    roots: list[Path] = []
    for entry in entries:
        if entry.get("name") != package_name:
            continue
        source = entry.get("source")
        version = str(entry.get("version") or "0.0.0")
        if source == "path":
            if vendor_root.is_dir():
                candidate = vendor_root / "local" / package_name / version
                if candidate.exists():
                    roots.append(candidate)
                    continue
            path_value = entry.get("path")
            if path_value:
                roots.append((project_root / str(path_value)).resolve())
        elif source == "registry":
            if vendor_root.is_dir():
                host = _registry_host(entry.get("registry"))
                roots.append(vendor_root / host / package_name / version)
        elif source == "git":
            if vendor_root.is_dir():
                roots.append(vendor_root / "git" / package_name / version)
    return roots


def _fallback_pkg_candidates(
    module_name: str,
    *,
    caller_path: Optional[Path],
    search_paths: List[Path],
) -> list[Path]:
    rel_path = Path(*module_name.split("."))
    roots: list[Path] = []
    if caller_path:
        roots.append(caller_path.parent)
    roots.extend(search_paths)
    return _expand_module_candidates(rel_path, roots)


def _expand_module_candidates(rel_path: Path, roots: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for root in roots:
        candidates.append((root / rel_path).with_suffix(".tiny"))
        if rel_path.name != "__init__":
            candidates.append(root / rel_path / "__init__.tiny")
    return candidates


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
    config: ModuleResolutionConfig,
) -> List[Path]:
    """Return possible filesystem paths for a module name."""
    if module_name.startswith(("stdlib.", "std.")):
        rel_path = Path(*module_name.split(".")[1:])
        if config.stdlib_root.exists():
            return _expand_module_candidates(rel_path, [config.stdlib_root])
        return []
    if module_name.startswith("pkg."):
        parts = module_name.split(".")[1:]
        if not parts:
            return []
        package_name = parts[0]
        project_root = config.project_root or _find_project_root(caller_path or Path.cwd())
        package_roots = _package_roots_for(package_name, project_root=project_root)
        module_rel_paths = _pkg_module_rel_paths(parts)
        if package_roots and module_rel_paths:
            candidates: List[Path] = []
            for package_root in package_roots:
                for base in (package_root / "src", package_root):
                    for rel in module_rel_paths:
                        candidates.extend(_expand_module_candidates(rel, [base]))
            return candidates
        return _fallback_pkg_candidates(
            module_name,
            caller_path=caller_path,
            search_paths=config.search_paths,
        )
    rel_path = Path(*module_name.split("."))
    roots: List[Path] = []
    if caller_path:
        roots.append(caller_path.parent)
    roots.extend(config.search_paths)
    return _expand_module_candidates(rel_path, roots)
