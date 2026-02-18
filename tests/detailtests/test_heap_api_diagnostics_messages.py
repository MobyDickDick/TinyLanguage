"""Detail tests for distinct heap API user-facing diagnostics."""

import re

from tiny_language import Runtime, compile_and_run


def _run_tiny(src: str) -> str:
    """Execute source with an explicit runtime and return stdout."""
    runtime = Runtime(src)
    return compile_and_run(src, runtime=runtime)


def test_heap_invalid_pointer_error_message_is_specific(monkeypatch):
    """Invalid pointers should emit the dedicated invalid-pointer diagnostic."""
    src = """
    print(heap_get(0, 0));
    print(errorMessage);
    """

    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = _run_tiny(src)

    assert re.search(
        r"heap access error: pointer 0 is invalid \(must refer to a live positive allocation\)",
        out,
    )


def test_heap_out_of_bounds_error_message_is_specific(monkeypatch):
    """Out-of-bounds accesses should emit index-range diagnostics."""
    src = """
    def ptr = new(2);
    print(heap_get(ptr, 5));
    print(errorMessage);
    def _cleanup = delete(ptr);
    """

    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = _run_tiny(src)

    assert re.search(
        r"heap access error: index 5 out of range for pointer 1 \(size 2; valid indices: 0\.\.1\)",
        out,
    )


def test_heap_double_delete_error_message_is_specific(monkeypatch):
    """Double-delete paths should emit already-freed pointer diagnostics."""
    src = """
    def ptr = new(1);
    def _cleanup1 = delete(ptr);
    def _cleanup2 = delete(ptr);
    print(errorMessage);
    """

    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = _run_tiny(src)

    assert re.search(
        r"heap delete error: pointer 1 was already freed \(size 1\)",
        out,
    )
