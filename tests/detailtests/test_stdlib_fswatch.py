"""Tests for the stdlib fswatch module stub."""


def test_stdlib_fswatch_mock_events(run_tiny_source):
    """Ensure mock watcher emits deterministic events."""
    out = run_tiny_source(
        """
        import stdlib.fswatch;

        def res = fswatch.watch("mock://events", Null);
        def rendered = match(res) {
          case Ok { value: watch } => watch.handle + "::" + JSON.stringify(Collections.len(watch.events));
          case Err { code: code, message: message } => code + "\n" + message;
        };
        print(rendered);
        """,
    )

    assert out == "mock-1::2\n"


def test_stdlib_fswatch_invalid_path(run_tiny_source):
    """Ensure missing paths surface as E_INVALID errors."""
    out = run_tiny_source(
        """
        import stdlib.fswatch;

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
    out = run_tiny_source(
        """
        import stdlib.fswatch;

        def res = fswatch.watch("/tmp", Null);
        def rendered = match(res) {
          case Ok { value: watch } => "ok";
          case Err { code: code, message: message } => code + "\n" + message;
        };
        print(rendered);
        """,
    )

    assert out == "E_PERMISSION\nfswatch capability not enabled\n"
