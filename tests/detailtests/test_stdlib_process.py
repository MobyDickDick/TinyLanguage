"""Tests for the stdlib process module stub."""

from tests.detailtests.stdlib_helpers import run_stdlib_module


def test_stdlib_process_invalid_command(run_tiny_source):
    """Ensure missing commands surface as E_INVALID errors."""
    out = run_stdlib_module(
        run_tiny_source,
        "process",
        """
        def args = new[];
        def res = process.run("", args, Null);
        def _cleanup_args = delete(args);
        def rendered = match(res) {
          case Ok { value: result } => "ok";
          case Err { code: code, message: message } => code + "\n" + message;
        };
        print(rendered);
        """,
    )

    assert out == "E_INVALID\ncommand required\n"


def test_stdlib_process_permission_denied(run_tiny_source):
    """Ensure process capability denial returns a permission error."""
    out = run_stdlib_module(
        run_tiny_source,
        "process",
        """
        def args = new[];
        def res = process.run("echo", args, Null);
        def _cleanup_args = delete(args);
        def rendered = match(res) {
          case Ok { value: result } => "ok";
          case Err { code: code, message: message } => code + "\n" + message;
        };
        print(rendered);
        """,
    )

    assert out == "E_PERMISSION\nprocess capability not enabled\n"
