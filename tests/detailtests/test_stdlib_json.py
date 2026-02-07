"""Tests for the stdlib json module wrapper."""

import json
import random

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


def _random_json_value(rng: random.Random, depth: int = 0):
    if depth >= 2:
        return rng.choice([None, True, False, rng.randint(-100, 100), rng.random(), "text"])
    choice = rng.choice(["scalar", "list", "dict"])
    if choice == "list":
        return [_random_json_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    if choice == "dict":
        return {
            f"key_{rng.randint(0, 10)}": _random_json_value(rng, depth + 1)
            for _ in range(rng.randint(0, 4))
        }
    return rng.choice([None, True, False, rng.randint(-100, 100), rng.random(), "text"])


def test_stdlib_json_roundtrip_fuzzed(run_tiny_source):
    """Ensure json module round-trips randomly generated payloads."""
    rng = random.Random(0)
    payloads = [_random_json_value(rng) for _ in range(20)]
    program_lines = []
    for idx, payload in enumerate(payloads):
        json_text = json.dumps(payload)
        json_literal = json.dumps(json_text)
        program_lines.append(
            f"""
            def data_{idx} = json.loads({json_literal});
            print(json.dumps(data_{idx}));
            def _cleanup_{idx} = delete(data_{idx});
            """
        )
    out = run_stdlib_module(run_tiny_source, "json", "\n".join(program_lines))
    lines = [line for line in out.splitlines() if line]
    assert len(lines) == len(payloads)
    for payload, line in zip(payloads, lines):
        assert json.loads(line) == payload
