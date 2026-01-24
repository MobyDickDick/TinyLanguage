"""Tests for the TinyLanguage source formatter."""

from formatter import format_import, format_source


def test_formatting_preserves_comments_and_spacing():
    """Ensure formatting normalizes spacing while keeping comments."""
    src = "fn add(x,y){return x+y;}//sum\n"
    expected = """fn add(x, y) {
    return x + y;
}
//sum
"""
    assert format_source(src) == expected


def test_format_import_output():
    """Verify canonical import formatting output."""
    assert format_import("math.core", "core") == "import math.core as core;"
