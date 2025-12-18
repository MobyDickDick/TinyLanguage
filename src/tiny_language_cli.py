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
    compile_to_llvm_ir,
    Runtime,
    run_with_native_backend,
    run_with_python_bytecode_backend,
    run_with_python_backend,
)


def _default_copy_on_call() -> bool:
    flag = os.environ.get("TINYLANG_COPY_ON_CALL", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


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


def _execute(
    source: str,
    *,
    backend: str,
    module_path: Path | None,
    stream_output: bool = True,
    copy_on_call: bool | None = None,
) -> tuple[str, bool]:
    """Dispatch execution to the requested backend and return captured output.

    The boolean return value signals whether output was already streamed to stdout
    during execution. When streaming is enabled we avoid reprinting the buffered
    output in ``main`` to prevent duplicate lines.
    """
    if backend == "interpreter":
        namespace = _module_namespace_for_path(module_path) if module_path else None
        runtime = Runtime(source)
        if copy_on_call is not None:
            runtime.copy_on_call = copy_on_call
        output = compile_and_run(
            source,
            runtime=runtime,
            module_namespace=namespace,
            module_path=module_path,
            stream_output=stream_output,
            copy_on_call=copy_on_call,
        )
        return output, runtime.streamed_output
    if backend == "python":
        return run_with_python_backend(source), False
    if backend == "native":
        return run_with_native_backend(source), False
    if backend == "native-python-bytecode":
        return run_with_python_bytecode_backend(source), False
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
    parser.add_argument(
        "--emit-llvm",
        action="store_true",
        help="Compile the program to LLVM IR and print it instead of executing",
    )
    parser.add_argument(
        "--copy-on-call",
        action=argparse.BooleanOptionalAction,
        default=_default_copy_on_call(),
        help="Deep-copy non-escaping mutable arguments before calls (env: TINYLANG_COPY_ON_CALL)",
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

    if args.emit_llvm:
        try:
            llvm_ir = compile_to_llvm_ir(source)
        except TinyLangError as err:
            sys.stderr.write(_format_error_for_source(source, err) + os.linesep)
            return 1
        sys.stdout.write(llvm_ir + os.linesep)
        return 0

    try:
        output, streamed = _execute(
            source,
            backend=args.backend,
            module_path=module_path,
            stream_output=True,
            copy_on_call=args.copy_on_call,
        )
    except TinyLangError as err:
        sys.stderr.write(_format_error_for_source(source, err) + os.linesep)
        return 1

    if not streamed:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
