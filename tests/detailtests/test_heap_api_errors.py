"""Tests covering heap API error handling and reporting."""

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src"))

from tiny_language import Runtime  # noqa: E402


def test_heap_access_errors_are_precise():
    """Ensure heap access errors include precise range diagnostics."""
    rt = Runtime("")
    ptr = rt._Runtime__new(2)  # noqa: SLF001 - intentional for testing

    assert rt.heap_get(ptr, 5) is None
    assert "index 5 out of range" in rt.error_message

    result = rt.heap_set(ptr, 3, 1)
    assert result["e"]["code"] == 1
    assert "index 3 out of range" in rt.error_message
    assert "valid indices: 0..1" in rt.error_message

    rt.delete(ptr)
    assert rt.heap_get(ptr, 0) is None
    assert "was already freed (size 2)" in rt.error_message

    result = rt.heap_set(999, 0, 1)
    assert result["e"]["code"] == 1
    assert "unknown pointer 999" in rt.error_message
    assert "freed" in rt.error_message


def test_heap_access_rejects_invalid_pointers():
    """Verify invalid heap pointers are rejected with clear messages."""
    rt = Runtime("")

    assert rt.heap_get(True, 0) is None
    assert "not numeric" in (rt.error_message or "")

    assert rt.heap_get("nope", 0) is None
    assert "not numeric" in (rt.error_message or "")

    assert rt.heap_get(1.5, 0) is None
    assert "not an integer pointer" in (rt.error_message or "")

    assert rt.heap_get(0, 0) is None
    assert "invalid (must refer to a live positive allocation)" in (rt.error_message or "")


def test_heap_delete_and_leak_report():
    """Check heap deletion and leak reporting across allocations."""
    rt = Runtime("")
    first = rt._Runtime__new(1)  # noqa: SLF001 - intentional for testing
    second = rt._Runtime__new(3)  # noqa: SLF001 - intentional for testing

    report = rt.heap_leak_report()
    assert report["count"] == 2
    assert report["live"][first] == 1
    assert report["live"][second] == 3
    assert report["allocations"][first] == 1
    assert report["allocations"][second] == 3
    assert report["has_leaks"] is True

    rt.delete(first)
    rt.delete(second)
    report = rt.heap_leak_report()
    assert report["count"] == 0
    assert report["freed_sizes"][first] == 1
    assert report["freed_sizes"][second] == 3
    assert first in report["freed"] and second in report["freed"]
    assert report["freed_count"] == 2
    assert report["has_leaks"] is False

    result = rt.delete(second)
    assert result["e"]["code"] == 1
    assert "was already freed" in rt.error_message


def test_heap_delete_rejects_invalid_pointers():
    """Ensure deleting invalid pointers returns structured errors."""
    rt = Runtime("")

    result = rt.delete("nope")
    assert result["e"]["code"] == 1
    assert "not numeric" in result["e"]["msg"]
    assert "nope" in result["e"]["msg"]

    result = rt.delete(2.5)
    assert result["e"]["code"] == 1
    assert "not an integer pointer" in result["e"]["msg"]

    result = rt.delete(0)
    assert result["e"]["code"] == 1
    assert "invalid (must refer to a live positive allocation)" in result["e"]["msg"]


def test_heap_errors_show_offending_values():
    """Confirm error messages include offending pointer/index values."""
    rt = Runtime("")

    bad_pointer = rt.heap_set("not-a-pointer", 0, 1)
    assert bad_pointer["e"]["code"] == 1
    assert "not-a-pointer" in bad_pointer["e"]["msg"]
    assert "not-a-pointer" in (rt.error_message or "")

    ptr = rt._Runtime__new(1)  # noqa: SLF001 - intentional for testing
    rt.heap_get(ptr, "nope")
    assert "nope" in (rt.error_message or "")


def test_heap_rejects_fractional_pointers_and_indices():
    """Validate fractional pointers and indices are rejected."""
    rt = Runtime("")

    assert rt.heap_get(1.5, 0) is None
    assert "not an integer pointer" in (rt.error_message or "")

    ptr = rt._Runtime__new(2)  # noqa: SLF001 - intentional for testing
    rt.heap_get(ptr, 0.25)
    assert "not an integer index" in (rt.error_message or "")

    rt.heap_get(ptr, False)
    assert "not numeric" in (rt.error_message or "")

    result = rt.heap_set(ptr, -1, 0)
    assert result["e"]["code"] == 1
    assert "out of range" in result["e"]["msg"]
    assert "valid indices: 0..1" in result["e"]["msg"]
