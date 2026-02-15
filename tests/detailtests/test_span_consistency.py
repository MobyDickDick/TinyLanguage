"""Tests for span consistency."""

import textwrap

import pytest

from tiny_language import TinyLangError, compile_and_run


def _assert_span(err: TinyLangError, start_line: int, start_col: int, stop_line: int, stop_col: int) -> None:
    """Helper to assert span."""
    assert err.span is not None, "Expected error to carry a SourceSpan"
    assert err.span.start.line == start_line
    assert err.span.start.column == start_col
    assert err.span.stop.line == stop_line
    assert err.span.stop.column == stop_col


def test_parser_error_span_tracks_unexpected_token():
    """Test that parser error span tracks unexpected token."""
    source = "def a = ;"

    with pytest.raises(TinyLangError) as exc:
        compile_and_run(source)

    _assert_span(exc.value, 1, 9, 1, 9)


def test_parser_error_span_points_to_eof():
    """Test that parser errors at EOF point to the end position."""
    source = "def a = 1"

    with pytest.raises(TinyLangError) as exc:
        compile_and_run(source)

    _assert_span(exc.value, 1, 10, 1, 10)


def test_parser_error_span_after_trailing_newline_stays_on_statement_line():
    """Test that parser EOF spans after trailing newline stay on the prior token line."""
    source = "def value = 1\n"

    with pytest.raises(TinyLangError) as exc:
        compile_and_run(source)

    _assert_span(exc.value, 1, 14, 1, 14)


def test_linter_error_span_tracks_reserved_binding_name():
    """Test that linter error span tracks reserved binding name."""
    source = textwrap.dedent(
        """
        def _ = 1;
        """
    ).strip()

    with pytest.raises(TinyLangError) as exc:
        compile_and_run(source)

    _assert_span(exc.value, 1, 5, 1, 5)


def test_runtime_error_span_tracks_unknown_variable():
    """Test that runtime error span tracks unknown variable."""
    source = textwrap.dedent(
        """
        print(x);
        """
    ).strip()

    with pytest.raises(TinyLangError) as exc:
        compile_and_run(source)

    _assert_span(exc.value, 1, 7, 1, 7)
