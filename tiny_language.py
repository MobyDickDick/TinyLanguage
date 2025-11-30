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

from __future__ import annotations  # Allow postponed evaluation of annotations

# Path handling is only needed while we stitch the module pieces together.
from pathlib import Path as _Path


def _load_and_exec_all() -> None:
    """Concatenate the segmented TinyLanguage sources and execute them.

    The original monolithic interpreter was split into several files. To keep
    imports stable for existing users, we read those pieces in order, join
    them, compile the resulting source code, and execute it in this module's
    namespace.
    """

    # Determine the directory that contains the segmented files.
    base = _Path(__file__).resolve().parent

    # Accumulate the textual contents of each segment in the correct order.
    parts = []
    for name in [
        "tiny_language_preamble.py",  # shared definitions and constants
        "tiny_language_lexer.py",  # tokenization logic
        "tiny_language_ast.py",  # abstract syntax tree node definitions
        "tiny_language_parser.py",  # source-to-AST parser
        "tiny_language_codegen_py.py",  # experimental Python code generator
        "tiny_language_linter.py",  # static analysis passes
        "tiny_language_runtime.py",  # execution runtime structures
        "tiny_language_eval.py",  # AST evaluator
        "tiny_language_api.py",  # public API and CLI entrypoints
    ]:
        # Construct the absolute path for the current segment file.
        path = base / name
        # Read the file contents using UTF-8 to preserve symbols.
        parts.append(path.read_text(encoding="utf-8"))

    # Join the individual source strings into a single Python module body.
    full_source = "".join(parts)

    # Compile the generated source so that tracebacks reference the stitched file.
    code = compile(full_source, str(base / "tiny_language_stitched.py"), "exec")

    # Execute the compiled module in this file's global namespace.
    exec(code, globals(), globals())


# Perform the stitching immediately when the module is imported.
_load_and_exec_all()

# Remove helper names so that the public namespace mirrors the original module.
del _load_and_exec_all, _Path
