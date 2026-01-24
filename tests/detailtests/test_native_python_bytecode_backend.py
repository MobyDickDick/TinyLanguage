"""Tests ensuring the Python bytecode backend matches native output."""

from tiny_language import run_with_native_backend, run_with_python_bytecode_backend


def test_bytecode_backend_matches_native_simple_math() -> None:
    """Compare simple arithmetic output between native and bytecode backends."""
    src = "def x = 2; def y = 3; print(x + y);"
    native_output = run_with_native_backend(src)
    bytecode_output = run_with_python_bytecode_backend(src)
    assert bytecode_output == native_output


def test_bytecode_backend_handles_functions_and_loops() -> None:
    """Verify functions and loops behave identically across backends."""
    src = """
    fn add_twice(a, b) {
        return a + b + b;
    }

    def total = 0;
    def i = 0;
    while (i < 3) {
        total = add_twice(total, i);
        i = i + 1;
    }
    print(total);
    """
    native_output = run_with_native_backend(src)
    bytecode_output = run_with_python_bytecode_backend(src)
    assert bytecode_output == native_output
