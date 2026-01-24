"""Covers language-server completions, hover, definitions, and diagnostics."""

from language_server import TinyLanguageServer


def test_completion_offers_symbols():
    """Symbols declared in source should appear in completion results."""
    server = TinyLanguageServer("fn answer() { return 42; }")
    labels = [item.label for item in server.completions("a")]
    assert "answer" in labels


def test_completion_includes_keywords_and_namespaces():
    """Verify keywords appear while namespace-qualified symbols are resolved."""
    server = TinyLanguageServer("namespace Math { fn add(x, y) { return x + y; } }")
    labels = [item.label for item in server.completions("M")]
    assert "Math.add" in labels
    assert "match" not in labels  # unrelated keyword
    keyword_labels = [item.label for item in server.completions("wh")]
    assert "while" in keyword_labels


def test_completion_offers_unqualified_members():
    """Namespace members should be offered both qualified and unqualified."""
    server = TinyLanguageServer("namespace Tools { fn double(x) { return x * 2; } }")
    labels = [item.label for item in server.completions("d")]
    assert "double" in labels
    assert "Tools.double" in [item.label for item in server.completions("Tools.")]


def test_completion_includes_kinds():
    """Completion items should include a kind identifier."""
    server = TinyLanguageServer("fn alpha(a) { return a; }")
    match = next(item for item in server.completions("al") if item.label == "alpha")
    assert match.kind == "function"


def test_hover_returns_position():
    """Hover responses should contain symbol and position data."""
    server = TinyLanguageServer("fn ping() { return 1; }")
    hover = server.hover("ping")
    assert hover is not None
    assert hover.symbol == "ping"
    assert isinstance(hover.position, tuple)
    assert all(isinstance(value, int) and value >= 0 for value in hover.position)


def test_hover_includes_signature_detail():
    """Hover details should surface callable signatures."""
    source = "\n".join(
        [
            "fn add(x: number, y) -> number { return x + y; }",
            "class Greeter { fn hello(self, name) { return name; } }",
        ]
    )
    server = TinyLanguageServer(source)
    hover = server.hover("add")
    assert hover is not None
    assert hover.detail.startswith("fn add(x: number, y) -> number")
    class_hover = server.hover("Greeter.hello")
    assert class_hover is not None
    assert class_hover.detail.startswith("method hello(self, name)")


def test_hover_missing_symbol_returns_none():
    """Unknown identifiers should not return hover information."""
    server = TinyLanguageServer("fn ping() { return 1; }")
    assert server.hover("pong") is None


def test_definition_returns_source_position():
    """Definition lookup should map to the original source location."""
    source = "namespace Math { fn add(x, y) { return x + y; } }\nfn main() { return Math.add(1, 2); }"
    server = TinyLanguageServer(source)
    pos = server.definition("Math.add")
    assert pos is not None
    assert pos.line == 1
    assert pos.col >= 1


def test_workspace_symbols_include_container_names():
    """Workspace symbols should include the container name for methods."""
    source = "class Greeter { fn hello(self, name) { return name; } }"
    server = TinyLanguageServer(source)
    results = server.workspace_symbols("hello")
    assert results
    assert results[0].name.endswith("hello")
    assert results[0].container == "Greeter"


def test_diagnostics_from_lints():
    """Lint diagnostics should be empty for clean sources."""
    server = TinyLanguageServer("fn greet() -> string { return \"hi\"; }\ndef ignored1 = greet();")
    diags = server.diagnostics()
    assert diags == []


def test_diagnostics_include_source_range_and_code():
    """Diagnostics should include error codes and a source span."""
    source = "fn describe(x: number) -> number { if (x > 0) { return x; } }"
    server = TinyLanguageServer(source)
    diags = server.diagnostics()
    assert diags
    diag = diags[0]
    assert diag.code == "E010"
    assert isinstance(diag.range, tuple)
    assert len(diag.range) == 4
    assert all(isinstance(value, int) for value in diag.range)


def test_diagnostics_use_span_when_available():
    """Multi-line spans should be captured by the diagnostic range."""
    source = "\n".join(
        [
            "fn describe(x: number) -> number {",
            "    if (x > 0) {",
            "        return x;",
            "    }",
            "}",
        ]
    )
    server = TinyLanguageServer(source)
    diags = server.diagnostics()
    assert diags
    start_line, start_col, end_line, end_col = diags[0].range
    assert start_line == 1
    assert end_line > start_line  # Span should cover the closing brace.
    assert end_col >= 2  # Exclusive column should advance beyond the brace.


def test_diagnostics_surface_parse_errors():
    """Parse errors should surface as diagnostics with ranges."""
    source = "fn incomplete() { return 1 "
    server = TinyLanguageServer(source)
    diags = server.diagnostics()
    assert diags
    diag = diags[0]
    assert diag.code
    assert isinstance(diag.range, tuple)
    assert len(diag.range) == 4
