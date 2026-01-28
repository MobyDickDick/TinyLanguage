"""Tests for the stdlib regex module."""

import pytest


def test_stdlib_regex_match_search_replace(run_tiny_source):
    """Ensure regex helpers return capture lists and replacements."""
    out = run_tiny_source(
        """
        import stdlib.regex;

        def match_result = regex.match("^ab(c+)", "abccc");
        print(Collections.len(match_result));
        print(heap_get(match_result, 0));
        print(heap_get(match_result, 1));
        def _cleanup_match = delete(match_result);

        def search_result = regex.search("b(c+)", "zzabccczz");
        print(Collections.len(search_result));
        print(heap_get(search_result, 0));
        print(heap_get(search_result, 1));
        def _cleanup_search = delete(search_result);

        print(regex.replace("c+", "abccc", "X"));
        """,
    )

    assert out == "2\nabccc\nccc\n2\nbccc\nccc\nabX\n"


def test_stdlib_regex_failure_cases(run_tiny_source):
    """Confirm regex failures and unsupported constructs surface errors."""
    out = run_tiny_source(
        """
        import stdlib.regex;

        def match_result = regex.match("a+", "bbb");
        def search_result = regex.search("a+", "bbb");
        print(match_result == Null);
        print(search_result == Null);
        """,
    )

    assert out == "true\ntrue\n"

    with pytest.raises(Exception, match=r"unsupported regex construct"):
        run_tiny_source(
            """
            import stdlib.regex;
            def _match = regex.match("(?=a)", "a");
            """,
        )
