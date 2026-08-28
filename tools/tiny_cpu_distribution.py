#!/usr/bin/env python3
"""Build and verify deterministic TinyCPU 1.0 distribution archives."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile


RELEASE = "1.0.0"
MANIFEST = "tinycpu-inventory-v1.json"
SOURCE_PATHS = (
    "hardware/logisim/README.md",
    "hardware/logisim/TinyCPU.circ",
    "hardware/logisim/ap5_countdown.lst",
    "hardware/logisim/ap5_countdown.rom",
    "hardware/logisim/ap5_countdown.tcpu",
    "hardware/logisim/ap5_countdown_trace.json",
    "hardware/logisim/tinycpu-16-12.json",
    "hardware/logisim/tinycpu-electrical-matrix-v1.json",
    "hardware/logisim/tinycpu-machine-v1.json",
    "hardware/logisim/tinycpu-release-v1.json",
    "hardware/logisim/tinycpu_integration_trace.json",
    "docs/tiny_cpu.md",
    "docs/tiny_cpu_compatibility.md",
    "docs/tiny_cpu_test_guide.md",
    "docs/tiny_cpu_1_0_release_plan.md",
    "LICENSE-TinyCPU.md",
    "scripts/test-logisim.sh",
    "scripts/test-logisim-local.sh",
    "src/tiny_cpu_assembler.py",
    "src/tiny_cpu_circuit.py",
    "src/tiny_cpu_cli.py",
    "src/tiny_cpu_isa.py",
    "src/tiny_cpu_logisim.py",
    "src/tiny_cpu_machine.py",
    "src/tiny_cpu_release.py",
    "src/tiny_cpu_trace.py",
    "src/tiny_cpu_verify.py",
    "src/tiny_cpu_vm.py",
    "tools/tiny_cpu_distribution.py",
)


class DistributionError(ValueError):
    """Raised when a distribution contains an unsafe or changed payload."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(path: str, data: bytes) -> dict[str, object]:
    return {"path": path, "size_bytes": len(data), "sha256": _digest(data)}


def _manifest(kind: str, payload: dict[str, bytes]) -> bytes:
    value = {
        "schema_version": 1,
        "release_version": RELEASE,
        "artifact": kind,
        "files": [_entry(path, payload[path]) for path in sorted(payload)],
    }
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _archive(path: Path, root_name: str, payload: dict[str, bytes]) -> None:
    """Write a gzip-compressed POSIX tar with stable metadata and ordering."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for relative in sorted(payload):
            info = tarfile.TarInfo(f"{root_name}/{relative}")
            info.size = len(payload[relative])
            info.mtime = 0
            info.mode = 0o755 if relative.endswith(".sh") or relative == "verify.py" else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(payload[relative]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            compressed.write(buffer.getvalue())


def _regular_bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise DistributionError(f"required file is missing: {relative}") from exc
    if not stat.S_ISREG(mode):
        raise DistributionError(f"required path is not a regular file: {relative}")
    return path.read_bytes()


def verify_directory(directory: Path) -> None:
    """Validate an extracted artifact using only its embedded inventory."""
    manifest_path = directory / MANIFEST
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise DistributionError(f"missing regular inventory: {MANIFEST}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DistributionError(f"invalid inventory: {exc}") from exc
    if manifest.get("schema_version") != 1 or manifest.get("release_version") != RELEASE:
        raise DistributionError("unsupported inventory contract")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise DistributionError("inventory files must be a list")
    declared: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise DistributionError("inventory contains an invalid entry")
        relative = entry["path"]
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or relative in declared:
            raise DistributionError(f"unsafe or duplicate inventory path: {relative}")
        declared.add(relative)
        data = _regular_bytes(directory, relative)
        if entry.get("size_bytes") != len(data) or entry.get("sha256") != _digest(data):
            raise DistributionError(f"size or digest mismatch: {relative}")
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    allowed = declared | {MANIFEST}
    if actual != allowed:
        details = sorted((actual - allowed) | (allowed - actual))
        raise DistributionError("undeclared or missing files: " + ", ".join(details))

    if manifest.get("artifact") == "simulator-bundle":
        _verify_acceptance(directory / "ap12-evidence")


def _verify_acceptance(directory: Path) -> None:
    """Validate the retained AP-12 report and its nested evidence inventory."""
    report_data = _regular_bytes(directory, "acceptance.json")
    try:
        report = json.loads(report_data)
    except json.JSONDecodeError as exc:
        raise DistributionError(f"invalid AP-12 acceptance report: {exc}") from exc
    if not isinstance(report, dict) or report.get("schema_version") != 2 or report.get("status") != "passed":
        raise DistributionError("AP-12 acceptance report is not a passed schema-version-2 report")
    if not isinstance(report.get("reset_restart_runs"), list) or not isinstance(report.get("matrix"), dict):
        raise DistributionError("AP-12 acceptance report is missing required sections")
    evidence = report.get("evidence")
    if not isinstance(evidence, list):
        raise DistributionError("AP-12 acceptance report has no evidence inventory")
    declared: set[str] = set()
    for entry in evidence:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise DistributionError("AP-12 evidence inventory contains an invalid entry")
        relative = entry["path"]
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or relative in declared:
            raise DistributionError(f"unsafe or duplicate AP-12 evidence path: {relative}")
        declared.add(relative)
        data = _regular_bytes(directory, relative)
        if entry.get("size_bytes") != len(data) or entry.get("sha256") != _digest(data):
            raise DistributionError(f"AP-12 evidence size or digest mismatch: {relative}")
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if (path.is_file() or path.is_symlink()) and path.name != "acceptance.json"
    }
    if actual != declared:
        raise DistributionError("AP-12 evidence contains undeclared or missing files")


def build(repository: Path, output: Path, acceptance: Path) -> tuple[Path, Path]:
    """Build source and simulator archives without writing into *repository*."""
    base = {path: _regular_bytes(repository, path) for path in SOURCE_PATHS}
    source = dict(base)
    source[MANIFEST] = _manifest("source", source)

    verify_script = base["tools/tiny_cpu_distribution.py"]
    bundle = dict(base)
    bundle["verify.py"] = verify_script
    if not acceptance.is_dir() or acceptance.is_symlink():
        raise DistributionError("AP-12 acceptance evidence must be a directory")
    _verify_acceptance(acceptance)
    evidence_files = sorted(path for path in acceptance.rglob("*") if path.is_file() or path.is_symlink())
    if not evidence_files:
        raise DistributionError("AP-12 acceptance evidence is empty")
    for path in evidence_files:
        relative = path.relative_to(acceptance).as_posix()
        bundle[f"ap12-evidence/{relative}"] = _regular_bytes(acceptance, relative)
    bundle[MANIFEST] = _manifest("simulator-bundle", bundle)

    source_path = output / f"TinyCPU-{RELEASE}-source.tar.gz"
    bundle_path = output / f"TinyCPU-{RELEASE}-simulator.tar.gz"
    _archive(source_path, f"TinyCPU-{RELEASE}-source", source)
    _archive(bundle_path, f"TinyCPU-{RELEASE}", bundle)
    return source_path, bundle_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="build both release archives")
    build_parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    build_parser.add_argument("--output-dir", type=Path, required=True)
    build_parser.add_argument("--acceptance", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify", help="verify an extracted archive offline")
    verify_parser.add_argument("directory", type=Path, nargs="?", default=Path(__file__).resolve().parent)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            artifacts = build(args.repository.resolve(), args.output_dir.resolve(), args.acceptance.resolve())
            print("\n".join(str(path) for path in artifacts))
        else:
            verify_directory(args.directory.resolve())
            print(f"TinyCPU {RELEASE} distribution verification passed")
    except (OSError, DistributionError) as exc:
        print(f"TinyCPU distribution FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
