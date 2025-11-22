import pathlib
import re
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import compile_and_run, main, run_file


def run_tiny(src: str) -> str:
    return compile_and_run(src)


def expect_compile_error(src: str, pattern: str) -> None:
    with pytest.raises(Exception, match=pattern):
        compile_and_run(src)


def test_lexer_basics_define():
    out = run_tiny(
        """
        define a = 7;
        print(a);
        """
    )
    assert out == "7\n"


def test_arithmetic_and_print_with_define():
    out = run_tiny(
        """
        define a = 7 + 5 * 2;
        print(a);
        """
    )
    assert out == "17\n"


def test_comparisons():
    out = run_tiny(
        """
        print(3 > 2);
        print(3 >= 3);
        print(2 < 1);
        print(2 <= 2);
        print(3 == 3);
        """
    )
    assert out == "true\ntrue\nfalse\ntrue\ntrue\n"


def test_function_return_call():
    out = run_tiny(
        """
        fn add(a, b) {
            print(a);     // beide Parameter werden verwendet
            return a + b;
        }
        define r = add(10, 5);
        print(r);
        """
    )
    assert out == "10\n15\n"


def test_while_if_else():
    out = run_tiny(
        """
        define i = 0;
        define s = 0;
        while (i < 4) {
            if (i == 2) {
                define t = 100;
                print(t);
            } else {
                define u = 1;
                print(u);
            }
            s = s + 1;
            i = i + 1;
        }
        print(s);
        """
    )
    assert out == "1\n1\n100\n1\n4\n"


def test_heap_ops_and_tag():
    out = run_tiny(
        """
        define p = new(3);

        { e } = heap_set(p, 0, 11); print(e.code);
        { e } = heap_set(p, 1, 22); print(e.code);
        { e } = heap_set(p, 2, 33); print(e.code);

        print(heap_get(p, 0));
        print(heap_get(p, 1));
        print(heap_get(p, 2));

        { e } = tag(p, Arr); print(e.code);

        { e } = delete(p);   print(e.code);
        """
    )
    assert out == "0\n0\n0\n11\n22\n33\n0\n0\n"


def test_pointer_of_arrays():
    out = run_tiny(
        """
        // flat init
        define p = new(3);
        { e } = heap_set(p, 0, 11); print(e.code);
        { e } = heap_set(p, 1, 22); print(e.code);
        { e } = heap_set(p, 2, 33); print(e.code);
        print(heap_get(p, 0));
        print(heap_get(p, 1));
        print(heap_get(p, 2));

        // literal init
        define q = new[7, 8, 9];
        print(heap_get(q, 0));
        print(heap_get(q, 1));
        print(heap_get(q, 2));

        // nested: array of pointers
        define a = new[1, 2, 3];
        define b = new[4, 5];

        define r = new(2);
        { e } = heap_set(r, 0, a); print(e.code);
        { e } = heap_set(r, 1, b); print(e.code);

        print(heap_get(heap_get(r, 0), 2)); // a[2] == 3
        print(heap_get(heap_get(r, 1), 1)); // b[1] == 5

        { e } = delete(a); print(e.code);
        { e } = delete(b); print(e.code);
        { e } = delete(p); print(e.code);
        { e } = delete(q); print(e.code);
        { e } = delete(r); print(e.code);
        """
    )
    assert out == "0\n0\n0\n11\n22\n33\n7\n8\n9\n0\n0\n3\n5\n0\n0\n0\n0\n0\n"


def test_classes_fields_methods():
    out = run_tiny(
        """
        class Point {
            x: number;
            y: number;

            fn init(self, x, y) {
                self.x = x;
                self.y = y;
                return self;
            }

            fn move(self, dx, dy) {
                self.x = self.x + dx;
                self.y = self.y + dy;
                return self;
            }

            fn sum(self) { return self.x + self.y; }
        }

        define p = new Point { x: 0; y: 0; };
        p = p.init(2, 3);
        p = p.move(1, -1);
        print(p.x);
        print(p.y);
        print(p.sum());
        """
    )
    assert out == "3\n2\n5\n"


def test_must_use_unused_param_function():
    src = """
    fn f(a, b) {
        print(a);
        return a;
    }
    """
    expect_compile_error(src, r"unused parameter\(s\) in function f: b")


def test_must_use_unused_local_binding_top_level():
    src = """
    define x = 1;
    print(42);
    """
    expect_compile_error(src, r"unused local binding\(s\): x")


def test_run_file_executes_source(tmp_path):
    src_file = tmp_path / "prog.tiny"
    src_file.write_text(
        """
        define x = 5;
        print(x + 1);
        """
    )

    out = run_file(str(src_file))
    assert out == "6\n"


def test_main_runs_and_writes_output(tmp_path, capsys):
    src_file = tmp_path / "prog.tiny"
    src_file.write_text("print(21 + 21);")

    exit_code = main([str(src_file)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "42\n"


def test_must_use_unused_local_binding_function():
    src = """
    fn g(a) {
        define t = 123;
        print(a);
        return a;
    }
    """
    expect_compile_error(src, r"unused local binding\(s\): t")


def test_must_use_bare_call_forbidden():
    src = """
    fn h() { return 1; }
    h();
    """
    expect_compile_error(src, r"bare call statements are not allowed")


def test_must_use_destructure_all_fields():
    src = """
    fn make() { return { p: 1, e: 0 }; }
    { p, e } = make();
    print(p);
    """
    expect_compile_error(src, r"unused local binding\(s\): e")


def test_ok_destructure_both_values():
    src = """
    fn make() { return { p: 1, e: 0 }; }
    { p, e } = make();
    print(p);
    print(e);
    """
    out = run_tiny(src)
    assert out == "1\n0\n"


def test_ok_function_call_as_argument():
    src = """
    fn one() { return 1; }
    print(one());
    """
    out = run_tiny(src)
    assert out == "1\n"


def test_typedef_simple_record():
    src = """
    type Error {
        code: number;
        msg: string;
    }

    fn make_error(c, m) {
        return { code: c, msg: m };
    }

    print(__type_field_type("Error", "code"));
    print(__type_field_type("Error", "msg"));
    """
    out = run_tiny(src)
    assert out == "number\nstring\n"
