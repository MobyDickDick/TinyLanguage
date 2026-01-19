import pytest

from tiny_language import Lexer, Parser, TinyLangError, _parse_and_lint, Let, MethodCall, Var


def test_math_tuple_requires_flag() -> None:
    source = "def area = (sqrt: 9);"
    with pytest.raises(TinyLangError) as excinfo:
        Parser(Lexer(source), source).parse()
    assert "--experimental-math-tuples" in str(excinfo.value)


def test_math_tuple_parses_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TINYLANG_EXPERIMENTAL_MATH_TUPLES", "1")
    source = "def area = (sqrt: 9); print(area);"
    stmts = _parse_and_lint(source)
    assert isinstance(stmts[0], Let)
    expr = stmts[0].expr
    assert isinstance(expr, MethodCall)
    assert isinstance(expr.obj, Var)
    assert expr.obj.name == "Math"
    assert expr.name == "sqrt"
    assert len(expr.args) == 1
