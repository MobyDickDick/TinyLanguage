from language_server import TinyLanguageServer


def test_completion_offers_symbols():
    server = TinyLanguageServer("fn answer() { return 42; }")
    labels = [item.label for item in server.completions("a")]
    assert "answer" in labels


def test_completion_includes_keywords_and_namespaces():
    server = TinyLanguageServer("namespace Math { fn add(x, y) { return x + y; } }")
    labels = [item.label for item in server.completions("M")]
    assert "Math.add" in labels
    assert "match" not in labels  # unrelated keyword
    keyword_labels = [item.label for item in server.completions("wh")]
    assert "while" in keyword_labels


def test_hover_returns_position():
    server = TinyLanguageServer("fn ping() { return 1; }")
    hover = server.hover("ping")
    assert hover is not None
    assert hover.symbol == "ping"
    assert isinstance(hover.position, tuple)
    assert all(isinstance(value, int) and value >= 0 for value in hover.position)


def test_hover_missing_symbol_returns_none():
    server = TinyLanguageServer("fn ping() { return 1; }")
    assert server.hover("pong") is None


def test_diagnostics_from_lints():
    server = TinyLanguageServer("fn greet() -> string { return \"hi\"; }\ngreet();")
    diags = server.diagnostics()
    assert diags
    assert diags[0].code == "E011"


def test_diagnostics_include_source_range_and_code():
    source = "fn describe(x: number) -> number { if (x > 0) { return x; } }"
    server = TinyLanguageServer(source)
    diags = server.diagnostics()
    assert diags
    diag = diags[0]
    assert diag.code == "E010"
    assert isinstance(diag.range, tuple)
    assert len(diag.range) == 4
    assert all(isinstance(value, int) for value in diag.range)
