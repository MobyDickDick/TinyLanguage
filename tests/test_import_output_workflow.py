"""Imports preserve captured output and debugger delivery in multi-file programs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tiny_language import Debugger, compile_and_run


def test_nested_imports_preserve_output_and_debugger_stream(tmp_path, capsys):
    (tmp_path / "inner.tiny").write_text('print("inner"); fn value() { return 7; }\n', encoding="utf-8")
    (tmp_path / "helper.tiny").write_text(
        'print("helper-before"); import inner; print("helper-after", inner.value()); fn value() { return 7; }\n',
        encoding="utf-8")
    source = 'print("before"); import helper; print("after", helper.value());'
    expected = "before\nhelper-before\ninner\nhelper-after 7\nafter 7\n"
    debugger = Debugger(mirror_stdout=False)
    events = []
    debugger.on_output = events.append
    output = compile_and_run(source, module_path=tmp_path / "main.tiny",
                             debugger=debugger, stream_output=False)
    assert output == expected
    assert "".join(events) == expected
    assert capsys.readouterr().out == ""
