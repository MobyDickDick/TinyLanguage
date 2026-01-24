"""Tests for repl highlighting."""

import types

import tiny_language as tl
from tiny_language_highlighting import PYGMENTS_AVAILABLE, highlight_source


def test_highlight_source_is_optional() -> None:
    """Test that highlight source is optional."""
    snippet = "def x = 1; // highlight me"
    highlighted = highlight_source(snippet)
    if PYGMENTS_AVAILABLE:
        assert isinstance(highlighted, str)
        assert "def" in highlighted
    else:
        assert highlighted is None


def test_repl_highlighting_requires_tty(monkeypatch) -> None:
    """Test that repl highlighting requires tty."""
    fake_stdout = types.SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(tl, "PYGMENTS_AVAILABLE", True)
    monkeypatch.setattr(tl.sys, "stdout", fake_stdout)
    monkeypatch.delenv("TINYL_REPL_HIGHLIGHT", raising=False)

    assert tl._repl_highlighting_enabled() is True

    monkeypatch.setattr(fake_stdout, "isatty", lambda: False)
    assert tl._repl_highlighting_enabled() is False


def test_repl_highlighting_can_be_disabled(monkeypatch) -> None:
    """Test that repl highlighting can be disabled."""
    fake_stdout = types.SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(tl, "PYGMENTS_AVAILABLE", True)
    monkeypatch.setattr(tl.sys, "stdout", fake_stdout)
    monkeypatch.setenv("TINYL_REPL_HIGHLIGHT", "0")

    assert tl._repl_highlighting_enabled() is False
