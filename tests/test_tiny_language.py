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


def test_double_definition_error():
    expect_compile_error(
        """
        define a = 2 + 3;
        define a = 4 + 5;
        """,
        r"variable a defined twice in a row",
    )


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


def test_power_operator():
    out = run_tiny(
        """
        print(2 ^ 3);
        print(2 ^ 3 ^ 2);
        """
    )
    assert out == "8\n512\n"


def test_power_operator_requires_integer_exponent():
    expect_compile_error(
        """
        print(2 ^ 0.5);
        """,
        r"exponent for \^ must be an integer",
    )


def test_power_function_allows_fractional_exponent():
    out = run_tiny(
        """
        print(power(81, 0.5));
        print(power(2, 0.5));
        """
    )
    assert out == "9\n1.4142135623730951\n"


def test_scientific_notation_not_supported():
    expect_compile_error(
        """
        print(1.2e2);
        """,
        r"expected SYM \)"
    )


def test_comparisons():
    out = run_tiny(
        """
        print(3 > 2);
        print(3 >= 3);
        print(2 < 1);
        print(2 <= 2);
        print(3 == 3);
        print(3 != 2);
        print(2 != 2);
        """
    )
    assert out == "true\ntrue\nfalse\ntrue\ntrue\ntrue\nfalse\n"


def test_boolean_literals_and_logic():
    out = run_tiny(
        """
        print(true);
        print(false);
        print(not false);
        print(true and false);
        print(true or false);
        print(false || (1 < 2));
        """,
    )

    assert out == "true\nfalse\ntrue\nfalse\ntrue\ntrue\n"


def test_len_and_variadic_print():
    out = run_tiny(
        """
        define arr = new[1, 2, 3, 4];
        print(len(arr));
        print(len("hi!"));
        print("values", 1 < 2, len(arr));
        """,
    )

    assert out == "4\n3\nvalues true 4\n"


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


def test_namespaced_functions_and_scoping():
    out = run_tiny(
        """
        namespace Math {
            fn add(a, b) { return a + b; }
            fn inc(x) { return add(x, 1); }
        }

        namespace Strings {
            fn add(a, b) { return a + b; }
        }

        print(Math.add(2, 3));
        print(Strings.add("hi", "!"));
        print(Math.inc(4));
        """
    )

    assert out == "5\nhi!\n5\n"


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


def test_class_inheritance_with_conflicting_fields_and_methods():
    out = run_tiny(
        """
        class BaseOne {
            myProperty: number;

            fn init(self, v) {
                self.myProperty = v;
                return self;
            }

            fn get(self) { return self.myProperty; }
        }

        class BaseTwo {
            myProperty: number;

            fn init(self, v) {
                self.myProperty = v;
                return self;
            }

            fn get(self) { return self.myProperty + 10; }
        }

        class Derived: BaseOne, BaseTwo {
            myProperty: number;

            fn init(self, a, b, c) {
                BaseOne.myProperty = a;
                BaseTwo.myProperty = b;
                self.myProperty = c;
                return self;
            }

            fn totals(self) { return BaseOne.myProperty + BaseTwo.myProperty + self.myProperty; }
            fn base_calls(self) { return BaseOne.get() + BaseTwo.get() + 0 * self.myProperty; }
        }

        define d = new Derived { };
        d = d.init(1, 2, 3);
        print(d.totals());
        print(d.base_calls());
        """
    )

    assert out == "6\n13\n"


def test_must_use_unused_param_function():
    src = """
    fn f(a, b) {
        print(a);
        return a;
    }
    """
    expect_compile_error(src, r"unused parameter\(s\) in function f: b")


def test_param_mutation_must_be_returned_function():
    src = """
    fn bump(a) {
        a = a + 1;
        return 0;
    }
    """
    expect_compile_error(src, r"mutated parameter\(s\) in function bump must be returned: a")


def test_param_mutation_returned_allows_change():
    src = """
    fn bump(a) {
        a = a + 1;
        return { a: a, e: 0 };
    }

    { a, e } = bump(1);
    print(a);
    print(e);
    """
    out = run_tiny(src)
    assert out == "2\n0\n"


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


def test_unused_binding_in_nested_block_function():
    src = """
    fn g(a) {
        if (true) {
            define t = 99;
        }
        return a;
    }
    """
    expect_compile_error(src, r"unused local binding\(s\): t")


def test_unused_binding_in_nested_block_method():
    src = """
    class Box {
        fn touch(self, v) {
            while (false) {
                define tmp = v;
            }
            return self;
        }
    }
    """
    expect_compile_error(src, r"unused local binding\(s\): tmp")


def test_method_param_mutation_must_be_returned():
    src = """
    class Box {
        value: number;

        fn set(self, v) {
            self.value = v;
            return 0;
        }
    }
    """

    expect_compile_error(src, r"mutated parameter\(s\) in method Box.set must be returned: self")


def test_ok_function_call_as_argument():
    src = """
    fn one() { return 1; }
    print(one());
    """
    out = run_tiny(src)
    assert out == "1\n"


def test_destructure_requires_all_call_args():
    src = """
    fn f(a) { return { a: a + 1, e: 0 }; }
    define a = 3;
    { a, e } = f(a);
    print(a);
    print(e);
    """
    out = run_tiny(src)
    assert out == "4\n0\n"


def test_destructure_missing_input_variable_fails():
    src = """
    fn f(a) { return { a: a + 1, e: 0 }; }
    define a = 3;
    { b, e } = f(a);
    """
    expect_compile_error(src, r"destructuring call to f must include output for argument\(s\): a")


def test_method_param_mutation_returned_allows_change():
    src = """
    class Box {
        value: number;

        fn set(self, v) {
            self.value = v;
            return self;
        }
    }

    define b = new Box { value: 1; };
    b = b.set(5);
    print(b.value);
    """

    out = run_tiny(src)
    assert out == "5\n"


def test_error_message_for_missing_heap_index():
    src = """
    define a = new[1, 2];
    print(heap_get(a, 5));
    print(errorMessage);
    """

    out = run_tiny(src)
    assert out == "None\nheap access error: index 5 out of range for pointer 1\n"


def test_error_message_for_missing_field():
    src = """
    define o = { existing: 1; };
    print(o.missing);
    print(errorMessage);
    """

    out = run_tiny(src)
    assert out == "None\nunknown field missing\n"


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
def test_rosetta_fibonacci_program():
    program = pathlib.Path(__file__).resolve().parents[1] / "rosetta_fibonacci.tiny"

    out = run_file(str(program))

    expected = "\n".join(
        [
            "0",
            "1",
            "1",
            "2",
            "3",
            "5",
            "8",
            "13",
            "21",
            "34",
        ]
    ) + "\n"

    assert out == expected


def test_number_class_with_operator_overloads():
    src = """
    class Number {
        value: number;
    }

    fn Number(v) {
        return new Number { value: v; };
    }

    operator + (a: Number, b: Number) -> Number { return Number(a.value + b.value); }
    operator - (a: Number, b: Number) -> Number { return Number(a.value - b.value); }
    operator * (a: Number, b: Number) -> Number { return Number(a.value * b.value); }
    operator / (a: Number, b: Number) -> Number { return Number(a.value / b.value); }

    define a = Number(5);
    define b = Number(7.5);

    define c = a + b;
    define d = a - b;
    define e = a * b;
    define f = a / b;

    print(c.value);
    print(d.value);
    print(e.value);
    print(f.value);
    """

    out = run_tiny(src)

    assert out == "12.5\n-2.5\n37.5\n0.6666666666666666\n"


def test_spawn_and_join():
    out = run_tiny(
        """
        fn add(x, y) {
            return x + y;
        }

        define first = spawn add(2, 3);
        define second = spawn add(4, 5);

        print(join(first));
        print(join(second));
        """
    )

    assert out == "5\n9\n"

