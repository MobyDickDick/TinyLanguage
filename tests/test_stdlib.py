import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from tiny_language import compile_and_run  # noqa: E402


def run_tiny(src: str) -> str:
    return compile_and_run(src)


def test_stdlib_functions_cover_math_string_and_collections():
    out = run_tiny(
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


def test_collections_pop_errors_on_empty():
    with pytest.raises(Exception, match=r"pop from empty collection"):
        run_tiny(
            """
            define arr = new[1];
            print(Collections.pop(arr));
            print(Collections.pop(arr));
            """,
        )
