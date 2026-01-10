"""Shared error and location types for TinyLanguage components.

Parsing, linting, code generation, and runtime modules rely on these definitions
to report positions, spans, and formatted error messages consistently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union


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


@dataclass(frozen=True)
class StackFrame:
    name: str
    namespace: Optional[str]
    pos: SourcePos

    @property
    def qualified_name(self) -> str:
        return f"{self.namespace}.{self.name}" if self.namespace else self.name


@dataclass
class TinyLangError(Exception):
    message: str
    pos: SourcePos = field(default_factory=SourcePos.origin)
    code: str = "E000"
    hint: Optional[str] = None
    stack: Tuple[StackFrame, ...] = field(default_factory=tuple)
    span: Optional[SourceSpan] = None

    def __str__(self) -> str:  # pragma: no cover - Exception already stringifies message
        return self.message


def _line_info(source: str, pos: Union[int, SourcePos, SourceSpan]) -> Tuple[int, int, str]:
    lines = source.splitlines()
    if isinstance(pos, SourceSpan):
        pos = pos.start
    if isinstance(pos, SourcePos):
        line = max(1, min(pos.line, len(lines) or 1))
        line_text = lines[line - 1] if 0 <= line - 1 < len(lines) else ""
        col = max(1, min(pos.col, len(line_text) + 1)) if line_text else pos.col
        return line, col, line_text
    idx = max(0, min(len(source), pos))
    line = source.count("\n", 0, idx) + 1
    last_nl = source.rfind("\n", 0, idx)
    col = idx - (last_nl + 1) + 1
    line_text = lines[line - 1] if lines else ""
    return line, col, line_text


def format_error(
    source: str, pos: Union[int, SourcePos, SourceSpan], message: str, *, code: str = "E000", hint: Optional[str] = None
) -> str:
    lines = source.splitlines()
    if isinstance(pos, SourceSpan):
        start_line, start_col, _ = _line_info(source, pos.start)
        stop_line, stop_col, _ = _line_info(source, pos.stop)
        gutter_width = len(str(max(1, len(lines))))
        if start_line == stop_line and start_col == stop_col:
            header = f"[{code}] {message} (line {start_line}, col {start_col})"
        else:
            header = (
                f"[{code}] {message} (line {start_line}, col {start_col} to line {stop_line}, col {stop_col})"
            )
        lines_out: List[str] = [header]

        context_start = max(1, start_line - 1)
        context_end = min(len(lines), stop_line + 1) if lines else stop_line

        for ln in range(context_start, context_end + 1):
            text = lines[ln - 1] if 0 <= ln - 1 < len(lines) else ""
            prefix = ">" if ln == start_line else " "
            lines_out.append(f"{prefix} {ln:>{gutter_width}} | {text}")

            if ln < start_line or ln > stop_line:
                continue

            if ln == start_line and ln == stop_line:
                underline_start = start_col
                underline_end = stop_col
            elif ln == start_line:
                underline_start = start_col
                underline_end = max(len(text), start_col)
            elif ln == stop_line:
                underline_start = 1
                underline_end = stop_col
            else:
                underline_start = 1
                underline_end = max(len(text), 1)

            underline_len = max(underline_end - underline_start + 1, 1)
            underline = " " * (underline_start - 1) + "^" * underline_len
            lines_out.append(f"  {' ' * gutter_width} | {underline}")

        if hint:
            lines_out.append(f"  Hint: {hint}")
        return "\n".join(lines_out)
    line, col, _ = _line_info(source, pos)
    gutter_width = len(str(max(1, len(lines))))
    start = max(1, line - 1)
    end = min(len(lines), line + 1) if lines else line
    context: List[str] = []
    for ln in range(start, end + 1):
        prefix = ">" if ln == line else " "
        text = lines[ln - 1] if 0 <= ln - 1 < len(lines) else ""
        context.append(f"{prefix} {ln:>{gutter_width}} | {text}")
    pointer_line = f"  {' ' * gutter_width} | {' ' * (col - 1)}^"
    header = f"[{code}] {message} (line {line}, col {col})"
    lines_out = [header] + context + [pointer_line]
    if hint:
        lines_out.append(f"  Hint: {hint}")
    return "\n".join(lines_out)
