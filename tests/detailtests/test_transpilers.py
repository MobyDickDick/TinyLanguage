"""Tests for transpilers."""

import textwrap

import pytest

from tiny_language_transpilers import (
    Assign,
    BinaryOp,
    Call,
    CppTranspiler,
    ExprStmt,
    FunctionIR,
    IfElse,
    JavaScriptTranspiler,
    JuliaTranspiler,
    Literal,
    Name,
    ProgramIR,
    PythonTranspiler,
    Return,
    While,
)


def sample_program():
    """Helper to sample program."""
    body = [Assign("total", BinaryOp("+", Name("a"), Name("b"))), Return(Name("total"))]
    return ProgramIR(functions=[FunctionIR(name="add", params=["a", "b"], body=body)])


def control_flow_program():
    """Helper to control flow program."""
    loop_body = [
        IfElse(
            BinaryOp("==", Name("x"), Literal(2)),
            then_body=[Return(Name("x"))],
            else_body=[Assign("x", BinaryOp("+", Name("x"), Literal(1)))],
        )
    ]
    body = [
        Assign("total", Literal(0)),
        While(BinaryOp("<", Name("x"), Literal(3)), loop_body),
        Return(Name("total")),
    ]
    return ProgramIR(functions=[FunctionIR(name="loop", params=["x"], body=body)])


def literal_program():
    """Helper to literal program."""
    body = [
        Assign("flag", Literal(True)),
        Assign("name", Literal("hi")),
        Return(Literal(None)),
    ]
    return ProgramIR(functions=[FunctionIR(name="literals", params=[], body=body)])


def test_python_roundtrip():
    """Test that python roundtrip."""
    program = sample_program()
    transpiler = PythonTranspiler()
    source = transpiler.to_source(program)
    assert "def add(a, b):" in source
    parsed = transpiler.from_source(source)
    assert parsed == program


def test_other_languages_render_expected_shape():
    """Test that other languages render expected shape."""
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
    """Test that cross language parsing to ir."""
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
    """Test that expression statements render across languages."""
    program = ProgramIR(
        functions=[],
        body=[ExprStmt(Call("print", [Literal("ready")]))],
    )

    python_source = PythonTranspiler().to_source(program)
    assert python_source.strip() == "print('ready')"

    js_source = JavaScriptTranspiler().to_source(program)
    assert js_source.strip() == 'print("ready");'

    cpp_source = CppTranspiler().to_source(program)
    assert cpp_source.strip() == 'print("ready");'

    julia_source = JuliaTranspiler().to_source(program)
    assert julia_source.strip() == 'print("ready")'


def test_literal_rendering_across_languages():
    """Test that literal rendering across languages."""
    program = literal_program()

    python_source = PythonTranspiler().to_source(program)
    assert "flag = True" in python_source
    assert "name = 'hi'" in python_source
    assert "return None" in python_source

    julia_source = JuliaTranspiler().to_source(program)
    assert "flag = true" in julia_source
    assert 'name = "hi"' in julia_source
    assert "return nothing" in julia_source

    js_source = JavaScriptTranspiler().to_source(program)
    assert "flag = true;" in js_source
    assert 'name = "hi";' in js_source
    assert "return null;" in js_source

    cpp_source = CppTranspiler().to_source(program)
    assert "flag = true;" in cpp_source
    assert 'name = "hi";' in cpp_source
    assert "return nullptr;" in cpp_source


def test_control_flow_roundtrip_python():
    """Test that control flow roundtrip python."""
    program = control_flow_program()
    transpiler = PythonTranspiler()
    rendered = transpiler.to_source(program)
    assert "while x < 3:" in rendered
    parsed = transpiler.from_source(rendered)
    assert parsed == program


def test_control_flow_roundtrip_other_languages():
    """Test that control flow roundtrip other languages."""
    program = control_flow_program()

    julia = JuliaTranspiler()
    julia_source = julia.to_source(program)
    assert "while x < 3" in julia_source
    assert julia.from_source(julia_source) == program

    js = JavaScriptTranspiler()
    js_source = js.to_source(program)
    assert "while (x < 3) {" in js_source
    assert js.from_source(js_source) == program

    cpp = CppTranspiler()
    cpp_source = cpp.to_source(program)
    assert "while (x < 3) {" in cpp_source
    assert cpp.from_source(cpp_source) == program


def test_literal_roundtrip_parsing():
    """Test that literal roundtrip parsing."""
    expected = literal_program()

    python_src = textwrap.dedent(
        """
        def literals():
            flag = True
            name = "hi"
            return None
        """
    )

    julia_src = textwrap.dedent(
        """
        function literals()
            flag = true
            name = "hi"
            return nothing
        end
        """
    )

    js_src = textwrap.dedent(
        """
        function literals() {
          const flag = true;
          const name = "hi";
          return null;
        }
        """
    )

    cpp_src = textwrap.dedent(
        """
        auto literals() {
          auto flag = true;
          auto name = "hi";
          return nullptr;
        }
        """
    )

    assert PythonTranspiler().from_source(python_src) == expected
    assert JuliaTranspiler().from_source(julia_src) == expected
    assert JavaScriptTranspiler().from_source(js_src) == expected
    assert CppTranspiler().from_source(cpp_src) == expected


def test_control_flow_cross_language_parsing():
    """Test that control flow cross language parsing."""
    expected = control_flow_program()

    python_src = textwrap.dedent(
        """
        def loop(x):
            total = 0
            while x < 3:
                if x == 2:
                    return x
                else:
                    x = x + 1
            return total
        """
    )

    julia_src = textwrap.dedent(
        """
        function loop(x)
            total = 0
            while x < 3
                if x == 2
                    return x
                else
                    x = x + 1
                end
            end
            return total
        end
        """
    )

    js_src = textwrap.dedent(
        """
        function loop(x) {
          let total = 0;
          while (x < 3) {
            if (x == 2) {
              return x;
            } else {
              x = x + 1;
            }
          }
          return total;
        }
        """
    )

    cpp_src = textwrap.dedent(
        """
        auto loop(auto x) {
          auto total = 0;
          while (x < 3) {
            if (x == 2) {
              return x;
            } else {
              x = x + 1;
            }
          }
          return total;
        }
        """
    )

    assert PythonTranspiler().from_source(python_src) == expected
    assert JuliaTranspiler().from_source(julia_src) == expected
    assert JavaScriptTranspiler().from_source(js_src) == expected
    assert CppTranspiler().from_source(cpp_src) == expected


@pytest.mark.parametrize(
    "transpiler, code",
    [
        (
            PythonTranspiler(),
            """
            def combine(a, b):
                return a and b
            """,
        ),
        (
            JuliaTranspiler(),
            """
            function combine(a, b)
                return a && b
            end
            """,
        ),
        (
            JavaScriptTranspiler(),
            """
            function combine(a, b) {
              return a && b;
            }
            """,
        ),
        (
            CppTranspiler(),
            """
            auto combine(auto a, auto b) {
              return a && b;
            }
            """,
        ),
    ],
)
def test_unsupported_boolean_operations_raise(transpiler, code):
    """Test that unsupported boolean operations raise."""
    with pytest.raises(ValueError):
        transpiler.from_source(textwrap.dedent(code))
