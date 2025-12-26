"""Prototype utilities for a TinyLanguage language server.

The goal is to make it easy to experiment with hover, completion and diagnostic
requests without implementing the full JSON-RPC plumbing. The types below
mirror the high-level structure of the Language Server Protocol while keeping a
lightweight Python interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from tiny_language import (
    BUILTINS,
    KEYWORDS,
    Lexer,
    MethodDef,
    Namespace,
    Parser,
    SourcePos,
    SourceSpan,
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

    def definition(self, symbol: str, position: Optional[Tuple[int, int]] = None) -> Optional[SourcePos]:
        """Return the recorded ``SourcePos`` for ``symbol`` if known.

        The lookup prefers exact matches but will also fall back to unqualified
        names (e.g., ``add``) when a symbol is defined in a namespace
        (e.g., ``Math.add``). If multiple candidates are present, the closest
        symbol to ``position`` is chosen; otherwise the earliest occurrence is
        returned for stability.
        """

        def _score(candidate: SourcePos) -> Tuple[int, int]:
            if position is None:
                return (candidate.line, candidate.col)
            line, col = position
            return (abs(candidate.line - line), abs(candidate.col - col))

        if symbol in self.symbols:
            return self.symbols[symbol]

        matches: List[Tuple[str, SourcePos]] = []
        for name, pos in self.symbols.items():
            if name == symbol or name.split(".")[-1] == symbol:
                matches.append((name, pos))

        if not matches:
            return None

        best = min(matches, key=lambda item: (_score(item[1]), item[0]))
        return best[1]

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
            diagnostics.append(
                Diagnostic(message=str(err), code=err.code, range=_diagnostic_range(err, self.source))
            )
        return diagnostics


def _diagnostic_range(err: TinyLangError, source: str) -> Tuple[int, int, int, int]:
    """Convert a ``TinyLangError`` to a 1-based diagnostic range.

    When the error carries a ``span`` we underline the full start→stop region.
    Otherwise we fall back to a single-character marker at ``err.pos``.
    """

    span: Optional[SourceSpan] = getattr(err, "span", None)
    if span is not None:
        start_line, start_col, _ = _line_info(source, span.start)
        stop_line, stop_col, _ = _line_info(source, span.stop)
        end_col = stop_col + 1  # Make the end position exclusive for VS Code ranges.
        if stop_line == start_line:
            end_col = max(end_col, start_col + 1)
        return (start_line, start_col, stop_line, end_col)

    line, col, _ = _line_info(source, err.pos)
    return (line, col, line, col + 1)


def completions_for_source(source: str, prefix: str = "") -> List[Dict[str, Any]]:
    """Return completion dicts for ``source`` filtered by ``prefix``."""
    server = TinyLanguageServer(source)
    return [{"label": item.label, "kind": item.kind} for item in server.completions(prefix)]


def hover_for_source(source: str, symbol: str) -> Dict[str, Any]:
    """Return hover details for ``symbol`` in ``source`` as a JSON-friendly dict."""
    server = TinyLanguageServer(source)
    result = server.hover(symbol)
    if result is None:
        return {}
    return {"symbol": result.symbol, "detail": result.detail, "position": list(result.position)}


def diagnostics_for_source(source: str) -> List[Dict[str, Any]]:
    """Return diagnostics for ``source`` as JSON-friendly dicts."""
    server = TinyLanguageServer(source)
    return [
        {"message": diag.message, "code": diag.code, "range": list(diag.range)}
        for diag in server.diagnostics()
    ]


__all__ = [
    "TinyLanguageServer",
    "HoverResult",
    "CompletionItem",
    "Diagnostic",
    "completions_for_source",
    "hover_for_source",
    "diagnostics_for_source",
]
