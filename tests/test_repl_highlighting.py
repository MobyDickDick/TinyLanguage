from tiny_language_highlighting import PYGMENTS_AVAILABLE, highlight_source


def test_highlight_source_is_optional() -> None:
    snippet = "define x = 1; // highlight me"
    highlighted = highlight_source(snippet)
    if PYGMENTS_AVAILABLE:
        assert isinstance(highlighted, str)
        assert "define" in highlighted
    else:
        assert highlighted is None
