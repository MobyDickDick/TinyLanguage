"""Tests for stdlib."""

import random

import pytest


def test_stdlib_functions_cover_math_string_and_collections(run_tiny_source, monkeypatch):
    """Test that stdlib functions cover math string and collections."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    out = run_tiny_source(
        """
        print(Math.abs(-5));
        print(Math.pow(2, 3));
        print(Math.sqrt(9));
        print(Math.max(-2, 10));
        print(Math.min(-2, 10));
        print(Math.clamp(42, 0, 10));

        def parts = String.split("a,b,c", ",");
        print(heap_get(parts, 0));
        print(String.join(parts, "-"));
        print(String.contains("tiny language", "lang"));
        print(String.replace("tiny language", " ", "_"));
        print(String.starts_with("tiny language", "tiny"));
        print(String.ends_with("tiny language", "age"));
        print(String.is_digit("12345"));
        print(String.is_digit("12a"));
        print(String.upper("Hello"));
        print(String.lower("Hello"));
        print(String.trim("  padded  "));
        print(String.strip("  padded  "));
        print(String.lstrip("  padded  "));
        print(String.rstrip("  padded  "));
        print(String.repeat("ha", 3));

        def arr = new[1, 2];
        print(Collections.len(arr));
        print(Collections.push(arr, 3));
        print(heap_get(arr, 2));
        print(Collections.pop(arr));
        print(Collections.len(arr));
        def source = new[10, 20, 30, 40];
        def sliced = Collections.slice(source, 1, 3);
        print(heap_get(sliced, 0));
        print(Collections.contains(sliced, 30));
        print(Collections.contains(sliced, 99));
        def _cleanup_parts = delete(parts);
        def _cleanup_sliced = delete(sliced);
        def _cleanup_source = delete(source);
        def _cleanup_arr = delete(arr);
        """,
    )

    assert (
        out
        == "5\n8\n3\n10\n-2\n10\na\na-b-c\ntrue\ntiny_language\ntrue\ntrue\ntrue\nfalse\nHELLO\nhello\npadded\npadded\npadded  \n  padded\nhahaha\n2\n3\n3\n3\n2\n20\ntrue\nfalse\n"
    )


def test_collections_pop_errors_on_empty(run_tiny_source):
    """Test that collections pop errors on empty."""
    with pytest.raises(Exception, match=r"pop from empty collection"):
        run_tiny_source(
            """
            def arr = new[1];
            print(Collections.pop(arr));
            print(Collections.pop(arr));
            """,
        )


def test_tl_stdlib_math_module_import(run_tiny_source):
    """Test that tl stdlib math module import."""
    out = run_tiny_source(
        """
        import stdlib.math;
        print(math.round_digits(math.pi, 3));
        print(math.round_digits(math.tau, 2));
        print(math.round_digits(math.e, 3));
        print(math.sqrt(9));
        print(math.clamp(12, 0, 10));
        print(math.sign(-5));
        """,
    )

    assert out == "3.142\n6.28\n2.718\n3\n10\n-1\n"


def test_tl_stdlib_random_module_import(run_tiny_source):
    """Test that tl stdlib random module import."""
    random.seed(1)
    out = run_tiny_source(
        """
        import stdlib.random;
        print(random.randint(1, 6));
        def colors = new["rot", "gruen", "blau"];
        print(random.choice(colors));
        def items = new["a", "b", "c"];
        print(random.shuffle(items));
        print(String.join(items, ""));
        def _cleanup_colors = delete(colors);
        def _cleanup_items = delete(items);
        """,
    )

    assert out == "2\nblau\n3\ncba\n"


def test_tl_stdlib_statistics_module_import(run_tiny_source):
    """Test that tl stdlib statistics module import."""
    out = run_tiny_source(
        """
        import stdlib.statistics;
        def values = new[1, 2, 3, 4];
        print(statistics.mean(values));
        print(statistics.std(values));
        def _cleanup_values = delete(values);
        """,
    )

    assert out == "2.5\n1.2909944487358056\n"


def test_tl_stdlib_string_module_import(run_tiny_source):
    """Test that tl stdlib string module import."""
    out = run_tiny_source(
        """
        import stdlib.string;
        def parts = string.split("a,b,c", ",");
        print(string.join(parts, "-"));
        print(string.contains("tiny language", "lang"));
        print(string.upper("hello"));
        print(string.lower("HELLO"));
        print(string.trim("  padded  "));
        print(string.strip("  padded  "));
        print(string.lstrip("  padded  "));
        print(string.rstrip("  padded  "));
        print(string.repeat("ha", 2));
        def _cleanup_parts = delete(parts);
        """,
    )

    assert out == "a-b-c\ntrue\nHELLO\nhello\npadded\npadded\npadded  \n  padded\nhaha\n"


def test_tl_stdlib_json_module_import(run_tiny_source):
    """Test that tl stdlib json module import."""
    out = run_tiny_source(
        """
        import stdlib.json;
        def data = json.loads("{\\"a\\": 1, \\"b\\": [2, 3]}");
        print(Map.get(data, "a", 0));
        def values = Map.get(data, "b", Null);
        print(Collections.len(values));
        print(json.dumps(data));
        def _cleanup_values = delete(values);
        def _cleanup_data = delete(data);
        """,
    )

    assert out == '1\n2\n{"a":1,"b":[2,3]}\n'


def test_tl_stdlib_os_and_pathlib_module_import(run_tiny_source, tmp_path):
    """Test that tl stdlib os and pathlib module import."""
    file_path = tmp_path / "dir" / "note.txt"
    out = run_tiny_source(
        f"""
        import stdlib.os;
        import stdlib.pathlib;

        def joined = os.path.join("{tmp_path.as_posix()}", "dir");
        print(joined);

        def p = pathlib.Path("{file_path.as_posix()}");
        print(p.parent().as_posix());
        def _written = p.write_text("ok");
        print(os.path.exists("{file_path.as_posix()}"));
        print(p.read_text());
        """,
    )

    expected_joined = f"{tmp_path.as_posix()}/dir"
    expected_parent = file_path.parent.as_posix()
    assert out == f"{expected_joined}\n{expected_parent}\ntrue\nok\n"


def test_string_repeat_validates_count(run_tiny_source):
    """Test that string repeat validates count."""
    with pytest.raises(Exception, match=r"repeat count must be non-negative"):
        run_tiny_source('print(String.repeat("x", -1));')

    with pytest.raises(Exception, match=r"repeat expects an integer count"):
        run_tiny_source('print(String.repeat("x", "oops"));')


def test_map_set_and_deque_helpers(run_tiny_source):
    """Test that map set and deque helpers."""
    out = run_tiny_source(
        """
        def capitals = Map.new();
        def _cap1 = Map.set(capitals, "DE", "Berlin");
        def _cap2 = Map.set(capitals, "AT", "Wien");
        print(Map.get(capitals, "DE", "?"));
        print(Map.has(capitals, "CH"));
        def _unused41 = Map.set(capitals, "CH", "Bern");
        print(Map.len(capitals));
        print(Map.get(capitals, "CH", "?"));
        def keys = Map.keys(capitals);
        print(heap_get(keys, 1));

        def feature_parts = String.split("map,set,deque", ",");
        def features = Set.from_list(feature_parts);
        print(Set.add(features, "json"));
        print(Set.len(features));
        print(Set.has(features, "map"));

        def todo_parts = String.split("a,b", ",");
        def todo = Deque.new(todo_parts);
        def _dq = Deque.push_left(todo, "start");
        print(Deque.peek_right(todo));
        print(Deque.pop_left(todo));
        def todo_list = Deque.to_list(todo);
        print(String.join(todo_list, "|"));
        def _cleanup_keys = delete(keys);
        def _cleanup_feature_parts = delete(feature_parts);
        def _cleanup_features = delete(features);
        def _cleanup_todo_parts = delete(todo_parts);
        def _cleanup_todo_list = delete(todo_list);
        def _cleanup_todo = delete(todo);
        def _cleanup_capitals = delete(capitals);
        """,
    )

    assert out == "Berlin\nfalse\n3\nBern\nAT\ntrue\n4\ntrue\nb\nstart\na|b\n"


def test_random_file_and_json_helpers(run_tiny_source, tmp_path):
    """Test that random file and json helpers."""
    random.seed(0)
    file_path = tmp_path / "demo.json"
    out = run_tiny_source(
        f"""
        print(Random.randint(1, 10));
        def colors = new["rot", "gruen", "blau"];
        print(Random.choice(colors));

        def data = JSON.parse("{{\\"n\\": [1, 2], \\"flag\\": true}}");
        def _unused53 = Map.set(data, "extra", 5);
        def path = "{file_path.as_posix()}";
        def _write = File.write(path, JSON.stringify(data));
        print(File.exists(path));
        def text = File.read(path);
        print(String.contains(text, "flag"));
        def parsed = JSON.parse(text);
        print(Map.get(parsed, "flag", false));
        def _rm = File.remove(path);
        print(File.exists(path));
        def _cleanup_parsed = delete(parsed);
        def _cleanup_data = delete(data);
        def _cleanup_colors = delete(colors);
        """
    )

    lines = out.strip().split("\n")
    assert lines[0].isdigit()
    assert lines[1] in {"rot", "gruen", "blau"}
    assert lines[2:] == ["true", "true", "true", "false"]


def test_json_stringify_roundtrip_collections(run_tiny_source):
    """Test that json stringify roundtrip collections."""
    out = run_tiny_source(
        """
        def data = Map.new();
        def numbers = new["one", "two", "three"];
        def tags_list = new["b", "a"];
        def queue_list = new["x", "y"];
        def _nums = Map.set(data, "numbers", numbers);
        def tags = Set.from_list(tags_list);
        def _tags = Map.set(data, "tags", tags);
        def queue = Deque.new(queue_list);
        def _queue = Map.set(data, "queue", queue);
        def text = JSON.stringify(data);
        print(text);
        def parsed = JSON.parse(text);
        print(JSON.stringify(parsed));
        def _cleanup_numbers = delete(numbers);
        def _cleanup_tags_list = delete(tags_list);
        def _cleanup_queue_list = delete(queue_list);
        def _cleanup_tags = delete(tags);
        def _cleanup_queue = delete(queue);
        def _cleanup_parsed = delete(parsed);
        def _cleanup_data = delete(data);
        """,
    )

    lines = out.strip().split("\n")
    assert lines[0] == '{"numbers":["one","two","three"],"tags":["a","b"],"queue":["x","y"]}'
    assert lines[0] == lines[1]


def test_json_stringify_roundtrip_nested_collections(run_tiny_source):
    """Test that json stringify roundtrip nested collections."""
    out = run_tiny_source(
        """
        def mapping = Map.new();
        def _k1 = Map.set(mapping, "k1", "one");
        def _k2 = Map.set(mapping, "k2", "two");
        def tags_list = new["b", "a"];
        def queue_list = new["x", "y"];
        def nested_a = new["alpha", "beta"];
        def nested_b_inner = new["delta", "epsilon"];
        def nested_b = new["gamma", nested_b_inner];
        def tags = Set.from_list(tags_list);
        def queue = Deque.new(queue_list);
        def nested = new[nested_a, nested_b];
        def values = new[mapping, tags, queue, nested];
        def text = JSON.stringify(values);
        print(text);
        def parsed = JSON.parse(text);
        print(JSON.stringify(parsed));
        def _cleanup_values = delete(values);
        def _cleanup_nested_a = delete(nested_a);
        def _cleanup_nested_b_inner = delete(nested_b_inner);
        def _cleanup_nested_b = delete(nested_b);
        def _cleanup_nested = delete(nested);
        def _cleanup_queue_list = delete(queue_list);
        def _cleanup_tags_list = delete(tags_list);
        def _cleanup_queue = delete(queue);
        def _cleanup_tags = delete(tags);
        def _cleanup_mapping = delete(mapping);
        def _cleanup_parsed = delete(parsed);
        """,
    )

    lines = out.strip().split("\n")
    assert lines[0] == '[{"k1":"one","k2":"two"},["a","b"],["x","y"],[["alpha","beta"],["gamma",["delta","epsilon"]]]]'
    assert lines[0] == lines[1]


def test_json_stringify_roundtrip_heap_nested_lists(run_tiny_source):
    """Test that json stringify roundtrip heap nested lists."""
    out = run_tiny_source(
        """
        def inner = Map.new();
        def _a = Map.set(inner, "a", 101);
        def values_b = new[201, 202];
        def flags_list = new["on", "off"];
        def queue_list = new["left", "right"];
        def nested_left = new[301, 302];
        def nested_right_left = new[303];
        def nested_right_right = new[304, 305];
        def nested_right = new[nested_right_left, nested_right_right];
        def nested = new[nested_left, nested_right];
        def _b = Map.set(inner, "b", values_b);
        def flags = Set.from_list(flags_list);
        def queue = Deque.new(queue_list);
        def data = Map.new();
        def _inner = Map.set(data, "inner", inner);
        def _flags = Map.set(data, "flags", flags);
        def _queue = Map.set(data, "queue", queue);
        def _nested = Map.set(data, "nested", nested);
        def text = JSON.stringify(data);
        print(text);
        def parsed = JSON.parse(text);
        print(JSON.stringify(parsed));
        def _cleanup_values_b = delete(values_b);
        def _cleanup_flags_list = delete(flags_list);
        def _cleanup_queue_list = delete(queue_list);
        def _cleanup_nested_left = delete(nested_left);
        def _cleanup_nested_right_left = delete(nested_right_left);
        def _cleanup_nested_right_right = delete(nested_right_right);
        def _cleanup_nested_right = delete(nested_right);
        def _cleanup_nested = delete(nested);
        def _cleanup_flags = delete(flags);
        def _cleanup_queue = delete(queue);
        def _cleanup_inner = delete(inner);
        def _cleanup_parsed = delete(parsed);
        def _cleanup_data = delete(data);
        """,
    )

    lines = out.strip().split("\n")
    assert (
        lines[0]
        == '{"inner":{"a":101,"b":[201,202]},"flags":["off","on"],"queue":["left","right"],"nested":[[301,302],[[303],[304,305]]]}'
    )
    assert lines[0] == lines[1]
