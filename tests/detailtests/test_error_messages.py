"""Tests for TinyLanguage error message formatting and hints."""

import pathlib
import re
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from tiny_language import TinyLangError, compile_and_run


def test_parser_error_includes_context():
    """Ensure parser errors include inline source context."""
    source = "def a = 1;\nprint(a;\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E000] expected SYM ) (line 2, col 8)\n  1 | def a = 1;\n> 2 | print(a;\n    |        ^"
    )


def test_unified_error_format_headers():
    """Verify parser, lint, and runtime errors share a common header format."""
    parser_source = "def a = 1\n"
    with pytest.raises(TinyLangError) as parser_excinfo:
        compile_and_run(parser_source)
    parser_header = str(parser_excinfo.value).splitlines()[0]
    assert re.match(r"^\[E\d{3}\] .+ \(line \d+, col \d+", parser_header)

    lint_source = "def unused = 1;\n"
    with pytest.raises(TinyLangError) as lint_excinfo:
        compile_and_run(lint_source)
    lint_output = str(lint_excinfo.value)
    lint_header = lint_output.splitlines()[0]
    assert re.match(r"^\[E\d{3}\] .+ \(line \d+, col \d+", lint_header)
    assert "Hint:" in lint_output

    runtime_source = "callme();\n"
    with pytest.raises(TinyLangError) as runtime_excinfo:
        compile_and_run(runtime_source)
    runtime_output = str(runtime_excinfo.value)
    runtime_header = runtime_output.splitlines()[0]
    assert re.match(r"^\[E\d{3}\] .+ \(line \d+, col \d+", runtime_header)
    assert "Hint:" in runtime_output


def test_runtime_error_includes_context():
    """Ensure runtime errors include inline source context."""
    source = "callme();\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E001] call with return value must be bound; bare call statements are not allowed (offending call: callme()) (line 1, col 1)\n> 1 | callme();\n    | ^\n  Hint: Bind the return value, e.g. `def result = call();`, or add a return that includes the mutated data."
    )


def test_unknown_variable_suggests_name():
    """Check unknown variables suggest the closest known name."""
    source = "def value = 1;\nprint(value + val);\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E003] unknown variable val (line 2, col 15 to line 2, col 17)\n"
        "  1 | def value = 1;\n"
        "> 2 | print(value + val);\n"
        "    |               ^^^\n"
        "  Hint: Did you mean `value`? Declare the variable first, e.g. `def name = ...;`."
    )


def test_unused_binding_reports_hint():
    """Verify unused bindings report a helpful hint."""
    source = "def unused = 1;\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E002] unused local binding(s): unused (line 1, col 5 to line 1, col 10)\n"
        "> 1 | def unused = 1;\n"
        "    |     ^^^^^^\n"
        "  Hint: Remove the unused binding or reference it."
    )


def test_mutated_param_requires_return():
    """Ensure mutated parameters trigger the appropriate error message."""
    source = "fn foo(x) { x = x + 1; }\nfoo(1);\n"

    with pytest.raises(Exception) as excinfo:
        compile_and_run(source)

    assert (
        str(excinfo.value)
        == "[E001] mutated parameter(s) in function foo must be returned: x (line 1, col 1)\n> 1 | fn foo(x) { x = x + 1; }\n  2 | foo(1);\n    | ^\n  Hint: Return the mutated parameters so callers receive the updates."
    )


def test_parser_error_exposes_code_and_location():
    """Confirm parser errors expose code and location metadata."""
    source = "def a = 1\n"

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    err = excinfo.value
    assert err.code == "E000"
    assert err.hint is None
    assert err.pos.line == 1
    assert err.pos.col == 10
    assert str(err) == "[E000] expected SYM ; (line 1, col 10)\n> 1 | def a = 1\n    |          ^"


def test_unknown_variable_error_includes_hint():
    """Ensure unknown variable errors include the suggestion hint."""
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
        == "[E003] unknown variable vale (line 2, col 15 to line 2, col 18)\n"
        "  1 | def value = 1;\n"
        "> 2 | print(value + vale);\n"
        "    |               ^^^^\n"
        "  Hint: Did you mean `value`? Declare the variable first, e.g. `def name = ...;`."
    )
