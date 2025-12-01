from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SourcePos:
    """
    Repräsentiert eine Position im Quelltext (1-basiert).
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
    Repräsentiert einen Bereich im Quelltext, von `start` bis `stop` (inklusive).
    """

    start: SourcePos
    stop: SourcePos


@dataclass
class TinyError(Exception):
    """
    Einheitlicher Fehlertyp für Lexer/Parser/Typchecker/Linter.

    - kind: z.B. "lex", "parse", "type", "linter"
    - msg:  menschenlesbare Beschreibung
    - span: optionaler Quellbereich
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

    Formatiert einen TinyError mit Kontextzeile und Unterstreichung (falls span gesetzt).
    `source` ist der komplette TinyLanguage-Quelltext.
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
