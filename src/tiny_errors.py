from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SourcePos:
    """
    Represents a position in the source text (1-based).
    """

    line: int
    column: int

    @staticmethod
    def origin() -> "SourcePos":
        return SourcePos(1, 1)

    @property
    def col(self) -> int:
        return self.column


@dataclass(frozen=True)
class SourceSpan:
    """
    Represents a span in the source text from `start` to `stop` (inclusive).
    """

    start: SourcePos
    stop: SourcePos


@dataclass
class TinyError(Exception):
    """
    Unified error type for lexer, parser, type checker, and linter.

    - kind: e.g., "lex", "parse", "type", "linter"
    - msg: human-readable description
    - span: optional source span
    """

    kind: str
    msg: str
    span: Optional[SourceSpan] = None

    def __str__(self) -> str:  # Fallback, falls format_error nicht benutzt wird
        if self.span is None:
            return f"[{self.kind}] {self.msg}"
        s = self.span.start
        return f"[{self.kind}] {self.msg} (line {s.line}, column {s.column})"


def format_error(err: TinyError, source: str) -> str:
    """
    format_error(err, source) -> str

    Format a TinyError with a context line and underline (if a span is set).
    `source` is the full TinyLanguage source text.
    """

    header = f"[{err.kind}] {err.msg}"
    span = err.span
    if span is None:
        return header

    # Zeilen 0-basiert
    lines = source.splitlines(keepends=False)
    line_index = span.start.line - 1

    # Fallback, falls die gespeicherte Position nicht mehr passt
    if not (0 <= line_index < len(lines)):
        return header

    line_text = lines[line_index]

    # Start/Ende innerhalb der Zeile clampen
    start_col = max(span.start.column, 1)
    end_col = max(span.stop.column, start_col)

    underline = " " * (start_col - 1) + "^" * max(end_col - start_col + 1, 1)

    return (
        f"{header}\n"
        f"line {span.start.line}, column {span.start.column}:\n"
        f"{line_text}\n"
        f"{underline}"
    )
