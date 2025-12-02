import textwrap

from tiny_language import Lexer, Parser


def test_let_statement_span_tracks_semicolon():
    src = "define value = 1 + 2;"
    stmts = Parser(Lexer(src), src).parse()
    define_stmt = stmts[0]

    assert define_stmt.span.start.line == 1
    assert define_stmt.span.start.column == 1
    assert define_stmt.span.stop.column == 21
    # expression span should cover the arithmetic part
    assert define_stmt.expr.span.start.column == 16
    assert define_stmt.expr.span.stop.column == 20


def test_print_statement_span_includes_trailing_semicolon():
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
