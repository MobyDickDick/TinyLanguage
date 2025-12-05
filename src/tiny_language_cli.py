"""Command-line entrypoint for running TinyLanguage programs.

The CLI intentionally mirrors the interpreter's public API so users can
execute `.tiny` files or inline snippets with a choice of backends. Error
formatting stays consistent with the library helpers to make debugging via
stdin/stdout/stderr predictable in shell scripts and CI pipelines.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tiny_language import (
    TinyLangError,
    _format_error_for_source,
    compile_and_run,
    run_with_native_backend,
    run_with_python_bytecode_backend,
    run_with_python_backend,
)


def _read_source_from_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - argparse already guards path existence
        raise SystemExit(f"File not found: {path}") from exc


def _module_namespace_for_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(Path.cwd())
        return ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001 - fall back if relative resolution fails
        return path.stem


def _execute(source: str, *, backend: str, module_path: Path | None) -> str:
    """Dispatch execution to the requested backend and return captured output."""
    if backend == "interpreter":
        namespace = _module_namespace_for_path(module_path) if module_path else None
        return compile_and_run(source, module_namespace=namespace, module_path=module_path)
    if backend == "python":
        return run_with_python_backend(source)
    if backend == "native":
        return run_with_native_backend(source)
    if backend == "native-python-bytecode":
        return run_with_python_bytecode_backend(source)
    raise SystemExit(f"Unknown backend: {backend}")


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run the requested program, and emit output/errors."""
    parser = argparse.ArgumentParser(description="Run TinyLanguage programs from the command line")
    parser.add_argument("path", nargs="?", type=Path, help="Path to a .tiny source file")
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--file", "-f", type=Path, help="Path to a .tiny source file")
    source_group.add_argument("--source", "-s", type=str, help="Inline TinyLanguage source code")
    parser.add_argument(
        "--backend",
        choices=["interpreter", "python", "native", "native-python-bytecode"],
        default="interpreter",
        help="Execution backend (interpreter/python/native/native-python-bytecode)",
    )

    args = parser.parse_args(argv)
    module_path: Path | None = None
    source: str
    cli_path = args.path or args.file
    if cli_path:
        module_path = cli_path.resolve()
        source = _read_source_from_file(module_path)
    elif args.source is not None:
        source = args.source
    else:
        parser.error("either provide a path argument, --file, or --source")

    try:
        output = _execute(source, backend=args.backend, module_path=module_path)
    except TinyLangError as err:
        sys.stderr.write(_format_error_for_source(source, err) + os.linesep)
        return 1

    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
