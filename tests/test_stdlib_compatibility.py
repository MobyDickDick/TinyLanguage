from __future__ import annotations

import datetime as py_datetime
import math as py_math
import random as py_random

import pytest

from tests.utils import run_tiny


def _run_lines(source: str) -> list[str]:
    output = run_tiny(source).strip()
    if not output:
        return []
    return output.splitlines()


def test_stdlib_math_matches_python() -> None:
    source = """
import stdlib.math;
print(math.sqrt(81));
print(math.pow(2, 5));
print(math.floor(3.9));
print(math.ceil(3.1));
print(math.round(3.14159));
print(math.round_digits(3.14159, 3));
print(math.clamp(-2, 0, 5));
print(math.sign(-7));
print(math.max(2, 9));
print(math.min(2, 9));
"""
    values = [float(value) for value in _run_lines(source)]
    expected = [
        py_math.sqrt(81),
        py_math.pow(2, 5),
        py_math.floor(3.9),
        py_math.ceil(3.1),
        round(3.14159),
        round(3.14159, 3),
        max(min(-2, 5), 0),
        -1,
        max(2, 9),
        min(2, 9),
    ]
    assert values == pytest.approx(expected)


def test_stdlib_string_matches_python() -> None:
    source = """
import stdlib.string;

def parts = string.split("a,b,c", ",");
print(string.join(parts, "|"));
print(string.upper("Tiny"));
print(string.lower("Tiny"));
print(string.trim("  hi  "));
print(string.repeat("ha", 3));
print(string.contains("tiny language", "lang"));
print(string.replace("tiny language", " ", "_"));
print(string.starts_with("tiny language", "tiny"));
print(string.ends_with("tiny language", "age"));
print(string.is_digit("12345"));
"""
    lines = _run_lines(source)
    expected = [
        "a|b|c",
        "TINY",
        "tiny",
        "hi",
        "hahaha",
        "true",
        "tiny_language",
        "true",
        "true",
        "true",
    ]
    assert lines == expected


def test_stdlib_random_matches_python() -> None:
    source = """
import stdlib.random;
import stdlib.string;

def _seeded = random.seed(1337);
print(random.random());
print(random.randint(1, 10));

def items = new["a", "b", "c", "d"];
print(random.choice(items));
def _shuffled = random.shuffle(items);
print(string.join(items, ","));
"""
    lines = _run_lines(source)

    py_random.seed(1337)
    items = ["a", "b", "c", "d"]
    expected_random = py_random.random()
    expected_randint = py_random.randint(1, 10)
    expected_choice = py_random.choice(items)
    py_random.shuffle(items)
    expected_join = ",".join(items)

    assert float(lines[0]) == pytest.approx(expected_random)
    assert int(lines[1]) == expected_randint
    assert lines[2] == expected_choice
    assert lines[3] == expected_join


def test_stdlib_datetime_matches_python() -> None:
    source = """
import stdlib.datetime;

print(datetime.datetime_isoformat(2024, 2, 3, 4, 5, 6));
print(datetime.date_isoformat(2024, 2, 3));
print(datetime.time_isoformat(4, 5, 6));
print(datetime.total_seconds(1, 30));
"""
    lines = _run_lines(source)

    dt = py_datetime.datetime(2024, 2, 3, 4, 5, 6)
    d = py_datetime.date(2024, 2, 3)
    t = py_datetime.time(4, 5, 6)
    delta = py_datetime.timedelta(days=1, seconds=30)

    assert lines[0] == dt.isoformat()
    assert lines[1] == d.isoformat()
    assert lines[2] == t.isoformat()
    assert float(lines[3]) == pytest.approx(delta.total_seconds())
