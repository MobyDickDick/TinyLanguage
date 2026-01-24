"""Tests for copy-on-call semantics in TinyLanguage."""

import pytest

from tiny_language import TinyLangError, compile_and_run

from tests.utils import execute_tiny_program


def test_non_escaped_parameter_is_copied_by_default():
    """Ensure arguments are copied unless explicitly escaped."""
    source = """
    fn bump(buf) {
        def ignored1 = heap_set(buf, 0, 99);
    }

    def data = new(1);
    def ignored1 = heap_set(data, 0, 1);
    def _unused3 = bump(data);
    print(heap_get(data, 0));
    """

    output = compile_and_run(source, copy_on_call=True)

    assert output.strip() == "1"


def test_escaped_parameter_mutations_propagate():
    """Confirm escaped parameters share mutations with the caller."""
    source = """
    fn passthrough(buf) {
        def ignored1 = heap_set(buf, 0, 42);
        return buf;
    }

    def data = new(1);
    def ignored1 = heap_set(data, 0, 7);
    def alias = passthrough(data);
    print(heap_get(data, 0));
    print(heap_get(alias, 0));
    """

    output = compile_and_run(source, copy_on_call=True)

    assert output.strip().splitlines() == ["42", "42"]


def test_legacy_behavior_when_copy_on_call_disabled():
    """Verify legacy in-place mutation when copy-on-call is disabled."""
    source = """
    fn bump(buf) {
        def ignored1 = heap_set(buf, 0, 99);
    }

    def data = new(1);
    def ignored1 = heap_set(data, 0, 1);
    def _unused11 = bump(data);
    print(heap_get(data, 0));
    """

    output = compile_and_run(source, copy_on_call=False)

    assert output.strip() == "99"


def test_mutating_protected_argument_raises():
    """Ensure mutating a protected alias raises a TinyLangError."""
    source = """
    def shared = new(1);

    fn mutate_through_alias(p) {
        if (p == p) {
            def ignored1 = heap_set(shared, 0, 5);
        }
    }

    def _unused14 = mutate_through_alias(shared);
    """

    with pytest.raises(TinyLangError) as excinfo:
        compile_and_run(source, copy_on_call=True)

    assert "protected parameter p" in str(excinfo.value)


def test_cli_flag_enables_copy_on_call():
    """Check CLI flag toggles copy-on-call behavior."""
    source = """
    fn bump(buf) {
        def ignored1 = heap_set(buf, 0, 99);
    }

    def data = new(1);
    def ignored1 = heap_set(data, 0, 1);
    def _unused17 = bump(data);
    print(heap_get(data, 0));
    """

    result = execute_tiny_program(source, args=["--copy-on-call"])

    assert result.returncode == 0
    assert result.stdout.strip() == "1"
    assert result.stderr == ""
