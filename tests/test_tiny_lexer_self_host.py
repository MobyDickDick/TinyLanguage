import json
import pathlib

from tiny_language import compile_and_run


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
LEXER_SRC = (PROJECT_ROOT / "src_tiny" / "tiny_language_lexer.tiny").read_text(encoding="utf-8")


def _run_lexer_program(body: str) -> str:
    """Execute a Tiny program that expects ``lex`` to be defined in the source."""

    program = LEXER_SRC + "\n\n" + body
    return compile_and_run(program)


def test_tiny_lexer_emits_expected_token_stream():
    source_literal = json.dumps('def a = 7;\nprint("hi"); // comment')
    body = f"""
def tokens = lex({source_literal});
def i = 0;
while (i < len(tokens)) {{
    def tok = heap_get(tokens, i);
    print(tok.kind + ":" + tok.text);
    i = i + 1;
}}
"""

    output = _run_lexer_program(body).strip().splitlines()

    assert output == [
        "KW:def",
        "NAME:a",
        "SYM:=",
        "NUMBER:7",
        "SYM:;",
        "KW:print",
        "SYM:(",
        "STRING:hi",
        "SYM:)",
        "SYM:;",
        "EOF:",
    ]


def test_tiny_lexer_tracks_source_positions():
    source_literal = json.dumps('while (x <= 10) { print(x); }')
    body = f"""
def tokens = lex({source_literal});
def i = 0;
while (i < len(tokens)) {{
    def tok = heap_get(tokens, i);
    print("pos", tok.kind, tok.text, tok.start.line, tok.start.column, tok.stop.line, tok.stop.column);
    i = i + 1;
}}
"""

    lines = _run_lexer_program(body).strip().splitlines()
    # spot-check a few representative tokens (keyword, operator, identifier)
    assert lines[0] == "pos KW while 1 1 1 5"
    assert lines[1] == "pos SYM ( 1 7 1 7"
    assert lines[3] == "pos OP <= 1 10 1 11"
    assert lines[4] == "pos NUMBER 10 1 13 1 14"
    assert lines[7] == "pos KW print 1 19 1 23"
    assert lines[-1].startswith("pos EOF")  # EOF should come last


def test_tiny_lexer_handles_ops_and_escaped_strings():
    source_literal = json.dumps(
        'if (a == b && c != d || e >= f && g <= h) { print("slash: \\\\"); }'
    )
    body = f"""
def tokens = lex({source_literal});
def i = 0;
while (i < len(tokens)) {{
    def tok = heap_get(tokens, i);
    print(tok.kind + ":" + tok.text);
    i = i + 1;
}}
"""

    output = _run_lexer_program(body).strip().splitlines()

    assert output == [
        "KW:if",
        "SYM:(",
        "NAME:a",
        "OP:==",
        "NAME:b",
        "OP:&&",
        "NAME:c",
        "OP:!=",
        "NAME:d",
        "OP:||",
        "NAME:e",
        "OP:>=",
        "NAME:f",
        "OP:&&",
        "NAME:g",
        "OP:<=",
        "NAME:h",
        "SYM:)",
        "SYM:{",
        "KW:print",
        "SYM:(",
        "STRING:slash: \\",
        "SYM:)",
        "SYM:;",
        "SYM:}",
        "EOF:",
    ]


def test_tiny_lexer_multiline_string_span_tracks_end_line():
    source_literal = "\"\\\"a\\nb\\\"\""
    body = f"""
def tokens = lex({source_literal});
def tok = heap_get(tokens, 0);
print("pos", tok.kind, tok.start.line, tok.start.column, tok.stop.line, tok.stop.column);
"""

    output = _run_lexer_program(body).strip().splitlines()
    assert output == ["pos STRING 1 1 2 2"]
