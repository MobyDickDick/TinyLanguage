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
import os
import sys  # Detect frozen executables (e.g., PyInstaller) so we can locate bundled sources.
import tokenize


def _load_and_exec_all() -> None:
    """Concatenate the segmented TinyLanguage sources and execute them."""

    # Determine the directory that contains the segmented files so we can read them.
    # When packaged with PyInstaller, the source files can be bundled as data alongside
    # the executable; ``sys._MEIPASS`` points to that extraction directory.
    base = _Path(getattr(sys, "_MEIPASS", _Path(__file__).resolve().parent))

    # Accumulate the textual contents of each segment in the correct order.
    parts = []  # Prepare a list that will hold each source fragment.
    segments = []  # Track raw segments for fallback execution if stitching fails.
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
        with tokenize.open(path) as handle:
            segment = handle.read()  # Respect encoding cookies if present.
        normalized = segment.replace("\r\n", "\n").replace("\r", "\n")
        normalized = normalized.lstrip("\ufeff")
        if not normalized.endswith("\n"):
            normalized += "\n"
        parts.append(f"# --- segment: {name} ---\n{normalized}")  # Include a separator to avoid accidental merges.
        segments.append((name, segment))

    full_source = "\n".join(parts)
    stitched_path = base / "tiny_language_stitched.py"
    temp_path = stitched_path.with_suffix(".py.tmp")
    temp_path.write_text(full_source, encoding="utf-8")
    temp_path.replace(stitched_path)

    try:
        code = compile(full_source, str(stitched_path), "exec")  # Compile so tracebacks reference the stitched file.
    except SyntaxError as exc:
        lineno = exc.lineno or 0
        context_lines = full_source.splitlines()
        if lineno > 0:
            window_start = max(lineno - 3, 1)
            window_end = lineno + 3
            snippet = "\n".join(
                f"{idx:5d}: {context_lines[idx - 1]}"
                for idx in range(window_start, min(window_end, len(context_lines)) + 1)
            )
            sys.stderr.write(
                f"[tiny_language stitch] SyntaxError near line {lineno}:\n{snippet}\n"
            )
            sys.stderr.write(
                f"[tiny_language stitch] repr(line {lineno}): {context_lines[lineno - 1]!r}\n"
            )
        sys.stderr.write(
            f"[tiny_language stitch] total lines={len(context_lines)} "
            f"bytes={len(full_source.encode('utf-8'))}\n"
        )
        sys.stderr.write(
            f"[tiny_language stitch] segment names: {', '.join(segment_names)}\n"
        )
        sys.stderr.write(
            "[tiny_language stitch] Falling back to per-segment execution.\n"
        )
        try:
            for name, segment in segments:
                segment_path = base / name
                exec(compile(segment, str(segment_path), "exec"), globals(), globals())
        except SyntaxError as seg_exc:
            lineno = seg_exc.lineno or 0
            segment_lines = segment.splitlines()
            if lineno > 0 and lineno <= len(segment_lines):
                window_start = max(lineno - 3, 1)
                window_end = lineno + 3
                snippet = "\n".join(
                    f"{idx:5d}: {segment_lines[idx - 1]}"
                    for idx in range(window_start, min(window_end, len(segment_lines)) + 1)
                )
                sys.stderr.write(
                    f"[tiny_language stitch] Segment {name} SyntaxError near line {lineno}:\n{snippet}\n"
                )
                sys.stderr.write(
                    f"[tiny_language stitch] repr(line {lineno}): {segment_lines[lineno - 1]!r}\n"
                )
            raise
        return

    if os.getenv("TINYLANG_STITCH_DEBUG"):
        sys.stderr.write(
            f"[tiny_language stitch] Wrote {stitched_path} with {full_source.count(chr(10)) + 1} lines\n"
        )
        sys.stderr.write(
            f"[tiny_language stitch] segment names: {', '.join(segment_names)}\n"
        )

    exec(code, globals(), globals())  # Execute the compiled module in this file's global namespace.


_load_and_exec_all()  # Perform the stitching immediately when the module is imported.

del _load_and_exec_all, _Path  # Remove helper names so that the public namespace mirrors the original module.
