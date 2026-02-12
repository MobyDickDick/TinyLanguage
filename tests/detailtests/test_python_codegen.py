"""Tests for python codegen."""

from tiny_language import compile_and_run, compile_to_python_source, run_with_python_backend


def test_python_backend_executes_basic_program():
    """Test that python backend executes basic program."""
    src = """
    fn add(x, y) {
        return x + y;
    }

    def total = add(2, 3);
    print(total);
    """

    interpreted = compile_and_run(src)
    generated = run_with_python_backend(src)

    assert interpreted == "5\n"
    assert generated == interpreted


def test_emit_python_source_contains_entrypoint():
    """Test that emit python source contains entrypoint."""
    src = "print(1 + 1);"
    emitted = compile_to_python_source(src)

    assert "def tiny_main" in emitted


def test_python_backend_supports_comparisons_and_method_calls():
    """Python backend should support comparisons and method calls."""
    src = """
    def lower = String.lower("hello");
    def less = 1 < 2;
    def less_equal = 2 <= 2;
    print(lower, less, less_equal);
    """

    interpreted = compile_and_run(src)
    generated = run_with_python_backend(src)

    assert interpreted == "hello true true\n"
    assert generated == interpreted
