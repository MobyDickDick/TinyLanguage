"""Resolve TinyLanguage package dependencies and persist a lockfile.

This module provides a minimal dependency resolver that reads ``tiny.toml``,
applies SemVer constraints, and writes a deterministic ``tiny.lock``. It does
not download packages; instead it relies on local registry indexes or exact
version constraints to select versions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Mapping

if importlib.util.find_spec("tomllib"):
    tomllib = importlib.import_module("tomllib")
else:
    tomllib = importlib.import_module("tomli")


_SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


@dataclass(frozen=True, order=True)
class SemVer:
    """Simple SemVer representation restricted to MAJOR.MINOR.PATCH."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        match = _SEMVER_PATTERN.match(value.strip())
        if not match:
            raise ValueError(f"Invalid SemVer string: {value}")
        major, minor, patch = (int(part) for part in match.groups())
        return cls(major=major, minor=minor, patch=patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class VersionRange:
    """Closed-open SemVer range: [lower, upper)."""

    lower: SemVer
    upper: SemVer | None

    def contains(self, version: SemVer) -> bool:
        if version < self.lower:
            return False
        if self.upper is None:
            return True
        return version < self.upper


@dataclass(frozen=True)
class VersionConstraint:
    """Parsed SemVer constraint supporting exact, caret, tilde, and comparators."""

    ranges: tuple[VersionRange, ...]
    exact: SemVer | None = None

    def matches(self, version: SemVer) -> bool:
        if self.exact is not None:
            return version == self.exact
        return all(range_.contains(version) for range_ in self.ranges)


@dataclass(frozen=True)
class ResolvedDependency:
    """Resolved dependency entry for the lockfile."""

    name: str
    version: str
    source: str
    checksum: str
    registry: str | None = None
    registry_checksum: str | None = None
    path: str | None = None
    url: str | None = None
    rev: str | None = None
    tag: str | None = None


def _parse_constraint(constraint: str) -> VersionConstraint:
    constraint = constraint.strip()
    if not constraint or constraint == "*":
        return VersionConstraint(ranges=())
    if constraint.startswith("^"):
        base = SemVer.parse(_normalize_version(constraint[1:]))
        upper = _caret_upper_bound(base)
        return VersionConstraint(ranges=(VersionRange(base, upper),))
    if constraint.startswith("~"):
        base = SemVer.parse(_normalize_version(constraint[1:]))
        upper = SemVer(base.major, base.minor + 1, 0)
        return VersionConstraint(ranges=(VersionRange(base, upper),))
    if constraint.startswith((">=", "<=", ">", "<")):
        return VersionConstraint(ranges=_parse_comparators(constraint))
    if " " in constraint:
        return VersionConstraint(ranges=_parse_comparators(constraint))
    exact = SemVer.parse(_normalize_version(constraint))
    return VersionConstraint(ranges=(), exact=exact)


def _normalize_version(value: str) -> str:
    parts = value.strip().split(".")
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:3])


def _caret_upper_bound(base: SemVer) -> SemVer:
    if base.major != 0:
        return SemVer(base.major + 1, 0, 0)
    if base.minor != 0:
        return SemVer(0, base.minor + 1, 0)
    return SemVer(0, 0, base.patch + 1)


def _parse_comparators(raw: str) -> tuple[VersionRange, ...]:
    ranges: list[VersionRange] = []
    tokens = raw.split()
    for token in tokens:
        if token.startswith(">="):
            version = SemVer.parse(_normalize_version(token[2:]))
            ranges.append(VersionRange(version, None))
        elif token.startswith(">"):
            version = SemVer.parse(_normalize_version(token[1:]))
            ranges.append(VersionRange(SemVer(version.major, version.minor, version.patch + 1), None))
        elif token.startswith("<="):
            version = SemVer.parse(_normalize_version(token[2:]))
            upper = SemVer(version.major, version.minor, version.patch + 1)
            ranges.append(VersionRange(SemVer(0, 0, 0), upper))
        elif token.startswith("<"):
            version = SemVer.parse(_normalize_version(token[1:]))
            ranges.append(VersionRange(SemVer(0, 0, 0), version))
        else:
            raise ValueError(f"Unsupported constraint token: {token}")
    return tuple(ranges)


def _manifest_hash(manifest_text: str) -> str:
    normalized = manifest_text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def manifest_hash_for_path(manifest_path: Path) -> str:
    """Return the canonical manifest hash used by lockfile entries."""
    manifest_text = manifest_path.read_text(encoding="utf-8")
    return _manifest_hash(manifest_text)


def _hash_directory(path: Path) -> str:
    hasher = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        relative = file_path.relative_to(path).as_posix()
        hasher.update(relative.encode("utf-8"))
        hasher.update(file_path.read_bytes())
    return hasher.hexdigest()


def _hash_string(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_registry_index(registry_url: str, manifest_dir: Path) -> Mapping[str, Mapping[str, Mapping[str, str]]]:
    index_path = _resolve_registry_index_path(registry_url, manifest_dir)
    if index_path is None or not index_path.is_file():
        return {}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if "packages" in data and isinstance(data["packages"], dict):
        packages = data["packages"]
    else:
        packages = data
    normalized: dict[str, dict[str, dict[str, str]]] = {}
    for name, versions in packages.items():
        if isinstance(versions, dict) and "versions" in versions:
            versions = versions["versions"]
        if isinstance(versions, dict):
            normalized[name] = {
                version: entry if isinstance(entry, dict) else {"checksum": str(entry)}
                for version, entry in versions.items()
            }
    return normalized


def _resolve_registry_index_path(registry_url: str, manifest_dir: Path) -> Path | None:
    env_path = Path.cwd() / "tiny_registry.json"
    if env_path.is_file():
        return env_path
    if registry_url.startswith("file://"):
        return Path(registry_url[len("file://") :])
    candidate = manifest_dir / registry_url
    if candidate.is_file():
        return candidate
    if Path(registry_url).is_file():
        return Path(registry_url)
    return None


def _read_manifest(manifest_path: Path) -> tuple[dict, str]:
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_data = tomllib.loads(manifest_text)
    return manifest_data, manifest_text


def _select_registry_version(
    name: str,
    constraint: VersionConstraint,
    registry_index: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> tuple[str, str | None]:
    versions = registry_index.get(name, {})
    candidates: list[SemVer] = []
    for version in versions:
        try:
            parsed = SemVer.parse(version)
        except ValueError:
            continue
        if constraint.matches(parsed):
            candidates.append(parsed)
    if not candidates:
        if constraint.exact is not None:
            version = str(constraint.exact)
            return version, None
        raise SystemExit(f"No registry versions found for {name} matching constraint.")
    best = max(candidates)
    entry = versions.get(str(best), {})
    checksum = entry.get("checksum")
    return str(best), checksum


def _resolve_path_version(path: Path, declared_version: str | None) -> str:
    if declared_version:
        return str(SemVer.parse(_normalize_version(declared_version)))
    manifest_path = path / "tiny.toml"
    if manifest_path.is_file():
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        version = manifest.get("package", {}).get("version")
        if version:
            return str(SemVer.parse(_normalize_version(version)))
    return "0.0.0"


def _parse_dependency_entry(name: str, value: object) -> dict[str, object]:
    if isinstance(value, str):
        return {"version": value}
    if isinstance(value, dict):
        return dict(value)
    raise SystemExit(f"Unsupported dependency format for {name}.")


def _normalize_manifest_path(value: str) -> str:
    """Normalize manifest path values to a stable, cross-platform form."""
    return str(Path(value.replace("\\", "/")).as_posix())


def resolve_manifest(
    manifest_path: Path,
) -> tuple[dict[str, list[ResolvedDependency]], str, str | None]:
    manifest, manifest_text = _read_manifest(manifest_path)
    manifest_dir = manifest_path.parent
    registries = manifest.get("registries", {})
    default_registry = registries.get("default")
    registry_indexes: dict[str, Mapping[str, Mapping[str, Mapping[str, str]]]] = {}
    if default_registry:
        registry_indexes[default_registry] = _load_registry_index(default_registry, manifest_dir)
    sections = ("dependencies", "dev-dependencies", "build-dependencies")
    overrides = manifest.get("dependency-overrides", {})
    resolved: dict[str, list[ResolvedDependency]] = {section: [] for section in sections}
    for section in sections:
        deps = manifest.get(section, {})
        for name in sorted(deps):
            value = deps[name]
            entry = _parse_dependency_entry(name, value)
            override = overrides.get(name)
            if isinstance(override, dict) and "path" in override:
                override_manifest_path = _normalize_manifest_path(str(override["path"]))
                override_path = (manifest_dir / override_manifest_path).resolve()
                if override_path.exists():
                    entry = {"path": override_manifest_path, "version": entry.get("version")}
            if "path" in entry:
                entry_path = _normalize_manifest_path(str(entry["path"]))
                path = (manifest_dir / entry_path).resolve()
                if not path.exists():
                    raise SystemExit(f"Dependency path does not exist for {name}: {path}")
                version = _resolve_path_version(path, entry.get("version"))
                checksum = _hash_directory(path)
                resolved[section].append(
                    ResolvedDependency(
                        name=name,
                        version=version,
                        source="path",
                        checksum=checksum,
                        path=entry_path,
                    )
                )
                continue
            if "git" in entry:
                git_spec = entry["git"]
                if isinstance(git_spec, dict):
                    url = git_spec.get("url")
                    rev = git_spec.get("rev")
                    tag = git_spec.get("tag")
                else:
                    url = git_spec
                    rev = entry.get("rev")
                    tag = entry.get("tag")
                if not url:
                    raise SystemExit(f"Git dependency {name} missing url.")
                version = entry.get("version") or "0.0.0"
                checksum = _hash_string(f"git:{url}@{rev or tag or 'HEAD'}")
                resolved[section].append(
                    ResolvedDependency(
                        name=name,
                        version=str(SemVer.parse(_normalize_version(version))),
                        source="git",
                        checksum=checksum,
                        url=str(url),
                        rev=rev,
                        tag=tag,
                    )
                )
                continue
            constraint_value = entry.get("version", "*")
            constraint = _parse_constraint(str(constraint_value))
            registry = entry.get("registry") or default_registry
            registry_index = registry_indexes.get(registry, {})
            version, registry_checksum = _select_registry_version(name, constraint, registry_index)
            checksum = registry_checksum or _hash_string(f"{name}@{version}")
            resolved[section].append(
                ResolvedDependency(
                    name=name,
                    version=version,
                    source="registry",
                    checksum=checksum,
                    registry=registry,
                    registry_checksum=registry_checksum,
                )
            )
    return resolved, _manifest_hash(manifest_text), default_registry


def write_lockfile(lock_path: Path, manifest_path: Path) -> Path:
    resolved, manifest_hash, default_registry = resolve_manifest(manifest_path)
    lines: list[str] = [
        "lockfile_version = 1",
        f'manifest_hash = "{manifest_hash}"',
    ]
    if default_registry:
        lines.append(f'registry = "{default_registry}"')
    for section, deps in resolved.items():
        for dep in deps:
            lines.append("")
            lines.append(f"[[{section}]]")
            lines.append(f'name = "{dep.name}"')
            lines.append(f'version = "{dep.version}"')
            lines.append(f'source = "{dep.source}"')
            lines.append(f'checksum = "{dep.checksum}"')
            if dep.registry:
                lines.append(f'registry = "{dep.registry}"')
            if dep.registry_checksum:
                lines.append(f'registry_checksum = "{dep.registry_checksum}"')
            if dep.path:
                lines.append(f'path = "{dep.path}"')
            if dep.url:
                lines.append(f'url = "{dep.url}"')
            if dep.rev:
                lines.append(f'rev = "{dep.rev}"')
            if dep.tag:
                lines.append(f'tag = "{dep.tag}"')
    lock_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return lock_path
