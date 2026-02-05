"""Shared error and location types for TinyLanguage components.

Parsing, linting, code generation, and runtime modules rely on these definitions
to report positions, spans, and formatted error messages consistently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union


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
    suggestions: Tuple[str, ...] = field(default_factory=tuple)
    stack: Tuple[StackFrame, ...] = field(default_factory=tuple)
    span: Optional[SourceSpan] = None

    def __post_init__(self) -> None:
        """Normalize spans and align positional defaults."""
        if self.span is not None:
            normalized = _normalize_span(self.span)
            if normalized != self.span:
                self.span = normalized
            if self.pos == SourcePos.origin():
                self.pos = normalized.start

    def __str__(self) -> str:  # pragma: no cover - Exception already stringifies message
        return self.message


def diagnostic_range(error: TinyLangError, source: str) -> Tuple[int, int, int, int]:
    """Return a 1-based, end-exclusive range for ``error`` within ``source``."""
    span = error.span
    if span is not None:
        span = _normalize_span(span)
        start_line, start_col, _ = _line_info(source, span.start)
        stop_line, stop_col, stop_text = _line_info(source, span.stop)
        max_col = len(stop_text) + 1 if stop_text else stop_col + 1
        end_col = min(stop_col + 1, max_col)
        if stop_line == start_line:
            end_col = min(max(end_col, start_col + 1), max_col)
        return (start_line, start_col, stop_line, end_col)
    line, col, _ = _line_info(source, error.pos)
    return (line, col, line, col + 1)


def diagnostic_payload(
    error: TinyLangError,
    source: str,
    *,
    phase: str,
    severity: str = "error",
    origin: str = "interpreter",
    uri: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a shared diagnostic payload for tooling and interpreter errors."""
    payload: Dict[str, Any] = {
        "message": str(error),
        "code": error.code,
        "severity": severity,
        "phase": phase,
        "range": list(diagnostic_range(error, source)),
        "origin": origin,
    }
    if error.hint:
        payload["hint"] = error.hint
    if error.suggestions:
        payload["suggestions"] = list(error.suggestions)
    if uri:
        payload["uri"] = uri
    if error.stack:
        payload["stack"] = [
            {
                "name": frame.name,
                "namespace": frame.namespace,
                "line": frame.pos.line,
                "column": frame.pos.column,
            }
            for frame in error.stack
        ]
    return payload


def _source_lines(source: str, *, preserve_trailing: bool = True) -> List[str]:
    """Return source lines, optionally preserving trailing empty lines."""
    lines = source.splitlines()
    if preserve_trailing and source.endswith("\n"):
        lines.append("")
    return lines


def _context_lines(lines: List[str], *, last_line_needed: int) -> List[str]:
    """Trim trailing empty context lines unless they are part of the target span."""
    if lines and lines[-1] == "" and last_line_needed < len(lines):
        return lines[:-1]
    return lines


def _line_info(source: str, pos: Union[int, SourcePos, SourceSpan]) -> Tuple[int, int, str]:
    lines = _source_lines(source, preserve_trailing=True)
    if isinstance(pos, SourceSpan):
        pos = _normalize_span(pos).start
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
    if os.environ.get("TINYLANG_DEBUG_ERRORS"):
        sys.stderr.write(
            f"[tiny_errors] format_error code={code} message={message!r} pos_type={type(pos).__name__}\n"
        )
    lines = _source_lines(source, preserve_trailing=True)
    if isinstance(pos, SourceSpan):
        pos = _normalize_span(pos)
        start_line, start_col, start_text = _line_info(source, pos.start)
        stop_line, stop_col, stop_text = _line_info(source, pos.stop)
        if start_text == "" and start_line == len(lines) and start_line > 1 and source.endswith("\n"):
            start_line -= 1
            start_col = 1
        if stop_text == "" and stop_line == len(lines) and stop_line > 1 and source.endswith("\n"):
            stop_line -= 1
            stop_col = 1
        lines = _context_lines(lines, last_line_needed=stop_line)
        gutter_width = len(str(max(1, len(lines))))
        header = f"[{code}] {message} (line {start_line}, col {start_col})"
        if start_line != stop_line or start_col != stop_col:
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
    line, col, line_text = _line_info(source, pos)
    if line_text == "" and line == len(lines) and line > 1 and source.endswith("\n"):
        line = line - 1
        col = 1
    lines = _context_lines(lines, last_line_needed=line)
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


def _normalize_span(span: SourceSpan) -> SourceSpan:
    """Ensure span ordering is consistent (start <= stop)."""
    if (span.start.line, span.start.column) <= (span.stop.line, span.stop.column):
        return span
    return SourceSpan(span.stop, span.start)
