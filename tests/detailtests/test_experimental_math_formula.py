import pytest

from tiny_language import Bin, Lexer, Let, Num, Parser, TinyLangError, _parse_and_lint


def test_math_formula_requires_flag() -> None:
    source = "def area = #[1 + 2];"
    with pytest.raises(TinyLangError) as excinfo:
        Parser(Lexer(source), source).parse()
    assert "--experimental-math-formula" in str(excinfo.value)


def test_math_formula_parses_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TINYLANG_EXPERIMENTAL_MATH_FORMULA", "1")
    source = "def area = #[1 + 2 * 3]; print(area);"
    stmts = _parse_and_lint(source)
    assert isinstance(stmts[0], Let)
    expr = stmts[0].expr
    assert isinstance(expr, Bin)
    assert expr.op == "+"
    assert isinstance(expr.a, Num)
    assert isinstance(expr.b, Bin)
    assert expr.b.op == "*"
