import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import TinyLangError, compile_and_run


def test_stacktrace_includes_call_chain():
    source = """
fn leaf() { missing(); }
fn middle() { return leaf(); }
fn top() { return middle(); }

print(top());
"""

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source)

    message = str(excinfo.value)
    assert "Stack trace:" in message
    assert "leaf" in message and "middle" in message and "top" in message


def test_try_catch_handles_error_object():
    source = """
fn explode() { return missing(); }
fn wrapper() {
  try {
    return explode();
  } catch(err) {
    print(err.code);
    return err.message;
  }
}

print(wrapper());
"""

    output = compile_and_run(source)

    assert output.startswith("E000\n")
    assert "unknown function missing" in output
