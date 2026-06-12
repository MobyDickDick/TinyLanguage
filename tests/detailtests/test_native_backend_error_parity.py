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
    ("len called with an unsized value", "print(len(1));"),
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


@pytest.mark.parametrize(
    "source",
    (
        'print(len("tiny"));',
        "def values = new[1, 2, 3]; print(len(values));",
        (
            'def values = Map.new(); def _updated = Map.set(values, "key", 1); '
            "print(len(values));"
        ),
    ),
    ids=("string", "list-heap-pointer", "collection-heap-pointer"),
)
def test_interpreter_and_native_backend_return_matching_len_values(source):
    """Native len should match the interpreter for every supported value category."""
    interpreter_output = compile_and_run(source, stream_output=False)
    native_output = run_with_native_backend(source)

    assert native_output == interpreter_output
