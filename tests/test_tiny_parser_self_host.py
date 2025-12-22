import json
import pathlib

import pytest

from tiny_language import compile_and_run


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
AST_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_ast.tiny").read_text(encoding="utf-8")
LEXER_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_lexer.tiny").read_text(encoding="utf-8")
PARSER_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_parser.tiny").read_text(encoding="utf-8")


def _run_parser_program(body: str) -> list[str]:
    program = "\n\n".join([AST_SRC, LEXER_SRC, PARSER_SRC, body])
    return compile_and_run(program).strip().splitlines()


def test_tiny_parser_builds_basic_ast_nodes():
    source_literal = json.dumps("define value = 7; print(value);")
    body = f"""
define ast = parse_program({source_literal});
print(len(ast));
define first = heap_get(ast, 0);
define second = heap_get(ast, 1);
print(Python.call("builtins", "repr", new[first], new["repr"]));
print(Python.call("builtins", "repr", new[second], new["repr"]));
"""

    lines = _run_parser_program(body)

    assert lines[0] == "2"
    assert "Let" in lines[1]
    assert "Print" in lines[2]


def test_tiny_parser_reports_span_context():
    program = "\n\n".join(
        [
            AST_SRC,
            LEXER_SRC,
            PARSER_SRC,
            'define _ = parse_program("define a = ;");',
        ]
    )

    with pytest.raises(Exception, match=r"unexpected token SYM \(line 1, col 12\)"):
        compile_and_run(program)
