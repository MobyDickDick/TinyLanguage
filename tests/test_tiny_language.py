"""Tests for tiny language."""

import io
import pathlib
import re
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from tests.utils import run_tiny

from tiny_language import Runtime, compile_and_run, main, run_file
from tiny_language_lexer import Lexer


def expect_compile_error(src: str, pattern: str) -> None:
    """Helper to expect compile error."""
    with pytest.raises(Exception, match=pattern):
        compile_and_run(src)


def test_double_definition_error():
    """Test that double definition error."""
    expect_compile_error(
        """
        def a = 2 + 3;
        def a = 4 + 5;
        """,
        r"variable a defined twice in a row",
    )


def test_prints_and_returns(capsys):
    """Test that prints and returns."""
    runtime = Runtime("")

    out = compile_and_run(
        """
        fn greet(name) {
            print("hi", name);
            return "ok";
        }

        print(greet("tiny"));
        """,
        runtime=runtime,
        stream_output=False,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert out == "hi tiny\nok\n"
    assert runtime.output == ["hi tiny\n", "ok\n"]


def test_reassign_with_different_type_errors():
    """Test that reassign with different type errors."""
    expect_compile_error(
        """
        def msg = "hi";
        msg = 0.5;
        print(msg);
        """,
        r"\[E014\] type change for variable msg: expected string but got float",
    )


def test_reassign_number_allows_float():
    """Test that reassign number allows float."""
    out = run_tiny(
        """
        def amount = 1;
        amount = 2.5;
        print(amount);
        """
    )
    assert out == "2.5\n"


def test_reassign_null_to_string_errors():
    """Test that reassign null to string errors."""
    expect_compile_error(
        """
        def maybe = Null;
        maybe = "now";
        print(maybe);
        """,
        r"\[E014\] type change for variable maybe: expected Null but got string",
    )


def test_inferred_return_type_stable_across_calls():
    """Test that inferred return type stable across calls."""
    expect_compile_error(
        """
        fn pick(flag) {
            if (flag) {
                return 1;
            }
            return "oops";
        }

        print(pick(true));
        print(pick(false));
        """,
        r"\[E014\] inferred return type for function pick changed: expected int but got string",
    )


def test_len_handles_heap_pointer():
    """Test that len handles heap pointer."""
    out = run_tiny(
        """
        def ptr = new(3);
        def ignored1 = heap_set(ptr, 0, 10);
        def ignored2 = heap_set(ptr, 1, 20);
        def ignored3 = heap_set(ptr, 2, 30);
        print(len(ptr));
        def _cleanup = delete(ptr);
        """
    )
    assert out == "3\n"


def test_len_reports_freed_pointer():
    """Test that len reports freed pointer."""
    expect_compile_error(
        """
        def ptr = new(1);
        def _cleanup = delete(ptr);
        print(len(ptr));
        """,
        r"\[E005\] len expects a sized value",
    )


def test_lexer_basics_define():
    """Test that lexer basics define."""
    out = run_tiny(
        """
        def a = 7;
        print(a);
        """
    )
    assert out == "7\n"


def test_lexer_multiline_string_span_tracks_end_line():
    """Test that lexer multiline string span tracks end line."""
    source = "\"a\nb\""
    lexer = Lexer(source)
    token = lexer.next_token()
    assert token.kind == "STRING"
    assert (token.start.line, token.start.column) == (1, 1)
    assert (token.stop.line, token.stop.column) == (2, 2)


def test_arithmetic_and_print_with_define():
    """Test that arithmetic and print with define."""
    out = run_tiny(
        """
        def a = 7 + 5 * 2;
        print(a);
        """
    )
    assert out == "17\n"


def test_power_operator():
    """Test that power operator."""
    out = run_tiny(
        """
        print(2 ^ 3);
        print(2 ^ 3 ^ 2);
        """
    )
    assert out == "8\n512\n"


def test_power_operator_allows_fractional_exponent():
    """Test that power operator allows fractional exponent."""
    out = run_tiny(
        """
        print(2 ^ 0.5);
        """
    )
    assert out == "1.4142135623730951\n"


def test_power_operator_rejects_fractional_negative_base():
    """Test that power operator rejects fractional negative base."""
    expect_compile_error(
        """
        print((-1) ^ 0.5);
        """,
        r"fractional exponent for \^ requires a non-negative base",
    )


def test_power_function_allows_fractional_exponent():
    """Test that power function allows fractional exponent."""
    out = run_tiny(
        """
        print(power(81, 0.5));
        print(power(2, 0.5));
        """
    )
    assert out == "9\n1.4142135623730951\n"


def test_scientific_notation_supported():
    """Test that scientific notation supported."""
    out = run_tiny(
        """
        print(1.2e2);
        print(1e3);
        """
    )
    assert out == "120.0\n1000\n"


def test_comparisons():
    """Test that comparisons."""
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
    """Test that boolean literals and logic."""
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
    """Test that len and variadic print."""
    out = run_tiny(
        """
        def arr = new[1, 2, 3, 4];
        print(len(arr));
        print(len("hi!"));
        print("values", 1 < 2, len(arr));
        def _unused0 = delete(arr);
        """,
    )

    assert out == "4\n3\nvalues true 4\n"


def test_switch_statement():
    """Test that switch statement."""
    out = run_tiny(
        """
        def value = 2;
        switch (value) {
            case 1: { print("one"); }
            case 2: { print("two"); }
            default: { print("other"); }
        }
        switch (value + 1) {
            case 3: { print("three"); }
            default: { print("fallback"); }
        }
        """
    )

    assert out == "two\nthree\n"


def test_function_return_call():
    """Test that function return call."""
    out = run_tiny(
        """
        fn add(a, b) {
            print(a);     // beide Parameter werden verwendet
            return a + b;
        }
        def r = add(10, 5);
        print(r);
        """
    )
    assert out == "10\n15\n"


def test_namespaced_functions_and_scoping():
    """Test that namespaced functions and scoping."""
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
    """Test that while if else."""
    out = run_tiny(
        """
        def i = 0;
        def s = 0;
        while (i < 4) {
            if (i == 2) {
                def t = 100;
                print(t);
            } else {
                def u = 1;
                print(u);
            }
            s = s + 1;
            i = i + 1;
        }
        print(s);
        """
    )
    assert out == "1\n1\n100\n1\n4\n"


def test_while_loop_skip_and_exit_conditions():
    """Test that while loop skip and exit conditions."""
    out = run_tiny(
        """
        def i = 0;
        def total = 0;
        def done = false;
        while (i < 5 && !done) {
            i = i + 1;
            if (i == 3) {
                // Skip adding 3 without using continue.
                def skip = true;
                if (!skip) {
                    total = total + i;
                }
            }
            if (i == 5) {
                done = true;
            } else {
                if (i != 3) {
                    total = total + i;
                }
            }
        }
        print(total);
        """
    )
    assert out == "7\n"


def test_heap_ops_and_tag():
    """Test that heap ops and tag."""
    out = run_tiny(
        """
        def p = new(3);

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
    """Test that pointer of arrays."""
    out = run_tiny(
        """
        // flat init
        def p = new(3);
        { e } = heap_set(p, 0, 11); print(e.code);
        { e } = heap_set(p, 1, 22); print(e.code);
        { e } = heap_set(p, 2, 33); print(e.code);
        print(heap_get(p, 0));
        print(heap_get(p, 1));
        print(heap_get(p, 2));

        // literal init
        def q = new[7, 8, 9];
        print(heap_get(q, 0));
        print(heap_get(q, 1));
        print(heap_get(q, 2));

        // nested: array of pointers
        def a = new[1, 2, 3];
        def b = new[4, 5];

        def r = new(2);
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
    """Test that classes fields methods."""
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

        def p = new Point { x: 0; y: 0; };
        p = p.init(2, 3);
        p = p.move(1, -1);
        print(p.x);
        print(p.y);
        print(p.sum());
        """
    )
    assert out == "3\n2\n5\n"


def test_class_inheritance_with_conflicting_fields_and_methods():
    """Test that class inheritance with conflicting fields and methods."""
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

        def d = new Derived { };
        d = d.init(1, 2, 3);
        print(d.totals());
        print(d.base_calls());
        """
    )

    assert out == "6\n13\n"


def test_must_use_unused_param_function():
    """Test that must use unused param function."""
    src = """
    fn f(a, b) {
        print(a);
        return a;
    }
    """
    expect_compile_error(src, r"unused parameter\(s\) in function f: b")


def test_call_stmt_counts_param_usage():
    """Test that call stmt counts param usage."""
    src = """
    def p = new(1);

    fn init(ptr) {
        def ignored1 = heap_set(ptr, 0, 99);
        return 0;
    }

    print(init(p));
    def _unused109 = delete(p);
    """

    assert run_tiny(src) == "0\n"


def test_param_mutation_must_be_returned_function():
    """Test that param mutation must be returned function."""
    src = """
    fn bump(a) {
        a = a + 1;
        return 0;
    }
    """
    expect_compile_error(src, r"mutated parameter\(s\) in function bump must be returned: a")


def test_param_mutation_returned_allows_change():
    """Test that param mutation returned allows change."""
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


def test_inconsistent_return_signature_in_function():
    """Test that inconsistent return signature in function."""
    src = """
    fn f(a) {
        if (a) {
            return { a: a + 1, e: 0 };
        }
        return { a: a + 2, e: 1, extra: 99 };
    }

    def _unused81 = f(1);
    """

    expect_compile_error(
        src,
        r"inconsistent return signature in function f: expected \{a, e\} but found \{a, e, extra\}",
    )


def test_must_use_unused_local_binding_top_level():
    """Test that must use unused local binding top level."""
    src = """
    def x = 1;
    print(42);
    """
    expect_compile_error(src, r"unused local binding\(s\): x")


def test_run_file_executes_source(tmp_path):
    """Test that run file executes source."""
    src_file = tmp_path / "prog.tiny"
    src_file.write_text(
        """
        def x = 5;
        print(x + 1);
        """
    )

    out = run_file(str(src_file))
    assert out == "6\n"


def test_main_runs_and_writes_output(run_program):
    """Test that main runs and writes output."""
    result = run_program("print(21 + 21);")

    assert result.returncode == 0
    assert result.stdout == "42\n"
    assert result.stderr == ""


def test_main_eval_executes_snippet(capsys):
    """Test that main eval executes snippet."""
    exit_code = main(["--eval", "print(3 * 4);"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "12\n"
    assert captured.err == ""


def test_main_eval_reports_error(capsys):
    """Test that main eval reports error."""
    exit_code = main(["--eval", "def x = ;"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "expected" in captured.err


def test_repl_executes_lines(monkeypatch, capsys):
    """Test that repl executes lines."""
    monkeypatch.setattr("sys.stdin", io.StringIO("print(2 + 3);\nprint(1);\n"))

    exit_code = main(["--repl"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "tiny> " in captured.out
    assert "5\ntiny> 1\n" in captured.out


def test_repl_reports_errors(monkeypatch, capsys):
    """Test that repl reports errors."""
    monkeypatch.setattr("sys.stdin", io.StringIO("def y = ;\n"))

    exit_code = main(["--repl"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "tiny> " in captured.out
    assert "expected" in captured.err


def test_repl_allows_underscore_binding(monkeypatch, capsys):
    """Test that repl allows underscore binding."""
    monkeypatch.setattr("sys.stdin", io.StringIO("def _ = 1;\nprint(0);\n"))

    exit_code = main(["--repl"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "tiny> " in captured.out
    assert "0\n" in captured.out
    assert captured.err == ""


def test_console_read_line_returns_input(monkeypatch):
    """Test that console read line returns input."""
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return "hello"

    monkeypatch.setattr("builtins.input", fake_input)

    out = run_tiny('print(Console.read_line("name: "));')

    assert out == "hello\n"
    assert prompts == ["name: "]


def test_console_read_line_handles_eof(monkeypatch):
    """Test that console read line handles eof."""
    def fake_input(prompt: str = "") -> str:
        raise EOFError()

    monkeypatch.setattr("builtins.input", fake_input)

    out = run_tiny("print(Console.read_line());")

    assert out == "\n"

def test_console_read_line_blocked_when_dap_disables_stdin(monkeypatch):
    """Test that console read line blocked when dap disables stdin."""
    monkeypatch.setenv("TINYLANGUAGE_DAP_DISABLE_STDIN", "1")

    with pytest.raises(Exception, match="Console\\.read_line is disabled"):
        run_tiny("print(Console.read_line());")


def test_must_use_unused_local_binding_function():
    """Test that must use unused local binding function."""
    src = """
    fn g(a) {
        def t = 123;
        print(a);
        return a;
    }
    """
    expect_compile_error(src, r"unused local binding\(s\): t")


def test_must_use_bare_call_forbidden():
    """Test that must use bare call forbidden."""
    src = """
    fn h() { return 1; }
    def _unused85 = h();
    """
    expect_compile_error(src, r"bare call statements are not allowed")


def test_must_use_destructure_all_fields():
    """Test that must use destructure all fields."""
    src = """
    fn make() { return { p: 1, e: 0 }; }
    { p, e } = make();
    print(p);
    """
    expect_compile_error(src, r"unused local binding\(s\): e")


def test_ok_destructure_both_values():
    """Test that ok destructure both values."""
    src = """
    fn make() { return { p: 1, e: 0 }; }
    { p, e } = make();
    print(p);
    print(e);
    """
    out = run_tiny(src)
    assert out == "1\n0\n"


def test_unused_binding_in_nested_block_function():
    """Test that unused binding in nested block function."""
    src = """
    fn g(a) {
        if (true) {
            def t = 99;
        }
        return a;
    }
    """
    expect_compile_error(src, r"unused local binding\(s\): t")


def test_unused_binding_in_nested_block_method():
    """Test that unused binding in nested block method."""
    src = """
    class Box {
        fn touch(self, v) {
            while (false) {
                def tmp = v;
            }
            return self;
        }
    }
    """
    expect_compile_error(src, r"unused local binding\(s\): tmp")


def test_unused_binding_must_be_used_on_all_paths():
    """Test that unused binding must be used on all paths."""
    src = """
    def x = 1;
    def flag = 1;
    if (flag) {
        print(x);
    } else {
        print(0);
    }
    """

    expect_compile_error(src, r"local binding\(s\) must be used on all control-flow paths: x")


def test_binding_used_in_all_branches_is_ok():
    """Test that binding used in all branches is ok."""
    src = """
    fn demo(flag) {
        def label = "hi";
        if (flag) {
            print(label);
        } else {
            print(label);
        }
        return 0;
    }
    print(demo(true));
    """

    out = run_tiny(src)
    assert out == "hi\n0\n"


def test_binding_used_on_non_exit_path_is_ok():
    """Test that binding used when only non-exit path continues is ok."""
    src = """
    fn demo(flag) {
        def x = 1;
        if (flag) {
            return 0;
        }
        print(x);
        return 1;
    }
    print(demo(false));
    """

    out = run_tiny(src)
    assert out == "1\n1\n"


def test_must_use_ignores_exit_paths_with_infinite_loop():
    """Test that must-use ignores exit paths with infinite loop."""
    src = """
    fn demo(flag) {
        def x = 1;
        if (flag) {
            while (true) {
                print(0);
            }
        } else {
            print(x);
        }
        return 0;
    }
    print(demo(false));
    """

    out = run_tiny(src)
    assert out == "1\n0\n"


def test_loop_skipped_counts_as_unused():
    """Test that loop skipped counts as unused."""
    src = """
    def msg = "once";
    while (false) {
        print(msg);
    }
    print(0);
    """

    expect_compile_error(src, r"unused local binding\(s\): msg")


def test_unreachable_statement_after_return():
    """Test that unreachable statement after return."""
    src = """
    fn demo() {
        return 1;
        print(2);
    }
    def _unused97 = demo();
    """

    expect_compile_error(src, r"unreachable statement after a guaranteed exit")


def test_unreachable_statement_after_infinite_loop():
    """Test that unreachable statement after infinite loop."""
    src = """
    fn demo() {
        while (true) {
            print(1);
        }
        print(2);
    }
    def _unused100 = demo();
    """

    expect_compile_error(src, r"unreachable statement after a guaranteed exit")


def test_method_param_mutation_must_be_returned():
    """Test that method param mutation must be returned."""
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


def test_inconsistent_return_signature_in_method():
    """Test that inconsistent return signature in method."""
    src = """
    class Box {
        value: number;

        fn wrap(self, v) {
            if (v) {
                return { value: self.value, e: 0 };
            }
            return { value: self.value, e: 1, extra: 2 };
        }
    }
    """

    expect_compile_error(
        src,
        r"inconsistent return signature in method Box.wrap: expected \{value, e\} but found \{value, e, extra\}",
    )


def test_ok_function_call_as_argument():
    """Test that ok function call as argument."""
    src = """
    fn one() { return 1; }
    print(one());
    """
    out = run_tiny(src)
    assert out == "1\n"


def test_destructure_requires_all_call_args():
    """Test that destructure requires all call args."""
    src = """
    fn f(a) { return { a: a + 1, e: 0 }; }
    def a = 3;
    { a, e } = f(a);
    print(a);
    print(e);
    """
    out = run_tiny(src)
    assert out == "4\n0\n"


def test_destructure_missing_input_variable_fails():
    """Test that destructure missing input variable fails."""
    src = """
    fn f(a) { return { a: a + 1, e: 0 }; }
    def a = 3;
    { b, e } = f(a);
    """
    expect_compile_error(src, r"destructuring call to f must include output for argument\(s\): a")


def test_method_param_mutation_returned_allows_change():
    """Test that method param mutation returned allows change."""
    src = """
    class Box {
        value: number;

        fn set(self, v) {
            self.value = v;
            return self;
        }
    }

    def b = new Box { value: 1; };
    b = b.set(5);
    print(b.value);
    """

    out = run_tiny(src)
    assert out == "5\n"


def test_error_message_for_missing_heap_index(monkeypatch):
    """Test that error message for missing heap index."""
    src = """
    def a = new[1, 2];
    print(heap_get(a, 5));
    print(errorMessage);
    def _unused206 = delete(a);
    """

    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = run_tiny(src)
    assert re.search(
        r"(?:\[E\d+\] )?heap access error: index 5 out of range for pointer 1 "
        r"\(size 2; valid indices: 0..1\) \(line 3, col \d+(?: to line \d+, col \d+)?\)",
        out,
    )
    assert "^" in out


def test_error_message_for_double_delete(monkeypatch):
    """Test that error message for double delete."""
    src = """
    def p = new(1);
    def _unused107 = delete(p);
    def _unused108 = delete(p);
    print(errorMessage);
    """

    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = run_tiny(src)
    assert re.search(
        r"(?:\[E\d+\] )?heap delete error: pointer 1 was already freed \(size 1\) "
        r"\(line 4, col \d+(?: to line \d+, col \d+)?\)",
        out,
    )
    assert "^" in out


def test_error_message_for_unknown_delete(monkeypatch):
    """Test that error message for unknown delete."""
    src = """
    def _unused110 = delete(9);
    print(errorMessage);
    """

    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = run_tiny(src)
    assert re.search(
        r"(?:\[E\d+\] )?heap delete error: unknown pointer 9.*\(line 2, col \d+(?: to line \d+, col \d+)?\)",
        out,
    )
    assert "^" in out


def test_error_message_for_heap_type_mismatch(monkeypatch):
    """Test that error message for heap type mismatch."""
    src = """
    def p = new(1);
    { e } = heap_set(p, 0, 1);
    { e } = heap_set(p, 0, "oops");
    print(e.code);
    print(errorMessage);
    def _unused207 = delete(p);
    """

    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = run_tiny(src)
    assert re.search(
        r"\[E014\] heap type mismatch at 1\[0\]: expected int but got string "
        r"\(line 4, col \d+(?: to line \d+, col \d+)?\)",
        out,
    )
    assert "^" in out


def test_heap_leak_report_tracks_live_allocations():
    """Test that heap leak report tracks live allocations."""
    src = """
    def first = new(2);
    def second = new[1, 2, 3];
    print(len(second));
    def _unused113 = delete(first);
    """

    runtime = Runtime(src)
    compile_and_run(src, runtime=runtime)
    report = runtime.heap_leak_report()

    assert report["count"] == 1
    assert report["live"] == {2: 3}
    assert report["freed"] == [1]
    assert report["freed_sizes"][1] == 2
    assert report["total_cells"] == 3
    assert report["has_leaks"] is True


def test_heap_leak_report_clears_after_cleanup():
    """Test that heap leak report clears after cleanup."""
    src = """
    def first = new(2);
    def second = new[1, 2, 3];
    print(len(second));
    def _unused113 = delete(first);
    def _unused114 = delete(second);
    """

    runtime = Runtime(src)
    compile_and_run(src, runtime=runtime)
    report = runtime.heap_leak_report()

    assert report["count"] == 0
    assert report["live"] == {}
    assert report["has_leaks"] is False


def test_error_message_for_missing_field():
    """Test that error message for missing field."""
    src = """
    def o = { existing: 1; };
    print(o.missing);
    print(errorMessage);
    """

    out = run_tiny(src)
    assert re.search(
        r"(?:\[E\d+\] )?unknown field missing \(line 3, col \d+(?: to line \d+, col \d+)?\)",
        out,
    )
    assert "^" in out


def test_parser_error_reports_context():
    """Test that parser error reports context."""
    expect_compile_error("def a = ;", r"unexpected token SYM \(line 1, col 9\)")


def test_runtime_error_reports_context():
    """Test that runtime error reports context."""
    expect_compile_error(
        "print(1/0);",
        r"(?s)(?:\[E\d+\] )?division by zero \(line 1, col \d+(?: to line 1, col \d+)?\).*\^+",
    )


def test_typedef_simple_record():
    """Test that typedef simple record."""
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
    """Test that rosetta fibonacci program."""
    program = pathlib.Path(__file__).resolve().parents[1] / "src_tiny" / "rosetta_fibonacci.tiny"

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
    """Test that number class with operator overloads."""
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

    def a = Number(5);
    def b = Number(7.5);

    def c = a + b;
    def d = a - b;
    def e = a * b;
    def f = a / b;

    print(c.value);
    print(d.value);
    print(e.value);
    print(f.value);
    """

    out = run_tiny(src)

    assert out == "12.5\n-2.5\n37.5\n0.6666666666666666\n"


def test_spawn_and_join():
    """Test that spawn and join."""
    out = run_tiny(
        """
        fn add(x, y) {
            return x + y;
        }

        def first = spawn add(2, 3);
        def second = spawn add(4, 5);

        print(join(first));
        print(join(second));
        """
    )

    assert out == "5\n9\n"
