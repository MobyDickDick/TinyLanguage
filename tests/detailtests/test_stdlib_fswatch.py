"""Tests for the stdlib fswatch module stub."""

from tests.detailtests.stdlib_helpers import run_stdlib_module


def test_stdlib_fswatch_mock_events(run_tiny_source):
    """Ensure mock watcher emits deterministic events."""
    out = run_stdlib_module(
        run_tiny_source,
        "fswatch",
        """
        def res = fswatch.watch("mock://events", Null);
        def rendered = match(res) {
          case Ok { value: watch } => watch.handle + "::" + JSON.stringify(Collections.len(watch.events));
          case Err { code: code, message: message } => code + "\n" + message;
        };
        print(rendered);
        def _cleanup = match(res) {
          case Ok { value: watch } => delete(watch.events);
          case Err { code: code, message: message } => Null;
        };
        """,
    )

    assert out == "mock-1::2\n"


def test_stdlib_fswatch_invalid_path(run_tiny_source):
    """Ensure missing paths surface as E_INVALID errors."""
    out = run_stdlib_module(
        run_tiny_source,
        "fswatch",
        """
        def res = fswatch.watch("", Null);
        def rendered = match(res) {
          case Ok { value: watch } => "ok";
          case Err { code: code, message: message } => code + "\n" + message;
        };
        print(rendered);
        """,
    )

    assert out == "E_INVALID\npath required\n"


def test_stdlib_fswatch_permission_denied(run_tiny_source):
    """Ensure fswatch capability denial returns a permission error."""
    out = run_stdlib_module(
        run_tiny_source,
        "fswatch",
        """
        def res = fswatch.watch("/tmp", Null);
        def rendered = match(res) {
          case Ok { value: watch } => "ok";
          case Err { code: code, message: message } => code + "\n" + message;
        };
        print(rendered);
        """,
    )

    assert out == "E_PERMISSION\nfswatch capability not enabled\n"
