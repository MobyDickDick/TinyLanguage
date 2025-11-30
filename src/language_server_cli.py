"""Command-line helper for the TinyLanguage language server prototype.

The script wraps the lightweight API from ``language_server.py`` so that
hover, completion, and diagnostic workflows can be tested without JSON-RPC
plumbing. Outputs are emitted as JSON for easy piping into tooling.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from language_server import CompletionItem, Diagnostic, HoverResult, TinyLanguageServer


def _load_source(args: argparse.Namespace) -> str:
    if args.source:
        return args.source
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    raise SystemExit("Provide --source or --file to supply TinyLanguage code")


def _hover_dict(result: HoverResult) -> Dict[str, Any]:
    return {
        "symbol": result.symbol,
        "detail": result.detail,
        "position": list(result.position),
    }


def _completion_dict(item: CompletionItem) -> Dict[str, Any]:
    return {"label": item.label, "kind": item.kind}


def _diagnostic_dict(diag: Diagnostic) -> Dict[str, Any]:
    return {
        "message": diag.message,
        "code": diag.code,
        "range": list(diag.range),
    }


def completions(server: TinyLanguageServer, prefix: str) -> List[Dict[str, Any]]:
    return [_completion_dict(item) for item in server.completions(prefix)]


def hover(server: TinyLanguageServer, symbol: str) -> Dict[str, Any]:
    result = server.hover(symbol)
    return _hover_dict(result) if result else {}


def diagnostics(server: TinyLanguageServer) -> List[Dict[str, Any]]:
    return [_diagnostic_dict(diag) for diag in server.diagnostics()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        help="Inline TinyLanguage program passed directly on the command line",
    )
    parser.add_argument("--file", help="Path to a .tiny program to load from disk")

    subparsers = parser.add_subparsers(dest="command", required=True)

    completions_parser = subparsers.add_parser("completions", help="List completion items")
    completions_parser.add_argument(
        "--prefix", default="", help="Prefix used to filter completion candidates"
    )

    hover_parser = subparsers.add_parser("hover", help="Show hover information for a symbol")
    hover_parser.add_argument("--symbol", required=True, help="Symbol name to inspect")

    subparsers.add_parser("diagnostics", help="List diagnostics for the source")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    source = _load_source(args)
    server = TinyLanguageServer(source)

    if args.command == "completions":
        payload = completions(server, args.prefix)
    elif args.command == "hover":
        payload = hover(server, args.symbol)
    elif args.command == "diagnostics":
        payload = diagnostics(server)
    else:
        raise SystemExit(f"unknown command: {args.command}")

    json.dump(payload, fp=sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
