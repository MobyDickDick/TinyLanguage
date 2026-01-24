"""Tests for readme concurrency demo cli."""

import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_readme_concurrency_demo_output_matches():
    """Test that readme concurrency demo output matches."""
    concurrency_demo = PROJECT_ROOT / "src_tiny" / "concurrency_demo.tiny"
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "src" / "tiny_language.py"), str(concurrency_demo)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "labels\n"
        "first=spawn | second=join | third=string | fourth=interop\n"
        "as list\n"
        "first=spawn -> second=join -> third=string -> fourth=interop\n"
    )
    assert result.stderr == ""
