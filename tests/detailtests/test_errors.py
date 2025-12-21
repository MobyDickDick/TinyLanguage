import pathlib
import sys

import pytest

# Ensure project root is importable
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import TinyLangError, compile_and_run  # noqa: E402


def read_fixture(name: str) -> str:
    return (PROJECT_ROOT / "tests" / "fixtures" / name).read_text()


def test_exponent_requires_integer_hint():
    source = read_fixture("float_exponent.tiny")

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    err = excinfo.value
    assert err.code == "E004"
    assert "exponent for ^ must be an integer" in str(err)
    assert err.hint == "Use an integer exponent (cast with `int(...)` if necessary) when using the ^ operator."


def test_len_reports_unsized_value():
    source = read_fixture("len_unsized.tiny")

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    err = excinfo.value
    assert err.code == "E005"
    assert "len expects a sized value" in str(err)
    assert err.hint == "Pass a list, string, heap pointer, or other sized value to `len`."


def test_destructuring_call_missing_outputs_includes_hint():
    source = read_fixture("invalid_destruct.tiny")

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    err = excinfo.value
    assert err.code == "E006"
    assert err.pos.line == 2
    assert err.pos.col == 1
    assert "destructuring call to foo must include output for argument(s): a" in str(err)
    assert err.hint == "Add the missing binding(s) to the destructuring pattern so each referenced argument is captured."
