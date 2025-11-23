from __future__ import annotations

import importlib.util
import pathlib
import sys
from pathlib import Path

import pytest

readline_spec = importlib.util.find_spec("readline")
if readline_spec is not None:
    import readline
else:
    readline = None

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

import tiny_language as tl


def test_is_incomplete_source_multiline_blocks():
    assert tl._is_incomplete_source("if true {")
    assert not tl._is_incomplete_source("if true {\n}")
    assert not tl._is_incomplete_source('print("{")')


def test_read_repl_command_collects_until_complete():
    lines = iter(["if true {", "print(1)", "}"])

    def reader(prompt: str) -> str:  # noqa: ARG001 - prompt unused in test
        try:
            return next(lines)
        except StopIteration:
            raise EOFError

    assert tl._read_repl_command(reader) == "if true {\nprint(1)\n}"


def test_history_file_roundtrip(tmp_path: Path):
    if readline is None:
        pytest.skip("readline not available on this platform", allow_module_level=True)

    history_file = tmp_path / "history"
    readline.clear_history()
    tl._configure_readline(history_file)
    readline.add_history("first entry")
    tl._save_history(history_file)

    readline.clear_history()
    tl._configure_readline(history_file)
    assert readline.get_history_item(1) == "first entry"
