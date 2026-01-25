"""Lightweight smoke tests for quick developer feedback."""

from tests.utils import execute_tiny_program, run_tiny


def test_smoke_run_tiny_addition() -> None:
    """Ensure in-process execution works for a simple program."""
    source = "\n".join(
        [
            "fn add(a, b) { return a + b; }",
            "print(add(2, 3));",
        ]
    )
    assert run_tiny(source).strip() == "5"


def test_smoke_cli_execution() -> None:
    """Ensure CLI execution handles a tiny program cleanly."""
    result = execute_tiny_program('print("hello");\n')
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"
    assert result.stderr.strip() == ""
