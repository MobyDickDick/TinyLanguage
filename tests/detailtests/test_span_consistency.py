import textwrap

import pytest

from tiny_language import TinyLangError, compile_and_run


def _assert_span(err: TinyLangError, start_line: int, start_col: int, stop_line: int, stop_col: int) -> None:
    assert err.span is not None, "Expected error to carry a SourceSpan"
    assert err.span.start.line == start_line
    assert err.span.start.column == start_col
    assert err.span.stop.line == stop_line
    assert err.span.stop.column == stop_col


def test_parser_error_span_tracks_unexpected_token():
    source = "def a = ;"

    with pytest.raises(TinyLangError) as exc:
        compile_and_run(source)

    _assert_span(exc.value, 1, 9, 1, 9)


def test_linter_error_span_tracks_reserved_binding_name():
    source = textwrap.dedent(
        """
        def _ = 1;
        """
    ).strip()

    with pytest.raises(TinyLangError) as exc:
        compile_and_run(source)

    _assert_span(exc.value, 1, 5, 1, 5)


def test_runtime_error_span_tracks_unknown_variable():
    source = textwrap.dedent(
        """
        print(x);
        """
    ).strip()

    with pytest.raises(TinyLangError) as exc:
        compile_and_run(source)

    _assert_span(exc.value, 1, 7, 1, 7)
