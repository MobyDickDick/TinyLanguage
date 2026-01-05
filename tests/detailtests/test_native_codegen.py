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


def test_collections_roundtrip_matches_interpreter():
    source = """
    define m = Map.new();
    define set_a = Map.set(m, "a", 1);
    define set_b = Map.set(m, "b", 2);
    print(Map.get(m, "a", 0));
    print(Map.has(m, "c"));
    define keys = Map.keys(m);
    print(heap_get(keys, 0));

    define s = Set.new();
    print(Set.add(s, "x"));
    print(Set.has(s, "x"));

    define q = Deque.new(new[1, 2]);
    define pushed = Deque.push_left(q, 0);
    print(Deque.pop_right(q));
    print(set_a, set_b, pushed);
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


def test_native_backend_supports_module_imports(tmp_path):
    module_src = """
    define value = 7;
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


def test_operator_overloads_roundtrip_matches_interpreter():
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

    define left = new Counter { total: 2; tag: "L" };
    define right = new Counter { total: 3; tag: "R" };
    define combined = left + right;
    print(combined.total, combined.tag);

    if (left == right) {
        print("equal");
    } else {
        print("diff");
    }
    """
    _assert_native_matches(source)


def test_unsupported_constructs_signal_not_implemented():
    source = """
    define x = { a: 1 };
    print(x);
    """

    with pytest.raises(NotImplementedError):
        run_with_native_backend(source)
