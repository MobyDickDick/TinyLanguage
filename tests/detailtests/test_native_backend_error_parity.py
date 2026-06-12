"""Focused interpreter/native diagnostic parity audit."""

import pytest

from tiny_errors import SourcePos, SourceSpan, TinyLangError
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


def _exception(run, source: str) -> Exception:
    """Return the public Python exception raised for a failing program."""
    with pytest.raises(Exception) as excinfo:
        run(source)
    return excinfo.value


def _diagnostic(run, source: str) -> str:
    return str(_exception(run, source))


def _metadata(error: Exception) -> tuple[object, ...]:
    """Expose the structured fields covered by the native API contract."""
    return (
        type(error),
        getattr(error, "code", None),
        getattr(error, "hint", None),
        getattr(error, "pos", None),
        getattr(error, "span", None),
    )


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


@pytest.mark.parametrize(
    ("label", "source", "interpreter_metadata", "native_metadata"),
    (
        (
            "unknown variable",
            "print(missing);",
            (
                TinyLangError,
                "E003",
                "Declare the variable first, e.g. `def name = ...;`.",
                SourcePos(1, 7),
                SourceSpan(SourcePos(1, 7), SourcePos(1, 13)),
            ),
            (RuntimeError, None, None, None, None),
        ),
        (
            "division by zero",
            "print(1 / 0);",
            (
                TinyLangError,
                "E000",
                None,
                SourcePos(1, 9),
                SourceSpan(SourcePos(1, 7), SourcePos(1, 11)),
            ),
            (
                TinyLangError,
                "E000",
                None,
                SourcePos(1, 7),
                SourceSpan(SourcePos(1, 7), SourcePos(1, 11)),
            ),
        ),
        (
            "function argument count",
            "fn add(a, b) { return a + b; }\nprint(add(1));",
            (
                TinyLangError,
                "E009",
                "Adjust the call to pass the expected number of arguments.",
                SourcePos(2, 7),
                SourceSpan(SourcePos(2, 7), SourcePos(2, 12)),
            ),
            (
                TinyLangError,
                "E009",
                "Adjust the call to pass the expected number of arguments.",
                SourcePos(2, 7),
                SourceSpan(SourcePos(2, 7), SourcePos(2, 12)),
            ),
        ),
        (
            "statically known heap bounds",
            "def p = new[1];\nprint(heap_get(p, 2));",
            (
                TinyLangError,
                "E020",
                "Ensure heap indices stay within the allocated size.",
                SourcePos(2, 7),
                SourceSpan(SourcePos(2, 7), SourcePos(2, 20)),
            ),
            (
                TinyLangError,
                "E020",
                "Ensure heap indices stay within the allocated size.",
                SourcePos(2, 7),
                SourceSpan(SourcePos(2, 7), SourcePos(2, 20)),
            ),
        ),
        (
            "len called with an unsized value",
            "print(len(1));",
            (
                TinyLangError,
                "E005",
                "Pass a list, string, heap pointer, or other sized value to `len`.",
                SourcePos(1, 7),
                SourceSpan(SourcePos(1, 7), SourcePos(1, 12)),
            ),
            (RuntimeError, None, None, None, None),
        ),
    ),
    ids=(
        "unknown-variable",
        "division-by-zero",
        "function-argument-count",
        "heap-bounds",
        "len-unsized",
    ),
)
def test_interpreter_and_native_backend_exception_metadata_contract(
    label, source, interpreter_metadata, native_metadata
):
    """Lock the documented Python API metadata contract independently of text parity."""
    interpreter_error = _exception(
        lambda program: compile_and_run(program, stream_output=False),
        source,
    )
    native_error = _exception(run_with_native_backend, source)

    assert _metadata(interpreter_error) == interpreter_metadata, label
    assert _metadata(native_error) == native_metadata, label
