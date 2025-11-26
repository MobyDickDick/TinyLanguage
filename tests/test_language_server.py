from language_server import TinyLanguageServer


def test_completion_offers_symbols():
    server = TinyLanguageServer("fn answer() { return 42; }")
    labels = [item.label for item in server.completions("a")]
    assert "answer" in labels


def test_hover_returns_position():
    server = TinyLanguageServer("fn ping() { return 1; }")
    hover = server.hover("ping")
    assert hover is not None
    assert hover.symbol == "ping"


def test_diagnostics_from_lints():
    server = TinyLanguageServer("fn greet() -> string { return \"hi\"; }\ngreet();")
    diags = server.diagnostics()
    assert diags
    assert diags[0].code == "E011"
