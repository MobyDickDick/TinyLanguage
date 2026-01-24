"""Compatibility wrapper for running the full TinyLanguage test and demo suite.

The main runner lives in ``src/run_all.py``. This shim lets tools invoke it from
the repository root without caring about the internal layout.
"""
from __future__ import annotations

from pathlib import Path
import runpy

# Resolve the repository root directory for deterministic path handling.
PROJECT_ROOT = Path(__file__).resolve().parent
# Identify the actual runner script inside the source tree.
RUNNER = PROJECT_ROOT / "src" / "run_all.py"

if __name__ == "__main__":
    # Execute the runner as if it were called directly.
    runpy.run_path(str(RUNNER), run_name="__main__")
