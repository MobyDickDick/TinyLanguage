"""Compatibility wrapper for running the full TinyLanguage test and demo suite."""
from __future__ import annotations

from pathlib import Path
import runpy

PROJECT_ROOT = Path(__file__).resolve().parent
RUNNER = PROJECT_ROOT / "src" / "run_all.py"

if __name__ == "__main__":
    runpy.run_path(str(RUNNER), run_name="__main__")
