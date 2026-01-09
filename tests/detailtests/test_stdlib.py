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
        print(String.upper("Hello"));
        print(String.lower("Hello"));
        print(String.trim("  padded  "));
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
        == "5\n8\n3\n10\n-2\n10\na\na-b-c\ntrue\ntiny_language\nHELLO\nhello\npadded\nhahaha\n2\n3\n3\n3\n2\n20\ntrue\nfalse\n"
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
        def _ = Map.set(capitals, "CH", "Bern");
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
        def _ = Map.set(data, "extra", 5);
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
