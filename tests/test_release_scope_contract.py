"""Independent expected results for the interpreter release contract."""

import re
from fractions import Fraction
from pathlib import Path

import pytest

from tiny_language import TinyLangError, compile_and_run

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("left,right", [(7, 2), (-7, 2), (1, 8), (0, 3)])
def test_core_arithmetic_has_independent_exact_oracle(left, right):
    """Small dyadic results are exact; an independent rational oracle defines them."""
    output = compile_and_run(
        f"print({left} + {right}); print({left} - {right}); "
        f"print({left} * {right}); print({left} / {right});", stream_output=False,
    )
    expected = [Fraction(left + right), Fraction(left - right),
                Fraction(left * right), Fraction(left, right)]
    assert [Fraction(line) for line in output.splitlines()] == expected


def test_encapsulation_example_executes_verbatim():
    """The actual Markdown example must execute and retain caller-owned data."""
    text = (ROOT / "docs/language_spec.md").read_text(encoding="utf-8")
    section = text.split("## Argument encapsulation\n", 1)[1].split("\n## ", 1)[0]
    match = re.search(r"```tiny\n(.*?)```", section, re.DOTALL)
    assert match, "Missing argument-encapsulation example"
    program = match.group(1) + "\nprint(heap_get(data, 0));\ndef ignored5 = delete(data);"
    assert compile_and_run(program, copy_on_call=True, stream_output=False) == "1\n"


@pytest.mark.parametrize("source,code", [
    ("print(missing);", "E003"),
    ("def values = new[1]; print(heap_get(values, 2));", "E020"),
])
def test_release_errors_are_failures_with_source_positions(source, code):
    """Errors must carry public structured diagnostics rather than success output."""
    with pytest.raises(TinyLangError) as error:
        compile_and_run(source, stream_output=False)
    assert error.value.code == code
    assert error.value.pos is not None
