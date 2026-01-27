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

from formatter import format_source
from language_server import (
    CodeAction,
    CompletionItem,
    Diagnostic,
    HoverResult,
    ReferenceLocation,
    TextEdit,
    TinyLanguageServer,
    WorkspaceSymbol,
)


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
        "severity": diag.severity,
        "phase": diag.phase,
        "source": diag.source,
        "origin": diag.origin,
        "hint": diag.hint,
    }


def _workspace_symbol_dict(symbol: WorkspaceSymbol) -> Dict[str, Any]:
    """Convert ``WorkspaceSymbol`` to a JSON-friendly mapping."""
    return {
        "name": symbol.name,
        "kind": symbol.kind,
        "detail": symbol.detail,
        "position": list(symbol.position),
        "container": symbol.container,
    }


def _reference_dict(item: ReferenceLocation) -> Dict[str, Any]:
    """Convert ``ReferenceLocation`` to a JSON-friendly mapping."""
    return {"range": list(item.range)}


def _text_edit_dict(edit: TextEdit) -> Dict[str, Any]:
    """Convert ``TextEdit`` to a JSON-friendly mapping."""
    return {"range": list(edit.range), "newText": edit.new_text}


def _code_action_dict(action: CodeAction) -> Dict[str, Any]:
    """Convert ``CodeAction`` to a JSON-friendly mapping."""
    return {
        "title": action.title,
        "kind": action.kind,
        "edits": [_text_edit_dict(edit) for edit in action.edits],
        "diagnostics": list(action.diagnostics),
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


def workspace_symbols(server: TinyLanguageServer, query: str) -> List[Dict[str, Any]]:
    """Return workspace symbol matches for ``query``."""
    return [_workspace_symbol_dict(item) for item in server.workspace_symbols(query)]


def format_source_payload(source: str) -> Dict[str, str]:
    """Return formatted source in a JSON-friendly payload."""
    return {"source": format_source(source)}


def definition(
    server: TinyLanguageServer, symbol: str, position: Optional[Tuple[int, int]]
) -> Dict[str, Any]:
    """Return definition information for ``symbol`` or an empty dict."""
    result = server.definition(symbol, position=position)
    if not result:
        return {}
    return {"symbol": symbol, "position": [result.line, result.col]}


def references(
    server: TinyLanguageServer, symbol: str, include_definition: bool
) -> List[Dict[str, Any]]:
    """Return reference locations for ``symbol``."""
    return [_reference_dict(item) for item in server.references(symbol, include_definition=include_definition)]


def rename(server: TinyLanguageServer, symbol: str, new_name: str) -> List[Dict[str, Any]]:
    """Return rename edits for ``symbol``."""
    return [_text_edit_dict(edit) for edit in server.rename(symbol, new_name)]


def format_edits(server: TinyLanguageServer) -> List[Dict[str, Any]]:
    """Return formatter edits as a list of text edits."""
    return [_text_edit_dict(edit) for edit in server.format_edits()]


def code_actions(server: TinyLanguageServer) -> List[Dict[str, Any]]:
    """Return code actions for ``server``."""
    return [_code_action_dict(action) for action in server.code_actions()]


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        help="Inline TinyLanguage program passed directly on the command line",
    )
    parser.add_argument("--file", help="Path to a .tiny program to load from disk")
    parser.add_argument(
        "--lint-profile",
        choices=["default", "typing"],
        default="default",
        help="Select the lint profile for diagnostics (default: default)",
    )

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
    subparsers.add_parser("format", help="Format the source and emit it as JSON")
    subparsers.add_parser("format-edits", help="Format the source and emit text edits")
    workspace_parser = subparsers.add_parser(
        "workspace-symbols", help="List symbols matching a workspace query"
    )
    workspace_parser.add_argument(
        "--query", default="", help="Substring used to filter workspace symbols"
    )
    references_parser = subparsers.add_parser(
        "references", help="Find references to a symbol"
    )
    references_parser.add_argument("--symbol", required=True, help="Symbol name to search for")
    references_parser.add_argument(
        "--exclude-definition",
        action="store_true",
        help="Exclude the definition location from results",
    )
    rename_parser = subparsers.add_parser("rename", help="Return rename edits for a symbol")
    rename_parser.add_argument("--symbol", required=True, help="Symbol name to rename")
    rename_parser.add_argument("--new-name", required=True, help="New symbol name")
    subparsers.add_parser("code-actions", help="List available code actions")

    return parser


def main() -> None:
    """Entrypoint for invoking the language-server utilities from the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    source = _load_source(args)
    if args.command == "completions":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        payload = completions(server, args.prefix)
    elif args.command == "hover":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        payload = hover(server, args.symbol)
    elif args.command == "definition":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        if (args.line is None) != (args.col is None):
            raise SystemExit("Provide both --line and --col or neither")
        position = None if args.line is None else (args.line, args.col)
        payload = definition(server, args.symbol, position)
    elif args.command == "diagnostics":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        payload = diagnostics(server)
    elif args.command == "format":
        payload = format_source_payload(source)
    elif args.command == "format-edits":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        payload = format_edits(server)
    elif args.command == "workspace-symbols":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        payload = workspace_symbols(server, args.query)
    elif args.command == "references":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        payload = references(
            server, args.symbol, include_definition=not args.exclude_definition
        )
    elif args.command == "rename":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        payload = rename(server, args.symbol, args.new_name)
    elif args.command == "code-actions":
        server = TinyLanguageServer(source, lint_profile=args.lint_profile)
        payload = code_actions(server)
    else:
        raise SystemExit(f"unknown command: {args.command}")

    json.dump(payload, fp=sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
