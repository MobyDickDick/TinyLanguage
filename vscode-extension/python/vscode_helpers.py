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
    formatted = format_source(source)
    sys.stdout.write(formatted)
    return 0


def diagnostics_command(source: str, file_path: str | None = None) -> int:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TinyLanguage VS Code helper")
    parser.add_argument("command", choices=["format", "diagnostics"], help="Tooling command to execute")
    parser.add_argument("--path", dest="path", help="Path of the file being processed", default=None)
    args = parser.parse_args(argv)

    source = sys.stdin.read()

    if args.command == "format":
        return format_command(source)
    if args.command == "diagnostics":
        return diagnostics_command(source, args.path)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
