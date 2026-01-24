"""Validates the heap pointer demo output and embedded error annotations."""

import pathlib
import re
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
# Make the local src package available for direct imports in tests.
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import compile_and_run


def test_heap_pointer_demo_outputs_errors_and_hints(monkeypatch):
    """Ensure the demo prints expected success output and recorded errors."""
    program = PROJECT_ROOT / "src_tiny" / "heap_pointer_demo.tiny"

    # Disable linting because this demo intentionally triggers runtime errors.
    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    output = compile_and_run(program.read_text())

    # The demo should start with the safe usage section and description text.
    assert output.startswith(
        "=== Safe heap usage ===\n"
        "Read value for index:\n"
        "2\n"
        "30\n\n"
        "=== Common pitfalls ===\n"
        "The next errors are triggered on purpose; the program still continues and exits successfully.\n"
    )
    # Recorded messages confirm that errors were captured, not fatal.
    assert "Recorded out-of-bounds message:" in output
    assert "Recorded missing-field message:" in output

    # Each runtime error should appear exactly once.
    assert len(re.findall(r"\[E000\] heap access error: index 5 out of range", output)) == 1
    assert len(re.findall(r"\[E000\] unknown field missing", output)) == 1

    # The error annotations should include the original source lines.
    assert re.search(
        r"> \d+ \| def ignored_oob = heap_get\(too_short, bad_index\); // Runtime error is recorded.",
        output,
    )
    assert re.search(
        r"> \d+ \| def ignored_missing = record\.missing; // Reports \"unknown field missing\"\.",
        output,
    )
