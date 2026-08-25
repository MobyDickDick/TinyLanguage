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


def test_stdlib_regex_character_escapes_are_ascii_only(run_tiny_source):
    """Lock the documented ASCII meaning of portable character escapes."""
    out = run_tiny_source(
        r'''
        import stdlib.regex;

        def ascii_word = regex.search("\\w+", "éclair ASCII_42");
        print(heap_get(ascii_word, 0));
        def _cleanup_word = delete(ascii_word);

        def ascii_digit = regex.search("\\d+", "٣ 42");
        print(heap_get(ascii_digit, 0));
        def _cleanup_digit = delete(ascii_digit);

        print(Regex.search("^\\s$", "\u00a0") == Null);
        print(regex.match("^.$", "é") != Null);
        '''
    )

    assert out == "clair\n42\ntrue\ntrue\n"
