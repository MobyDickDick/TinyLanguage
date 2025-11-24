from __future__ import annotations

import argparse
import difflib
import importlib.util
import math
import sys
import threading
from pathlib import Path

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from stdlib import register_stdlib

class _FallbackReadline:
    """Minimal in-memory readline replacement for platforms without it."""

    def __init__(self) -> None:
        self._history: List[str] = []
        self._completions = None
        self._history_length = 1000

    # Configuration API
    def set_completer_delims(self, _delims: str) -> None:  # pragma: no cover - noop
        return

    def set_completer(self, completer) -> None:  # pragma: no cover - noop
        self._completions = completer

    def parse_and_bind(self, _cmd: str) -> None:  # pragma: no cover - noop
        return

    # History management
    def read_history_file(self, path: Path) -> None:
        if not Path(path).exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            self._history = [line.rstrip("\n") for line in f]

    def write_history_file(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for entry in self._history[-self._history_length :]:
                f.write(entry + "\n")

    def set_history_length(self, length: int) -> None:  # pragma: no cover - simple setter
        self._history_length = max(0, length)

    def clear_history(self) -> None:
        self._history.clear()

    def add_history(self, line: str) -> None:
        self._history.append(line)

    def get_history_item(self, index: int) -> Optional[str]:
        idx = index - 1
        if 0 <= idx < len(self._history):
            return self._history[idx]
        return None

    def get_current_history_length(self) -> int:  # pragma: no cover - trivial
        return len(self._history)


def _load_readline():
    """Return a readline-compatible object even on platforms without it."""

    required_api = {
        "set_completer_delims",
        "set_completer",
        "parse_and_bind",
        "read_history_file",
        "write_history_file",
        "set_history_length",
        "clear_history",
        "add_history",
        "get_history_item",
        "get_current_history_length",
    }

    try:  # pragma: no cover - import may fail on some platforms
        import readline as rl  # type: ignore
    except Exception:  # pragma: no cover - fallback path
        return _FallbackReadline()

    missing = [name for name in required_api if not hasattr(rl, name)]
    if missing:  # pragma: no cover - platforms with partial readline support
        return _FallbackReadline()

    return rl


readline = _load_readline()


@dataclass(frozen=True)
class SourcePos:
    index: int
    line: int
    col: int

    @staticmethod
    def origin() -> "SourcePos":
        return SourcePos(0, 1, 1)


@dataclass
class TinyLangError(Exception):
    message: str
    pos: SourcePos = field(default_factory=SourcePos.origin)
    code: str = "E000"
    hint: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - Exception already stringifies message
        return self.message


def _line_info(source: str, pos: Union[int, SourcePos]) -> Tuple[int, int, str]:
    lines = source.splitlines()
    if isinstance(pos, SourcePos):
        line = max(1, min(pos.line, len(lines) or 1))
        line_text = lines[line - 1] if 0 <= line - 1 < len(lines) else ""
        col = max(1, min(pos.col, len(line_text) + 1)) if line_text else pos.col
        return line, col, line_text
    idx = max(0, min(len(source), pos))
    line = source.count("\n", 0, idx) + 1
    last_nl = source.rfind("\n", 0, idx)
    col = idx - (last_nl + 1) + 1
    line_text = lines[line - 1] if lines else ""
    return line, col, line_text


def format_error(
    source: str, pos: Union[int, SourcePos], message: str, *, code: str = "E000", hint: Optional[str] = None
) -> str:
    lines = source.splitlines()
    line, col, _ = _line_info(source, pos)
    gutter_width = len(str(max(1, len(lines))))
    start = max(1, line - 1)
    end = min(len(lines), line + 1) if lines else line
    context: List[str] = []
    for ln in range(start, end + 1):
        prefix = ">" if ln == line else " "
        text = lines[ln - 1] if 0 <= ln - 1 < len(lines) else ""
        context.append(f"{prefix} {ln:>{gutter_width}} | {text}")
    pointer_line = f"  {' ' * gutter_width} | {' ' * (col - 1)}^"
    header = f"[{code}] {message} (line {line}, col {col})"
    lines_out = [header] + context + [pointer_line]
    if hint:
        lines_out.append(f"  Hint: {hint}")
    return "\n".join(lines_out)


def _closest_match(name: str, candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _classify_error(msg: str, candidates: Optional[List[str]] = None) -> Tuple[str, Optional[str]]:
    lower_msg = msg.lower()
    if "return value must be bound" in lower_msg or "must be returned" in lower_msg:
        return "E001", "Bind the return value, e.g. `define result = call();`, or add a return that includes the mutated data."
    if lower_msg.startswith("unused"):
        return "E002", "Remove the unused binding or reference it so it is clearly consumed (prefix with '_' to silence)."
    if "unknown variable" in lower_msg:
        suggestion = _closest_match(msg.split()[-1], candidates or []) if candidates is not None else None
        base_hint = "Declare the variable first, e.g. `define name = ...;`."
        if suggestion:
            return "E003", f"Did you mean `{suggestion}`? {base_hint}"
        return "E003", base_hint
    return "E000", None

# ----- Lexer -----

KEYWORDS = {
    "define",
    "print",
    "if",
    "else",
    "while",
    "fn",
    "return",
    "operator",
    "new",
    "type",
    "class",
    "namespace",
    "spawn",
    "true",
    "false",
    "and",
    "or",
    "not",
}

BUILTINS = {"Collections", "Math", "String", "len", "print"}


@dataclass
class Token:
    kind: str
    text: str
    pos: SourcePos


class Lexer:
    def __init__(self, source: str):
        self.s = source
        self.i = 0
        self.n = len(source)
        self.line = 1
        self.col = 1

    def _peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    def _advance(self, n: int = 1) -> None:
        for _ in range(n):
            if self.i < self.n and self.s[self.i] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.i += 1

    def _skip_ws_comments(self) -> None:
        while self.i < self.n:
            c = self.s[self.i]
            if c in " \t\r\n":
                self._advance()
                continue
            if c == "/" and self.i + 1 < self.n and self.s[self.i + 1] == "/":
                self._advance(2)
                while self.i < self.n and self.s[self.i] != "\n":
                    self._advance()
                continue
            break

    def next_token(self) -> Token:
        self._skip_ws_comments()
        if self.i >= self.n:
            return Token("EOF", "", SourcePos(self.i, self.line, self.col))
        c = self.s[self.i]
        pos = SourcePos(self.i, self.line, self.col)

        if c == "&" and self.i + 1 < self.n and self.s[self.i + 1] == "&":
            self._advance(2)
            return Token("OP", "&&", pos)
        if c == "|" and self.i + 1 < self.n and self.s[self.i + 1] == "|":
            self._advance(2)
            return Token("OP", "||", pos)
        if c == '"':
            return self._read_string()
        if c.isalpha() or c == "_":
            j = self.i + 1
            while j < self.n and (self.s[j].isalnum() or self.s[j] == "_"):
                j += 1
            txt = self.s[self.i:j]
            consumed = j - self.i
            self.i = j
            self.col += consumed
            kind = "KW" if txt in KEYWORDS else "NAME"
            return Token(kind, txt, pos)
        if c.isdigit():
            j = self.i + 1
            hasdot = False
            while j < self.n:
                cj = self.s[j]
                if cj == "." and not hasdot:
                    hasdot = True
                    j += 1
                    continue
                if cj.isdigit():
                    j += 1
                    continue
                break
            txt = self.s[self.i:j]
            consumed = j - self.i
            self.i = j
            self.col += consumed
            return Token("NUMBER", txt, pos)
        if c in (">", "<", "=", "!"):
            if self.i + 1 < self.n and self.s[self.i + 1] == "=":
                self.i += 2
                self.col += 2
                return Token("OP", c + "=", pos)
        if c in "+-*/><^!":
            self._advance()
            return Token("OP", c, pos)
        if c in "(){}[];,=:.":
            self._advance()
            return Token("SYM", c, pos)
        raise TinyLangError(format_error(self.s, pos, f"lexing error: unexpected character '{c}'"), pos)

    def _read_string(self) -> Token:
        pos0 = SourcePos(self.i, self.line, self.col)
        self._advance()  # skip opening quote
        buf = []
        while self.i < self.n:
            c = self.s[self.i]
            if c == '"':
                self._advance()
                return Token("STRING", "".join(buf), pos0)
            if c == "\\":
                self._advance()
                if self.i >= self.n:
                    raise TinyLangError(
                        format_error(self.s, pos0, "unterminated escape in string"), pos0
                    )
                esc = self.s[self.i]
                self._advance()
                if esc == "n":
                    buf.append("\n")
                elif esc == "t":
                    buf.append("\t")
                elif esc == "r":
                    buf.append("\r")
                elif esc == '"':
                    buf.append('"')
                elif esc == "\\":
                    buf.append("\\")
                else:
                    buf.append("\\" + esc)
            else:
                buf.append(c)
                self._advance()
        raise TinyLangError(
            format_error(self.s, pos0, "unterminated string literal"), pos0
        )


# ----- AST Nodes -----


class IR:
    pass


@dataclass
class Let(IR):
    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Assign(IR):
    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class FieldAssign(IR):
    obj: IR
    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Print(IR):
    exprs: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class If(IR):
    cond: IR
    then: List[IR]
    els: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class While(IR):
    cond: IR
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Fn(IR):
    name: str
    params: List[str]
    body: List[IR]
    namespace: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodDef(IR):
    class_name: str
    name: str
    params: List[str]
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Namespace(IR):
    name: str
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Return(IR):
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class CallStmt(IR):
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class OpDef(IR):
    op: str
    a_name: str
    a_type: str
    b_name: str
    b_type: str
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class DestructAssign(IR):
    names: List[str]
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class TypeDef(IR):
    name: str
    fields: List[Tuple[str, str]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ClassDef(IR):
    name: str
    fields: List[Tuple[str, str]]
    methods: List["MethodDef"]
    bases: List[str]
    pos: SourcePos = field(default_factory=SourcePos.origin)


# Expressions
@dataclass
class Num(IR):
    txt: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Str(IR):
    txt: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Bool(IR):
    value: bool
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Var(IR):
    name: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Call(IR):
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class New(IR):
    size: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class NewLit(IR):
    items: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Bin(IR):
    op: str
    a: IR
    b: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ObjLit(IR):
    fields: List[Tuple[str, IR]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Field(IR):
    obj: IR
    name: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodCall(IR):
    obj: IR
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ClassNew(IR):
    name: str
    init: List[Tuple[str, IR]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Spawn(IR):
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


# ----- Parser -----


class Parser:
    def __init__(self, lx: Lexer, source: str):
        self.lx = lx
        self.source = source
        self.tok = lx.next_token()

    def _error(self, message: str, pos: SourcePos) -> TinyLangError:
        code, hint = _classify_error(message)
        return TinyLangError(format_error(self.source, pos, message, code=code, hint=hint), pos, code=code, hint=hint)

    def _eat(self, kind: str, text: Optional[str] = None) -> Token:
        if self.tok.kind != kind or (text is not None and self.tok.text != text):
            raise self._error(f"expected {kind}{' '+text if text else ''}", self.tok.pos)
        t = self.tok
        self.tok = self.lx.next_token()
        return t

    def _eat_name_or_kw(self) -> Token:
        if self.tok.kind in {"NAME", "KW"}:
            t = self.tok
            self.tok = self.lx.next_token()
            return t
        raise self._error("expected NAME", self.tok.pos)

    def _accept(self, kind: str, text: Optional[str] = None) -> bool:
        if self.tok.kind == kind and (text is None or self.tok.text == text):
            self.tok = self.lx.next_token()
            return True
        return False

    def parse(self) -> List[IR]:
        stmts: List[IR] = []
        while self.tok.kind != "EOF":
            stmts.append(self.parse_stmt())
        return stmts

    def parse_block(self) -> List[IR]:
        self._eat("SYM", "{")
        stmts: List[IR] = []
        while not (self.tok.kind == "SYM" and self.tok.text == "}"):
            stmts.append(self.parse_stmt())
        self._eat("SYM", "}")
        return stmts

    def parse_stmt(self) -> IR:
        if self.tok.kind == "KW" and self.tok.text == "define":
            kw = self._eat("KW", "define")
            name_tok = self._eat("NAME")
            self._eat("SYM", "=")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return Let(name_tok.text, expr, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "print":
            kw = self._eat("KW", "print")
            self._eat("SYM", "(")
            exprs: List[IR] = []
            if not (self.tok.kind == "SYM" and self.tok.text == ")"):
                exprs.append(self.parse_expr())
                while self._accept("SYM", ","):
                    exprs.append(self.parse_expr())
            self._eat("SYM", ")")
            self._eat("SYM", ";")
            return Print(exprs, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "if":
            kw = self._eat("KW", "if")
            self._eat("SYM", "(")
            cond = self.parse_expr()
            self._eat("SYM", ")")
            then = self.parse_block()
            els: List[IR] = []
            if self.tok.kind == "KW" and self.tok.text == "else":
                self._eat("KW", "else")
                els = self.parse_block()
            return If(cond, then, els, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "while":
            kw = self._eat("KW", "while")
            self._eat("SYM", "(")
            cond = self.parse_expr()
            self._eat("SYM", ")")
            body = self.parse_block()
            return While(cond, body, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "namespace":
            kw = self._eat("KW", "namespace")
            name = self.parse_qualified_name()
            body = self.parse_block()
            return Namespace(name, body, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "fn":
            kw = self._eat("KW", "fn")
            name_tok = self._eat("NAME")
            params = self.parse_param_list()
            body = self.parse_block()
            return Fn(name_tok.text, params, body, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "return":
            kw = self._eat("KW", "return")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return Return(expr, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "type":
            kw = self._eat("KW", "type")
            name_tok = self._eat("NAME")
            self._eat("SYM", "{")
            fields: List[Tuple[str, str]] = []
            while not self._accept("SYM", "}"):
                fname = self._eat("NAME").text
                self._eat("SYM", ":")
                ftype = self._eat("NAME").text
                self._eat("SYM", ";")
                fields.append((fname, ftype))
            return TypeDef(name_tok.text, fields, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "class":
            kw = self._eat("KW", "class")
            cname_tok = self._eat("NAME")
            bases: List[str] = []
            if self._accept("SYM", ":"):
                bases.append(self._eat("NAME").text)
                while self._accept("SYM", ","):
                    bases.append(self._eat("NAME").text)
            self._eat("SYM", "{")
            fields: List[Tuple[str, str]] = []
            methods: List[MethodDef] = []
            while not (self.tok.kind == "SYM" and self.tok.text == "}"):
                if self.tok.kind == "KW" and self.tok.text == "fn":
                    self._eat("KW", "fn")
                    mname_tok = self._eat_name_or_kw()
                    params = self.parse_param_list()
                    body = self.parse_block()
                    methods.append(MethodDef(cname_tok.text, mname_tok.text, params, body, pos=mname_tok.pos))
                else:
                    fname = self._eat("NAME").text
                    self._eat("SYM", ":")
                    ftype = self._eat("NAME").text
                    self._eat("SYM", ";")
                    fields.append((fname, ftype))
            self._eat("SYM", "}")
            return ClassDef(cname_tok.text, fields, methods, bases, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "operator":
            kw = self._eat("KW", "operator")
            op_tok = self._eat("OP")
            self._eat("SYM", "(")
            a_name = self._eat("NAME").text
            self._eat("SYM", ":")
            a_type = self._eat("NAME").text
            self._eat("SYM", ",")
            b_name = self._eat("NAME").text
            self._eat("SYM", ":")
            b_type = self._eat("NAME").text
            self._eat("SYM", ")")
            self._eat("OP", "-")
            self._eat("OP", ">")
            _ = self._eat("NAME").text  # return type (unused)
            body = self.parse_block()
            return OpDef(op_tok.text, a_name, a_type, b_name, b_type, body, pos=kw.pos)
        # destructuring or assignment/field assignment
        if self.tok.kind == "SYM" and self.tok.text == "{":
            names, start_pos = self.parse_destruct_names()
            self._eat("SYM", "=")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return DestructAssign(names, expr, pos=start_pos)
        if self.tok.kind == "NAME":
            # look ahead for field assignment or normal assignment/call
            name_tok = self.tok
            self._eat("NAME")
            if self._accept("SYM", "."):
                field_name = self._eat_name_or_kw().text
                if self._accept("SYM", "="):
                    expr = self.parse_expr()
                    self._eat("SYM", ";")
                    return FieldAssign(Var(name_tok.text, pos=name_tok.pos), field_name, expr, pos=name_tok.pos)
                # method call statement
                args = self.parse_arg_list()
                self._eat("SYM", ";")
                return CallStmt(f"{name_tok.text}.{field_name}", args, pos=name_tok.pos)
            if self._accept("SYM", "="):
                expr = self.parse_expr()
                self._eat("SYM", ";")
                return Assign(name_tok.text, expr, pos=name_tok.pos)
            # call statement on identifier
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                self._eat("SYM", ";")
                return CallStmt(name_tok.text, args, pos=name_tok.pos)
            raise self._error("unexpected token after name", name_tok.pos)
        raise self._error(f"unexpected token {self.tok.kind}", self.tok.pos)

    def parse_param_list(self) -> List[str]:
        self._eat("SYM", "(")
        params: List[str] = []
        if not (self.tok.kind == "SYM" and self.tok.text == ")"):
            params.append(self._eat("NAME").text)
            while self._accept("SYM", ","):
                params.append(self._eat("NAME").text)
        self._eat("SYM", ")")
        return params

    def parse_arg_list(self) -> List[IR]:
        self._eat("SYM", "(")
        args: List[IR] = []
        if not (self.tok.kind == "SYM" and self.tok.text == ")"):
            args.append(self.parse_expr())
            while self._accept("SYM", ","):
                args.append(self.parse_expr())
        self._eat("SYM", ")")
        return args

    def parse_destruct_names(self) -> Tuple[List[str], SourcePos]:
        start_pos = self._eat("SYM", "{").pos
        names = [self._eat("NAME").text]
        while self._accept("SYM", ","):
            names.append(self._eat("NAME").text)
        self._eat("SYM", "}")
        return names, start_pos

    # expression parsing with precedence
    def parse_expr(self) -> IR:
        return self.parse_logic_or()

    def parse_logic_or(self) -> IR:
        left = self.parse_logic_and()
        while (
            (self.tok.kind == "KW" and self.tok.text == "or")
            or (self.tok.kind == "OP" and self.tok.text == "||")
        ):
            op_tok = self.tok
            self._eat(self.tok.kind)
            right = self.parse_logic_and()
            left = Bin("or", left, right, pos=op_tok.pos)
        return left

    def parse_logic_and(self) -> IR:
        left = self.parse_compare()
        while (
            (self.tok.kind == "KW" and self.tok.text == "and")
            or (self.tok.kind == "OP" and self.tok.text == "&&")
        ):
            op_tok = self.tok
            self._eat(self.tok.kind)
            right = self.parse_compare()
            left = Bin("and", left, right, pos=op_tok.pos)
        return left

    def parse_compare(self) -> IR:
        left = self.parse_term()
        while self.tok.kind == "OP" and self.tok.text in (">", ">=", "<", "<=", "==", "!="):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_term()
            left = Bin(op, left, right, pos=op_tok.pos)
        return left

    def parse_term(self) -> IR:
        left = self.parse_factor()
        while self.tok.kind == "OP" and self.tok.text in ("+", "-"):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_factor()
            left = Bin(op, left, right, pos=op_tok.pos)
        return left

    def parse_factor(self) -> IR:
        left = self.parse_power()
        while self.tok.kind == "OP" and self.tok.text in ("*", "/"):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_power()
            left = Bin(op, left, right, pos=op_tok.pos)
        return left

    def parse_power(self) -> IR:
        left = self.parse_unary()
        if self.tok.kind == "OP" and self.tok.text == "^":
            op_tok = self._eat("OP")
            right = self.parse_power()
            return Bin("^", left, right, pos=op_tok.pos)
        return left

    def parse_unary(self) -> IR:
        if self.tok.kind == "OP" and self.tok.text == "-":
            op_tok = self._eat("OP")
            return Bin("-", Num("0", pos=op_tok.pos), self.parse_unary(), pos=op_tok.pos)
        if (self.tok.kind == "KW" and self.tok.text == "not") or (
            self.tok.kind == "OP" and self.tok.text == "!"
        ):
            op_tok = self.tok
            self._eat(self.tok.kind)
            return Bin("not", Num("0", pos=op_tok.pos), self.parse_unary(), pos=op_tok.pos)
        return self.parse_postfix()

    def parse_postfix(self) -> IR:
        expr = self.parse_primary()
        while True:
            if self.tok.kind == "SYM" and self.tok.text == ".":
                dot_tok = self._eat("SYM", ".")
                name_tok = self._eat_name_or_kw()
                if self.tok.kind == "SYM" and self.tok.text == "(":
                    args = self.parse_arg_list()
                    expr = MethodCall(expr, name_tok.text, args, pos=dot_tok.pos)
                else:
                    expr = Field(expr, name_tok.text, pos=dot_tok.pos)
                continue
            break
        return expr

    def parse_primary(self) -> IR:
        if self._accept("SYM", "("):
            inner = self.parse_expr()
            self._eat("SYM", ")")
            return inner
        if self.tok.kind == "NUMBER":
            t = self._eat("NUMBER")
            return Num(t.text, pos=t.pos)
        if self.tok.kind == "STRING":
            t = self._eat("STRING")
            return Str(t.text, pos=t.pos)
        if self.tok.kind == "KW" and self.tok.text in {"true", "false"}:
            kw = self.tok
            val = kw.text == "true"
            self._eat("KW")
            return Bool(val, pos=kw.pos)
        if self.tok.kind in {"NAME", "KW"}:
            name_tok = self._eat(self.tok.kind)
            name = name_tok.text
            if name == "spawn":
                target = self._eat_name_or_kw().text
                args = self.parse_arg_list()
                return Spawn(target, args, pos=name_tok.pos)
            if name == "new" and self.tok.kind == "SYM" and self.tok.text == "[":
                start_tok = self._eat("SYM", "[")
                items: List[IR] = []
                if not (self.tok.kind == "SYM" and self.tok.text == "]"):
                    items.append(self.parse_expr())
                    while self._accept("SYM", ","):
                        items.append(self.parse_expr())
                self._eat("SYM", "]")
                return NewLit(items, pos=start_tok.pos)
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                return Call(name, args, pos=name_tok.pos)
            if name == "new" and self.tok.kind == "NAME":
                cname = self._eat("NAME").text
                start_tok = self._eat("SYM", "{")
                init: List[Tuple[str, IR]] = []
                while not self._accept("SYM", "}"):
                    fname = self.parse_field_name()
                    self._eat("SYM", ":")
                    fexpr = self.parse_expr()
                    init.append((fname, fexpr))
                    if self._accept("SYM", "}"):
                        break
                    if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                        raise self._error("expected field separator", self.tok.pos)
                return ClassNew(cname, init, pos=name_tok.pos)
            return Var(name, pos=name_tok.pos)
        if self.tok.kind == "SYM" and self.tok.text == "{":
            start_tok = self._eat("SYM", "{")
            fields: List[Tuple[str, IR]] = []
            while not self._accept("SYM", "}"):
                fname = self.parse_field_name()
                self._eat("SYM", ":")
                fexpr = self.parse_expr()
                fields.append((fname, fexpr))
                if self._accept("SYM", "}"):
                    break
                if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                    raise self._error("expected field separator", self.tok.pos)
            return ObjLit(fields, pos=start_tok.pos)
        raise self._error(f"unexpected token {self.tok.kind}", self.tok.pos)

    def parse_field_name(self) -> str:
        name = self._eat("NAME").text
        if self._accept("SYM", "."):
            sub = self._eat("NAME").text
            return f"{name}.{sub}"
        return name

    def parse_qualified_name(self) -> str:
        parts = [self._eat("NAME").text]
        while self._accept("SYM", "."):
            parts.append(self._eat("NAME").text)
        return ".".join(parts)


# ----- Linter -----


def uses_in_expr(e: IR, reads: Dict[str, int]) -> None:
    if isinstance(e, Var):
        reads[e.name] = reads.get(e.name, 0) + 1
    elif isinstance(e, Bin):
        uses_in_expr(e.a, reads)
        uses_in_expr(e.b, reads)
    elif isinstance(e, Call):
        for a in e.args:
            uses_in_expr(a, reads)
    elif isinstance(e, Spawn):
        for a in e.args:
            uses_in_expr(a, reads)
    elif isinstance(e, New):
        uses_in_expr(e.size, reads)
    elif isinstance(e, NewLit):
        for it in e.items:
            uses_in_expr(it, reads)
    elif isinstance(e, Field):
        uses_in_expr(e.obj, reads)
    elif isinstance(e, MethodCall):
        uses_in_expr(e.obj, reads)
        for a in e.args:
            uses_in_expr(a, reads)
    elif isinstance(e, ClassNew):
        for _, v in e.init:
            uses_in_expr(v, reads)
    elif isinstance(e, ObjLit):
        for _, v in e.fields:
            uses_in_expr(v, reads)


def lint_stmt_reads(s: IR, reads: Dict[str, int]) -> None:
    if isinstance(s, (Let, Assign)):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, FieldAssign):
        uses_in_expr(s.obj, reads)
        uses_in_expr(s.expr, reads)
    elif isinstance(s, Print):
        for expr in s.exprs:
            uses_in_expr(expr, reads)
    elif isinstance(s, If):
        uses_in_expr(s.cond, reads)
        for t in s.then:
            lint_stmt_reads(t, reads)
        for t in s.els:
            lint_stmt_reads(t, reads)
    elif isinstance(s, While):
        uses_in_expr(s.cond, reads)
        for t in s.body:
            lint_stmt_reads(t, reads)
    elif isinstance(s, Return):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, OpDef):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp)
        miss = []
        if tmp.get(s.a_name, 0) == 0:
            miss.append(s.a_name)
        if tmp.get(s.b_name, 0) == 0:
            miss.append(s.b_name)
        if miss:
            raise RuntimeError(f"unused operator parameter(s) in op {s.op}: {', '.join(miss)}")
        for name, count in tmp.items():
            if name in {s.a_name, s.b_name}:
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, DestructAssign):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, MethodDef):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp)
        miss = [p for p in s.params if tmp.get(p, 0) == 0]
        if miss:
            raise RuntimeError(
                f"unused parameter(s) in method {s.class_name}.{s.name}: {', '.join(miss)}"
            )
        for name, count in tmp.items():
            if name in set(s.params):
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, Fn):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp)
        for name, count in tmp.items():
            if name in set(s.params):
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, ClassDef):
        for m in s.methods:
            lint_stmt_reads(m, reads)
    elif isinstance(s, Namespace):
        for t in s.body:
            lint_stmt_reads(t, reads)


def lint_fn_params_used(fn: Fn, source: Optional[str] = None) -> None:
    reads: Dict[str, int] = {}
    for st in fn.body:
        lint_stmt_reads(st, reads)
    unused = [p for p in fn.params if reads.get(p, 0) == 0]
    if unused:
        msg = f"unused parameter(s) in function {fn.name}: {', '.join(unused)}"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, fn.pos, msg, code="E002", hint="Remove the unused parameter or reference it."),
            fn.pos,
            code="E002",
            hint="Remove the unused parameter or reference it.",
        )
    lint_param_mutations_returned(fn.body, set(fn.params), fn.name, is_method=False, source=source, pos=fn.pos)
    lint_destruct_call_outputs(fn.body)
    lint_locals_used(fn.body, source)


def lint_method_params_used(md: MethodDef, source: Optional[str] = None) -> None:
    reads: Dict[str, int] = {}
    for st in md.body:
        lint_stmt_reads(st, reads)
    unused = [p for p in md.params if reads.get(p, 0) == 0]
    if unused:
        msg = f"unused parameter(s) in method {md.class_name}.{md.name}: {', '.join(unused)}"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, md.pos, msg, code="E002", hint="Remove the unused parameter or reference it."),
            md.pos,
            code="E002",
            hint="Remove the unused parameter or reference it.",
        )
    lint_param_mutations_returned(
        md.body, set(md.params), f"{md.class_name}.{md.name}", is_method=True, source=source, pos=md.pos
    )
    lint_destruct_call_outputs(md.body)
    lint_locals_used(md.body, source)


def lint_locals_used(stmts: List[IR], source: Optional[str] = None) -> None:
    defs: Dict[str, SourcePos] = {}
    uses: Dict[str, int] = {}

    def collect_defs(block: List[IR]) -> None:
        for idx, s in enumerate(block):
            if isinstance(s, Let):
                defs[s.name] = s.pos
            elif isinstance(s, DestructAssign):
                for nm in s.names:
                    defs[nm] = s.pos
            elif isinstance(s, If):
                collect_defs(s.then)
                collect_defs(s.els)
            elif isinstance(s, While):
                collect_defs(s.body)
            elif isinstance(s, Namespace):
                collect_defs(s.body)

    collect_defs(stmts)
    for s in stmts:
        lint_stmt_reads(s, uses)
    unused = [n for n in defs if uses.get(n, 0) == 0]
    if unused:
        pos = defs[unused[0]]
        msg = f"unused local binding(s): {', '.join(unused)}"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, pos, msg, code="E002", hint="Remove the unused binding or reference it."),
            pos,
            code="E002",
            hint="Remove the unused binding or reference it.",
        )


def lint_destruct_call_outputs(stmts: List[IR]) -> None:
    for st in stmts:
        lint_destruct_call_outputs_stmt(st)


def lint_no_consecutive_definitions(stmts: List[IR]) -> None:
    prev: Optional[str] = None

    def check_block(block: List[IR]) -> None:
        nonlocal prev
        prev = None
        for st in block:
            if isinstance(st, (If, While)):
                lint_no_consecutive_definitions(st.then if isinstance(st, If) else st.body)
                if isinstance(st, If):
                    lint_no_consecutive_definitions(st.els)
                prev = None
                continue
            if isinstance(st, Fn):
                lint_no_consecutive_definitions(st.body)
                prev = None
                continue
            if isinstance(st, MethodDef):
                lint_no_consecutive_definitions(st.body)
                prev = None
                continue
            if isinstance(st, ClassDef):
                for m in st.methods:
                    lint_no_consecutive_definitions(m.body)
                prev = None
                continue
            if isinstance(st, Namespace):
                lint_no_consecutive_definitions(st.body)
                prev = None
                continue

            current: Optional[str] = None
            if isinstance(st, Let):
                current = st.name

            if current is not None and prev == current:
                raise RuntimeError(f"variable {current} defined twice in a row")

            prev = current if current is not None else None

    check_block(stmts)


def lint_destruct_call_outputs_stmt(st: IR) -> None:
    if isinstance(st, DestructAssign):
        check_destruct_call_expr(st.expr, set(st.names))
    elif isinstance(st, If):
        lint_destruct_call_outputs(st.then)
        lint_destruct_call_outputs(st.els)
    elif isinstance(st, While):
        lint_destruct_call_outputs(st.body)
    elif isinstance(st, Fn):
        lint_destruct_call_outputs(st.body)
    elif isinstance(st, MethodDef):
        lint_destruct_call_outputs(st.body)
    elif isinstance(st, ClassDef):
        for m in st.methods:
            lint_destruct_call_outputs_stmt(m)
    elif isinstance(st, Namespace):
        lint_destruct_call_outputs(st.body)


def check_destruct_call_expr(expr: IR, names: set[str]) -> None:
    if isinstance(expr, Call):
        skip = {"heap_set", "heap_get", "delete", "tag", "__new", "new"}
        if expr.name in skip:
            return
        missing = sorted({arg.name for arg in expr.args if isinstance(arg, Var) and arg.name not in names})
        if missing:
            raise RuntimeError(
                f"destructuring call to {expr.name} must include output for argument(s): {', '.join(missing)}"
            )
    elif isinstance(expr, MethodCall):
        missing = sorted({arg.name for arg in expr.args if isinstance(arg, Var) and arg.name not in names})
        if missing:
            raise RuntimeError(
                f"destructuring method call to {expr.name} must include output for argument(s): {', '.join(missing)}"
            )


def lint_param_mutations_returned(
    stmts: List[IR], params: set[str], fn_name: str, *, is_method: bool, source: Optional[str] = None, pos: SourcePos
) -> None:
    mutated: set[str] = set()
    returned: set[str] = set()

    def visit(st: IR) -> None:
        if isinstance(st, Assign) and st.name in params:
            mutated.add(st.name)
        elif isinstance(st, FieldAssign) and isinstance(st.obj, Var) and st.obj.name in params:
            mutated.add(st.obj.name)
        elif isinstance(st, DestructAssign):
            mutated.update(nm for nm in st.names if nm in params)
        elif isinstance(st, Return):
            reads: Dict[str, int] = {}
            uses_in_expr(st.expr, reads)
            returned.update(n for n in reads if n in params)
        elif isinstance(st, If):
            for branch_stmt in st.then:
                visit(branch_stmt)
            for branch_stmt in st.els:
                visit(branch_stmt)
        elif isinstance(st, While):
            for body_stmt in st.body:
                visit(body_stmt)

    for st in stmts:
        visit(st)

    missing = sorted(mutated - returned)
    if missing:
        kind = "method" if is_method else "function"
        msg = f"mutated parameter(s) in {kind} {fn_name} must be returned: {', '.join(missing)}"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, pos, msg, code="E001", hint="Return the mutated parameters so callers receive the updates."),
            pos,
            code="E001",
            hint="Return the mutated parameters so callers receive the updates.",
        )


# ----- Runtime -----


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        super().__init__()
        self.value = value


@dataclass
class BaseView:
    obj: Dict[str, Any]
    class_name: str


@dataclass
class NamespaceRef:
    runtime: "Runtime"
    name: str


@dataclass
class SpawnHandle:
    thread: threading.Thread
    done: threading.Event
    result: Any = None
    error: Optional[BaseException] = None


class Runtime:
    def __init__(self, source: str):
        self._lock = threading.RLock()
        self.heap: Dict[int, List[Any]] = {}
        self.ptr_tags: Dict[int, str] = {}
        self.ops: Dict[Tuple[str, Optional[str], Optional[str]], Any] = {}
        self.methods: Dict[Tuple[str, str], MethodDef] = {}
        self.types: Dict[str, Dict[str, Any]] = {}
        self.next_ptr = 1
        self.output: List[str] = []
        self.functions: Dict[str, Fn] = {}
        self.native_functions: Dict[str, Callable[..., Any]] = {}
        self.error_messages: List[str] = []
        self.source = source

    @staticmethod
    def _qualify_name(name: str, namespace: Optional[str]) -> str:
        return f"{namespace}.{name}" if namespace else name

    def _record_error(
        self, msg: str, pos: Optional[SourcePos] = None, *, code: str = "E000", hint: Optional[str] = None
    ) -> None:
        formatted = format_error(self.source, pos, msg, code=code, hint=hint) if pos is not None else msg
        with self._lock:
            self.error_messages.append(formatted)

    def _error(
        self,
        msg: str,
        pos: SourcePos,
        *,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        candidates: Optional[List[str]] = None,
    ) -> TinyLangError:
        derived_code, derived_hint = _classify_error(msg, candidates)
        code = code or derived_code
        hint = hint or derived_hint
        formatted = format_error(self.source, pos, msg, code=code, hint=hint)
        self._record_error(msg, pos, code=code, hint=hint)
        return TinyLangError(formatted, pos, code=code, hint=hint)

    @property
    def error_message(self) -> Optional[str]:
        with self._lock:
            if not self.error_messages:
                return None
            return "; ".join(self.error_messages)

    # heap helpers
    def __new(self, n: int) -> int:
        if n < 0:
            raise RuntimeError("alloc error: negative size")
        with self._lock:
            p = self.next_ptr
            self.next_ptr += 1
            self.heap[p] = [0 for _ in range(int(n))]
            return p

    def delete(self, p: Any, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        try:
            ip = int(p)
            with self._lock:
                self.heap.pop(ip, None)
                self.ptr_tags.pop(ip, None)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def heap_get(self, p: Any, i: Any, *, pos: Optional[SourcePos] = None) -> Any:
        try:
            ip = int(p)
            idx = int(i)
        except Exception:
            self._record_error("heap access error: pointer or index is not numeric", pos)
            return None

        with self._lock:
            try:
                arr = self.heap[ip]
            except KeyError:
                self._record_error(f"heap access error: unknown pointer {ip}", pos)
                return None

            try:
                return arr[idx]
            except Exception:
                self._record_error(
                    f"heap access error: index {idx} out of range for pointer {ip}", pos
                )
                return None

    def heap_set(self, p: Any, i: Any, v: Any, *, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        try:
            with self._lock:
                self.heap[int(p)][int(i)] = v
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            self._record_error(str(e), pos)
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def tag(self, p: Any, typ: Any, *, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        try:
            with self._lock:
                self.ptr_tags[int(p)] = str(typ)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            self._record_error(str(e), pos)
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def __get_tag(self, v: Any) -> Optional[str]:
        if isinstance(v, dict) and "__tag__" in v:
            return v["__tag__"]
        try:
            iv = int(v)
            with self._lock:
                if iv in self.ptr_tags:
                    return self.ptr_tags[iv]
        except Exception:
            pass
        return None

    @staticmethod
    def _number_fields(val: Any) -> Optional[Dict[str, Any]]:
        if isinstance(val, dict) and val.get("__tag__") == "Number":
            return val.get("__fields__", {}).get("Number")
        return None

    @staticmethod
    def _make_number(value: Any, error: str) -> Dict[str, Any]:
        return {"__tag__": "Number", "__fields__": {"Number": {"value": value, "error": error}}}

    def _number_binop(self, op: str, a: Any, b: Any) -> Any:
        fields_a = self._number_fields(a)
        fields_b = self._number_fields(b)
        if fields_a is None or fields_b is None:
            return None

        val_a = fields_a.get("value", 0)
        val_b = fields_b.get("value", 0)
        err_a = fields_a.get("error", "normal") or "normal"
        err_b = fields_b.get("error", "normal") or "normal"

        def mk(err: str, value: Any = 0) -> Dict[str, Any]:
            return self._make_number(value, err)

        def overflow(v: float) -> Optional[str]:
            limit = 1e21
            if v > limit:
                return "plus_infinity"
            if v < -limit:
                return "minus_infinity"
            return None

        if op == "^":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a != "normal" or err_b != "normal":
                return mk("any_number")
            if not isinstance(val_b, (int, float)):
                return mk("any_number")
            if isinstance(val_b, float):
                if not val_b.is_integer():
                    return mk("any_number")
                val_b = int(val_b)
            try:
                res = val_a**val_b
            except Exception:
                return mk("any_number")
            ov = overflow(res)
            if ov:
                return mk(ov)
            rounded = False
            if isinstance(res, float):
                rounded = not res.is_integer()
                if not rounded:
                    res = int(res)
            return mk("rounded" if rounded else "normal", res)

        if op == "+":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a == "minus_infinity" and err_b == "normal" and val_b > 0:
                return mk("any_number")
            if err_b == "minus_infinity" and err_a == "normal" and val_a > 0:
                return mk("any_number")
            if err_a == "plus_infinity" or err_b == "plus_infinity":
                return mk("plus_infinity")
            if err_a == "minus_infinity" or err_b == "minus_infinity":
                return mk("minus_infinity")
            res = val_a + val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "-":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a == "plus_infinity" and err_b == "normal" and val_b > 0:
                return mk("any_number")
            if err_a == "plus_infinity" or err_b == "minus_infinity":
                return mk("plus_infinity")
            if err_a == "minus_infinity" or err_b == "plus_infinity":
                return mk("minus_infinity")
            res = val_a - val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "*":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a in {"plus_infinity", "minus_infinity"} and err_b in {"plus_infinity", "minus_infinity"}:
                sign = 1
                if err_a == "minus_infinity":
                    sign *= -1
                if err_b == "minus_infinity":
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            if err_a in {"plus_infinity", "minus_infinity"}:
                if val_b == 0:
                    return mk("any_number")
                sign = -1 if err_a == "minus_infinity" else 1
                if val_b < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            if err_b in {"plus_infinity", "minus_infinity"}:
                if val_a == 0:
                    return mk("any_number")
                sign = -1 if err_b == "minus_infinity" else 1
                if val_a < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            res = val_a * val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "/":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_b in {"plus_infinity", "minus_infinity"} and err_a == "normal":
                return mk("normal", 0)
            if err_b == "normal" and val_b == 0:
                if err_a == "plus_infinity":
                    return mk("plus_infinity")
                if err_a == "minus_infinity":
                    return mk("minus_infinity")
                if val_a > 0:
                    return mk("plus_infinity")
                if val_a < 0:
                    return mk("minus_infinity")
                return mk("any_number")
            if err_a in {"plus_infinity", "minus_infinity"}:
                if err_b in {"plus_infinity", "minus_infinity"}:
                    return mk("any_number")
                sign = -1 if err_a == "minus_infinity" else 1
                if err_b == "normal" and val_b < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            res = val_a / val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            rounded = False
            if isinstance(res, float):
                rounded = not res.is_integer()
                if not rounded:
                    res = int(res)
            return mk("rounded" if rounded else "normal", res)

        return None

    def _number_power(self, base: Any, exponent: Any) -> Any:
        fields_a = self._number_fields(base)
        fields_b = self._number_fields(exponent)
        if fields_a is None or fields_b is None:
            return None

        val_a = fields_a.get("value", 0)
        val_b = fields_b.get("value", 0)
        err_a = fields_a.get("error", "normal") or "normal"
        err_b = fields_b.get("error", "normal") or "normal"

        def mk(err: str, value: Any = 0) -> Dict[str, Any]:
            return self._make_number(value, err)

        def overflow(v: float) -> Optional[str]:
            limit = 1e21
            if v > limit:
                return "plus_infinity"
            if v < -limit:
                return "minus_infinity"
            return None

        if err_a == "any_number" or err_b == "any_number":
            return mk("any_number")
        if err_a != "normal" or err_b != "normal":
            return mk("any_number")
        try:
            res = val_a**val_b
        except Exception:
            return mk("any_number")
        ov = overflow(res)
        if ov:
            return mk(ov)
        rounded = False
        if isinstance(res, float):
            rounded = not res.is_integer()
            if not rounded:
                res = int(res)
        return mk("rounded" if rounded else "normal", res)

    def __binop(self, op: str, a: Any, b: Any) -> Any:
        ta = self.__get_tag(a)
        tb = self.__get_tag(b)
        num_res = self._number_binop(op, a, b)
        if num_res is not None:
            return num_res
        key = (op, ta, tb)
        with self._lock:
            impl = self.ops.get(key)
        if impl:
            return impl(a, b)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b
        if op == "^":
            if isinstance(b, float):
                if not b.is_integer():
                    raise RuntimeError("exponent for ^ must be an integer")
                b = int(b)
            elif not isinstance(b, int):
                raise RuntimeError("exponent for ^ must be an integer")
            return a**b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        raise RuntimeError(f"unsupported op {op}")

    def field_get(self, obj: Any, key: str, *, pos: Optional[SourcePos] = None) -> Any:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        if isinstance(target_obj, dict) and "__fields__" in target_obj:
            try:
                fmap = self._resolve_field_storage(
                    target_obj, key, owner_hint, target_obj["__tag__"], allow_write=False
                )
                return fmap[key]
            except Exception as err:  # noqa: BLE001
                self._record_error(str(err), pos)
                return None
        try:
            return target_obj[str(key)]
        except Exception:
            self._record_error(f"unknown field {key}", pos)
            return None

    def field_set(self, obj: Any, key: str, val: Any) -> None:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        if isinstance(target_obj, dict) and "__fields__" in target_obj:
            fmap = self._resolve_field_storage(target_obj, key, owner_hint, target_obj["__tag__"], allow_write=True)
            fmap[key] = val
            return
        target_obj[str(key)] = val

    def register_type(self, name: str, fields: List[Tuple[str, str]]) -> None:
        with self._lock:
            self.types[str(name)] = {"kind": "record", "fields": dict(fields)}

    def register_class(self, name: str, fields: List[Tuple[str, str]], bases: Optional[List[str]] = None) -> None:
        base_list = list(bases) if bases is not None else []
        with self._lock:
            existing = self.types.get(name)
            if existing:
                if existing.get("kind") != "class":
                    raise RuntimeError(f"type {name} already defined and is not a class")
                existing["fields"].update(dict(fields))
                if bases is not None:
                    existing["bases"] = base_list
                return
            self.types[str(name)] = {"kind": "class", "fields": dict(fields), "bases": base_list}

    def register_method(self, md: MethodDef) -> None:
        with self._lock:
            self.methods[(md.class_name, md.name)] = md

    def register_native(self, name: str, func: Callable[..., Any], namespace: Optional[str] = None) -> None:
        qualified = self._qualify_name(name, namespace)
        with self._lock:
            self.native_functions[qualified] = func

    def register_operator(self, opdef: OpDef, env: "Environment") -> None:
        def impl(a_val: Any, b_val: Any) -> Any:
            op_env = Environment(parent=env, namespace=env.namespace)
            op_env.values[opdef.a_name] = a_val
            op_env.values[opdef.b_name] = b_val
            res = self.eval_block(opdef.body, op_env, env.namespace)
            if isinstance(res, ReturnSignal):
                return res.value
            return res

        with self._lock:
            self.ops[(opdef.op, opdef.a_type, opdef.b_type)] = impl

    def class_mro(self, name: str) -> List[str]:
        with self._lock:
            info = self.types.get(name)
            if info is None or info.get("kind") != "class":
                raise RuntimeError(f"unknown class {name}")
            bases = list(info.get("bases", []))
        mro: List[str] = [name]
        for base in bases:
            with self._lock:
                if base not in self.types:
                    raise RuntimeError(f"unknown base class {base} for {name}")
            for ancestor in self.class_mro(base):
                if ancestor not in mro:
                    mro.append(ancestor)
        return mro

    @staticmethod
    def _split_field_name(fname: str) -> Tuple[Optional[str], str]:
        if "." in fname:
            owner, rest = fname.split(".", 1)
            return owner, rest
        return None, fname

    def instantiate_class(self, name: str, init: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            info = self.types.get(name)
            if info is None or info.get("kind") != "class":
                raise RuntimeError(f"unknown class {name}")
        mro = self.class_mro(name)
        obj: Dict[str, Any] = {"__tag__": name, "__fields__": {}}
        for cls in mro:
            with self._lock:
                finfo = self.types.get(cls)
                if finfo is None or finfo.get("kind") != "class":
                    raise RuntimeError(f"unknown class {cls}")
            obj["__fields__"][cls] = {fname: None for fname in finfo["fields"]}

        for raw_name, val in init.items():
            owner_hint, fname = self._split_field_name(raw_name)
            fmap = self._resolve_field_storage(obj, fname, owner_hint, name)
            fmap[fname] = val
        return obj

    def _resolve_function(self, name: str, env: "Environment") -> Tuple[Optional[str], Optional[Fn]]:
        with self._lock:
            fn = self.functions.get(name)
        if fn is not None:
            return name, fn
        if "." not in name and env.namespace:
            qualified = self._qualify_name(name, env.namespace)
            with self._lock:
                fn = self.functions.get(qualified)
            if fn is not None:
                return qualified, fn
        return None, None

    def _invoke_native(self, qualified_name: str, args: List[Any]) -> Tuple[bool, Any]:
        with self._lock:
            native = self.native_functions.get(qualified_name)
        if native is None:
            return False, None
        return True, native(*args)

    def _invoke_function(self, fn: Fn, args: List[Any]) -> Any:
        call_env = Environment(parent=None, namespace=fn.namespace)
        for pname, arg in zip(fn.params, args):
            call_env.values[pname] = arg
        res = self.eval_block(fn.body, call_env, fn.namespace)
        if isinstance(res, ReturnSignal):
            return res.value
        return res

    def _run_spawn(self, fn: Fn, args: List[Any], handle: SpawnHandle) -> None:
        try:
            handle.result = self._invoke_function(fn, args)
        except Exception as exc:  # noqa: BLE001
            handle.error = exc
        finally:
            handle.done.set()

    def join_handle(self, handle: Any) -> Any:
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("join expects a spawn handle")
        handle.done.wait()
        handle.thread.join()
        if handle.error:
            raise handle.error
        return handle.result

    def _resolve_field_storage(
        self,
        obj: Dict[str, Any],
        fname: str,
        owner_hint: Optional[str],
        current_class: str,
        *,
        allow_write: bool = True,
    ) -> Dict[str, Any]:
        if "__fields__" not in obj:
            raise RuntimeError("field access on non-class value")

        def lookup_mro(start_class: str) -> List[str]:
            return self.class_mro(start_class)

        mro = lookup_mro(owner_hint or current_class)
        matches: List[Tuple[str, Dict[str, Any]]] = []

        for cls in mro:
            fmap = obj["__fields__"].get(cls, {})
            if fname in fmap:
                matches.append((cls, fmap))

        if owner_hint:
            for cls, fmap in matches:
                if cls == owner_hint:
                    return fmap
            raise RuntimeError(f"unknown field {fname} for base class {owner_hint}")

        if matches:
            primary_class = current_class
            for cls, fmap in matches:
                if cls == primary_class:
                    return fmap

        if len(matches) == 1:
            return matches[0][1]
        if len(matches) > 1:
            action = "assign" if allow_write else "access"
            raise RuntimeError(
                f"ambiguous field {fname} during {action}; please qualify with a base class name"
            )
        raise RuntimeError(f"unknown field {fname} for class {current_class}")

    def find_method(self, start_class: str, name: str) -> Optional[MethodDef]:
        for cls in self.class_mro(start_class):
            with self._lock:
                md = self.methods.get((cls, name))
            if md:
                return md
        return None

    def call_method(self, obj: Any, name: str, args: List[Any]) -> Any:
        if isinstance(obj, NamespaceRef):
            qualified_name = self._qualify_name(name, obj.name)
            invoked, native_res = self._invoke_native(qualified_name, args)
            if invoked:
                return native_res
            fn = self.functions.get(qualified_name)
            if fn is None:
                raise RuntimeError(f"unknown function {qualified_name}")
            call_env = Environment(parent=None, namespace=fn.namespace)
            for pname, arg in zip(fn.params, args):
                call_env.values[pname] = arg
            res = self.eval_block(fn.body, call_env, fn.namespace)
            if isinstance(res, ReturnSignal):
                return res.value
            return res
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        start_class = obj.class_name if isinstance(obj, BaseView) else self.__get_tag(target_obj)
        cname = self.__get_tag(target_obj)
        if start_class is None or cname is None:
            raise RuntimeError("method call on untagged value")
        md = self.find_method(start_class, name)
        if md is None:
            raise RuntimeError(f"no method {name} for class {start_class}")
        env = Environment(parent=None)
        self_value: Any = target_obj
        if md.class_name != cname:
            self_value = BaseView(target_obj, md.class_name)
        env.values[md.params[0]] = self_value  # self
        for base in self.class_mro(cname)[1:]:
            env.values[base] = BaseView(target_obj, base)
        for pname, arg in zip(md.params[1:], args):
            env.values[pname] = arg
        res = self.eval_block(md.body, env)
        if isinstance(res, ReturnSignal):
            return res.value
        return res

    def type_field_type(self, tname: str, fname: str) -> Optional[str]:
        with self._lock:
            t = self.types.get(tname)
        if t is None:
            return None
        owner_hint, field_name = self._split_field_name(fname)
        if t.get("kind") == "class":
            targets: List[str] = []
            if owner_hint:
                targets.append(owner_hint)
            else:
                targets.append(tname)
                targets.extend(self.class_mro(tname)[1:])
            hits = []
            for cls in targets:
                info = self.types.get(cls)
                if info and field_name in info.get("fields", {}):
                    hits.append(info["fields"][field_name])
                    if owner_hint:
                        break
                    if cls == tname:
                        return info["fields"][field_name]
            if len(hits) == 1:
                return hits[0]
            return None
        return t["fields"].get(field_name)

    @staticmethod
    def format_value(val: Any) -> str:
        if isinstance(val, dict) and val.get("__tag__") == "Number":
            fields = val.get("__fields__", {}).get("Number", {})
            err = fields.get("error")
            if err in {"plus_infinity", "minus_infinity", "any_number"}:
                return str(err)
            if "value" in fields:
                value = fields.get("value")
                if err == "rounded":
                    return f"{value} (rounded)"
                return str(value)
        if isinstance(val, dict) and val.get("__tag__") == "NumberIntervall":
            fields = val.get("__fields__", {}).get("NumberIntervall", {})
            err = fields.get("error")
            if err in {"plus_infinity", "minus_infinity", "any_number"}:
                return str(err)
            if err == "upper_bound_is_plus_infinity":
                lower = fields.get("lower")
                return f"[{lower}, infinity]"
            if err == "lower_bound_is_minus_infinity":
                upper = fields.get("upper")
                return f"[-infinity, {upper}]"
            if err == "wrapped_interval":
                lower = fields.get("lower")
                upper = fields.get("upper")
                return f"[{lower}, {upper}]"
            if "lower" in fields and "upper" in fields:
                lower = fields.get("lower")
                upper = fields.get("upper")
                center = (lower + upper) / 2
                radius = (upper - lower) / 2
                return f"{center} +/- {radius}"
        if isinstance(val, bool):
            return "true" if val else "false"
        return str(val)

    @staticmethod
    def _is_truthy(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, str):
            return len(val) > 0
        try:
            return bool(val)
        except Exception:
            return True

    # ----- Evaluation -----
    def eval_block(self, stmts: List[IR], env: "Environment", namespace: Optional[str] = None) -> Any:
        for st in stmts:
            res = self.eval_stmt(st, env, namespace)
            if isinstance(res, ReturnSignal):
                return res
        return None

    def eval_stmt(self, s: IR, env: "Environment", namespace: Optional[str] = None) -> Any:
        try:
            if isinstance(s, Let):
                env.values[s.name] = self.eval_expr(s.expr, env)
            elif isinstance(s, Assign):
                if env.contains(s.name):
                    env.set(s.name, self.eval_expr(s.expr, env))
                else:
                    env.values[s.name] = self.eval_expr(s.expr, env)
            elif isinstance(s, FieldAssign):
                obj = self.eval_expr(s.obj, env)
                val = self.eval_expr(s.expr, env)
                self.field_set(obj, s.name, val)
            elif isinstance(s, Print):
                vals = [self.eval_expr(expr, env) for expr in s.exprs]
                text = " ".join(self.format_value(v) for v in vals)
                with self._lock:
                    self.output.append(f"{text}\n")
            elif isinstance(s, If):
                cond = self.eval_expr(s.cond, env)
                branch = s.then if self._is_truthy(cond) else s.els
                res = self.eval_block(branch, env, namespace)
                if isinstance(res, ReturnSignal):
                    return res
            elif isinstance(s, While):
                while self._is_truthy(self.eval_expr(s.cond, env)):
                    res = self.eval_block(s.body, env, namespace)
                    if isinstance(res, ReturnSignal):
                        return res
            elif isinstance(s, Namespace):
                qualified = self._qualify_name(s.name, namespace)
                child_env = Environment(parent=env, namespace=qualified)
                env.values[s.name] = NamespaceRef(self, qualified)
                self.eval_block(s.body, child_env, qualified)
            elif isinstance(s, Fn):
                s.namespace = namespace
                fn_name = self._qualify_name(s.name, namespace)
                with self._lock:
                    self.functions[fn_name] = s
            elif isinstance(s, Return):
                return ReturnSignal(self.eval_expr(s.expr, env))
            elif isinstance(s, CallStmt):
                allowed = s.name in {"heap_set", "heap_get", "delete", "tag", "join"}
                if not allowed:
                    raise RuntimeError(
                        f"call with return value must be bound; bare call statements are not allowed (offending call: {s.name}())"
                    )
                self.eval_expr(Call(s.name, s.args, pos=s.pos), env)
            elif isinstance(s, OpDef):
                self.register_operator(s, env)
            elif isinstance(s, DestructAssign):
                val = self.eval_expr(s.expr, env)
                for nm in s.names:
                    env.values[nm] = val[str(nm)]
            elif isinstance(s, TypeDef):
                # type and class share same registration
                self.register_type(s.name, s.fields)
            elif isinstance(s, ClassDef):
                self.register_class(s.name, s.fields, s.bases)
                for m in s.methods:
                    self.register_method(m)
            elif isinstance(s, MethodDef):
                self.register_class(s.class_name, []) if s.class_name not in self.types else None
                self.register_method(s)
            else:
                raise RuntimeError(f"unknown statement {s}")
            return None
        except (ReturnSignal, TinyLangError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._error(str(exc), getattr(s, "pos", SourcePos.origin())) from exc

    def eval_expr(self, e: IR, env: "Environment") -> Any:
        try:
            if isinstance(e, Num):
                return float(e.txt) if "." in e.txt else int(e.txt)
            if isinstance(e, Str):
                return e.txt
            if isinstance(e, Bool):
                return e.value
            if isinstance(e, Var):
                if e.name == "errorMessage":
                    return self.error_message
                if env.contains(e.name):
                    return env.get(e.name)
                # Allow tag identifiers such as `Arr` to be passed through as plain
                # strings when they look like type names, while still flagging
                # genuinely undefined variables used in expressions.
                if e.name and e.name[0].isupper():
                    return e.name
                raise self._error(
                    f"unknown variable {e.name}",
                    e.pos,
                    candidates=env.all_names(),
                )
            if isinstance(e, Call):
                if e.name == "__type_field_type":
                    return self.type_field_type(str(self.eval_expr(e.args[0], env)), str(self.eval_expr(e.args[1], env)))
                if e.name == "__new":
                    return self.__new(int(self.eval_expr(e.args[0], env)))
                if e.name == "new":
                    return self.__new(int(self.eval_expr(e.args[0], env)))
                if e.name == "heap_get":
                    return self.heap_get(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env), pos=e.pos)
                if e.name == "heap_set":
                    return self.heap_set(
                        self.eval_expr(e.args[0], env),
                        self.eval_expr(e.args[1], env),
                        self.eval_expr(e.args[2], env),
                        pos=e.pos,
                    )
                if e.name == "delete":
                    return self.delete(self.eval_expr(e.args[0], env), pos=e.pos)
                if e.name == "tag":
                    return self.tag(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env), pos=e.pos)
                if e.name == "join":
                    if len(e.args) != 1:
                        raise RuntimeError("join expects 1 argument")
                    return self.join_handle(self.eval_expr(e.args[0], env))
                if e.name == "len":
                    if len(e.args) != 1:
                        raise RuntimeError("len expects 1 argument")
                    target = self.eval_expr(e.args[0], env)
                    try:
                        if isinstance(target, int) and target in self.heap:
                            return len(self.heap[target])
                        return len(target)  # type: ignore[arg-type]
                    except Exception:
                        raise RuntimeError("len expects a sized value")
                if e.name == "__nextafter":
                    return math.nextafter(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env))
                if e.name == "power":
                    base = self.eval_expr(e.args[0], env)
                    exp = self.eval_expr(e.args[1], env)
                    number_res = self._number_power(base, exp)
                    if number_res is not None:
                        return number_res
                    res = math.pow(base, exp)
                    if isinstance(res, float) and res.is_integer():
                        res = int(res)
                    return res
                arg_values = [self.eval_expr(arg_expr, env) for arg_expr in e.args]
                invoked, native_res = self._invoke_native(e.name, arg_values)
                if invoked:
                    return native_res
                resolved_name, fn = self._resolve_function(e.name, env)
                if fn is not None:
                    return self._invoke_function(fn, arg_values)
                raise RuntimeError(f"unknown function {e.name}")
            if isinstance(e, Spawn):
                resolved_name, fn = self._resolve_function(e.name, env)
                if fn is None:
                    raise RuntimeError(f"unknown function {e.name}")
                arg_values = [self.eval_expr(arg, env) for arg in e.args]

                done = threading.Event()

                def run_task() -> None:
                    self._run_spawn(fn, arg_values, handle)

                handle = SpawnHandle(thread=threading.Thread(target=run_task), done=done)
                handle.thread.start()
                return handle
            if isinstance(e, New):
                return self.__new(int(self.eval_expr(e.size, env)))
            if isinstance(e, NewLit):
                p = self.__new(len(e.items))
                for idx, item in enumerate(e.items):
                    self.heap_set(p, idx, self.eval_expr(item, env), pos=e.pos)
                return p
            if isinstance(e, Bin):
                if e.op == "and":
                    left = self.eval_expr(e.a, env)
                    if not self._is_truthy(left):
                        return False
                    return bool(self._is_truthy(self.eval_expr(e.b, env)))
                if e.op == "or":
                    left = self.eval_expr(e.a, env)
                    if self._is_truthy(left):
                        return True
                    return bool(self._is_truthy(self.eval_expr(e.b, env)))
                if e.op == "not":
                    return not self._is_truthy(self.eval_expr(e.b, env))
                return self.__binop(e.op, self.eval_expr(e.a, env), self.eval_expr(e.b, env))
            if isinstance(e, ObjLit):
                obj: Dict[str, Any] = {"__tag__": "Struct"}
                for k, v in e.fields:
                    obj[k] = self.eval_expr(v, env)
                return obj
            if isinstance(e, Field):
                obj = self.eval_expr(e.obj, env)
                return self.field_get(obj, e.name, pos=e.pos)
            if isinstance(e, MethodCall):
                obj = self.eval_expr(e.obj, env)
                args = [self.eval_expr(a, env) for a in e.args]
                return self.call_method(obj, e.name, args)
            if isinstance(e, ClassNew):
                init = {k: self.eval_expr(v, env) for k, v in e.init}
                self.register_class(e.name, []) if e.name not in self.types else None
                return self.instantiate_class(e.name, init)
            raise RuntimeError(f"unknown expr {e}")
        except TinyLangError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._error(str(exc), getattr(e, "pos", SourcePos.origin())) from exc


class Environment:
    def __init__(self, parent: Optional["Environment"], namespace: Optional[str] = None):
        self.parent = parent
        self.namespace = namespace
        self.values: Dict[str, Any] = {}

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise RuntimeError(f"unknown variable {name}")

    def set(self, name: str, value: Any) -> None:
        if name in self.values:
            self.values[name] = value
        elif self.parent is not None:
            self.parent.set(name, value)
        else:
            self.values[name] = value

    def contains(self, name: str) -> bool:
        if name in self.values:
            return True
        return self.parent.contains(name) if self.parent else False

    def all_names(self) -> List[str]:
        names = list(self.values.keys())
        if self.parent:
            names.extend(self.parent.all_names())
        return names


# ----- Public API -----


def compile_and_run(src: str) -> str:
    parser = Parser(Lexer(src), src)
    stmts = parser.parse()
    runtime = Runtime(src)

    # lint functions + top level locals
    lint_destruct_call_outputs(stmts)
    lint_no_consecutive_definitions(stmts)
    lint_locals_used(stmts, src)
    def lint_nested(block: List[IR]) -> None:
        for st in block:
            if isinstance(st, Fn):
                lint_fn_params_used(st, src)
            if isinstance(st, MethodDef):
                lint_method_params_used(st, src)
            if isinstance(st, ClassDef):
                for m in st.methods:
                    lint_method_params_used(m, src)
            if isinstance(st, Namespace):
                lint_nested(st.body)

    lint_nested(stmts)

    env = Environment(parent=None, namespace=None)
    register_stdlib(runtime, env)
    for st in stmts:
        runtime.eval_stmt(st, env)
    return "".join(runtime.output)


def run_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return compile_and_run(f.read())


def _format_error_for_source(source: str, err: TinyLangError) -> str:
    if "(line " in err.message:
        return err.message
    return format_error(source, err.pos, err.message)


def _is_incomplete_source(src: str) -> bool:
    balances = {"(": 0, "[": 0, "{": 0}
    in_string = False
    escape = False
    for ch in src:
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in balances:
            balances[ch] += 1
        elif ch in (")", "]", "}"):
            match = {"}": "{", ")": "(", "]": "["}[ch]
            if balances[match] > 0:
                balances[match] -= 1
    return in_string or any(v > 0 for v in balances.values())


def _configure_readline(history_path: Path) -> None:
    if readline is None:
        return
    readline.set_completer_delims(" \t\n")
    completions = sorted(KEYWORDS | BUILTINS)

    def completer(text: str, state: int) -> Optional[str]:
        matches = [word for word in completions if word.startswith(text)]
        return matches[state] if state < len(matches) else None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    try:
        readline.read_history_file(history_path)
    except FileNotFoundError:
        history_path.touch()
    readline.set_history_length(1000)


def _save_history(history_path: Path) -> None:
    if readline is None:
        return
    try:
        readline.write_history_file(history_path)
    except FileNotFoundError:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.touch()
        readline.write_history_file(history_path)


def _read_repl_command(read_fn) -> Optional[str]:
    buffer: List[str] = []
    while True:
        prompt = "tiny> " if not buffer else "...> "
        try:
            line = read_fn(prompt)
        except EOFError:
            return None if not buffer else "\n".join(buffer)
        buffer.append(line)
        src = "\n".join(buffer)
        if _is_incomplete_source(src):
            continue
        return src


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a TinyLanguage program from a file")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "-e",
        "--eval",
        metavar="SRC",
        help="Execute the provided TinyLanguage source code string",
    )
    mode_group.add_argument("--repl", action="store_true", help="Start a TinyLanguage REPL")
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the TinyLanguage source file to execute",
    )
    args = parser.parse_args(argv)

    if args.eval is not None:
        try:
            output = compile_and_run(args.eval)
            print(output, end="")
            return 0
        except TinyLangError as err:
            print(_format_error_for_source(args.eval, err), file=sys.stderr)
            return 1
        except Exception as exc:  # pragma: no cover - unexpected errors
            print(str(exc), file=sys.stderr)
            return 1

    if args.repl:
        history_path = Path.home() / ".tiny_language_history"
        _configure_readline(history_path)
        try:
            while True:
                src = _read_repl_command(input)
                if src is None:
                    print()
                    break
                if not src.strip():
                    continue
                try:
                    output = compile_and_run(src)
                    if output:
                        print(output, end="")
                except TinyLangError as err:
                    print(_format_error_for_source(src, err), file=sys.stderr)
                except Exception as exc:  # pragma: no cover - unexpected errors
                    print(str(exc), file=sys.stderr)
        finally:
            _save_history(history_path)
        return 0

    if not args.file:
        parser.error("the following arguments are required: file")

    output = run_file(args.file)
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["compile_and_run", "run_file", "main"]
