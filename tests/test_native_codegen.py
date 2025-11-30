import pytest

from tiny_language import compile_and_run, run_with_native_backend


def _assert_native_matches(source: str) -> None:
    interpreter_output = compile_and_run(source)
    native_output = run_with_native_backend(source)
    assert native_output == interpreter_output


def test_arithmetic_and_print_roundtrip():
    source = """
    define a = 1 + 2 * 3;
    define b = (a - 2) / 2;
    print(a, b);
    """
    _assert_native_matches(source)


def test_function_calls_and_recursion():
    source = """
    fn add(x, y) { return x + y; }

    fn fib(n) {
        if (n <= 1) { return n; }
        return add(fib(n - 1), fib(n - 2));
    }

    print(fib(5));
    """
    _assert_native_matches(source)


def test_control_flow_and_assignment():
    source = """
    define i = 0;
    define acc = 0;

    while (i < 4) {
        if (i == 2) { acc = acc + 3; } else { acc = acc + i; }
        i = i + 1;
    }

    print(acc);
    """
    _assert_native_matches(source)


def test_boolean_formatting_matches_interpreter():
    source = """
    define a = true;
    define b = false;
    print(a, b, a && b, a || b);
    """
    interpreter_output = compile_and_run(source)
    native_output = run_with_native_backend(source)
    assert native_output == interpreter_output
