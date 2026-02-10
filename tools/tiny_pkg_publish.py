#!/usr/bin/env python3
"""Stage a TinyLanguage package publish payload without network operations."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tarfile
from typing import Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from tiny_pkg_resolution import SemVer, manifest_hash_for_path  # noqa: E402

if importlib.util.find_spec("tomllib"):
    tomllib = importlib.import_module("tomllib")
else:
    tomllib = importlib.import_module("tomli")


DEFAULT_OUTPUT_DIR = Path("publish")
EXCLUDED_DIRS = {".git", "__pycache__"}


def _read_manifest(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"Missing manifest: {path}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _read_lockfile(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"Missing lockfile: {path}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _require_package_fields(manifest: Mapping[str, object]) -> tuple[str, str]:
    package = manifest.get("package")
    if not isinstance(package, Mapping):
        raise SystemExit("Missing [package] table in tiny.toml")
    name = package.get("name")
    version = package.get("version")
    if not isinstance(name, str) or not name.strip():
        raise SystemExit("Package name is required in [package]")
    if not isinstance(version, str) or not version.strip():
        raise SystemExit("Package version is required in [package]")
    try:
        SemVer.parse(version)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    return name.strip(), version.strip()


def _validate_lockfile(lock_data: Mapping[str, object], manifest_hash: str) -> None:
    lock_hash = lock_data.get("manifest_hash")
    if not isinstance(lock_hash, str):
        raise SystemExit("Lockfile is missing manifest_hash")
    if lock_hash != manifest_hash:
        raise SystemExit("Lockfile manifest_hash does not match tiny.toml (lockfile drift)")


def _iter_publish_files(root: Path, output_dir: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if relative.parts and relative.parts[0] in EXCLUDED_DIRS:
            continue
        if output_dir in path.parents:
            continue
        yield path


def _tarball_path(output_dir: Path, name: str, version: str) -> Path:
    return output_dir / f"{name}-{version}.tar.gz"


def _metadata_path(output_dir: Path, name: str, version: str) -> Path:
    return output_dir / f"{name}-{version}.json"


def _manifest_path(output_dir: Path) -> Path:
    return output_dir / "manifest.json"


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_tarball(root: Path, files: Iterable[Path], target: Path) -> list[str]:
    entries: list[str] = []
    with tarfile.open(target, "w:gz") as tar:
        for path in files:
            relative = path.relative_to(root).as_posix()
            tar.add(path, arcname=relative)
            entries.append(relative)
    return entries


def _write_metadata(
    *,
    output_path: Path,
    name: str,
    version: str,
    registry: str | None,
    tarball_checksum: str,
    tiny_version_range: str,
) -> None:
    data = {
        "name": name,
        "version": version,
        "registry": registry or "registry-placeholder",
        "dist": {
            "url": "dist-url-placeholder",
            "checksum": tarball_checksum,
        },
        "tiny_version": tiny_version_range,
        "published_at": "timestamp-placeholder",
    }
    output_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(
    *,
    output_path: Path,
    files: Iterable[str],
    total_bytes: int,
    tarball_checksum: str,
) -> None:
    data = {
        "files": list(files),
        "total_bytes": total_bytes,
        "tarball_sha256": tarball_checksum,
    }
    output_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _summarize(
    *,
    name: str,
    version: str,
    registry: str | None,
    tarball_path: Path,
    tarball_checksum: str,
    metadata_path: Path,
) -> None:
    size_kb = tarball_path.stat().st_size / 1024
    print("Dry-run publish payload staged.")
    print(f"Package: {name} {version}")
    print(f"Registry: {registry or 'registry-placeholder'}")
    print(f"Tarball: {tarball_path} ({size_kb:.1f} KiB)")
    print(f"Checksum: {tarball_checksum}")
    print(f"Metadata: {metadata_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage a tiny pkg publish payload without network operations",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tiny.toml"),
        help="Path to tiny.toml (default: ./tiny.toml)",
    )
    parser.add_argument(
        "--lockfile",
        type=Path,
        default=Path("tiny.lock"),
        help="Path to tiny.lock (default: ./tiny.lock)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to stage publish artifacts",
    )
    parser.add_argument(
        "--registry",
        type=str,
        default=None,
        help="Registry URL override",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Manifest profile selector (reserved for future use)",
    )

    args = parser.parse_args(argv)

    manifest = _read_manifest(args.manifest)
    lock_data = _read_lockfile(args.lockfile)
    name, version = _require_package_fields(manifest)

    manifest_hash = manifest_hash_for_path(args.manifest)
    _validate_lockfile(lock_data, manifest_hash)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    root = args.manifest.parent.resolve()
    files = list(_iter_publish_files(root, output_dir.resolve()))
    total_bytes = sum(path.stat().st_size for path in files)

    tarball_path = _tarball_path(output_dir, name, version)
    entries = _write_tarball(root, files, tarball_path)
    tarball_checksum = _hash_file(tarball_path)

    tiny_version = "*"
    package_table = manifest.get("package")
    if isinstance(package_table, Mapping):
        tiny_version = str(package_table.get("tiny_version", "*"))

    metadata_path = _metadata_path(output_dir, name, version)
    _write_metadata(
        output_path=metadata_path,
        name=name,
        version=version,
        registry=args.registry,
        tarball_checksum=tarball_checksum,
        tiny_version_range=tiny_version,
    )

    manifest_path = _manifest_path(output_dir)
    _write_manifest(
        output_path=manifest_path,
        files=entries,
        total_bytes=total_bytes,
        tarball_checksum=tarball_checksum,
    )

    _summarize(
        name=name,
        version=version,
        registry=args.registry,
        tarball_path=tarball_path,
        tarball_checksum=tarball_checksum,
        metadata_path=metadata_path,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
