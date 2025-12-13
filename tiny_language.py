"""Python module wrapper for running the TinyLanguage CLI via ``python -m tiny_language``.

Running TinyLanguage as a module is convenient, but the main interpreter lives in
``src/tiny_language.py``. This shim ensures that invoking ``python -m tiny_language``
behaves the same as executing the source file directly.
"""
from __future__ import annotations

from pathlib import Path
import runpy
import sys


def _main() -> int:
    repo_root = Path(__file__).resolve().parent
    src_entrypoint = repo_root / "src" / "tiny_language.py"

    # Ensure bundled modules (e.g., tiny_errors.py) are importable even when the project
    # is not installed as a package.
    src_dir = src_entrypoint.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    if not src_entrypoint.is_file():
        raise SystemExit("Cannot find src/tiny_language.py; run from the repository root.")

    # Execute the real CLI script as __main__ so its argument parsing and exit codes are preserved.
    try:
        runpy.run_path(str(src_entrypoint), run_name="__main__")
    except SystemExit as exc:  # Propagate the exit code from the wrapped script.
        return int(exc.code) if exc.code is not None else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
