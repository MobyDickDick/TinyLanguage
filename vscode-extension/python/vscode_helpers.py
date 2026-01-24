"""Helper CLI for TinyLanguage VS Code extension features."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from formatter import format_source  # type: ignore
from language_server import TinyLanguageServer  # type: ignore


def format_command(source: str) -> int:
    """Format TinyLanguage source and write it to stdout."""
    formatted = format_source(source)
    sys.stdout.write(formatted)
    return 0


def diagnostics_command(source: str, file_path: str | None = None) -> int:
    """Emit diagnostics JSON for TinyLanguage source."""
    server = TinyLanguageServer(source)
    diagnostics = []
    for diag in server.diagnostics():
        start_line, start_col, end_line, end_col = diag.range
        diagnostics.append(
            {
                "message": diag.message,
                "code": diag.code,
                "range": [start_line, start_col, end_line, end_col],
                "path": file_path,
            }
        )
    json.dump(diagnostics, sys.stdout)
    return 0


def completions_command(source: str, prefix: str) -> int:
    """Emit completion items for the given prefix as JSON."""
    server = TinyLanguageServer(source)
    items = [
        {
            "label": item.label,
            "kind": item.kind,
        }
        for item in server.completions(prefix)
    ]
    json.dump(items, sys.stdout)
    return 0


def hover_command(source: str, symbol: str) -> int:
    """Emit hover information for a symbol as JSON."""
    server = TinyLanguageServer(source)
    result = server.hover(symbol)
    if result is None:
        sys.stdout.write("null")
        return 0
    payload = {
        "symbol": result.symbol,
        "detail": result.detail,
        "position": list(result.position),
    }
    json.dump(payload, sys.stdout)
    return 0


def definitions_command(source: str, symbol: str, position: tuple[int, int] | None = None) -> int:
    """Emit definition locations for a symbol as JSON."""
    server = TinyLanguageServer(source)
    result = server.definition(symbol, position)
    if result is None:
        sys.stdout.write("null")
        return 0
    payload = {
        "line": result.line,
        "column": result.col,
    }
    json.dump(payload, sys.stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the module entry point."""
    parser = argparse.ArgumentParser(description="TinyLanguage VS Code helper")
    parser.add_argument(
        "command",
        choices=["format", "diagnostics", "completions", "hover", "definitions"],
        help="Tooling command to execute",
    )
    parser.add_argument("--path", dest="path", help="Path of the file being processed", default=None)
    parser.add_argument("--prefix", dest="prefix", help="Completion prefix", default="")
    parser.add_argument("--symbol", dest="symbol", help="Hover symbol", default="")
    parser.add_argument(
        "--position",
        dest="position",
        help="Cursor position as 'line:column' (1-based)",
        default="",
    )
    args = parser.parse_args(argv)

    source = sys.stdin.read()

    if args.command == "format":
        return format_command(source)
    if args.command == "diagnostics":
        return diagnostics_command(source, args.path)
    if args.command == "completions":
        return completions_command(source, args.prefix)
    if args.command == "hover":
        return hover_command(source, args.symbol)
    if args.command == "definitions":
        position = None
        if args.position:
            try:
                line_str, col_str = args.position.split(":")
                position = (int(line_str), int(col_str))
            except ValueError:
                pass
        return definitions_command(source, args.symbol, position)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
