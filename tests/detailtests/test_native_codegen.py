"""Regression tests for the TinyLanguage native code generation pipeline."""

import subprocess
import sys
from pathlib import Path

import pytest

from tiny_language import compile_and_run, run_with_native_backend


def _assert_native_matches(source: str) -> None:
    """Compile with both backends and assert that outputs are identical."""
    interpreter_output = compile_and_run(source)
    native_output = run_with_native_backend(source)
    assert native_output == interpreter_output


def test_arithmetic_and_print_roundtrip():
    """Ensure arithmetic expressions are compiled with identical output."""
    source = """
    def a = 1 + 2 * 3;
    def b = (a - 2) / 2;
    print(a, b);
    """
    _assert_native_matches(source)


def test_function_calls_and_recursion():
    """Exercise function calls and recursion in the native backend."""
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
    """Validate control flow and variable assignments match interpreter output."""
    source = """
    def i = 0;
    def acc = 0;

    while (i < 4) {
        if (i == 2) { acc = acc + 3; } else { acc = acc + i; }
        i = i + 1;
    }

    print(acc);
    """
    _assert_native_matches(source)


def test_switch_roundtrip_matches_interpreter():
    """Verify switch/case dispatch produces the same printed output."""
    source = """
    def value = 2;
    switch (value) {
        case 1: { print("one"); }
        case 2: { print("two"); }
        default: { print("other"); }
    }
    """
    _assert_native_matches(source)


def test_boolean_formatting_matches_interpreter():
    """Check boolean formatting is aligned between backend outputs."""
    source = """
    def a = true;
    def b = false;
    print(a, b, a && b, a || b);
    """
    interpreter_output = compile_and_run(source)
    native_output = run_with_native_backend(source)
    assert native_output == interpreter_output


def test_not_operator_roundtrip_matches_interpreter():
    """Ensure logical negation operators behave consistently."""
    source = """
    def a = true;
    def b = false;
    print(not a, not b, !b, not (1 == 2));
    """
    _assert_native_matches(source)


def test_heap_roundtrip_matches_interpreter():
    """Exercise heap allocation and mutations in the native backend."""
    source = """
    def p = new(2);
    def set1 = heap_set(p, 0, 10);
    if (set1.e.code != 0) { print(set1.e.msg); }
    def set2 = heap_set(p, 1, 20);
    if (set2.e.code != 0) { print(set2.e.msg); }
    print(heap_get(p, 0), heap_get(p, 1));
    """
    _assert_native_matches(source)


def test_array_literal_roundtrip_matches_interpreter():
    """Confirm array literal creation matches interpreter output."""
    source = """
    def p = new[7, 8, 9];
    print(heap_get(p, 0), heap_get(p, 2));
    """
    _assert_native_matches(source)


def test_collections_roundtrip_matches_interpreter():
    """Cover core collection types (Map, Set, Deque) in the native backend."""
    source = """
    def m = Map.new();
    def set_a = Map.set(m, "a", 1);
    def set_b = Map.set(m, "b", 2);
    print(Map.get(m, "a", 0));
    print(Map.has(m, "c"));
    def keys = Map.keys(m);
    print(heap_get(keys, 0));

    def s = Set.new();
    print(Set.add(s, "x"));
    print(Set.has(s, "x"));

    def q = Deque.new(new[1, 2]);
    def pushed = Deque.push_left(q, 0);
    print(Deque.pop_right(q));
    print(set_a, set_b, pushed);
    """
    _assert_native_matches(source)


def test_native_cli_flag_executes_program(tmp_path):
    """Run the CLI with native backend flag to ensure full program execution."""
    script = """
    def x = 2;
    def y = 3;
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


def test_native_backend_supports_module_imports(tmp_path):
    """Ensure module resolution and imports work for the native backend."""
    module_src = """
    def value = 7;
    fn add(a, b) { return a + b; }
    fn get_value() { return value; }
    """
    main_src = """
    import helpers;
    print(helpers.add(2, 3));
    print(helpers.value);
    """
    module_path = tmp_path / "helpers.tiny"
    module_path.write_text(module_src)
    main_path = tmp_path / "main.tiny"
    main_path.write_text(main_src)

    interpreter_output = compile_and_run(
        main_path.read_text(),
        module_path=main_path,
        module_namespace="main",
    )
    native_output = run_with_native_backend(
        main_path.read_text(),
        module_path=main_path,
        module_namespace="main",
    )
    assert native_output == interpreter_output


def test_class_methods_roundtrip_matches_interpreter():
    """Verify class methods and field mutations execute consistently."""
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

    def p = new Point { x: 2; y: 3 };
    print(p.sum());
    print(p.move(1, 2));
    print(p.x, p.y);
    """
    _assert_native_matches(source)


def test_match_and_variants_roundtrip_matches_interpreter():
    """Validate sum types and pattern matching in native execution."""
    source = """
    type Result = sum {
        def _unused22 = Ok(value: Number);
        def _unused23 = Err(msg: String);
    }

    fn unwrap(result) {
        return match(result) {
            case Ok(v) => v;
            case Err(_) => 0;
        };
    }

    def ok = Ok { value: 7 };
    def err = Err { msg: "oops" };
    print(unwrap(ok));
    print(unwrap(err));
    """
    _assert_native_matches(source)


def test_operator_overloads_roundtrip_matches_interpreter():
    """Check operator overloading for custom classes in native backend."""
    source = """
    class Counter {
        total: number;
        tag: string;
    }

    operator + (a: Counter, b: Counter) -> Counter {
        return new Counter { total: a.total + b.total; tag: a.tag + "+" + b.tag };
    }

    operator == (a: Counter, b: Counter) -> Bool {
        return a.total == b.total && a.tag == b.tag;
    }

    def left = new Counter { total: 2; tag: "L" };
    def right = new Counter { total: 3; tag: "R" };
    def combined = left + right;
    print(combined.total, combined.tag);

    if (left == right) {
        print("equal");
    } else {
        print("diff");
    }
    """
    _assert_native_matches(source)


def test_python_interop_roundtrip_matches_interpreter():
    """Exercise Python interop to match interpreter results."""
    source = """
    def math = Python.import_module("math", new["sqrt", "tau"]);
    print(math.sqrt(9));
    print(math.tau);
    def chars = Python.call("builtins", "list", new["ab"], new["list"]);
    print(heap_get(chars, 0));
    """
    _assert_native_matches(source)


def test_python_call_requires_allowlist_in_native_backend():
    """Ensure Python interop enforces allowlist restrictions."""
    source = """
    def value = Python.call("math", "sqrt", new[9]);
    print(value);
    """

    with pytest.raises(RuntimeError):
        run_with_native_backend(source)


def test_unsupported_constructs_signal_not_implemented():
    """Validate that unsupported constructs are surfaced as errors."""
    source = """
    def x = { a: 1 };
    print(x);
    """

    with pytest.raises(NotImplementedError):
        run_with_native_backend(source)
