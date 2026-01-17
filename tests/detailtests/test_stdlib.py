import random

import pytest


def test_stdlib_functions_cover_math_string_and_collections(run_tiny_source):
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
        def sliced = Collections.slice(new[10, 20, 30, 40], 1, 3);
        print(heap_get(sliced, 0));
        print(Collections.contains(sliced, 30));
        print(Collections.contains(sliced, 99));
        """,
    )

    assert (
        out
        == "5\n8\n3\n10\n-2\n10\na\na-b-c\ntrue\ntiny_language\ntrue\ntrue\ntrue\nfalse\nHELLO\nhello\npadded\npadded\npadded  \n  padded\nhahaha\n2\n3\n3\n3\n2\n20\ntrue\nfalse\n"
    )


def test_collections_pop_errors_on_empty(run_tiny_source):
    with pytest.raises(Exception, match=r"pop from empty collection"):
        run_tiny_source(
            """
            def arr = new[1];
            print(Collections.pop(arr));
            print(Collections.pop(arr));
            """,
        )


def test_tl_stdlib_math_module_import(run_tiny_source):
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
    random.seed(1)
    out = run_tiny_source(
        """
        import stdlib.random;
        print(random.randint(1, 6));
        print(random.choice(new["rot", "gruen", "blau"]));
        def items = new["a", "b", "c"];
        print(random.shuffle(items));
        print(String.join(items, ""));
        """,
    )

    assert out == "2\nblau\n3\ncba\n"


def test_tl_stdlib_statistics_module_import(run_tiny_source):
    out = run_tiny_source(
        """
        import stdlib.statistics;
        def values = new[1, 2, 3, 4];
        print(statistics.mean(values));
        print(statistics.std(values));
        """,
    )

    assert out == "2.5\n1.2909944487358056\n"


def test_tl_stdlib_string_module_import(run_tiny_source):
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
        """,
    )

    assert out == "a-b-c\ntrue\nHELLO\nhello\npadded\npadded\npadded  \n  padded\nhaha\n"


def test_tl_stdlib_json_module_import(run_tiny_source):
    out = run_tiny_source(
        """
        import stdlib.json;
        def data = json.loads("{\\"a\\": 1, \\"b\\": [2, 3]}");
        print(Map.get(data, "a", 0));
        print(Collections.len(Map.get(data, "b", new[])));
        print(json.dumps(data));
        """,
    )

    assert out == '1\n2\n{"a": 1, "b": [2, 3]}\n'


def test_tl_stdlib_os_and_pathlib_module_import(run_tiny_source, tmp_path):
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
    with pytest.raises(Exception, match=r"repeat count must be non-negative"):
        run_tiny_source('print(String.repeat("x", -1));')

    with pytest.raises(Exception, match=r"repeat expects an integer count"):
        run_tiny_source('print(String.repeat("x", "oops"));')


def test_map_set_and_deque_helpers(run_tiny_source):
    out = run_tiny_source(
        """
        def capitals = Map.from_entries(new[
            new["DE", "Berlin"],
            new["AT", "Wien"]
        ]);
        print(Map.get(capitals, "DE", "?"));
        print(Map.has(capitals, "CH"));
        def _unused41 = Map.set(capitals, "CH", "Bern");
        print(Map.len(capitals));
        print(Map.get(capitals, "CH", "?"));
        print(heap_get(Map.keys(capitals), 1));

        def features = Set.from_list(String.split("map,set,deque", ","));
        print(Set.add(features, "json"));
        print(Set.len(features));
        print(Set.has(features, "map"));

        def todo = Deque.new(String.split("a,b", ","));
        def _dq = Deque.push_left(todo, "start");
        print(Deque.peek_right(todo));
        print(Deque.pop_left(todo));
        print(String.join(Deque.to_list(todo), "|"));
        """,
    )

    assert out == "Berlin\nfalse\n3\nBern\nAT\ntrue\n4\ntrue\nb\nstart\na|b\n"


def test_random_file_and_json_helpers(run_tiny_source, tmp_path):
    random.seed(0)
    file_path = tmp_path / "demo.json"
    out = run_tiny_source(
        f"""
        print(Random.randint(1, 10));
        print(Random.choice(new["rot", "gruen", "blau"]));

        def data = JSON.parse("{{\\"n\\": [1, 2], \\"flag\\": true}}");
        def _unused53 = Map.set(data, "extra", 5);
        def path = "{file_path.as_posix()}";
        def _write = File.write(path, JSON.stringify(data));
        print(File.exists(path));
        def text = File.read(path);
        print(String.contains(text, "flag"));
        print(Map.get(JSON.parse(text), "flag", false));
        def _rm = File.remove(path);
        print(File.exists(path));
        """
    )

    lines = out.strip().split("\n")
    assert lines[0].isdigit()
    assert lines[1] in {"rot", "gruen", "blau"}
    assert lines[2:] == ["true", "true", "true", "false"]


def test_json_stringify_roundtrip_collections(run_tiny_source):
    out = run_tiny_source(
        """
        def data = Map.new();
        def _nums = Map.set(data, "numbers", new["one", "two", "three"]);
        def _tags = Map.set(data, "tags", Set.from_list(new["b", "a"]));
        def _queue = Map.set(data, "queue", Deque.new(new["x", "y"]));
        def text = JSON.stringify(data);
        print(text);
        def parsed = JSON.parse(text);
        print(JSON.stringify(parsed));
        """,
    )

    lines = out.strip().split("\n")
    assert lines[0] == lines[1]


def test_json_stringify_roundtrip_nested_collections(run_tiny_source):
    out = run_tiny_source(
        """
        def mapping = Map.new();
        def _k1 = Map.set(mapping, "k1", 1);
        def _k2 = Map.set(mapping, "k2", 2);
        def tags = Set.from_list(new["b", "a"]);
        def queue = Deque.new(new["x", "y"]);
        def nested = new[new[1, 2], new[3, new[4, 5]]];
        def values = new[mapping, tags, queue, nested];
        def text = JSON.stringify(values);
        print(text);
        def parsed = JSON.parse(text);
        print(JSON.stringify(parsed));
        """,
    )

    lines = out.strip().split("\n")
    assert lines[0] == lines[1]
