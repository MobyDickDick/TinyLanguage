#!/usr/bin/env python3
"""Vendor runtime dependencies for src/image_composite_converter.py.

This script copies imported third-party modules from a local virtualenv into
`vendor/converter_runtime` so the converter can run without online installs.
"""

from __future__ import annotations

import argparse
import ast
import shutil
import sys
from pathlib import Path


DEFAULT_SOURCE = Path("src/image_composite_converter.py")
DEFAULT_VENDOR_ROOT = Path("vendor/converter_runtime")


# Explicit mapping for dependencies currently used by image_composite_converter.
DEFAULT_MODULES = ("cv2", "numpy", "fitz")


def _candidate_site_packages(venv_root: Path) -> list[Path]:
    py_mm = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return [
        venv_root / "Lib" / "site-packages",
        venv_root / "lib" / py_mm / "site-packages",
    ]


def _discover_import_roots(source_file: Path) -> set[str]:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _copy_entry(src: Path, dest: Path) -> None:
    if dest.exists():
        if dest.is_dir() and src.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)


def vendor_runtime(source_file: Path, venv_root: Path, vendor_root: Path, modules: tuple[str, ...]) -> list[str]:
    copied: list[str] = []
    site_packages = [p for p in _candidate_site_packages(venv_root) if p.exists()]
    if not site_packages:
        raise FileNotFoundError(f"Keine site-packages unter {venv_root} gefunden.")

    vendor_root.mkdir(parents=True, exist_ok=True)

    imported_roots = _discover_import_roots(source_file)
    for module in modules:
        if module not in imported_roots:
            continue

        found = False
        for sp in site_packages:
            dir_candidate = sp / module
            file_candidate = sp / f"{module}.py"
            if dir_candidate.exists():
                _copy_entry(dir_candidate, vendor_root / module)
                copied.append(str(vendor_root / module))
                found = True
                break
            if file_candidate.exists():
                _copy_entry(file_candidate, vendor_root / f"{module}.py")
                copied.append(str(vendor_root / f"{module}.py"))
                found = True
                break
        if not found:
            print(f"[WARN] Modul '{module}' wurde in site-packages nicht gefunden.")

        # Copy dist-info/metadata and binary sidecar files matching the package.
        lowered = module.lower()
        for sp in site_packages:
            for entry in sp.iterdir():
                name = entry.name.lower()
                if name.startswith(lowered) and (
                    name.endswith(".dist-info")
                    or name.endswith(".data")
                    or name.endswith(".libs")
                    or name.endswith(".dll")
                    or name.endswith(".pyd")
                    or name.endswith(".so")
                    or name.endswith(".dylib")
                ):
                    target = vendor_root / entry.name
                    _copy_entry(entry, target)
                    copied.append(str(target))

    manifest = vendor_root / "MANIFEST.txt"
    manifest.write_text("\n".join(sorted(set(copied))) + "\n", encoding="utf-8")
    return sorted(set(copied))


def main() -> int:
    parser = argparse.ArgumentParser(description="Vendor converter runtime dependencies from a local .venv")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--venv", type=Path, default=Path(".venv"))
    parser.add_argument("--vendor-root", type=Path, default=DEFAULT_VENDOR_ROOT)
    parser.add_argument("--modules", nargs="*", default=list(DEFAULT_MODULES))
    args = parser.parse_args()

    copied = vendor_runtime(args.source, args.venv, args.vendor_root, tuple(args.modules))
    print(f"[INFO] {len(copied)} Einträge nach {args.vendor_root} kopiert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
