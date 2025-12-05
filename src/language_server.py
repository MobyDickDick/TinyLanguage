"""Prototype utilities for a TinyLanguage language server.

The goal is to make it easy to experiment with hover, completion and diagnostic
requests without implementing the full JSON-RPC plumbing. The types below
mirror the high-level structure of the Language Server Protocol while keeping a
lightweight Python interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from tiny_language import (
    BUILTINS,
    KEYWORDS,
    Lexer,
    Namespace,
    Parser,
    SourcePos,
    TinyLangError,
    _collect_function_signatures,
    _line_info,
    lint_bare_call_results,
    lint_destruct_call_outputs,
    lint_fn_params_used,
    lint_import_style,
    lint_locals_used,
    lint_method_params_used,
    lint_no_consecutive_definitions,
)


@dataclass
class HoverResult:
    """Structured hover payload returned by ``TinyLanguageServer.hover``."""

    symbol: str
    detail: str
    position: Tuple[int, int]


@dataclass
class CompletionItem:
    """Small completion entry with label and kind fields."""

    label: str
    kind: str = "identifier"


@dataclass
class Diagnostic:
    """Single diagnostic emitted by the linters or parser."""

    message: str
    code: str
    range: Tuple[int, int, int, int]


class TinyLanguageServer:
    """Extremely small convenience wrapper around the parser and linters."""

    def __init__(self, source: str):
        """Parse ``source`` and eagerly build symbol tables for lookups."""
        self.source = source
        self.parser = Parser(Lexer(source), source)
        self.stmts = self.parser.parse()
        self.symbols: Dict[str, SourcePos] = {}
        self._index_symbols(self.stmts)

    def _index_symbols(self, stmts, prefix: str = "") -> None:
        """Recursively collect symbol names with their source positions."""
        for st in stmts:
            if isinstance(st, Namespace):
                nested = f"{prefix}.{st.name}" if prefix else st.name
                self._index_symbols(st.body, nested)
            if hasattr(st, "name"):
                name = getattr(st, "name")
                qualified = f"{prefix}.{name}" if prefix else name
                if isinstance(name, str):
                    self.symbols[qualified] = getattr(st, "pos", SourcePos.origin())

    def completions(self, prefix: str = "") -> List[CompletionItem]:
        """Return completion items for keywords, builtins, and indexed symbols."""
        candidates: Set[str] = set(KEYWORDS) | set(BUILTINS) | set(self.symbols.keys())

        # Provide both fully qualified and short forms for names nested in
        # namespaces. This keeps completions useful in small files where users
        # may type ``add`` before ``Math.add`` without losing access to scoped
        # suggestions.
        for symbol in list(self.symbols.keys()):
            if "." in symbol:
                candidates.add(symbol.split(".")[-1])

        filtered = sorted([c for c in candidates if c.startswith(prefix)])
        return [CompletionItem(label=c) for c in filtered]

    def hover(self, symbol: str) -> Optional[HoverResult]:
        """Produce hover info for ``symbol`` if the name is known."""
        if symbol not in self.symbols:
            return None
        pos = self.symbols[symbol]
        return HoverResult(symbol=symbol, detail="TinyLanguage symbol", position=(pos.line, pos.col))

    def diagnostics(self) -> List[Diagnostic]:
        """Run linters and parser checks, returning any diagnostics."""
        diagnostics: List[Diagnostic] = []

        try:
            lint_destruct_call_outputs(self.stmts, self.source)
            lint_no_consecutive_definitions(self.stmts)
            lint_import_style(self.stmts, self.source)
            lint_locals_used(self.stmts, self.source)
            signatures = _collect_function_signatures(self.stmts)
            lint_bare_call_results(self.stmts, signatures, self.source)
            for st in self.stmts:
                if hasattr(st, "params"):
                    if hasattr(st, "class_name"):
                        lint_method_params_used(st, self.source)
                    else:
                        lint_fn_params_used(st, self.source)
        except TinyLangError as err:
            line, col, _ = _line_info(self.source, err.pos)
            diagnostics.append(Diagnostic(message=str(err), code=err.code, range=(line, col, line, col + 1)))
        return diagnostics


__all__ = ["TinyLanguageServer", "HoverResult", "CompletionItem", "Diagnostic"]
