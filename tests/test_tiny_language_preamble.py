import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_errors import SourcePos, SourceSpan
from tiny_language_preamble import (
    StackFrame,
    _FallbackReadline,
    _classify_error,
    _closest_match,
    format_error,
)


def test_stack_frame_qualified_name():
    frame = StackFrame(name="run", namespace="Core", pos=SourcePos(line=1, column=1))
    assert frame.qualified_name == "Core.run"

    frame = StackFrame(name="main", namespace=None, pos=SourcePos(line=1, column=1))
    assert frame.qualified_name == "main"


def test_format_error_with_position():
    source = "first\nsecond"
    output = format_error(source, SourcePos(line=2, column=3), "boom", code="E123")

    assert "[E123] boom (line 2, col 3)" in output
    assert "> 2 | second" in output
    assert "^" in output


def test_format_error_with_span_and_hint():
    source = "alpha\nbeta\ngamma"
    span = SourceSpan(SourcePos(line=1, column=2), SourcePos(line=2, column=3))
    output = format_error(source, span, "bad span", code="E777", hint="fix it")

    assert "[E777] bad span (line 1, col 2 to line 2, col 3)" in output
    assert "Hint: fix it" in output
    assert "^" in output


def test_closest_match_prefers_best_candidate():
    match = _closest_match("banana", ["bandana", "banana", "ban"])
    assert match == "banana"


def test_classify_error_suggestions():
    code, hint = _classify_error("unused binding foo")
    assert code == "E002"
    assert "unused" in hint.lower()

    code, hint = _classify_error("unknown variable banana", candidates=["bananas", "banana"])
    assert code == "E003"
    assert hint is not None
    assert "Did you mean `banana`" in hint

    code, hint = _classify_error("return value must be bound")
    assert code == "E001"
    assert hint is not None


def test_fallback_readline_history_round_trip(tmp_path):
    rl = _FallbackReadline()
    rl.add_history("first")
    rl.add_history("second")
    rl.set_history_length(1)

    history_path = tmp_path / "history.txt"
    rl.write_history_file(history_path)

    contents = history_path.read_text(encoding="utf-8")
    assert contents.strip() == "second"

    rl.clear_history()
    rl.read_history_file(history_path)

    assert rl.get_current_history_length() == 1
    assert rl.get_history_item(1) == "second"

    rl.add_history("third")
    assert rl.get_history_item(2) == "third"
