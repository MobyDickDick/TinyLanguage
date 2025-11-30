"""TinyLanguage formatting utilities.

The formatter is intentionally minimal: it preserves the existing syntax and
comments while enforcing a handful of layout rules so that files become
predictable and diff-friendly.

Rules:
- **Spacing**: binary operators, keyword/identifier boundaries and commas are
  padded with a single space. Parentheses/brackets stay tight to their inner
  content, and member access via `.` never inserts spaces.
- **Semikolons**: every statement delimiter stays attached to the preceding
  token and ends the current line.
- **Imports**: imports are normalised to `import <path> [as <alias>];` with a
  single space between the parts. They are kept in their original order; linting
  is responsible for placement checks.

The implementation works directly on the lexer stream (augmented to retain
comments) so it can be reused without going through the full parser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Sequence


@dataclass
class _FmtToken:
    kind: str
    text: str


def _tokenize_with_comments(src: str) -> Iterator[_FmtToken]:
    """Yield tokens while preserving line comments.

    The standard lexer drops comments. For formatting we want to keep them, so
    we manually scan for ``//`` and otherwise fall back to the regular lexer.
    """

    from tiny_language import Lexer

    lx = Lexer(src)
    buf = src
    pos = 0
    while pos < len(buf):
        if buf.startswith("//", pos):
            end = buf.find("\n", pos)
            end = len(buf) if end == -1 else end
            yield _FmtToken("COMMENT", buf[pos:end].rstrip())
            pos = end
            continue
        lx.i = pos
        lx.line = src.count("\n", 0, pos) + 1
        last_nl = src.rfind("\n", 0, pos)
        lx.col = pos - (last_nl + 1) + 1
        token = lx.next_token()
        pos = lx.i
        if token.kind == "EOF":
            break
        yield _FmtToken(token.kind, token.text)


def _needs_space(prev: _FmtToken | None, curr: _FmtToken) -> bool:
    if prev is None:
        return False

    no_space_before = {";", ",", ")", "]", "}", "."}
    no_space_after = {"(", "[", "{"}

    if curr.text in no_space_before:
        return False
    if prev.text in no_space_after:
        return False
    if prev.text in {",", ":"}:
        return True

    operator_like = {"=", "+", "-", "*", "/", "^", "==", "!=", "<", ">", "<=", ">=", "&&", "||"}
    from tiny_language import KEYWORDS as keyword_like

    if curr.text in {"(", "["}:
        return prev.kind == "KW"
    if curr.text == "{":
        return prev is not None and prev.text not in no_space_after
    if prev.text in operator_like or curr.text in operator_like:
        return True
    if prev.text in keyword_like or curr.text in keyword_like:
        return True
    if prev.kind in {"NAME", "NUMBER", "STRING", "KW"} and curr.kind in {"NAME", "NUMBER", "STRING", "KW"}:
        return True
    if prev.text in {")",
        "]",
        "}",
    } and curr.kind in {"NAME", "NUMBER", "STRING", "KW"}:
        return True
    return False


def format_source(src: str, *, indent: int = 4) -> str:
    tokens = list(_tokenize_with_comments(src))
    lines: List[str] = []
    current = ""
    depth = 0

    def flush(force: bool = False) -> None:
        nonlocal current
        if current or force:
            lines.append(current.rstrip())
            current = ""

    for idx, tok in enumerate(tokens):
        nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None

        if tok.kind == "COMMENT":
            if not current:
                current = " " * (depth * indent)
            if current.strip():
                flush()
                current = " " * (depth * indent)
            current += tok.text
            flush()
            continue

        if tok.text == "}":
            flush()
            depth = max(0, depth - 1)
            current = " " * (depth * indent) + "}"
            if nxt is not None and nxt.text not in {"else", ";"}:
                flush()
            continue

        if not current:
            current = " " * (depth * indent)

        if tok.text == "{":
            if _needs_space(tokens[idx - 1] if idx > 0 else None, tok):
                current += " "
            current += "{"
            flush()
            depth += 1
            continue

        if tok.text == ";":
            current = current.rstrip() + ";"
            flush()
            continue

        prev = tokens[idx - 1] if idx > 0 else None
        if _needs_space(prev, tok):
            current = current.rstrip() + " "
        current += tok.text

    flush(force=True)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(line.rstrip() for line in lines if line.strip() or line == "") + "\n"


def format_import(module: str, alias: str | None = None) -> str:
    parts: List[str] = ["import", module]
    if alias:
        parts.extend(["as", alias])
    return " ".join(parts) + ";"


__all__: Sequence[str] = ["format_source", "format_import"]
