"""Run the stdlib documentation examples and verify their output."""

from __future__ import annotations

import pytest

from tests.detailtests.utils import PROJECT_ROOT

DOC_PATH = PROJECT_ROOT / "docs" / "stdlib_examples.md"


def _extract_examples() -> list[tuple[str, str, str]]:
    """Return (label, code, output) tuples from the stdlib examples doc."""

    text = DOC_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    examples: list[tuple[str, str, str]] = []
    current_label = "(unknown)"
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if line.startswith("## "):
            current_label = line.replace("## ", "", 1).strip()
            idx += 1
            continue

        if line.startswith("```tiny"):
            idx += 1
            code_lines: list[str] = []
            while idx < len(lines) and not lines[idx].startswith("```"):
                code_lines.append(lines[idx])
                idx += 1
            if idx >= len(lines):
                raise AssertionError("Unterminated tiny code block in stdlib examples.")
            idx += 1

            while idx < len(lines) and lines[idx].strip() == "":
                idx += 1

            if idx >= len(lines) or not lines[idx].startswith("```text"):
                raise AssertionError(
                    f"Missing text output block after tiny example: {current_label}"
                )

            idx += 1
            out_lines: list[str] = []
            while idx < len(lines) and not lines[idx].startswith("```"):
                out_lines.append(lines[idx])
                idx += 1
            if idx >= len(lines):
                raise AssertionError("Unterminated text output block in stdlib examples.")
            idx += 1

            code = "\n".join(code_lines).rstrip() + "\n"
            output = "\n".join(out_lines)
            if output:
                output += "\n"
            examples.append((current_label, code, output))
            continue

        idx += 1

    if not examples:
        raise AssertionError("No stdlib examples found to test.")

    return examples


@pytest.mark.parametrize("label, code, expected", _extract_examples())
def test_stdlib_doc_examples(run_tiny_source, monkeypatch, label, code, expected):
    """Execute each stdlib documentation example from the markdown file."""

    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    assert run_tiny_source(code) == expected, f"Stdlib example failed: {label}"
