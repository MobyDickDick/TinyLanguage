"""Tests for spans."""

import textwrap

import pytest

from tiny_language import Lexer, Parser
from tiny_language_preamble import TinyLangError


def test_let_statement_span_tracks_semicolon():
    """Test that let statement span tracks semicolon."""
    src = "def value = 1 + 2;"
    stmts = Parser(Lexer(src), src).parse()
    define_stmt = stmts[0]

    assert define_stmt.span.start.line == 1
    assert define_stmt.span.start.column == 1
    assert define_stmt.span.stop.column == 18
    # expression span should cover the arithmetic part
    assert define_stmt.expr.span.start.column == 13
    assert define_stmt.expr.span.stop.column == 17


def test_print_statement_span_includes_trailing_semicolon():
    """Test that print statement span includes trailing semicolon."""
    src = textwrap.dedent(
        """
        print(value);
        """
    ).strip()
    stmts = Parser(Lexer(src), src).parse()
    print_stmt = stmts[0]

    assert print_stmt.span.start.column == 1
    assert print_stmt.span.stop.column == 13
    var = print_stmt.exprs[0]
    assert var.span.start.column == 7
    assert var.span.stop.column == 11


def test_parser_error_reports_stable_multiline_span_for_malformed_input():
    """Lock in parser diagnostics with line/column span details for malformed input."""
    src = "def value = 1;\nprint((value + ));\n"

    with pytest.raises(TinyLangError) as exc_info:
        Parser(Lexer(src), src).parse()

    err = exc_info.value
    assert err.span is not None
    assert (err.span.start.line, err.span.start.column) == (2, 16)
    assert (err.span.stop.line, err.span.stop.column) == (2, 16)
    assert "unexpected token SYM (line 2, col 16)" in str(err)
    assert "2 | print((value + ));" in str(err)
