"""Tests for the stdlib csv module wrapper."""

import pytest

from tests.detailtests.stdlib_helpers import run_stdlib_module, stdlib_program


def test_stdlib_csv_parse_defaults(run_tiny_source):
    """Parse CSV text into rows using default delimiter/quote settings."""
    out = run_stdlib_module(
        run_tiny_source,
        "csv",
        """
        def rows = csv.parse("name,score\nAda,10\nLinus,12");
        print(Collections.len(rows));
        def header = heap_get(rows, 0);
        def row1 = heap_get(rows, 1);
        def row2 = heap_get(rows, 2);
        print(String.join(header, "|"));
        print(String.join(row1, "|"));
        print(String.join(row2, "|"));
        def _cleanup_header = delete(header);
        def _cleanup_row1 = delete(row1);
        def _cleanup_row2 = delete(row2);
        def _cleanup_rows = delete(rows);
        """,
    )

    assert out == "3\nname|score\nAda|10\nLinus|12\n"


def test_stdlib_csv_parse_with_header(run_tiny_source):
    """Parse CSV text into dictionaries when a header row is present."""
    out = run_stdlib_module(
        run_tiny_source,
        "csv",
        """
        def text = "name,score,team\nAda,10\nLinus,12,Kernel,Extra";
        def rows = csv.parse_with_header(text);
        print(Collections.len(rows));
        def first = heap_get(rows, 0);
        def second = heap_get(rows, 1);
        print(Map.get(first, "name", ""));
        print(Map.get(first, "team", "missing"));
        print(Map.get(second, "team", "missing"));
        def _cleanup_first = delete(first);
        def _cleanup_second = delete(second);
        def _cleanup_rows = delete(rows);
        """,
    )

    assert out == "2\nAda\nNull\nKernel\n"


def test_stdlib_csv_stringify_with_headers(run_tiny_source):
    """Serialize CSV data deterministically with explicit headers."""
    out = run_stdlib_module(
        run_tiny_source,
        "csv",
        """
        def headers = new["name", "note"];
        def row1 = Map.new();
        Map.set(row1, "name", "Ada");
        Map.set(row1, "note", "hello");
        def row2 = Map.new();
        Map.set(row2, "name", "Linus, Jr.");
        Map.set(row2, "note", "\\\"kernel\\\"");
        def rows = new[row1, row2];
        print(csv.stringify_with_headers(rows, headers));
        def _cleanup_row1 = delete(row1);
        def _cleanup_row2 = delete(row2);
        def _cleanup_rows = delete(rows);
        def _cleanup_headers = delete(headers);
        """,
    )

    assert out == "name,note\nAda,hello\n\"Linus, Jr.\",\"\"\"kernel\"\"\"\n"


def test_stdlib_csv_invalid_delimiter_raises(run_tiny_source):
    """Invalid delimiter or quote inputs should raise a ValueError."""
    with pytest.raises(Exception, match=r"delimiter must be a single character"):
        run_tiny_source(
            stdlib_program(
                "csv",
                """
                def _rows = csv.parse_with_options("a,b", "||", "\\\"", false);
                """,
            ),
        )

    with pytest.raises(Exception, match=r"quote must be a single character"):
        run_tiny_source(
            stdlib_program(
                "csv",
                """
                def _rows = csv.parse_with_options("a,b", ",", "''", false);
                """,
            ),
        )
