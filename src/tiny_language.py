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

from __future__ import annotations  # Enable postponed evaluation for annotations used later.

# Path handling is only needed while we stitch the module pieces together.
from pathlib import Path as _Path  # Import Path with an alias to avoid polluting the public API.
import sys  # Detect frozen executables (e.g., PyInstaller) so we can locate bundled sources.


def _load_and_exec_all() -> None:
    """Concatenate the segmented TinyLanguage sources and execute them."""

    # Determine the directory that contains the segmented files so we can read them.
    # When packaged with PyInstaller, the source files can be bundled as data alongside
    # the executable; ``sys._MEIPASS`` points to that extraction directory.
    base = _Path(getattr(sys, "_MEIPASS", _Path(__file__).resolve().parent))

    # Accumulate the textual contents of each segment in the correct order.
    parts = []  # Prepare a list that will hold each source fragment.
    segment_names = [
        "tiny_language_preamble.py",  # shared definitions and constants
        "tiny_language_lexer.py",  # tokenization logic
        "tiny_language_ast.py",  # abstract syntax tree node definitions
        "tiny_language_parser.py",  # source-to-AST parser
        "tiny_language_codegen_py.py",  # experimental Python code generator
        "tiny_language_codegen_native.py",  # experimental native bytecode backend
        "tiny_language_codegen_c.py",  # experimental C backend
        "tiny_language_codegen_llvm.py",  # experimental LLVM text backend
        "tiny_language_linter.py",  # static analysis passes
        "tiny_language_runtime.py",  # execution runtime structures
        "tiny_language_eval.py",  # AST evaluator
        "tiny_language_api.py",  # public API and CLI entrypoints
    ]
    for name in segment_names:
        path = base / name  # Construct the absolute path for the current segment file.
        segment = path.read_text(encoding="utf-8")  # Read the file contents using UTF-8 to preserve symbols.
        parts.append(f"# --- segment: {name} ---\n{segment.rstrip()}")  # Include a separator to avoid accidental merges.

    full_source = "\n\n".join(parts) + "\n"
    full_source = full_source.replace("\r\n", "\n").replace("\r", "\n")
    stitched_path = base / "tiny_language_stitched.py"
    stitched_path.write_text(full_source, encoding="utf-8")

    code = compile(full_source, str(stitched_path), "exec")  # Compile so tracebacks reference the stitched file.

    exec(code, globals(), globals())  # Execute the compiled module in this file's global namespace.


_load_and_exec_all()  # Perform the stitching immediately when the module is imported.

del _load_and_exec_all, _Path  # Remove helper names so that the public namespace mirrors the original module.
