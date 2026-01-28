"""Smoke test for the parity runner against tiny fixtures."""

from __future__ import annotations

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from parity_runner import main  # noqa: E402


def test_parity_runner_on_fixtures() -> None:
    """Run parity checks on the bundled fixtures using core backends."""
    parity_dir = PROJECT_ROOT / "tests" / "parity"
    exit_code = main(
        [
            "--fixtures",
            str(parity_dir),
            "--backend",
            "interpreter",
            "--backend",
            "native",
        ]
    )
    assert exit_code == 0
