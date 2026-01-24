"""Tests for readme hello world cli."""

import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_readme_hello_world_cli_output_matches():
    """Test that readme hello world cli output matches."""
    hello_world = PROJECT_ROOT / "src_tiny" / "hello_world.tiny"
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "src" / "tiny_language.py"), str(hello_world)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Hello, TinyLanguage!\n"
    assert result.stderr == ""
