"""Tests for the stdlib toml module wrapper."""

from __future__ import annotations

import json
import random

import pytest

from tests.detailtests.stdlib_helpers import run_stdlib_module, stdlib_program


def test_stdlib_toml_parse_and_stringify(run_tiny_source):
    """Ensure stdlib toml wraps TOML.parse/stringify helpers."""
    out = run_stdlib_module(
        run_tiny_source,
        "toml",
        """
        def text = "title = \\"Tiny\\"\\n\\n[owner]\\nname = \\"Ada\\"\\nage = 42\\n";
        def data = toml.parse(text);
        print(Map.get(data, "title", ""));
        def owner = Map.get(data, "owner", Null);
        print(Map.get(owner, "name", ""));
        print(toml.stringify(data));
        def _cleanup_owner = delete(owner);
        def _cleanup_data = delete(data);
        """,
    )

    assert out.splitlines()[0:2] == ["Tiny", "Ada"]
    assert "title = \"Tiny\"" in out
    assert "[owner]" in out


def test_stdlib_toml_validate(run_tiny_source):
    """Validate TOML input without raising errors."""
    out = run_stdlib_module(
        run_tiny_source,
        "toml",
        """
        print(toml.validate("title = \\"Tiny\\""));
        print(toml.validate("broken = ["));
        """,
    )

    assert out == "true\nfalse\n"


def test_stdlib_toml_parse_invalid_raises(run_tiny_source):
    """Invalid TOML should raise via the wrapper."""
    with pytest.raises(Exception, match=r"invalid toml"):
        run_tiny_source(
            stdlib_program(
                "toml",
                """
                def _value = toml.parse("broken = [");
                """,
            ),
        )


def _random_toml_value(rng: random.Random, depth: int = 0):
    if depth >= 2:
        return rng.choice([True, False, rng.randint(-100, 100), rng.random(), "text"])
    choice = rng.choice(["scalar", "list", "dict"])
    if choice == "list":
        return [_random_toml_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    if choice == "dict":
        return {
            f"key_{rng.randint(0, 10)}": _random_toml_value(rng, depth + 1)
            for _ in range(rng.randint(0, 4))
        }
    return rng.choice([True, False, rng.randint(-100, 100), rng.random(), "text"])


def _random_toml_map(rng: random.Random) -> dict[str, object]:
    return {
        f"key_{rng.randint(0, 10)}": _random_toml_value(rng, 1) for _ in range(rng.randint(1, 4))
    }


def test_stdlib_toml_roundtrip_fuzzed(run_tiny_source):
    """Ensure toml module round-trips randomly generated payloads."""
    rng = random.Random(1)
    payloads = [_random_toml_map(rng) for _ in range(15)]
    program_lines = []
    for idx, payload in enumerate(payloads):
        json_text = json.dumps(payload)
        json_literal = json.dumps(json_text)
        program_lines.append(
            f"""
            def data_{idx} = JSON.parse({json_literal});
            def toml_{idx} = toml.stringify(data_{idx});
            def round_{idx} = toml.parse(toml_{idx});
            print(JSON.stringify(round_{idx}));
            def _cleanup_round_{idx} = delete(round_{idx});
            def _cleanup_data_{idx} = delete(data_{idx});
            """
        )
    out = run_stdlib_module(run_tiny_source, "toml", "\n".join(program_lines))
    lines = [line for line in out.splitlines() if line]
    assert len(lines) == len(payloads)
    for payload, line in zip(payloads, lines):
        assert json.loads(line) == payload
