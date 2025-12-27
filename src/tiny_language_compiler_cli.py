"""Command-line entrypoint for compiling TinyLanguage programs via the C backend."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tiny_language import (
    TinyLangError,
    _format_error_for_source,
    compile_to_c_executable,
    compile_to_c_source,
    compile_to_llvm_ir_via_c,
)


def _default_compiler() -> str:
    return os.environ.get("TINYLANG_C_COMPILER", "cc")


def _read_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # pragma: no cover - argparse handles missing paths
        raise SystemExit(f"File not found: {path}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile TinyLanguage programs with the C backend")
    parser.add_argument("path", type=Path, help="Path to a .tiny source file")
    parser.add_argument(
        "--emit-c",
        nargs="?",
        const="-",
        metavar="PATH",
        help="Emit generated C source (default: stdout when flag is set without PATH)",
    )
    parser.add_argument(
        "--emit-llvm",
        nargs="?",
        const="-",
        metavar="PATH",
        help="Emit LLVM IR via clang from generated C source (default: stdout when flag is set without PATH)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="a.out",
        help="Output executable path (default: a.out)",
    )
    parser.add_argument(
        "--compiler",
        default=_default_compiler(),
        help="C compiler to invoke (default: cc, env: TINYLANG_C_COMPILER)",
    )

    args = parser.parse_args(argv)
    if args.emit_c is not None and args.emit_llvm is not None:
        parser.error("choose only one of --emit-c or --emit-llvm")
    source = _read_source(args.path)

    try:
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
            llvm_ir = compile_to_llvm_ir_via_c(source, compiler=args.compiler)
            if args.emit_llvm == "-":
                sys.stdout.write(llvm_ir + os.linesep)
            else:
                out_path = Path(args.emit_llvm)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(llvm_ir, encoding="utf-8")
            return 0
        compile_to_c_executable(source, args.output, compiler=args.compiler)
        return 0
    except TinyLangError as err:
        sys.stderr.write(_format_error_for_source(source, err) + os.linesep)
        return 1
    except RuntimeError as err:
        sys.stderr.write(str(err) + os.linesep)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
