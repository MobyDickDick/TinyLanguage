"""Tests for the stdlib gui module."""

from __future__ import annotations

from tests.detailtests.stdlib_helpers import stdlib_program


def test_stdlib_gui_describe_returns_expected_shape(run_tiny_source, monkeypatch):
    """Ensure the declarative app builder returns a stable summary map."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")

    out = run_tiny_source(
        stdlib_program(
            "gui",
            """
            def app = gui.app("Demo", 640, 360);
            def _label_result = gui.label(app, "Hello");
            def _button_result = gui.button(app, "Close");
            def summary = gui.describe(app);
            print(Map.get(summary, "backend"));
            print(Map.get(summary, "title"));
            print(Map.get(summary, "width"));
            print(Map.get(summary, "height"));
            print(Map.get(summary, "widget_count"));
            def widget_types = Map.get(summary, "widget_types");
            print(heap_get(widget_types, 0));
            print(heap_get(widget_types, 1));
            def _cleanup_widget_types = delete(widget_types);
            def _cleanup_summary = delete(summary);
            def _cleanup_buttons = delete(Map.get(app, "buttons"));
            def _cleanup_labels = delete(Map.get(app, "labels"));
            """,
        ),
    )

    lines = out.strip().splitlines()
    assert lines[0] == "tkinter"
    assert lines[1] == "Demo"
    assert lines[2] == "640"
    assert lines[3] == "360"
    assert lines[4] == "2"
    assert lines[5] == "label"
    assert lines[6] == "button"
