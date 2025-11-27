"""
TinyLanguage - stitched from modular segments.

This module preserves the original public API, but the implementation
is split across several files:

- tiny_language_preamble.py
- tiny_language_lexer.py
- tiny_language_ast.py
- tiny_language_parser.py
- tiny_language_linter.py
- tiny_language_runtime.py
- tiny_language_eval.py
- tiny_language_api.py

At import time we read those segment files, concatenate their source
code in the original order, compile it as a single module and execute
it in this module's global namespace. This way indentation across
segments (e.g. methods inside classes) keeps working exactly as in the
original monolithic file.
"""

from __future__ import annotations

from pathlib import Path as _Path


def _load_and_exec_all() -> None:
    base = _Path(__file__).resolve().parent
    parts = []
    for name in [
        "tiny_language_preamble.py",
        "tiny_language_lexer.py",
        "tiny_language_ast.py",
        "tiny_language_parser.py",
        "tiny_language_linter.py",
        "tiny_language_runtime.py",
        "tiny_language_eval.py",
        "tiny_language_api.py",
    ]:
        path = base / name
        parts.append(path.read_text(encoding="utf-8"))
    full_source = "".join(parts)
    code = compile(full_source, str(base / "tiny_language_stitched.py"), "exec")
    exec(code, globals(), globals())


_load_and_exec_all()

# Clean up helper names
del _load_and_exec_all, _Path
