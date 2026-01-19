from __future__ import annotations

import datetime as py_datetime
import json as py_json
import math as py_math
import os as py_os
import random as py_random
import statistics as py_statistics
from collections import deque as py_deque
from pathlib import Path as PyPath

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
print(math.fabs(-12.5));
print(math.pow(2, 5));
print(math.floor(3.9));
print(math.ceil(3.1));
print(math.round(3.14159));
print(math.round_digits(3.14159, 3));
print(math.clamp(-2, 0, 5));
print(math.sign(-7));
print(math.max(2, 9));
print(math.min(2, 9));
print(math.pi);
print(math.tau);
print(math.e);
"""
    values = [float(value) for value in _run_lines(source)]
    expected = [
        py_math.sqrt(81),
        py_math.fabs(-12.5),
        py_math.pow(2, 5),
        py_math.floor(3.9),
        py_math.ceil(3.1),
        round(3.14159),
        round(3.14159, 3),
        max(min(-2, 5), 0),
        -1,
        max(2, 9),
        min(2, 9),
        py_math.pi,
        py_math.tau,
        py_math.e,
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
print(string.strip("  hi  "));
print(string.lstrip("  hi  "));
print(string.rstrip("  hi  "));
print(string.repeat("ha", 3));
print(string.contains("tiny language", "lang"));
print(string.replace("tiny language", " ", "_"));
print(string.starts_with("tiny language", "tiny"));
print(string.ends_with("tiny language", "age"));
print(string.is_digit("12345"));
def _cleanup_parts = delete(parts);
"""
    lines = _run_lines(source)
    expected = [
        "a|b|c",
        "TINY",
        "tiny",
        "hi",
        "hi",
        "hi  ",
        "  hi",
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
def _unused = delete(items);
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


def test_stdlib_json_matches_python() -> None:
    source = """
import stdlib.json;

def data = json.loads("{\\"name\\": \\"Tiny\\", \\"values\\": [1, 2, 3]}");
print(Map.get(data, "name", ""));
def values = Map.get(data, "values", Null);
print(Collections.len(values));
print(json.dumps(data));
def _cleanup_values = delete(values);
def _cleanup_data = delete(data);
"""
    lines = _run_lines(source)
    expected = py_json.loads('{"name": "Tiny", "values": [1, 2, 3]}')

    assert lines[0] == expected["name"]
    assert int(lines[1]) == len(expected["values"])
    assert py_json.loads(lines[2]) == expected


def test_stdlib_json_file_roundtrip(tmp_path: PyPath) -> None:
    source_path = tmp_path / "payload.json"
    target_path = tmp_path / "written.json"
    payload = {"active": True, "scores": [1, 2, 3], "label": "tiny"}
    source_path.write_text(py_json.dumps(payload))

    source = f"""
import stdlib.json;

def data = json.load("{source_path.as_posix()}");
print(Map.get(data, "label", ""));
def _dumped = json.dump("{target_path.as_posix()}", data);
def _cleanup_data = delete(data);
"""
    lines = _run_lines(source)

    assert lines[0] == payload["label"]
    assert py_json.loads(target_path.read_text()) == payload


def test_stdlib_json_aliases_match_python() -> None:
    source = """
import stdlib.json;

def data = json.parse("{\\"a\\": 1, \\"b\\": [true, false]}");
print(Map.get(data, "a", 0));
def flags = Map.get(data, "b", Null);
print(Collections.len(flags));
print(json.stringify(data));
def _cleanup_flags = delete(flags);
def _cleanup_data = delete(data);
"""
    lines = _run_lines(source)
    expected = py_json.loads('{"a": 1, "b": [true, false]}')

    assert int(lines[0]) == expected["a"]
    assert int(lines[1]) == len(expected["b"])
    assert py_json.loads(lines[2]) == expected


def test_stdlib_os_and_pathlib_match_python(tmp_path: PyPath) -> None:
    base = tmp_path / "root"
    child = "note.txt"
    joined = py_os.path.join(base.as_posix(), child)
    expected_dir = py_os.path.dirname(joined)
    expected_name = py_os.path.basename(joined)

    source = f"""
import stdlib.os;
import stdlib.pathlib;

def joined = os.path.join("{base.as_posix()}", "{child}");
print(joined);
print(os.path.basename(joined));
print(os.path.dirname(joined));

def p = pathlib.Path(joined);
print(p.name());
print(p.parent().as_posix());
def _write = p.write_text("hi");
print(os.path.exists(p.as_posix()));
print(p.read_text());
"""
    lines = _run_lines(source)

    assert lines[0] == joined
    assert lines[1] == expected_name
    assert lines[2] == expected_dir
    assert lines[3] == PyPath(joined).name
    assert lines[4] == PyPath(joined).parent.as_posix()
    assert lines[5:] == ["true", "hi"]


def test_stdlib_os_remove_and_pathlib_joinpath(tmp_path: PyPath) -> None:
    base = tmp_path / "root"
    child = "note.txt"
    joined = py_os.path.join(base.as_posix(), child)
    expected = PyPath(joined)
    base.mkdir()
    expected.write_text("cleanup")

    source = f"""
import stdlib.os;
import stdlib.pathlib;

def base = pathlib.Path("{base.as_posix()}");
def child = base.joinpath("{child}");
print(child.as_posix());
print(child.name());
def _exists_before = child.exists();
print(_exists_before);
def _remove = os.remove(child.as_posix());
print(os.path.exists(child.as_posix()));
"""
    lines = _run_lines(source)

    assert lines[0] == joined
    assert lines[1] == expected.name
    assert lines[2:] == ["true", "false"]


def test_stdlib_os_text_helpers_match_python(tmp_path: PyPath) -> None:
    target = tmp_path / "note.txt"
    payload = "hello tiny"

    source = f"""
import stdlib.os;

def _written = os.write_text("{target.as_posix()}", "{payload}");
print(os.path.exists("{target.as_posix()}"));
print(os.read_text("{target.as_posix()}"));
"""
    lines = _run_lines(source)

    assert lines[0] == "true"
    assert lines[1] == payload
    assert target.read_text() == payload


def test_stdlib_statistics_matches_python() -> None:
    source = """
import stdlib.statistics;

def values = new[2, 4, 6, 8, 10];
def floats = new[1.5, 2.5, 3.5];
print(statistics.mean(values));
print(statistics.std(values));
print(statistics.mean(floats));
print(statistics.std(floats));
def _cleanup_values = delete(values);
def _cleanup_floats = delete(floats);
"""
    lines = _run_lines(source)
    values = [2, 4, 6, 8, 10]
    floats = [1.5, 2.5, 3.5]

    assert float(lines[0]) == pytest.approx(py_statistics.mean(values))
    assert float(lines[1]) == pytest.approx(py_statistics.stdev(values))
    assert float(lines[2]) == pytest.approx(py_statistics.mean(floats))
    assert float(lines[3]) == pytest.approx(py_statistics.stdev(floats))


def test_stdlib_collections_map_set_deque_match_python() -> None:
    source = """
def values = new[10, 20, 30];
print(Collections.len(values));
print(Collections.contains(values, 20));
print(Collections.push(values, 40));
print(Collections.pop(values));
def sliced = Collections.slice(values, 1, 3);
print(Collections.len(sliced));
print(heap_get(sliced, 0));
print(heap_get(sliced, 1));

def capitals = Map.new();
def _cap1 = Map.set(capitals, "DE", "Berlin");
def _cap2 = Map.set(capitals, "AT", "Wien");
print(Map.len(capitals));
print(Map.get(capitals, "DE", "?"));
print(Map.has(capitals, "CH"));
def _cap3 = Map.delete(capitals, "AT");
print(Map.len(capitals));

def tags_list = new["a", "b", "a"];
def tags = Set.from_list(tags_list);
print(Set.len(tags));
print(Set.has(tags, "a"));
print(Set.add(tags, "c"));
print(Set.len(tags));

def queue_items = new["a", "b"];
def queue = Deque.new(queue_items);
print(Deque.peek_left(queue));
print(Deque.peek_right(queue));
def _left = Deque.push_left(queue, "start");
def _right = Deque.push_right(queue, "end");
print(Deque.len(queue));
print(Deque.pop_left(queue));
print(Deque.pop_right(queue));
def remaining = Deque.to_list(queue);
print(String.join(remaining, "|"));
def _cleanup_remaining = delete(remaining);
def _cleanup_queue_items = delete(queue_items);
def _cleanup_queue = delete(queue);
def _cleanup_tags_list = delete(tags_list);
def _cleanup_tags = delete(tags);
def _cleanup_sliced = delete(sliced);
def _cleanup_values = delete(values);
def _cleanup_capitals = delete(capitals);
"""
    lines = _run_lines(source)

    py_values = [10, 20, 30]
    expected = [
        str(len(py_values)),
        str(20 in py_values).lower(),
        str(len(py_values) + 1),
        str(40),
    ]
    py_values.append(40)
    py_values.pop()
    py_slice = py_values[1:3]
    expected.extend(
        [
            str(len(py_slice)),
            str(py_slice[0]),
            str(py_slice[1]),
        ],
    )

    capitals = {"DE": "Berlin", "AT": "Wien"}
    expected.extend(
        [
            str(len(capitals)),
            capitals["DE"],
            str("CH" in capitals).lower(),
        ],
    )
    capitals.pop("AT")
    expected.append(str(len(capitals)))

    tags = {"a", "b"}
    expected.extend(
        [
            str(len(tags)),
            str("a" in tags).lower(),
            str("c" not in tags).lower(),
            str(len(tags | {"c"})),
        ],
    )

    queue = py_deque(["a", "b"])
    expected.extend(
        [
            queue[0],
            queue[-1],
        ],
    )
    queue.appendleft("start")
    queue.append("end")
    expected.append(str(len(queue)))
    expected.append(queue.popleft())
    expected.append(queue.pop())
    expected.append("|".join(queue))

    assert lines == expected


def test_stdlib_file_helpers_match_python(tmp_path: PyPath) -> None:
    target = tmp_path / "note.txt"
    payload = "hello tiny"

    source = f"""
def _write = File.write("{target.as_posix()}", "{payload}");
print(File.exists("{target.as_posix()}"));
print(File.read("{target.as_posix()}"));
def _remove = File.remove("{target.as_posix()}");
print(File.exists("{target.as_posix()}"));
"""
    lines = _run_lines(source)

    assert lines == ["true", payload, "false"]
    assert not target.exists()
