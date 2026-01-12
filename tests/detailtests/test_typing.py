import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from tiny_language import TinyLangError, compile_and_run


def test_typed_function_happy_path():
    source = "fn greet(name: string) -> string { return \"hi \" + name; }\nprint(greet(\"Ada\"));\n"

    assert compile_and_run(source) == "hi Ada\n"


def test_typed_function_argument_mismatch():
    source = "fn add(x: number, label: string) -> number { print(label); return x; }\nprint(add(\"oops\", \"ok\"));\n"

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E009"
    assert "parameter x in function add" in str(excinfo.value)


def test_typed_function_return_mismatch():
    source = "fn as_text(x: number) -> number { if (x > 0) { return \"txt\"; } return \"txt\"; }\nprint(as_text(1));\n"

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E009"
    assert "return value for function as_text" in str(excinfo.value)


def test_typed_function_requires_all_paths_return():
    source = """
fn maybe(x: number) -> number {
    if (x > 0) { return x; }
}
def _unused2 = maybe(1);
"""

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E010"
    assert "not all paths in function maybe" in str(excinfo.value)


def test_optional_parameter_allows_null():
    source = """
fn greet(name: string?) -> string {
    if (name == Null) { return "hi"; }
    return "hi " + name;
}
print(greet(Null));
"""

    assert compile_and_run(source) == "hi\n"


def test_optional_return_skips_exhaustiveness_check():
    source = """
fn maybe_label(x: number) -> string? {
    if (x > 0) { return "positive"; }
}
print(maybe_label(-2));
"""

    assert compile_and_run(source) == "Null\n"


def test_inferred_number_allows_float_assignment():
    source = """
def x = 0;
x = 1.5;
"""
    assert compile_and_run(source) == ""


def test_inferred_type_still_prevents_unrelated_changes():
    source = """
def msg = "hello";
msg = 123;
"""

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E014"
