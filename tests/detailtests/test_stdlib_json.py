"""Tests for the stdlib json module wrapper."""

import pytest

from tests.detailtests.stdlib_helpers import run_stdlib_module, stdlib_program


def test_stdlib_json_parse_and_stringify(run_tiny_source):
    """Ensure stdlib json wraps JSON.parse/stringify helpers."""
    out = run_stdlib_module(
        run_tiny_source,
        "json",
        """
        def data = json.parse("{\\"a\\": 1, \\"b\\": [true, null]}");
        print(Map.get(data, "a", 0));
        def values = Map.get(data, "b", Null);
        print(Collections.len(values));
        print(json.stringify(data));
        def _cleanup_values = delete(values);
        def _cleanup_data = delete(data);
        """,
    )

    assert out == '1\n2\n{"a":1,"b":[true,null]}\n'


def test_stdlib_json_validate(run_tiny_source):
    """Validate JSON input without raising errors."""
    out = run_stdlib_module(
        run_tiny_source,
        "json",
        """
        print(json.validate("{\\"ok\\": true}"));
        print(json.validate("{broken}"));
        """,
    )

    assert out == "true\nfalse\n"


def test_stdlib_json_parse_invalid_raises(run_tiny_source):
    """Invalid JSON should raise via the wrapper."""
    with pytest.raises(Exception, match=r"invalid json"):
        run_tiny_source(
            stdlib_program(
                "json",
                """
                def _value = json.parse("{broken}");
                """,
            ),
        )
