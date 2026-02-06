"""CLI utilities for the TinyLanguage package manager workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tomllib
from typing import Any, Iterable
from urllib.parse import urlparse
from urllib.request import urlopen

from tiny_pkg_resolution import write_lockfile


_DEFAULT_TEMPLATE = """\
[package]
name = "your-package-name"
version = "0.1.0"
description = "One-line summary of the package."
license = "MIT"
authors = ["Your Name <you@example.com>"]
homepage = "https://example.com"
repository = "https://github.com/your-org/your-package-name"

[dependencies]
# Example versioned dependency:
# http = "^1.2"
# Example local path dependency:
# config = { path = "../config" }
# Example registry override:
# json = { version = "~0.9", registry = "https://registry.tiny-lang.org" }

[dev-dependencies]
# test-utils = "^0.3"

[build-dependencies]
# codegen = { version = ">=1.0 <2.0" }

[registries]
default = "https://registry.tiny-lang.org"
"""


def _load_template() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    template_path = repo_root / "docs" / "tiny_pkg_init_template.toml"
    if template_path.is_file():
        return template_path.read_text(encoding="utf-8")
    return _DEFAULT_TEMPLATE


def _write_manifest_template(target: Path, *, force: bool) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / "tiny.toml"
    if manifest_path.exists() and not force:
        raise SystemExit(f"Refusing to overwrite existing manifest: {manifest_path}")
    manifest_path.write_text(_load_template(), encoding="utf-8")
    return manifest_path


def _read_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise SystemExit(f"Missing manifest: {manifest_path}")
    return tomllib.loads(manifest_path.read_text(encoding="utf-8"))


def _format_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return _format_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(
            f"{key} = {_format_value(item_value)}" for key, item_value in value.items()
        )
        return "{ " + items + " }"
    return _format_string(str(value))


def _iter_section_items(section: str, table: dict[str, Any]) -> Iterable[tuple[str, Any]]:
    if section in {"dependencies", "dev-dependencies", "build-dependencies", "dependency-overrides"}:
        for key in sorted(table):
            yield key, table[key]
    else:
        for key, value in table.items():
            yield key, value


def _serialize_manifest(manifest: dict[str, Any]) -> str:
    ordered_sections = [
        "package",
        "dependencies",
        "dev-dependencies",
        "build-dependencies",
        "dependency-overrides",
        "registries",
    ]
    extra_sections = [key for key in manifest.keys() if key not in ordered_sections]
    lines: list[str] = []

    def emit_table(name: str, table: dict[str, Any]) -> None:
        lines.append(f"[{name}]")
        for key, value in _iter_section_items(name, table):
            if name == "package" and key == "template" and isinstance(value, dict):
                continue
            lines.append(f"{key} = {_format_value(value)}")
        if name == "package" and isinstance(table.get("template"), dict):
            lines.append("")
            lines.append("[package.template]")
            for key, value in _iter_section_items("package.template", table["template"]):
                lines.append(f"{key} = {_format_value(value)}")

    for section in ordered_sections + extra_sections:
        table = manifest.get(section)
        if not isinstance(table, dict):
            if table is None:
                continue
            lines.append(f"{section} = {_format_value(table)}")
            lines.append("")
            continue
        emit_table(section, table)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_manifest(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest_path.write_text(_serialize_manifest(manifest), encoding="utf-8")


def _parse_dependency_spec(spec: str) -> tuple[str, str | None]:
    if "@" not in spec:
        return spec, None
    name, constraint = spec.split("@", 1)
    if not name:
        raise SystemExit(f"Invalid dependency spec: {spec}")
    return name, constraint or None


def _lockfile_entries(lock_path: Path) -> list[dict[str, Any]]:
    if not lock_path.is_file():
        raise SystemExit(f"Missing lockfile: {lock_path}")
    lock_data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        entries.extend(lock_data.get(section, []))
    return entries


def _registry_host(registry: str | None) -> str:
    if not registry:
        return "registry"
    parsed = urlparse(registry)
    host = parsed.netloc or parsed.path
    host = host.strip("/").replace(":", "_")
    return host or "registry"


def _load_registry_index(registry_url: str, manifest_dir: Path) -> dict[str, Any]:
    env_path = manifest_dir / "tiny_registry.json"
    if env_path.is_file():
        return json.loads(env_path.read_text(encoding="utf-8"))
    if registry_url.startswith("file://"):
        return json.loads(Path(registry_url[len("file://") :]).read_text(encoding="utf-8"))
    candidate = manifest_dir / registry_url
    if candidate.is_file():
        return json.loads(candidate.read_text(encoding="utf-8"))
    if Path(registry_url).is_file():
        return json.loads(Path(registry_url).read_text(encoding="utf-8"))
    return {}


def _lookup_registry_dist(
    index: dict[str, Any],
    name: str,
    version: str,
) -> tuple[str | None, str | None]:
    packages = index.get("packages") if isinstance(index.get("packages"), dict) else index
    if not isinstance(packages, dict):
        return None, None
    entry = packages.get(name, {})
    versions = entry.get("versions") if isinstance(entry, dict) and "versions" in entry else entry
    if not isinstance(versions, dict):
        return None, None
    metadata = versions.get(version, {})
    if isinstance(metadata, dict):
        dist = metadata.get("dist") or metadata.get("path")
        checksum = metadata.get("sha256") or metadata.get("checksum")
        return dist, checksum
    if isinstance(metadata, str):
        return metadata, None
    return None, None


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    dest_path = dest.resolve()
    for member in tar.getmembers():
        target = dest_path / member.name
        if not str(target.resolve()).startswith(str(dest_path)):
            raise SystemExit(f"Refusing to extract unsafe archive member: {member.name}")
    tar.extractall(dest_path)


def _copy_tree(source: Path, dest: Path, *, force: bool) -> None:
    ignore = shutil.ignore_patterns(".git", "__pycache__", ".tiny-cache", "build", ".venv")
    if dest.exists():
        if not force:
            raise SystemExit(f"Destination already exists: {dest}")
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=ignore)


def _normalize_checksum(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.startswith("sha256:"):
        value = value.split(":", 1)[1]
    return value or None


def _checksum_matches(path: Path, checksum: str | None) -> bool:
    normalized = _normalize_checksum(checksum)
    if not normalized:
        return True
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == normalized


def _download_to_cache(url: str, cache_path: Path, *, checksum: str | None) -> Path:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    with urlopen(url) as response, tmp_path.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    tmp_path.replace(cache_path)
    if not _checksum_matches(cache_path, checksum):
        cache_path.unlink(missing_ok=True)
        raise SystemExit(f"Checksum mismatch for cached download: {cache_path}")
    return cache_path


def _vendor_from_dist(
    dist: str,
    dest: Path,
    *,
    force: bool,
    cache_path: Path | None = None,
    checksum: str | None = None,
) -> None:
    if dist.startswith(("http://", "https://")):
        if cache_path is None:
            raise SystemExit("Cache path required for remote registry fetches.")
        if cache_path.is_file() and _checksum_matches(cache_path, checksum):
            dist_path = cache_path
        else:
            dist_path = _download_to_cache(dist, cache_path, checksum=checksum)
    elif dist.startswith("file://"):
        dist_path = Path(dist[len("file://") :])
    else:
        dist_path = Path(dist)
    if dist_path.is_dir():
        _copy_tree(dist_path, dest, force=force)
        return
    if dist_path.suffixes[-2:] == [".tar", ".gz"] or dist_path.suffix == ".tgz":
        if dest.exists():
            if not force:
                raise SystemExit(f"Destination already exists: {dest}")
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        if not _checksum_matches(dist_path, checksum):
            raise SystemExit(f"Checksum mismatch for archive: {dist_path}")
        with tarfile.open(dist_path) as tar:
            _safe_extract(tar, dest)
        return
    raise SystemExit(f"Unsupported registry dist: {dist}")


def _vendor_dependency(
    entry: dict[str, Any],
    project_root: Path,
    vendor_root: Path,
    *,
    cache_root: Path,
    force: bool,
) -> None:
    name = entry.get("name")
    version = entry.get("version", "0.0.0")
    source = entry.get("source")
    if not name:
        return
    if source == "path":
        path_value = entry.get("path")
        if not path_value:
            raise SystemExit(f"Missing path for dependency {name}")
        source_path = (project_root / str(path_value)).resolve()
        dest = vendor_root / "local" / name / version
        _copy_tree(source_path, dest, force=force)
        return
    if source == "registry":
        registry = entry.get("registry")
        host = _registry_host(registry)
        index = _load_registry_index(registry or "", project_root)
        dist, checksum = _lookup_registry_dist(index, name, version)
        if not dist:
            raise SystemExit(f"Registry entry missing dist for {name}@{version}")
        dest = vendor_root / host / name / version
        cache_filename = Path(urlparse(dist).path).name or f"{name}-{version}.tar.gz"
        cache_path = cache_root / "registry" / host / name / version / cache_filename
        _vendor_from_dist(dist, dest, force=force, cache_path=cache_path, checksum=checksum)
        return
    if source == "git":
        url = entry.get("url")
        if not url:
            raise SystemExit(f"Git dependency {name} missing url")
        if url.startswith("file://"):
            source_path = Path(url[len("file://") :])
        else:
            source_path = Path(url)
        if not source_path.exists():
            raise SystemExit(f"Git dependency {name} source not found: {url}")
        dest = vendor_root / "git" / name / version
        _copy_tree(source_path, dest, force=force)
        return
    raise SystemExit(f"Unsupported dependency source for {name}: {source}")


def _cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    manifest_path = _write_manifest_template(target, force=args.force)
    src_dir = target / "src"
    src_dir.mkdir(exist_ok=True)
    main_path = src_dir / "main.tiny"
    if not main_path.exists():
        main_path.write_text('fn main()\n  print("Hello from TinyLanguage!")\nend\n', encoding="utf-8")
    lock_path = target / "tiny.lock"
    write_lockfile(lock_path, manifest_path)
    print(f"Created {manifest_path}")
    print(f"Initialized {src_dir}")
    print(f"Wrote {lock_path}")
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    manifest = _read_manifest(manifest_path)
    name, constraint = _parse_dependency_spec(args.dependency)
    dependencies = manifest.setdefault("dependencies", {})
    if not isinstance(dependencies, dict):
        raise SystemExit("Manifest dependencies section must be a table.")
    if args.path:
        entry: dict[str, Any] = {"path": args.path}
        if constraint:
            entry["version"] = constraint
        dependencies[name] = entry
    elif constraint:
        dependencies[name] = constraint
    else:
        dependencies[name] = "*"
    _write_manifest(manifest_path, manifest)
    lock_path = manifest_path.parent / "tiny.lock"
    write_lockfile(lock_path, manifest_path)
    print(f"Added dependency {name} to {manifest_path}")
    print(f"Resolved dependencies into {lock_path}")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    manifest = _read_manifest(manifest_path)
    removed = False
    for section in ("dependencies", "dev-dependencies", "build-dependencies", "dependency-overrides"):
        table = manifest.get(section)
        if isinstance(table, dict) and args.dependency in table:
            del table[args.dependency]
            removed = True
    if not removed:
        raise SystemExit(f"Dependency not found in manifest: {args.dependency}")
    _write_manifest(manifest_path, manifest)
    lock_path = manifest_path.parent / "tiny.lock"
    write_lockfile(lock_path, manifest_path)
    print(f"Removed dependency {args.dependency} from {manifest_path}")
    print(f"Resolved dependencies into {lock_path}")
    return 0


def _cmd_update(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    if args.dependency:
        manifest = _read_manifest(manifest_path)
        found = False
        for section in ("dependencies", "dev-dependencies", "build-dependencies"):
            table = manifest.get(section)
            if isinstance(table, dict) and args.dependency in table:
                found = True
                break
        if not found:
            raise SystemExit(f"Dependency not found in manifest: {args.dependency}")
    lock_path = manifest_path.parent / "tiny.lock"
    write_lockfile(lock_path, manifest_path)
    print(f"Resolved dependencies into {lock_path}")
    return 0


def _resolve_cache_root(project_root: Path) -> Path:
    env_root = os.environ.get("TINY_PKG_CACHE", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return project_root / ".tiny-cache"


def _cmd_vendor(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    project_root = manifest_path.parent
    lock_path = project_root / "tiny.lock"
    entries = _lockfile_entries(lock_path)
    vendor_root = project_root / "vendor"
    vendor_root.mkdir(parents=True, exist_ok=True)
    cache_root = _resolve_cache_root(project_root)
    for entry in entries:
        _vendor_dependency(
            entry,
            project_root,
            vendor_root,
            cache_root=cache_root,
            force=args.force,
        )
    print(f"Vendored dependencies into {vendor_root}")
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.is_file():
        raise SystemExit(f"Missing manifest: {manifest_path}")
    lock_path = manifest_path.parent / "tiny.lock"
    write_lockfile(lock_path, manifest_path)
    print(f"Resolved dependencies into {lock_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TinyLanguage package tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a tiny.toml manifest")
    init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Directory where tiny.toml should be created (default: current directory)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite tiny.toml if it already exists",
    )
    init_parser.set_defaults(func=_cmd_init)

    add_parser = subparsers.add_parser("add", help="Add a dependency")
    add_parser.add_argument(
        "dependency",
        help="Dependency identifier, e.g. name@1.2.3",
    )
    add_parser.add_argument(
        "--path",
        help="Optional local path override",
    )
    add_parser.add_argument(
        "--manifest",
        default="tiny.toml",
        help="Path to the tiny.toml manifest (default: ./tiny.toml)",
    )
    add_parser.set_defaults(func=_cmd_add)

    remove_parser = subparsers.add_parser("remove", help="Remove a dependency")
    remove_parser.add_argument("dependency", help="Dependency name to remove")
    remove_parser.add_argument(
        "--manifest",
        default="tiny.toml",
        help="Path to the tiny.toml manifest (default: ./tiny.toml)",
    )
    remove_parser.set_defaults(func=_cmd_remove)

    update_parser = subparsers.add_parser("update", help="Update resolved dependencies")
    update_parser.add_argument("dependency", nargs="?", help="Optional dependency to validate before update")
    update_parser.add_argument(
        "--manifest",
        default="tiny.toml",
        help="Path to the tiny.toml manifest (default: ./tiny.toml)",
    )
    update_parser.set_defaults(func=_cmd_update)

    vendor_parser = subparsers.add_parser("vendor", help="Vendor dependencies into ./vendor")
    vendor_parser.add_argument(
        "--manifest",
        default="tiny.toml",
        help="Path to the tiny.toml manifest (default: ./tiny.toml)",
    )
    vendor_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite vendor entries if they already exist",
    )
    vendor_parser.set_defaults(func=_cmd_vendor)

    resolve_parser = subparsers.add_parser("resolve", help="Resolve dependencies")
    resolve_parser.add_argument(
        "--manifest",
        default="tiny.toml",
        help="Path to the tiny.toml manifest (default: ./tiny.toml)",
    )
    resolve_parser.set_defaults(func=_cmd_resolve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())
