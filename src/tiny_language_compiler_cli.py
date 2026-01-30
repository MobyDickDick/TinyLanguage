"""Command-line entrypoint for compiling TinyLanguage programs via the C backend."""

from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path

from tiny_language import (
    TinyLangError,
    _format_error_for_source,
    compile_to_c_executable,
    compile_to_c_source,
    compile_to_llvm_bitcode_via_c,
    compile_to_llvm_ir_via_c,
    Lexer,
    Parser,
    lint_annotation_enforcement,
    lint_assignment_types,
    lint_call_validation,
    lint_return_validation,
)


def _write_error(message: str) -> None:
    if message.endswith("\n"):
        sys.stderr.write(message)
    else:
        sys.stderr.write(f"{message}\n")


def _default_compiler() -> str:
    return os.environ.get("TINYLANG_C_COMPILER", "cc")


def _experimental_flag_enabled(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _read_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - argparse handles missing paths
        raise SystemExit(f"File not found: {path}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile TinyLanguage programs with the C backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              tinyc_cli.py program.tiny --emit-llvm program.ll
              tinyc_cli.py program.tiny --emit-bc build/program.bc
            """
        ),
    )
    parser.add_argument("path", type=Path, help="Path to a .tiny source file")
    emit_group = parser.add_mutually_exclusive_group()
    emit_group.add_argument(
        "--emit-c",
        nargs="?",
        const="-",
        metavar="PATH",
        help="Emit generated C source (default: stdout when flag is set without PATH)",
    )
    emit_group.add_argument(
        "--emit-llvm",
        nargs="?",
        const="-",
        metavar="PATH",
        help="Emit LLVM IR via clang from generated C source (default: stdout when flag is set without PATH)",
    )
    emit_group.add_argument(
        "--emit-bc",
        metavar="PATH",
        help="Emit LLVM bitcode via clang from generated C source",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="a.out",
        help="Output executable path (default: a.out)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Include debug symbols and disable optimizations (passes -g -O0 to the compiler)",
    )
    parser.add_argument(
        "--compiler",
        default=_default_compiler(),
        help="C compiler to invoke (default: cc, env: TINYLANG_C_COMPILER)",
    )
    parser.add_argument(
        "--typecheck",
        action="store_true",
        help="Run static typing checks and fail before compilation",
    )

    args = parser.parse_args(argv)
    source = _read_source(args.path)
    extra_args = ["-g", "-O0"] if args.debug else None

    try:
        if args.typecheck:
            parser_impl = Parser(
                Lexer(source),
                source,
                allow_math_tuples=_experimental_flag_enabled("TINYLANG_EXPERIMENTAL_MATH_TUPLES"),
                allow_math_formula=_experimental_flag_enabled("TINYLANG_EXPERIMENTAL_MATH_FORMULA"),
            )
            stmts = parser_impl.parse()
            lint_assignment_types(stmts, source)
            lint_call_validation(stmts, source)
            lint_return_validation(stmts, source)
            lint_annotation_enforcement(stmts, source)
        if args.emit_c is not None:
            c_source = compile_to_c_source(source)
            if args.emit_c == "-":
                sys.stdout.write(c_source + os.linesep)
            else:
                out_path = Path(args.emit_c)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(c_source, encoding="utf-8")
            return 0
        if args.emit_llvm is not None:
            llvm_ir = compile_to_llvm_ir_via_c(source, compiler=args.compiler, extra_args=extra_args)
            if args.emit_llvm == "-":
                sys.stdout.write(llvm_ir + os.linesep)
            else:
                out_path = Path(args.emit_llvm)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(llvm_ir, encoding="utf-8")
            return 0
        if args.emit_bc is not None:
            bitcode = compile_to_llvm_bitcode_via_c(source, compiler=args.compiler, extra_args=extra_args)
            out_path = Path(args.emit_bc)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(bitcode)
            return 0
        compile_to_c_executable(source, args.output, compiler=args.compiler, extra_args=extra_args)
        return 0
    except TinyLangError as err:
        _write_error(_format_error_for_source(source, err))
        return 1
    except RuntimeError as err:
        _write_error(str(err))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
