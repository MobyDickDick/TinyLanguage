import json
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import Environment, Lexer, NamespaceRef, Parser, Runtime, register_stdlib
from tiny_language_transpilers import (
    Assign,
    BinaryOp,
    CppTranspiler,
    FunctionIR,
    JavaScriptTranspiler,
    JuliaTranspiler,
    Name,
    ProgramIR,
    PythonTranspiler,
    Return,
)

TINY_TRANSPILER_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_transpilers.tiny").read_text(encoding="utf-8")

TINY_TRANSPILER_DRIVER = """
fn __build_program() {
    define body = new[
        Assign("total", BinaryOp("+", Name("a"), Name("b"))),
        Return(Name("total"))
    ];
    define fn_ir = FunctionIR("add", new["a", "b"], body);
    return ProgramIR(new[fn_ir], new[]);
}

fn __render_all() {
    define program = __build_program();
    define py = PythonTranspiler();
    define ju = JuliaTranspiler();
    define js = JavaScriptTranspiler();
    define cpp = CppTranspiler();
    define outputs = new[
        py.to_source(program),
        ju.to_source(program),
        js.to_source(program),
        cpp.to_source(program)
    ];
    define quoted = new[];
    define i = 0;
    while (i < len(outputs)) {
        define _ = Collections.push(quoted, __json_dump(heap_get(outputs, i)));
        i = i + 1;
    }
    return "[" + String.join(quoted, ",") + "]";
}

define __OUTPUTS = __render_all();
"""


def build_sample_program() -> ProgramIR:
    body = [Assign("total", BinaryOp("+", Name("a"), Name("b"))), Return(Name("total"))]
    return ProgramIR(functions=[FunctionIR(name="add", params=["a", "b"], body=body)])


def run_tiny_transpilers() -> list[str]:
    program = TINY_TRANSPILER_SRC + "\n\n" + TINY_TRANSPILER_DRIVER
    parser = Parser(Lexer(program), program)
    stmts = parser.parse()
    runtime = Runtime(program)
    runtime.stream_output = False
    env = Environment(parent=None, namespace=None, runtime=runtime)
    runtime.global_env = env
    register_stdlib(runtime, env, NamespaceRef)
    for stmt in stmts:
        runtime.eval_stmt(stmt, env)
    return json.loads(env.get("__OUTPUTS"))


def test_tiny_transpiler_rendering_matches_python() -> None:
    program = build_sample_program()
    expected = [
        PythonTranspiler().to_source(program),
        JuliaTranspiler().to_source(program),
        JavaScriptTranspiler().to_source(program),
        CppTranspiler().to_source(program),
    ]
    outputs = run_tiny_transpilers()
    assert outputs == expected
