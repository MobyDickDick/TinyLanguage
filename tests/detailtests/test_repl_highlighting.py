import types

import tiny_language as tl
from tiny_language_highlighting import PYGMENTS_AVAILABLE, highlight_source


def test_highlight_source_is_optional() -> None:
    snippet = "define x = 1; // highlight me"
    highlighted = highlight_source(snippet)
    if PYGMENTS_AVAILABLE:
        assert isinstance(highlighted, str)
        assert "define" in highlighted
    else:
        assert highlighted is None


def test_repl_highlighting_requires_tty(monkeypatch) -> None:
    fake_stdout = types.SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(tl, "PYGMENTS_AVAILABLE", True)
    monkeypatch.setattr(tl.sys, "stdout", fake_stdout)
    monkeypatch.delenv("TINYL_REPL_HIGHLIGHT", raising=False)

    assert tl._repl_highlighting_enabled() is True

    monkeypatch.setattr(fake_stdout, "isatty", lambda: False)
    assert tl._repl_highlighting_enabled() is False


def test_repl_highlighting_can_be_disabled(monkeypatch) -> None:
    fake_stdout = types.SimpleNamespace(isatty=lambda: True)
    monkeypatch.setattr(tl, "PYGMENTS_AVAILABLE", True)
    monkeypatch.setattr(tl.sys, "stdout", fake_stdout)
    monkeypatch.setenv("TINYL_REPL_HIGHLIGHT", "0")

    assert tl._repl_highlighting_enabled() is False
