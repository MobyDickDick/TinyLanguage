import subprocess
import sys
from pathlib import Path

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


def test_heap_roundtrip_matches_interpreter():
    source = """
    define p = new(2);
    heap_set(p, 0, 10);
    heap_set(p, 1, 20);
    print(heap_get(p, 0), heap_get(p, 1));
    """
    _assert_native_matches(source)


def test_array_literal_roundtrip_matches_interpreter():
    source = """
    define p = new[7, 8, 9];
    print(heap_get(p, 0), heap_get(p, 2));
    """
    _assert_native_matches(source)


def test_native_cli_flag_executes_program(tmp_path):
    script = """
    define x = 2;
    define y = 3;
    fn add(a, b) { return a + b; }
    print(add(x, y));
    """
    src_file = tmp_path / "program.tiny"
    src_file.write_text(script)

    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[2] / "src" / "tiny_language.py"), "--native-backend", str(src_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "5"


def test_class_methods_roundtrip_matches_interpreter():
    source = """
    class Point {
        x: number;
        y: number;
        fn sum(self) { return self.x + self.y; }
        fn move(self, dx, dy) {
            self.x = self.x + dx;
            self.y = self.y + dy;
            return self.sum();
        }
    }

    define p = new Point { x: 2; y: 3 };
    print(p.sum());
    print(p.move(1, 2));
    print(p.x, p.y);
    """
    _assert_native_matches(source)


def test_unsupported_constructs_signal_not_implemented():
    source = """
    define x = { a: 1 };
    print(x);
    """

    with pytest.raises(NotImplementedError):
        run_with_native_backend(source)
