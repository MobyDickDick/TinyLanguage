import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

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
maybe(1);
"""

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    assert excinfo.value.code == "E010"
    assert "not all paths in function maybe" in str(excinfo.value)
