import pathlib
import re
import sys
from dataclasses import fields, is_dataclass
from typing import Any

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
LANGUAGE_SPEC = PROJECT_ROOT / "docs" / "language_spec.md"
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import Lexer, Parser, _parse_with_tiny_parser
from tiny_language_lexer import KEYWORDS
from tiny_language_preamble import TinyLangError


GRAMMAR_SAMPLES = [
    pytest.param(
        "def value = 1 + 2 * 3 ^ 2;\nprint(value, 4);\nflush();",
        id="define_print_flush",
    ),
    pytest.param(
        "def n = 0;\n"
        "while (n < 3) { n = n + 1; }\n"
        "if (n >= 3) { print(n); } else { print(0); }\n"
        "try { print(\"ok\"); } catch (err) { print(err); }",
        id="if_while_try",
    ),
    pytest.param(
        "import math.trig as trig;\nnamespace Tools { fn ping() { return 1; } }",
        id="import_namespace",
    ),
    pytest.param(
        "fn add(x: number, y: number) -> number { return x + y; }",
        id="fn_return_type",
    ),
    pytest.param(
        "type Shape { Circle { radius: number }; Rectangle { width: number, height: number }; }\n"
        "class Greeter { name: string; fn greet(self) { return self.name; } }\n"
        "operator + (a: number, b: number) -> number { return a + b; }",
        id="type_class_operator",
    ),
    pytest.param(
        "fn pair(a, b) { return { a: a, b: b }; }\n"
        "{ a, b } = pair(1, 2);\n"
        "point.x = 3;\n"
        "point.move(1, 2);",
        id="destruct_calls",
    ),
    pytest.param(
        "type Shape { Circle { radius: number }; }\n"
        "def shape = Circle { radius: 2 };\n"
        "def size = match shape { case Circle { radius: r } => r; };",
        id="match_variant",
    ),
    pytest.param(
        "async fn job() { return 1; }\n"
        "fn run() { return await job(); }\n"
        "def buf = new[1, 2, 3];\n"
        "def obj = { a: 1, b: 2 };\n"
        "def empty = Null;",
        id="async_await_new",
    ),
    pytest.param(
        "class Box { value: number; }\n"
        "def box = new Box { value: 5 };",
        id="class_new",
    ),
    pytest.param(
        "import .local.module;",
        id="relative_import",
    ),
]


def _normalize(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, set):
        return sorted(_normalize(item) for item in value)
    if isinstance(value, dict):
        return {key: _normalize(val) for key, val in value.items()}
    if is_dataclass(value):
        payload = {"__type__": value.__class__.__name__}
        for field in fields(value):
            if field.name in {
                "pos",
                "span",
                "name_span",
                "module_span",
                "binding_span",
                "name_spans",
                "return_param_names",
            }:
                continue
            payload[field.name] = _normalize(getattr(value, field.name))
        return payload
    return value


def _parse_python(source: str) -> list[Any]:
    parser = Parser(Lexer(source), source)
    return parser.parse()


def _parse_tiny(source: str) -> list[Any]:
    return _parse_with_tiny_parser(source)


def _load_language_spec() -> str:
    return LANGUAGE_SPEC.read_text(encoding="utf-8")


def _extract_keyword_list(spec: str) -> set[str]:
    match = re.search(r"Keywords today include:(.*)", spec)
    if not match:
        raise AssertionError("Unable to locate keyword list in language spec.")
    return set(re.findall(r"`([^`]+)`", match.group(1)))


def _extract_token_table(spec: str) -> set[str]:
    match = re.search(
        r"\| Category \| Tokens \|\n\|[- |]+\|\n(?P<rows>(?:\|.*\n)+?)\n",
        spec,
    )
    if not match:
        raise AssertionError("Unable to locate lexer/token table in language spec.")
    rows = match.group("rows")
    return set(re.findall(r"`([^`]+)`", rows))


def _extract_grammar_block(spec: str) -> str:
    match = re.search(r"```ebnf\n(.*?)```", spec, flags=re.S)
    if not match:
        raise AssertionError("Unable to locate EBNF grammar block in language spec.")
    return match.group(1)


@pytest.mark.parametrize("source", GRAMMAR_SAMPLES)
def test_grammar_samples_match_tiny_parser(source: str) -> None:
    python_ast = _normalize(_parse_python(source))
    tiny_ast = _normalize(_parse_tiny(source))

    assert python_ast == tiny_ast


def test_language_spec_keywords_match_lexer() -> None:
    spec = _load_language_spec()
    documented = _extract_keyword_list(spec)

    assert documented == set(KEYWORDS)


def test_language_spec_token_table_matches_lexer() -> None:
    spec = _load_language_spec()
    documented = _extract_token_table(spec)

    symbols = set("(){}[];,=:.?")
    op_single = set("+-*/><^!%")
    op_multi = {"&&", "||", "==", "!=", "<=", ">="}
    expected = symbols | op_single | op_multi | {"//"}

    assert documented == expected


def test_language_spec_grammar_mentions_task_and_catch_name() -> None:
    grammar = _extract_grammar_block(_load_language_spec())

    assert '"task" block' in grammar
    assert '"try" block "catch" ("(" NAME ")" | NAME) block' in grammar


def test_language_spec_string_escapes_match_lexer() -> None:
    source = '"line1\\nline2\\t\\r\\\"\\\\\\q"'

    token = Lexer(source).next_token()

    expected = "".join(
        [
            "line1\n",
            "line2\t",
            "\r",
            '"',
            "\\",
            "\\q",
        ]
    )

    assert token.text == expected


def test_language_spec_disallows_scientific_notation() -> None:
    lexer = Lexer("def x = 1e2;")
    lexer.next_token()
    lexer.next_token()
    lexer.next_token()

    with pytest.raises(TinyLangError):
        lexer.next_token()
