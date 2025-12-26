"""Command-line helper for the TinyLanguage language server prototype.

The script wraps the lightweight API from ``language_server.py`` so that
hover, completion, and diagnostic workflows can be tested without JSON-RPC
plumbing. Outputs are emitted as JSON for easy piping into tooling.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from language_server import CompletionItem, Diagnostic, HoverResult, TinyLanguageServer


def _load_source(args: argparse.Namespace) -> str:
    """Return inline source or contents of ``args.file``; exit if missing."""
    if args.source:
        return args.source
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    raise SystemExit("Provide --source or --file to supply TinyLanguage code")


def _hover_dict(result: HoverResult) -> Dict[str, Any]:
    """Convert ``HoverResult`` to a JSON-friendly mapping."""
    return {
        "symbol": result.symbol,
        "detail": result.detail,
        "position": list(result.position),
    }


def _completion_dict(item: CompletionItem) -> Dict[str, Any]:
    """Convert ``CompletionItem`` to a JSON-friendly mapping."""
    return {"label": item.label, "kind": item.kind}


def _diagnostic_dict(diag: Diagnostic) -> Dict[str, Any]:
    """Convert ``Diagnostic`` to a JSON-friendly mapping."""
    return {
        "message": diag.message,
        "code": diag.code,
        "range": list(diag.range),
    }


def completions(server: TinyLanguageServer, prefix: str) -> List[Dict[str, Any]]:
    """Return completion payloads for ``prefix`` using ``server``."""
    return [_completion_dict(item) for item in server.completions(prefix)]


def hover(server: TinyLanguageServer, symbol: str) -> Dict[str, Any]:
    """Return hover information for ``symbol`` or an empty dict."""
    result = server.hover(symbol)
    return _hover_dict(result) if result else {}


def diagnostics(server: TinyLanguageServer) -> List[Dict[str, Any]]:
    """Return diagnostics emitted by ``server`` in JSON-friendly form."""
    return [_diagnostic_dict(diag) for diag in server.diagnostics()]


def definition(
    server: TinyLanguageServer, symbol: str, position: Optional[Tuple[int, int]]
) -> Dict[str, Any]:
    """Return definition information for ``symbol`` or an empty dict."""
    result = server.definition(symbol, position=position)
    if not result:
        return {}
    return {"symbol": symbol, "position": [result.line, result.col]}


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser with subcommands."""
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

    definition_parser = subparsers.add_parser("definition", help="Locate a symbol definition")
    definition_parser.add_argument("--symbol", required=True, help="Symbol name to resolve")
    definition_parser.add_argument(
        "--line", type=int, help="Optional 0-based line used to disambiguate symbols"
    )
    definition_parser.add_argument(
        "--col", type=int, help="Optional 0-based column used to disambiguate symbols"
    )

    subparsers.add_parser("diagnostics", help="List diagnostics for the source")

    return parser


def main() -> None:
    """Entrypoint for invoking the language-server utilities from the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    source = _load_source(args)
    server = TinyLanguageServer(source)

    if args.command == "completions":
        payload = completions(server, args.prefix)
    elif args.command == "hover":
        payload = hover(server, args.symbol)
    elif args.command == "definition":
        if (args.line is None) != (args.col is None):
            raise SystemExit("Provide both --line and --col or neither")
        position = None if args.line is None else (args.line, args.col)
        payload = definition(server, args.symbol, position)
    elif args.command == "diagnostics":
        payload = diagnostics(server)
    else:
        raise SystemExit(f"unknown command: {args.command}")

    json.dump(payload, fp=sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
