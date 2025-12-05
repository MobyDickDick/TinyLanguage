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
    MethodDef,
    Namespace,
    Parser,
    SourcePos,
    TypeDef,
    TinyLangError,
    ClassDef,
    Fn,
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
        self.symbol_kinds: Dict[str, str] = {}
        self.symbol_details: Dict[str, str] = {}
        self._index_symbols(self.stmts)

    def _record_symbol(self, name: str, pos: SourcePos, kind: str, detail: Optional[str]) -> None:
        """Store a symbol with supplemental metadata for hover/completion."""

        self.symbols[name] = pos
        self.symbol_kinds[name] = kind
        if detail:
            self.symbol_details[name] = detail

    def _format_signature(self, name: str, params: List, return_type: Optional[str]) -> str:
        parts = []
        for param in params:
            suffix = f": {param.type}" if getattr(param, "type", None) else ""
            parts.append(f"{param.name}{suffix}")
        signature = ", ".join(parts)
        return_annotation = f" -> {return_type}" if return_type else ""
        return f"{name}({signature}){return_annotation}".strip()

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
                    pos = getattr(st, "pos", SourcePos.origin())
                    kind = "identifier"
                    detail: Optional[str] = None
                    if isinstance(st, Fn):
                        kind = "function"
                        detail = f"fn {self._format_signature(name, st.params, st.return_type)}"
                    elif isinstance(st, MethodDef):
                        kind = "method"
                        detail = f"method {self._format_signature(name, st.params, st.return_type)}"
                    elif isinstance(st, ClassDef):
                        kind = "class"
                    elif isinstance(st, TypeDef):
                        kind = "type"
                    self._record_symbol(qualified, pos, kind, detail)
                    if isinstance(st, ClassDef):
                        for method in st.methods:
                            method_name = f"{qualified}.{method.name}" if qualified else method.name
                            method_detail = f"method {self._format_signature(method.name, method.params, method.return_type)}"
                            self._record_symbol(method_name, getattr(method, "pos", pos), "method", method_detail)

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
        return [CompletionItem(label=c, kind=self.symbol_kinds.get(c, "identifier")) for c in filtered]

    def hover(self, symbol: str) -> Optional[HoverResult]:
        """Produce hover info for ``symbol`` if the name is known."""
        if symbol not in self.symbols:
            return None
        pos = self.symbols[symbol]
        detail = self.symbol_details.get(symbol, "TinyLanguage symbol")
        return HoverResult(symbol=symbol, detail=detail, position=(pos.line, pos.col))

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
