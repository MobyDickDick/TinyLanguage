import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from tiny_language import TinyLangError, compile_and_run


def test_parser_error_includes_context():
    source = "def a = 1;\nprint(a;\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E000] expected SYM ) (line 2, col 8)\n  1 | def a = 1;\n> 2 | print(a;\n    |        ^"
    )


def test_runtime_error_includes_context():
    source = "callme();\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E001] call with return value must be bound; bare call statements are not allowed (offending call: callme()) (line 1, col 1)\n> 1 | callme();\n    | ^\n  Hint: Bind the return value, e.g. `def result = call();`, or add a return that includes the mutated data."
    )


def test_unknown_variable_suggests_name():
    source = "def value = 1;\nprint(value + val);\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E003] unknown variable val (line 2, col 15)\n  1 | def value = 1;\n> 2 | print(value + val);\n    |               ^\n  Hint: Did you mean `value`? Declare the variable first, e.g. `def name = ...;`."
    )


def test_unused_binding_reports_hint():
    source = "def unused = 1;\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E002] unused local binding(s): unused (line 1, col 8)\n> 1 | def unused = 1;\n    |        ^^^^^^\n  Hint: Remove the unused binding or reference it."
    )


def test_mutated_param_requires_return():
    source = "fn foo(x) { x = x + 1; }\nfoo(1);\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E001] mutated parameter(s) in function foo must be returned: x (line 1, col 1)\n> 1 | fn foo(x) { x = x + 1; }\n  2 | foo(1);\n    | ^\n  Hint: Return the mutated parameters so callers receive the updates."
    )


def test_parser_error_exposes_code_and_location():
    source = "def a = 1\n"

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    err = excinfo.value
    assert err.code == "E000"
    assert err.hint is None
    assert err.pos.line == 2
    assert err.pos.col == 1
    assert str(err) == "[E000] expected SYM ; (line 1, col 1)\n> 1 | def a = 1\n    | ^"


def test_unknown_variable_error_includes_hint():
    source = "def value = 1;\nprint(value + vale);\n"

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    err = excinfo.value
    assert err.code == "E003"
    assert (
        err.hint
        == "Did you mean `value`? Declare the variable first, e.g. `def name = ...;`."
    )
    assert err.pos.line == 2
    assert err.pos.col == 15
    assert (
        str(err)
        == "[E003] unknown variable vale (line 2, col 15)\n  1 | def value = 1;\n> 2 | print(value + vale);\n    |               ^\n  Hint: Did you mean `value`? Declare the variable first, e.g. `def name = ...;`."
    )
