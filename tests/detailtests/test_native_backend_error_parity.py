"""Focused interpreter/native diagnostic parity audit."""

import pytest

from tiny_language import compile_and_run, run_with_native_backend


PARITY_CASES = (
    ("unknown variable", "print(missing);"),
    ("division by zero", "print(1 / 0);"),
    (
        "function argument count",
        "fn add(a, b) { return a + b; }\nprint(add(1));",
    ),
    (
        "statically known heap bounds",
        "def p = new[1];\nprint(heap_get(p, 2));",
    ),
)


def _diagnostic(run, source: str) -> str:
    with pytest.raises(Exception) as excinfo:
        run(source)
    return str(excinfo.value)


@pytest.mark.parametrize(("label", "source"), PARITY_CASES, ids=[case[0] for case in PARITY_CASES])
def test_interpreter_and_native_backend_emit_matching_diagnostics(label, source):
    """Representative frontend and runtime failures should render identically."""
    interpreter_message = _diagnostic(
        lambda program: compile_and_run(program, stream_output=False),
        source,
    )
    native_message = _diagnostic(run_with_native_backend, source)

    assert native_message == interpreter_message, label


def test_native_len_error_delta_remains_explicit_and_bounded():
    """The audit records the one uncovered built-in instead of hiding its delta."""
    source = "print(len(1));"

    interpreter_message = _diagnostic(
        lambda program: compile_and_run(program, stream_output=False),
        source,
    )
    native_message = _diagnostic(run_with_native_backend, source)

    assert "[E005] len expects a sized value" in interpreter_message
    assert "[E000] unknown function len" in native_message
    assert "line 1, col 7 to line 1, col 12" in interpreter_message
    assert "line 1, col 7 to line 1, col 12" in native_message
