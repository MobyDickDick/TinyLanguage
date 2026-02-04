"""Tests for TinyLangError formatting utilities."""

import textwrap

from tiny_language import SourcePos, SourceSpan, TinyLangError, _format_error_for_source


def test_format_error_includes_code_hint_and_span():
    """Ensure formatted errors include code, hints, and span markers."""
    source = textwrap.dedent(
        """
        def value = 1 + 2;
        print(value);
        """
    ).strip()
    start = SourcePos(1, 8)
    stop = SourcePos(1, 12)
    err = TinyLangError("example failure", start, code="E123", hint="Check the expression", span=SourceSpan(start, stop))

    formatted = _format_error_for_source(source, err)

    assert "[E123] example failure" in formatted
    assert "Hint: Check the expression" in formatted
    assert "^^^^^" in formatted


def test_format_error_rebuilds_inline_location_without_context():
    """Rebuild context when a message only contains inline line/col info."""
    source = "alpha beta gamma"
    err = TinyLangError(
        "[E999] lint failure (line 1, col 7)",
        SourcePos(1, 7),
        code="E999",
    )

    formatted = _format_error_for_source(source, err)

    assert "[E999] lint failure (line 1, col 7)" in formatted
    assert "1 | alpha beta gamma" in formatted
    assert "[E999] [E999]" not in formatted


def test_multiline_span_highlights_each_line():
    """Verify multi-line spans highlight all affected lines."""
    source = textwrap.dedent(
        """
        alpha beta gamma
        second line here
        tail
        """
    ).strip()
    start = SourcePos(1, 7)
    stop = SourcePos(2, 7)
    err = TinyLangError("multi-line failure", start, code="E321", span=SourceSpan(start, stop))

    formatted = _format_error_for_source(source, err)

    assert "1 | alpha beta gamma" in formatted
    assert "2 | second line here" in formatted
    assert "^^^^^^^" in formatted  # at least the combined carets are rendered


def test_format_error_normalizes_reversed_span():
    """Ensure reversed spans are normalized for formatting."""
    source = "alpha beta gamma"
    start = SourcePos(1, 12)
    stop = SourcePos(1, 7)
    err = TinyLangError("reverse span", start, code="E404", span=SourceSpan(start, stop))

    formatted = _format_error_for_source(source, err)

    assert "[E404] reverse span" in formatted
    assert "^^^^^^" in formatted
