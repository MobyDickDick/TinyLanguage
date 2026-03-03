"""Helpers to load vendored runtime dependencies for image composite conversion."""

from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path
from shutil import rmtree


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENDOR_RUNTIME_ROOT = PROJECT_ROOT / "vendor" / "converter_runtime"


def configure_converter_runtime(vendor_root: Path | None = None) -> Path | None:
    """Put vendored runtime paths on sys.path/PATH so cv2/numpy/fitz can be imported.

    Returns the resolved vendor runtime path if available.
    """

    root = (vendor_root or VENDOR_RUNTIME_ROOT).resolve()
    if not root.exists():
        return None

    _remove_vendor_bytecode_caches(root)

    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    # OpenCV and similar packages can need a DLL/shared-lib search path.
    existing_path = os.environ.get("PATH", "")
    path_parts = existing_path.split(os.pathsep) if existing_path else []
    if root_str not in path_parts:
        os.environ["PATH"] = os.pathsep.join([root_str, *path_parts]) if path_parts else root_str

    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(root_str)
        except OSError:
            # Not all platforms/paths support this call.
            pass

    return root


def _remove_vendor_bytecode_caches(vendor_root: Path) -> None:
    """Remove cached bytecode from synced vendor folders.

    Cloud sync tools occasionally truncate ``.pyc`` files which then crash imports
    with errors like ``EOFError: marshal data too short``. Keeping only source
    files avoids this entire class of startup failures.
    """

    for cache_dir in vendor_root.rglob("__pycache__"):
        if cache_dir.is_dir():
            rmtree(cache_dir, ignore_errors=True)

    for pyc_file in vendor_root.rglob("*.pyc"):
        try:
            pyc_file.unlink()
        except OSError:
            # Best effort cleanup; imports can still succeed from source files.
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Configure vendored converter runtime path and optionally execute a Python script.",
    )
    parser.add_argument(
        "--vendor-root",
        type=Path,
        default=VENDOR_RUNTIME_ROOT,
        help="Path to vendored runtime directory (default: %(default)s)",
    )
    parser.add_argument(
        "--run-script",
        type=Path,
        help="Optional Python script to run after runtime bootstrap (receives -- separator args).",
    )
    parser.add_argument(
        "script_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to --run-script (prefix with --).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    configured = configure_converter_runtime(args.vendor_root)
    if configured is None:
        print(f"[WARN] Runtime-Pfad nicht gefunden: {args.vendor_root}")
    else:
        print(f"[INFO] Runtime-Pfad aktiviert: {configured}")

    if args.run_script is None:
        return 0

    script_path = args.run_script.resolve()
    if not script_path.exists():
        parser.error(f"Script nicht gefunden: {script_path}")

    forwarded = list(args.script_args)
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]

    sys.argv = [str(script_path), *forwarded]
    runpy.run_path(str(script_path), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
