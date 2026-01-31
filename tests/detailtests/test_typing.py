"""Tests for typing."""

import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from tiny_language import TinyLangError, compile_and_run


def test_typed_function_happy_path():
    """Test that typed function happy path."""
    source = "fn greet(name: string) -> string { return \"hi \" + name; }\nprint(greet(\"Ada\"));\n"

    assert compile_and_run(source) == "hi Ada\n"


def test_typed_function_argument_mismatch():
    """Test that typed function argument mismatch."""
    source = "fn add(x: number, label: string) -> number { print(label); return x; }\nprint(add(\"oops\", \"ok\"));\n"

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E009"
    assert "parameter x in function add" in str(excinfo.value)


def test_typed_function_return_mismatch():
    """Test that typed function return mismatch."""
    source = "fn as_text(x: number) -> number { if (x > 0) { return \"txt\"; } return \"txt\"; }\nprint(as_text(1));\n"

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E009"
    assert "return value for function as_text" in str(excinfo.value)


def test_typed_function_requires_all_paths_return():
    """Test that typed function requires all paths return."""
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
    """Test that optional parameter allows null."""
    source = """
fn greet(name: string?) -> string {
    if (name == Null) { return "hi"; }
    return "hi " + name;
}
print(greet(Null));
"""

    assert compile_and_run(source) == "hi\n"


def test_optional_return_skips_exhaustiveness_check():
    """Test that optional return skips exhaustiveness check."""
    source = """
fn maybe_label(x: number) -> string? {
    if (x > 0) { return "positive"; }
}
print(maybe_label(-2));
"""

    assert compile_and_run(source) == "Null\n"


def test_typed_list_parameter_accepts_list_literal():
    """Test that typed list parameters accept compatible list literals."""
    source = """
fn first_item(items: List[number]) -> number {
    return heap_get(items, 0);
}
print(first_item(new[1, 2, 3]));
"""
    assert compile_and_run(source) == "1\n"


def test_typed_list_parameter_rejects_mismatched_elements():
    """Test that typed list parameters reject incompatible element types."""
    source = """
fn first_item(items: List[number]) -> number {
    return heap_get(items, 0);
}
print(first_item(new["oops"]));
"""

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E009"


def test_inferred_number_allows_float_assignment():
    """Test that inferred number allows float assignment."""
    source = """
def x = 0;
x = 1.5;
"""
    assert compile_and_run(source) == ""


def test_inferred_type_still_prevents_unrelated_changes():
    """Test that inferred type still prevents unrelated changes."""
    source = """
def msg = "hello";
msg = 123;
"""

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E014"


def test_import_summary_validates_argument_types(tmp_path, monkeypatch):
    """Validate that module summaries enforce typed call arguments."""
    monkeypatch.chdir(tmp_path)
    module_path = tmp_path / "lib" / "math.tiny"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_source = "fn add(a: number, b: number) -> number { return a + b; }\n"
    module_path.write_text(module_source)

    compile_and_run(
        module_source,
        module_namespace="lib.math",
        module_path=module_path,
        stream_output=False,
    )

    main_source = "import lib.math;\nprint(math.add(\"oops\", 1));\n"
    main_path = tmp_path / "main.tiny"
    main_path.write_text(main_source)

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(
            main_source,
            module_namespace="main",
            module_path=main_path,
            stream_output=False,
        )

    assert excinfo.value.code == "E009"
    assert "function lib.math.add" in str(excinfo.value)


def test_import_summary_validates_argument_count(tmp_path, monkeypatch):
    """Validate that module summaries enforce argument counts."""
    monkeypatch.chdir(tmp_path)
    module_path = tmp_path / "helpers" / "calc.tiny"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_source = "fn scale(value: number, factor: number) -> number { return value * factor; }\n"
    module_path.write_text(module_source)

    compile_and_run(
        module_source,
        module_namespace="helpers.calc",
        module_path=module_path,
        stream_output=False,
    )

    main_source = "import helpers.calc;\nprint(calc.scale(3));\n"
    main_path = tmp_path / "main.tiny"
    main_path.write_text(main_source)

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(
            main_source,
            module_namespace="main",
            module_path=main_path,
            stream_output=False,
        )

    assert excinfo.value.code == "E009"
    assert "function helpers.calc.scale" in str(excinfo.value)
