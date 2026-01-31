"""Prototype utilities for a TinyLanguage language server.

The goal is to make it easy to experiment with hover, completion and diagnostic
requests without implementing the full JSON-RPC plumbing. The types below
mirror the high-level structure of the Language Server Protocol while keeping a
lightweight Python interface.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from tiny_errors import diagnostic_range
from tiny_language import (
    BUILTINS,
    KEYWORDS,
    Token,
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
    lint_bare_call_results,
    lint_annotation_enforcement,
    lint_assignment_types,
    lint_call_validation,
    lint_destruct_call_outputs,
    lint_fn_params_used,
    lint_heap_lifetimes,
    lint_import_style,
    lint_locals_used,
    lint_method_params_used,
    lint_no_consecutive_definitions,
    lint_return_validation,
)


def _heap_lints_enabled() -> bool:
    value = os.environ.get("TINY_LINT_HEAP", "").strip().lower()
    return value not in {"0", "false", "no", "off"}


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
    severity: str = "error"
    phase: str = "lint"
    source: str = "linter"
    origin: str = "language_server"
    hint: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)


@dataclass
class WorkspaceSymbol:
    """Summary of a symbol for workspace-level search results."""

    name: str
    kind: str
    detail: str
    position: Tuple[int, int]
    container: str = ""


@dataclass
class ReferenceLocation:
    """Location entry for a reference lookup."""

    range: Tuple[int, int, int, int]


@dataclass
class TextEdit:
    """Text edit entry for formatting, rename, or code actions."""

    range: Tuple[int, int, int, int]
    new_text: str


@dataclass
class CodeAction:
    """Minimal code action entry for formatting or quick fixes."""

    title: str
    kind: str
    edits: List[TextEdit]
    diagnostics: List[str]




class TinyLanguageServer:
    """Extremely small convenience wrapper around the parser and linters."""

    def __init__(self, source: str, *, lint_profile: str = "default"):
        """Parse ``source`` and eagerly build symbol tables for lookups."""
        if lint_profile not in {"default", "typing"}:
            raise ValueError(f"Unknown lint profile: {lint_profile}")
        self.source = source
        self.lint_profile = lint_profile
        self.parse_error: Optional[TinyLangError] = None
        self.parser = Parser(Lexer(source), source)
        try:
            self.stmts = self.parser.parse()
        except TinyLangError as err:
            self.stmts = []
            self.parse_error = err
        self.symbols: Dict[str, SourcePos] = {}
        self.symbol_kinds: Dict[str, str] = {}
        self.symbol_details: Dict[str, str] = {}
        self._tokens: List[Token] = []
        try:
            self._tokens = self._collect_tokens()
        except TinyLangError:
            self._tokens = []
        if self.parse_error is None:
            self._index_symbols(self.stmts)

    def _collect_tokens(self) -> List[Token]:
        """Return a cached list of lexer tokens for source lookups."""
        tokens: List[Token] = []
        lexer = Lexer(self.source)
        while True:
            token = lexer.next_token()
            if token.kind == "EOF":
                break
            tokens.append(token)
        return tokens

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

    def _token_range(self, token: Token) -> Tuple[int, int, int, int]:
        """Return a 1-based, end-exclusive range for a token."""
        return (token.start.line, token.start.col, token.stop.line, token.stop.col + 1)

    def _source_end_position(self) -> Tuple[int, int]:
        """Return the 1-based end position for the current source."""
        if not self.source:
            return (1, 1)
        last_newline = self.source.rfind("\n")
        if last_newline == -1:
            return (1, len(self.source) + 1)
        line = self.source.count("\n") + 1
        col = len(self.source) - last_newline
        return (line, col)

    def _text_at_range(self, range_hint: Tuple[int, int, int, int]) -> str:
        """Return the source snippet covered by ``range_hint`` if it is single-line."""
        start_line, start_col, end_line, end_col = range_hint
        if start_line != end_line:
            return ""
        lines = self.source.splitlines()
        if not (1 <= start_line <= len(lines)):
            return ""
        line_text = lines[start_line - 1]
        start_idx = max(start_col - 1, 0)
        end_idx = max(end_col - 1, start_idx)
        return line_text[start_idx:end_idx]

    def _unused_binding_quickfix(self, diag: Diagnostic) -> Optional[CodeAction]:
        """Return a quick fix for unused bindings when possible."""
        if diag.code != "E002" or "unused" not in diag.message.lower():
            return None
        name = self._text_at_range(diag.range).strip()
        if not name or name == "_" or name.startswith("_"):
            return None
        if not name.isidentifier():
            return None
        new_name = f"_{name}"
        edit = TextEdit(range=diag.range, new_text=new_name)
        return CodeAction(
            title=f"Rename unused binding to '{new_name}'",
            kind="quickfix",
            edits=[edit],
            diagnostics=[diag.code],
        )

    def _iter_dotted_names(self) -> Iterable[Tuple[str, Token]]:
        """Yield dotted name strings with the final token for highlighting."""
        tokens = self._tokens
        for idx, token in enumerate(tokens):
            if token.kind != "NAME":
                continue
            parts = [token.text]
            last_token = token
            j = idx
            while j + 2 < len(tokens) and tokens[j + 1].text == "." and tokens[j + 2].kind == "NAME":
                parts.append(tokens[j + 2].text)
                last_token = tokens[j + 2]
                j += 2
            yield ".".join(parts), last_token

    def _reference_candidates(self, symbol: str) -> Set[str]:
        """Return all symbol spellings eligible for reference matching."""
        candidates = {symbol}
        if "." not in symbol:
            for name in self.symbols:
                if name.split(".")[-1] == symbol:
                    candidates.add(name)
        return candidates

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

    def definition(
        self, symbol: str, position: Optional[Tuple[int, int]] = None
    ) -> Optional[SourcePos]:
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

    def references(self, symbol: str, *, include_definition: bool = True) -> List[ReferenceLocation]:
        """Return reference locations for ``symbol`` based on lexer matches."""
        candidates = self._reference_candidates(symbol)
        results: List[ReferenceLocation] = []
        for name, token in self._iter_dotted_names():
            if name in candidates or name.split(".")[-1] == symbol:
                results.append(ReferenceLocation(range=self._token_range(token)))
        if not include_definition:
            definition = self.definition(symbol)
            if definition is not None:
                results = [
                    ref
                    for ref in results
                    if not (
                        ref.range[0] == definition.line
                        and ref.range[1] == definition.col
                    )
                ]
        return results

    def rename(self, symbol: str, new_name: str) -> List[TextEdit]:
        """Return text edits needed to rename ``symbol`` to ``new_name``."""
        edits = [
            TextEdit(range=ref.range, new_text=new_name)
            for ref in self.references(symbol, include_definition=True)
        ]
        return edits

    def diagnostics(self) -> List[Diagnostic]:
        """Run linters and parser checks, returning any diagnostics."""
        diagnostics: List[Diagnostic] = []

        if self.parse_error is not None:
            return [
                Diagnostic(
                    message=str(self.parse_error),
                    code=self.parse_error.code,
                    range=diagnostic_range(self.parse_error, self.source),
                    phase="parse",
                    source="parser",
                    origin="language_server",
                    hint=self.parse_error.hint,
                    suggestions=list(self.parse_error.suggestions),
                )
            ]

        try:
            lint_destruct_call_outputs(self.stmts, self.source)
            lint_no_consecutive_definitions(self.stmts, self.source)
            lint_import_style(self.stmts, self.source)
            if self.lint_profile == "typing":
                lint_assignment_types(self.stmts, self.source)
                lint_call_validation(self.stmts, self.source)
                lint_return_validation(self.stmts, self.source)
                lint_annotation_enforcement(self.stmts, self.source)
            lint_locals_used(self.stmts, self.source)
            if _heap_lints_enabled():
                lint_heap_lifetimes(self.stmts, self.source)
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
                Diagnostic(
                    message=str(err),
                    code=err.code,
                    range=diagnostic_range(err, self.source),
                    phase="lint",
                    source="linter",
                    origin="language_server",
                    hint=err.hint,
                    suggestions=list(err.suggestions),
                )
            )
        return diagnostics

    def format_edits(self) -> List[TextEdit]:
        """Return text edits that apply the formatter to the whole document."""
        from formatter import format_source

        formatted = format_source(self.source)
        if formatted == self.source:
            return []
        end_line, end_col = self._source_end_position()
        return [TextEdit(range=(1, 1, end_line, end_col), new_text=formatted)]

    def code_actions(self) -> List[CodeAction]:
        """Return available code actions, such as formatting."""
        actions: List[CodeAction] = []
        format_edits = self.format_edits()
        if format_edits:
            actions.append(
                CodeAction(
                    title="Format document",
                    kind="source.format",
                    edits=format_edits,
                    diagnostics=[],
                )
            )
        for diagnostic in self.diagnostics():
            action = self._unused_binding_quickfix(diagnostic)
            if action:
                actions.append(action)
        return actions

    def workspace_symbols(self, query: str = "") -> List[WorkspaceSymbol]:
        """Return symbols whose names match ``query`` for workspace search."""
        if self.parse_error is not None:
            return []
        normalized = query.lower().strip()
        results: List[WorkspaceSymbol] = []
        for name, pos in self.symbols.items():
            short_name = name.split(".")[-1]
            haystack = (name, short_name)
            if normalized and not any(normalized in candidate.lower() for candidate in haystack):
                continue
            container = name.rsplit(".", 1)[0] if "." in name else ""
            detail = self.symbol_details.get(name, "")
            kind = self.symbol_kinds.get(name, "identifier")
            results.append(
                WorkspaceSymbol(
                    name=name,
                    kind=kind,
                    detail=detail,
                    position=(pos.line, pos.col),
                    container=container,
                )
            )
        return sorted(results, key=lambda item: item.name)


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
        {
            "message": diag.message,
            "code": diag.code,
            "range": list(diag.range),
            "severity": diag.severity,
            "phase": diag.phase,
            "source": diag.source,
            "origin": diag.origin,
            "hint": diag.hint,
            "suggestions": list(diag.suggestions),
        }
        for diag in server.diagnostics()
    ]


def references_for_source(source: str, symbol: str, include_definition: bool = True) -> List[Dict[str, Any]]:
    """Return reference ranges for ``symbol`` in ``source``."""
    server = TinyLanguageServer(source)
    return [{"range": list(item.range)} for item in server.references(symbol, include_definition=include_definition)]


def rename_for_source(source: str, symbol: str, new_name: str) -> List[Dict[str, Any]]:
    """Return rename edits for ``symbol`` in ``source``."""
    server = TinyLanguageServer(source)
    return [{"range": list(edit.range), "newText": edit.new_text} for edit in server.rename(symbol, new_name)]


def format_edits_for_source(source: str) -> List[Dict[str, Any]]:
    """Return formatting edits for ``source``."""
    server = TinyLanguageServer(source)
    return [{"range": list(edit.range), "newText": edit.new_text} for edit in server.format_edits()]


def code_actions_for_source(source: str) -> List[Dict[str, Any]]:
    """Return code actions for ``source``."""
    server = TinyLanguageServer(source)
    return [
        {
            "title": action.title,
            "kind": action.kind,
            "edits": [{"range": list(edit.range), "newText": edit.new_text} for edit in action.edits],
            "diagnostics": action.diagnostics,
        }
        for action in server.code_actions()
    ]


def definition_for_source(
    source: str, symbol: str, position: Optional[Tuple[int, int]] = None
) -> Dict[str, Any]:
    """Return definition details for ``symbol`` in ``source`` as JSON-friendly dict."""
    server = TinyLanguageServer(source)
    result = server.definition(symbol, position=position)
    if result is None:
        return {}
    return {"symbol": symbol, "position": [result.line, result.col]}


__all__ = [
    "TinyLanguageServer",
    "HoverResult",
    "CompletionItem",
    "ReferenceLocation",
    "TextEdit",
    "CodeAction",
    "Diagnostic",
    "completions_for_source",
    "definition_for_source",
    "hover_for_source",
    "diagnostics_for_source",
    "references_for_source",
    "rename_for_source",
    "format_edits_for_source",
    "code_actions_for_source",
]
