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


def _write_error(message: str) -> None:
    if message.endswith("\n"):
        sys.stderr.write(message)
    else:
        sys.stderr.write(f"{message}\n")


def _default_copy_on_call() -> bool:
    flag = os.environ.get("TINYLANG_COPY_ON_CALL", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _read_source_from_file(path: Path) -> str:
    if str(path) == "-":
        return sys.stdin.read()
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
        namespace = _module_namespace_for_path(module_path) if module_path else None
        return run_with_native_backend(
            source,
            module_namespace=namespace,
            module_path=module_path,
        ), False
    if backend == "native-python-bytecode":
        return run_with_python_bytecode_backend(source), False
    raise SystemExit(f"Unknown backend: {backend}")


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run the requested program, and emit output/errors."""
    parser = argparse.ArgumentParser(description="Run TinyLanguage programs from the command line")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Path to a .tiny source file (use '-' for stdin)",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Path to a .tiny source file (use '-' for stdin)",
    )
    source_group.add_argument(
        "--source",
        "-s",
        "-e",
        type=str,
        help="Inline TinyLanguage source code",
    )
    backend_group = parser.add_mutually_exclusive_group()
    backend_group.add_argument(
        "--backend",
        choices=["interpreter", "python", "native", "native-python-bytecode"],
        default="interpreter",
        help="Execution backend (interpreter/python/native/native-python-bytecode)",
    )
    backend_group.add_argument(
        "--python-backend",
        action="store_true",
        help="Alias for --backend python",
    )
    backend_group.add_argument(
        "--native-backend",
        action="store_true",
        help="Alias for --backend native",
    )
    backend_group.add_argument(
        "--native-python-bytecode",
        action="store_true",
        help="Alias for --backend native-python-bytecode",
    )
    parser.add_argument(
        "--emit-llvm",
        nargs="?",
        const="-",
        metavar="FILE",
        help="Compile the program to LLVM IR and write it to FILE (use '-' for stdout)",
    )
    parser.add_argument(
        "--llvm-target-triple",
        dest="llvm_target_triple",
        help="Override the LLVM target triple for --emit-llvm",
    )
    parser.add_argument(
        "--llvm-data-layout",
        dest="llvm_data_layout",
        help="Override the LLVM data layout for --emit-llvm",
    )
    parser.add_argument(
        "--llvm-opt",
        action="store_true",
        help="Run basic LLVM optimization passes (mem2reg, instcombine) on emitted IR",
    )
    parser.add_argument(
        "--llvm-opt-level",
        type=int,
        choices=[0, 1, 2, 3],
        help="Set LLVM optimization level for emitted IR (0-3, implies --llvm-opt)",
    )
    parser.add_argument(
        "--copy-on-call",
        action=argparse.BooleanOptionalAction,
        default=_default_copy_on_call(),
        help="Deep-copy non-escaping mutable arguments before calls (env: TINYLANG_COPY_ON_CALL)",
    )
    parser.add_argument(
        "--experimental-math-tuples",
        action="store_true",
        help="Enable experimental tuple-based math forms like (sum: x) (env: TINYLANG_EXPERIMENTAL_MATH_TUPLES)",
    )
    parser.add_argument(
        "--native-diagnostics",
        action="store_true",
        help="Print native backend diagnostics to stderr when using LLVM flags",
    )

    args, remaining = parser.parse_known_args(argv)
    if args.experimental_math_tuples:
        os.environ["TINYLANG_EXPERIMENTAL_MATH_TUPLES"] = "1"
    program_args = list(remaining)
    if program_args and program_args[0] == "--":
        program_args = program_args[1:]
    resolved_llvm_opt_level = args.llvm_opt_level if args.llvm_opt_level is not None else (1 if args.llvm_opt else 0)
    module_path: Path | None = None
    source: str
    cli_path = args.path or args.file
    if cli_path:
        if str(cli_path) == "-":
            source = _read_source_from_file(cli_path)
        else:
            module_path = cli_path.resolve()
            source = _read_source_from_file(module_path)
    elif args.source is not None:
        source = args.source
    elif not sys.stdin.isatty():
        source = sys.stdin.read()
    else:
        parser.error("either provide a path argument, --file, or --source")

    if args.python_backend:
        args.backend = "python"
    elif args.native_backend:
        args.backend = "native"
    elif args.native_python_bytecode:
        args.backend = "native-python-bytecode"

    if args.emit_llvm is not None:
        try:
            if args.native_diagnostics:
                sys.stderr.write("Native backend diagnostics:\n")
                sys.stderr.write(f"- mode: emit-llvm{os.linesep}")
                sys.stderr.write(
                    f"- llvm opt-level: {resolved_llvm_opt_level}"
                    + os.linesep
                )
                sys.stderr.write(
                    f"- llvm target triple: {args.llvm_target_triple or 'default'}{os.linesep}"
                )
                sys.stderr.write(
                    f"- llvm data layout: {args.llvm_data_layout or 'default'}{os.linesep}"
                )
            llvm_ir = compile_to_llvm_ir(
                source,
                target_triple=args.llvm_target_triple,
                data_layout=args.llvm_data_layout,
                llvm_opt=args.llvm_opt,
                llvm_opt_level=args.llvm_opt_level,
                module_path=module_path,
            )
        except TinyLangError as err:
            _write_error(_format_error_for_source(source, err))
            return 1
        if args.emit_llvm == "-":
            sys.stdout.write(llvm_ir + os.linesep)
        else:
            out_path = Path(args.emit_llvm)
            out_path.write_text(llvm_ir + os.linesep, encoding="utf-8")
        return 0

    program_argv = []
    if module_path is not None:
        program_argv.append(str(module_path))
    else:
        program_argv.append("<source>")
    program_argv.extend(program_args)
    original_argv = sys.argv[:]
    sys.argv = program_argv
    try:
        output, streamed = _execute(
            source,
            backend=args.backend,
            module_path=module_path,
            stream_output=True,
            copy_on_call=args.copy_on_call,
        )
    except TinyLangError as err:
        _write_error(_format_error_for_source(source, err))
        return 1
    finally:
        sys.argv = original_argv

    if not streamed:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
