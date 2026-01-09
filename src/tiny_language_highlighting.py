"""Optional syntax highlighting utilities for TinyLanguage REPL sessions.

The helpers in this module depend on ``pygments`` when available and are
intended to be harmless no-ops when the dependency is missing. A small
``RegexLexer`` covers the current TinyLanguage surface area so REPL users can
see keywords, builtins, literals, and comments in color without changing any
runtime behavior.
"""

from __future__ import annotations

import importlib.util
from typing import Optional

from tiny_language_lexer import BUILTINS, KEYWORDS

PYGMENTS_AVAILABLE = importlib.util.find_spec("pygments") is not None

if PYGMENTS_AVAILABLE:  # pragma: no cover - exercised when pygments is installed
    from pygments import highlight
    from pygments.formatters import TerminalFormatter
    from pygments.lexer import RegexLexer
    from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String, Text

    class TinyLanguageLexer(RegexLexer):
        """Minimal Pygments lexer for TinyLanguage syntax highlighting."""

        name = "TinyLanguage"
        aliases = ["tiny"]
        flags = 0
        _keyword_pattern = r"\\b(" + r"|".join(sorted(KEYWORDS)) + r")\\b"
        _builtin_pattern = r"\\b(" + r"|".join(sorted(BUILTINS)) + r")\\b"

        tokens = {
            "root": [
                (r"//.*$", Comment.Single),
                (r'"(\\\\.|[^"\\\\])*"', String.Double),
                (_keyword_pattern, Keyword),
                (_builtin_pattern, Name.Builtin),
                (r"[0-9]+(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", Number),
                (r"[+\-*/^%=!<>:&|]+", Operator),
                (r"[{}\\[\\]();,.]", Punctuation),
                (r"[A-Za-z_][A-Za-z0-9_]*", Name),
                (r"\\s+", Text),
            ]
        }

    def highlight_source(source: str) -> Optional[str]:
        """Return a syntax-highlighted version of ``source`` when pygments is present."""

        return highlight(source, TinyLanguageLexer(), TerminalFormatter())
else:  # pragma: no cover - executed when pygments is absent
    def highlight_source(_source: str) -> Optional[str]:
        """Indicate that highlighting is unavailable without requiring pygments."""

        return None


__all__ = ["highlight_source", "PYGMENTS_AVAILABLE"]
if PYGMENTS_AVAILABLE:
    __all__.append("TinyLanguageLexer")
