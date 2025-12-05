"""Shared error types and formatting helpers for TinyLanguage components.

Parsing, linting, code generation, and runtime modules all rely on these
definitions to report positions, spans, and user-facing messages consistently.
The formatting helpers keep diagnostics readable whether they originate from the
CLI, the REPL, or downstream tooling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SourcePos:
    """Represents a position in the source text (1-based)."""

    line: int
    column: int

    @staticmethod
    def origin() -> "SourcePos":
        """Return the canonical starting position (line 1, column 1)."""
        return SourcePos(1, 1)

    @property
    def col(self) -> int:
        """Provide an alias for ``column`` for backward compatibility."""
        return self.column


@dataclass(frozen=True)
class SourceSpan:
    """Represents a span in the source text from ``start`` to ``stop`` (inclusive)."""

    start: SourcePos
    stop: SourcePos


@dataclass
class TinyError(Exception):
    """Unified error type for lexer, parser, type checker, and linter.

    Attributes:
        kind: Short identifier such as "lex", "parse", "type", or "linter".
        msg: Human-readable description of the error condition.
        span: Optional source span used to highlight the error location.

    """

    kind: str
    msg: str
    span: Optional[SourceSpan] = None

    def __str__(self) -> str:  # Fallback, falls format_error nicht benutzt wird
        """Render a concise textual representation for fallback error formatting."""
        if self.span is None:
            return f"[{self.kind}] {self.msg}"
        s = self.span.start
        return f"[{self.kind}] {self.msg} (line {s.line}, column {s.column})"


def format_error(err: TinyError, source: str) -> str:
    """Format a TinyError with source context and underline markers."""
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
