import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import compile_and_run


def test_result_helpers_wrap_and_unwrap_errors():
    source = """
fn explode() { return missing(); }
fn safe_call() {
  try {
    return Result.ok(explode());
  } catch(err) {
    return Result.err(err);
  }
}

define res = safe_call();
print(res);
print(Result.is_ok(res));
print(Result.is_err(res));
print(Result.unwrap_or(res, "default"));
"""

    output = compile_and_run(source)
    lines = output.strip().splitlines()
    assert "unknown function missing" in lines[0]
    assert "Stack trace:" in lines[0]
    assert lines[1] == "false"
    assert lines[2] == "true"
    assert lines[3] == "default"


def test_result_err_handles_strings_without_throwing():
    source = """
fn returns_result(flag) {
  if (flag) {
    return Result.ok(1);
  }
  return Result.err("boom");
}

print(Result.unwrap_or(returns_result(true), 0));
print(Result.unwrap_or(returns_result(false), 0));
"""

    output = compile_and_run(source)
    assert output.splitlines() == ["1", "0"]
