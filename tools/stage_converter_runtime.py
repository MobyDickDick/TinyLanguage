#!/usr/bin/env python3
"""Stage only required conversion runtime libraries into a repo-local folder.

This helps keep the repository small while still allowing conversion checks in
CI or constrained environments.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
from pathlib import Path


REQUIRED_MODULES = ("numpy", "cv2", "fitz")


def _module_location(module_name: str) -> Path:
    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None:
        raise RuntimeError(f"Module '{module_name}' not found in current interpreter: {sys.executable}")

    origin = Path(spec.origin)
    if origin.name == "__init__.py":
        return origin.parent
    return origin


def _copy_item(src: Path, dst_root: Path) -> Path:
    dst = dst_root / src.name
    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return dst


def _iter_binary_sidecars(module_src: Path) -> list[Path]:
    sidecars: list[Path] = []
    if module_src.is_file():
        base = module_src.stem
        for cand in module_src.parent.iterdir():
            if not cand.is_file():
                continue
            if not cand.stem.startswith(base):
                continue
            if cand.suffix.lower() in {".so", ".pyd", ".dll", ".dylib"}:
                sidecars.append(cand)
    return sidecars


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="vendor/converter_runtime",
        help="Directory that will contain staged runtime libraries",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove output directory before staging",
    )
    args = parser.parse_args()

    out_dir = Path(args.output)
    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    manifest_lines = [
        "# Converter runtime manifest",
        f"python_executable={sys.executable}",
        f"python_version={sys.version.split()[0]}",
        "",
    ]

    for module in REQUIRED_MODULES:
        src = _module_location(module)
        dst = _copy_item(src, out_dir)
        copied.append(dst)
        manifest_lines.append(f"{module}={dst.name}")

        for sidecar in _iter_binary_sidecars(src):
            copied.append(_copy_item(sidecar, out_dir))
            manifest_lines.append(f"{module}_sidecar={sidecar.name}")

    manifest = out_dir / "MANIFEST.txt"
    manifest.write_text("\n".join(manifest_lines).rstrip() + "\n", encoding="utf-8")

    print(f"Staged runtime at: {out_dir}")
    for path in copied:
        size_kb = path.stat().st_size / 1024 if path.is_file() else 0
        suffix = f" ({size_kb:.1f} KiB)" if path.is_file() else ""
        print(f"- {path}{suffix}")
    print(f"Manifest: {manifest}")
    print("Use with: python tools/attempt_convert_ac_range.py --runtime-path " + str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
