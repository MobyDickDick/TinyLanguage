from native_ir import format_program
from tiny_language import NativeCodeGenerator, _parse_and_lint


def test_format_program_lists_entry_and_functions():
    source = """
    fn add(x, y) { return x + y; }

    def a = 1;
    def b = 2;
    print(add(a, b));
    """

    stmts = _parse_and_lint(source)
    program = NativeCodeGenerator().compile_program(stmts)

    formatted = format_program(program)

    assert "entry[00]: PUSH_CONST 1" in formatted
    assert "entry[02]: PUSH_CONST 2" in formatted
    assert "entry[06]: CALL ('add', 2)" in formatted
    assert "function add(x, y)" in formatted
    assert "add[00]: LOAD x" in formatted
