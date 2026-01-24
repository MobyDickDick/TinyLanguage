"""Tests for Tiny wrapper modules that delegate to Python implementations."""

from tests.utils import run_tiny


def test_tiny_language_api_wrapper_compile_and_run() -> None:
    """Test that tiny language api wrapper compile and run."""
    source = """
import src_tiny.tiny_language_api as api;

def output = api.compile_and_run("print(1);");
print(output);
"""
    result = run_tiny(source)
    assert result.strip() == "1"
