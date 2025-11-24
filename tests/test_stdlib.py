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

        define parts = String.split("a,b,c", ",");
        print(heap_get(parts, 0));
        print(String.join(parts, "-"));
        print(String.contains("tiny language", "lang"));
        print(String.upper("Hello"));
        print(String.lower("Hello"));
        print(String.trim("  padded  "));
        print(String.repeat("ha", 3));

        define arr = new[1, 2];
        print(Collections.len(arr));
        print(Collections.push(arr, 3));
        print(heap_get(arr, 2));
        print(Collections.pop(arr));
        print(Collections.len(arr));
        define sliced = Collections.slice(new[10, 20, 30, 40], 1, 3);
        print(heap_get(sliced, 0));
        print(Collections.contains(sliced, 30));
        print(Collections.contains(sliced, 99));
        """,
    )

    assert (
        out
        == "5\n8\n3\n10\n-2\n10\na\na-b-c\ntrue\nHELLO\nhello\npadded\nhahaha\n2\n3\n3\n3\n2\n20\ntrue\nfalse\n"
    )


def test_collections_pop_errors_on_empty(run_tiny_source):
    with pytest.raises(Exception, match=r"pop from empty collection"):
        run_tiny_source(
            """
            define arr = new[1];
            print(Collections.pop(arr));
            print(Collections.pop(arr));
            """,
        )


def test_string_repeat_validates_count(run_tiny_source):
    with pytest.raises(Exception, match=r"repeat count must be non-negative"):
        run_tiny_source('print(String.repeat("x", -1));')

    with pytest.raises(Exception, match=r"repeat expects an integer count"):
        run_tiny_source('print(String.repeat("x", "oops"));')
