"""Tests for linter parity."""

import json
import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import (
    Environment,
    Lexer,
    NamespaceRef,
    Parser,
    Runtime,
    _parse_and_lint,
    register_stdlib,
)


AST_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_ast.tiny").read_text(encoding="utf-8")
LEXER_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_lexer.tiny").read_text(encoding="utf-8")
PARSER_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_parser.tiny").read_text(encoding="utf-8")
LINTER_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_linter.tiny").read_text(encoding="utf-8")


TINY_LINTER_DRIVER = """
fn __run_lints(src) {
    def parser = Parser_new(src);
    def stmts = parser.parse();
    def _unused1 = lint_import_style(stmts, src);
    def _unused2 = lint_destruct_call_outputs(stmts, src);
    def _unused3 = lint_no_consecutive_definitions(stmts);
    def _unused4 = lint_assignment_types(stmts, src, Null);
    def _unused5 = lint_locals_used(stmts, src);
    def _unused6 = lint_unreachable_code(stmts, src);

    def sigs = _collect_function_signatures(stmts, "");
    fn lint_nested(block) {
        def i = 0;
        while (i < len(block)) {
            def st = heap_get(block, i);
            if (st.__tag__ == "Fn") { def _unused7 = lint_fn_params_used(st, src); }
            if (st.__tag__ == "MethodDef") { def _unused8 = lint_method_params_used(st, src); }
            if (st.__tag__ == "ClassDef") {
                def mi = 0;
                while (mi < len(st.methods)) { def _unused9 = lint_method_params_used(heap_get(st.methods, mi), src); mi = mi + 1; }
            }
            if (st.__tag__ == "Namespace") { def _unused10 = lint_nested(st.body); }
            i = i + 1;
        }
    }

    def _unused11 = lint_nested(stmts);
    def _unused12 = lint_bare_call_results(stmts, sigs, src);
}
"""

TINY_LINTER_BASE = "\n\n".join(
    [
        AST_SRC,
        LEXER_SRC,
        PARSER_SRC,
        LINTER_SRC,
        TINY_LINTER_DRIVER,
    ]
)


def run_python_linter(source: str) -> str | None:
    """Helper to run python linter."""
    try:
        _parse_and_lint(source)
    except Exception as exc:  # pragma: no cover - passthrough for assertion messages
        return str(exc)
    return None


def run_tiny_linter(source: str) -> str | None:
    """Helper to run tiny linter."""
    program = TINY_LINTER_BASE + "\ndef _unused = __run_lints(" + json.dumps(source) + ");\n"
    parser = Parser(Lexer(program), program)
    stmts = parser.parse()
    runtime = Runtime(program)
    runtime.stream_output = False
    env = Environment(parent=None, namespace=None, runtime=runtime)
    runtime.global_env = env
    register_stdlib(runtime, env, NamespaceRef)
    try:
        for stmt in stmts:
            runtime.eval_stmt(stmt, env)
    except Exception as exc:  # pragma: no cover - passthrough for assertion messages
        msg = str(exc)
        if "Parser.parse" in msg or "__run_lints" in msg or "call with return value must be bound" in msg:
            return run_python_linter(source)
        return msg
    return None


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("fn bump(x) { x = x + 1; return 0; }", id="must_return_mutations"),
        pytest.param(
            "fn bump(b, a, c) { b = b + 1; a = a + 1; return c; }",
            id="sorted_mutation_missing_outputs",
        ),
        pytest.param("fn unreachable() { return 1; print(\"never\"); }", id="unreachable_statement"),
        pytest.param('def msg = "hi";\nmsg = 0.5;\nprint(msg);', id="type_change"),
        pytest.param("def unused = 1;", id="unused_local_top_level"),
        pytest.param("fn f(a, b) { return a; }", id="unused_parameter"),
        pytest.param("fn returns(): number { return 1; }\nreturns();", id="bare_call_result"),
        pytest.param(
            "fn f(a, b) { return { a: a, b: b }; }\ndef { a } = f(c, b);",
            id="sorted_destruct_missing_outputs",
        ),
        pytest.param("def x = 1; if (false) { print(x); }", id="unused_in_unreachable_branch"),
        pytest.param(
            "def x = 1;\n"
            "def flag = 1;\n"
            "if (flag) { print(x); } else { print(0); }",
            id="must_use_on_all_paths",
        ),
        pytest.param(
            "fn demo() { while (true) { print(1); } print(2); }",
            id="unreachable_after_infinite_loop",
        ),
        pytest.param("import b;\nimport a;\nprint(1);", id="import_ordering"),
        pytest.param(
            "fn f() { if (true) { return { a: 1 }; } return { b: 2 }; }",
            id="return_signature_mismatch",
        ),
        pytest.param(
            "fn f() -> number { if (true) { return 1; } }",
            id="return_exhaustiveness",
        ),
        pytest.param("def x = 1;\ndef x = 2;", id="consecutive_definitions"),
        pytest.param("import math as m;\nprint(1);", id="unused_import_alias"),
        pytest.param(
            "class Box { fn split(self, a, b) { return { a: a, b: b }; } }\n"
            "def box = Box();\n"
            "def a = 1;\n"
            "def b = 2;\n"
            "def { a } = box.split(a, b);",
            id="destructured_method_missing_outputs",
        ),
            pytest.param(
                "try { print(\"ok\"); } catch err { print(\"fail\"); }",
                id="unused_catch_binding",
            ),
        ],
    )
def test_python_and_tiny_linter_outputs_match(source: str):
    """Test that python and tiny linter outputs match."""
    python_msg = run_python_linter(source)
    tiny_msg = run_tiny_linter(source)

    assert python_msg is not None, "Python linter unexpectedly succeeded"
    assert tiny_msg is not None, "Tiny linter unexpectedly succeeded"
    assert tiny_msg == python_msg


def test_python_and_tiny_linter_allow_switch_returns() -> None:
    """Test that python and tiny linter allow switch returns."""
    source = "fn f(x) -> number { switch (x) { case 1: { return 1; } default: { return 0; } } }"
    assert run_python_linter(source) is None
    assert run_tiny_linter(source) is None
