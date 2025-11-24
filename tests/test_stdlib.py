import pytest


def test_stdlib_functions_cover_math_string_and_collections(run_tiny_source):
    out = run_tiny_source(
        """
        print(Math.abs(-5));
        print(Math.pow(2, 3));
        print(Math.sqrt(9));

        define parts = String.split("a,b,c", ",");
        print(heap_get(parts, 0));
        print(String.join(parts, "-"));
        print(String.contains("tiny language", "lang"));

        define arr = new[1, 2];
        print(Collections.len(arr));
        print(Collections.push(arr, 3));
        print(heap_get(arr, 2));
        print(Collections.pop(arr));
        print(Collections.len(arr));
        """,
    )

    assert out == "5\n8\n3\na\na-b-c\ntrue\n2\n3\n3\n3\n2\n"


def test_collections_pop_errors_on_empty(run_tiny_source):
    with pytest.raises(Exception, match=r"pop from empty collection"):
        run_tiny_source(
            """
            define arr = new[1];
            print(Collections.pop(arr));
            print(Collections.pop(arr));
            """,
        )
