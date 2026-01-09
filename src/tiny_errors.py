"""Shared location types for TinyLanguage components.

Parsing, linting, code generation, and runtime modules rely on these definitions
to report positions and spans consistently.
"""

from __future__ import annotations

from dataclasses import dataclass


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
