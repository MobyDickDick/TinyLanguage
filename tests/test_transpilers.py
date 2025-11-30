import textwrap

import pytest

from tiny_language_transpilers import (
    Assign,
    BinaryOp,
    Call,
    CppTranspiler,
    ExprStmt,
    FunctionIR,
    JavaScriptTranspiler,
    JuliaTranspiler,
    Literal,
    Name,
    ProgramIR,
    PythonTranspiler,
    Return,
)


def sample_program():
    body = [Assign("total", BinaryOp("+", Name("a"), Name("b"))), Return(Name("total"))]
    return ProgramIR(functions=[FunctionIR(name="add", params=["a", "b"], body=body)])


def test_python_roundtrip():
    program = sample_program()
    transpiler = PythonTranspiler()
    source = transpiler.to_source(program)
    assert "def add(a, b):" in source
    parsed = transpiler.from_source(source)
    assert parsed == program


def test_other_languages_render_expected_shape():
    program = sample_program()

    julia = JuliaTranspiler().to_source(program)
    assert "function add(a, b)" in julia
    assert "end" in julia.splitlines()[-1]

    js = JavaScriptTranspiler().to_source(program)
    assert js.startswith("function add(a, b) {")
    assert js.strip().endswith("}")

    cpp = CppTranspiler().to_source(program)
    assert cpp.startswith("auto add(auto a, auto b) {")
    assert cpp.strip().endswith("}")


def test_cross_language_parsing_to_ir():
    expected = sample_program()

    python_src = textwrap.dedent(
        """
        def add(a, b):
            total = a + b
            return total
        """
    )
    julia_src = textwrap.dedent(
        """
        function add(a, b)
            total = a + b
            return total
        end
        """
    )
    js_src = textwrap.dedent(
        """
        function add(a, b) {
          const total = a + b;
          return total;
        }
        """
    )
    cpp_src = textwrap.dedent(
        """
        auto add(auto a, auto b) {
          auto total = a + b;
          return total;
        }
        """
    )

    assert PythonTranspiler().from_source(python_src) == expected
    assert JuliaTranspiler().from_source(julia_src) == expected
    assert JavaScriptTranspiler().from_source(js_src) == expected
    assert CppTranspiler().from_source(cpp_src) == expected


def test_expression_statements_render_across_languages():
    program = ProgramIR(
        functions=[],
        body=[ExprStmt(Call("print", [Literal("ready")]))],
    )

    python_source = PythonTranspiler().to_source(program)
    assert python_source.strip() == "print('ready')"

    js_source = JavaScriptTranspiler().to_source(program)
    assert js_source.strip() == "print('ready');"

    cpp_source = CppTranspiler().to_source(program)
    assert cpp_source.strip() == "print('ready');"

    julia_source = JuliaTranspiler().to_source(program)
    assert julia_source.strip() == "print('ready')"
