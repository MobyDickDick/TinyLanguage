import pathlib
import sys
from dataclasses import fields, is_dataclass
from typing import Any

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import Lexer, Parser, _parse_with_tiny_parser


GRAMMAR_SAMPLES = [
    pytest.param(
        "define value = 1 + 2 * 3 ^ 2;\nprint(value, 4);\nflush();",
        id="define_print_flush",
    ),
    pytest.param(
        "define n = 0;\n"
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
        "define shape = Circle { radius: 2 };\n"
        "define size = match shape { case Circle { radius: r } => r; };",
        id="match_variant",
    ),
    pytest.param(
        "async fn job() { return 1; }\n"
        "fn run() { return await job(); }\n"
        "define buf = new[1, 2, 3];\n"
        "define obj = { a: 1, b: 2 };\n"
        "define empty = Null;",
        id="async_await_new",
    ),
    pytest.param(
        "class Box { value: number; }\n"
        "define box = new Box { value: 5 };",
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


@pytest.mark.parametrize("source", GRAMMAR_SAMPLES)
def test_grammar_samples_match_tiny_parser(source: str) -> None:
    python_ast = _normalize(_parse_python(source))
    tiny_ast = _normalize(_parse_tiny(source))

    assert python_ast == tiny_ast
