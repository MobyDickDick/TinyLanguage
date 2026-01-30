"""Tests for the stdlib logging module wrapper."""

import json

from tests.detailtests.stdlib_helpers import run_stdlib_module, stdlib_program


def test_stdlib_logging_formatting(run_tiny_source):
    """Format structured log lines with context and timestamps."""
    out = run_stdlib_module(
        run_tiny_source,
        "logging",
        """
        def context = Map.new();
        def _job = Map.set(context, "job", "import");
        def _ok = Map.set(context, "ok", true);
        def text = logging.format("info", "started", context, "2024-01-01T00:00:00Z");
        def parsed = JSON.parse(text);
        print(Map.get(parsed, "level", ""));
        print(Map.get(parsed, "message", ""));
        print(Map.get(parsed, "timestamp", ""));
        def parsed_context = Map.get(parsed, "context", Null);
        print(Map.get(parsed_context, "job", ""));
        print(Map.get(parsed_context, "ok", false));
        def _cleanup_parsed_context = delete(parsed_context);
        def _cleanup_parsed = delete(parsed);
        def _cleanup_context = delete(context);
        """,
    )

    assert out == "info\nstarted\n2024-01-01T00:00:00Z\nimport\ntrue\n"


def test_stdlib_logging_file_helpers(run_tiny_source, tmp_path):
    """Write and append structured log entries to a file."""
    log_path = tmp_path / "app.log"
    out = run_tiny_source(
        stdlib_program(
            "logging",
            f"""
            def path = "{log_path.as_posix()}";
            def _write = logging.write(path, "info", "first", Null, "2024-01-01T00:00:00Z");
            def _append = logging.append(path, "error", "second", Null, "2024-01-02T00:00:00Z");
            def text = File.read(path);
            print(text);
            """,
        ),
    )

    lines = out.strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first == {
        "level": "info",
        "message": "first",
        "timestamp": "2024-01-01T00:00:00Z",
    }
    assert second == {
        "level": "error",
        "message": "second",
        "timestamp": "2024-01-02T00:00:00Z",
    }
