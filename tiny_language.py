from __future__ import annotations

import argparse
import difflib
import importlib.util
import math
import os
import sys
import threading
from pathlib import Path
try:  # pragma: no cover - platform-specific imports
    import termios  # type: ignore
    import tty  # type: ignore
    _HAS_TERMIOS = True
except ImportError:  # pragma: no cover - Windows and other platforms without termios
    termios = None  # type: ignore
    tty = None  # type: ignore
    _HAS_TERMIOS = False

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from stdlib import register_stdlib

class _FallbackReadline:
    """Minimal in-memory readline replacement for platforms without it."""

    def __init__(self) -> None:
        self._history: List[str] = []
        self._completions = None
        self._history_length = 1000
        self._history_index: Optional[int] = None

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
        self._history_index = None

    def get_history_item(self, index: int) -> Optional[str]:
        idx = index - 1
        if 0 <= idx < len(self._history):
            return self._history[idx]
        return None

    def get_current_history_length(self) -> int:  # pragma: no cover - trivial
        return len(self._history)

    # Interactive helpers
    def _collect_matches(self, text: str) -> List[str]:
        if self._completions is None:
            return []
        matches: List[str] = []
        idx = 0
        while True:
            candidate = self._completions(text, idx)
            if candidate is None:
                break
            matches.append(candidate)
            idx += 1
        return matches

    def _redraw(self, prompt: str, buffer: List[str], last_len: int) -> int:
        sys.stdout.write("\r")
        rendered = prompt + "".join(buffer)
        sys.stdout.write(rendered)
        if last_len > len(buffer):
            sys.stdout.write(" " * (last_len - len(buffer)))
        sys.stdout.write("\r")
        sys.stdout.write(prompt + "".join(buffer))
        sys.stdout.flush()
        return len(buffer)

    def _reverse_search(self, prompt: str, fd: int) -> Optional[str]:
        if not _HAS_TERMIOS:
            return None
        sys.stdout.write("\n(reverse-search): ")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, self._old_settings)
        try:
            query = sys.stdin.readline().rstrip("\n")
        finally:
            tty.setraw(fd)
        if not query:
            return None
        for entry in reversed(self._history):
            if query in entry:
                return entry
        return None

    def readline(self, prompt: str = "") -> str:
        if not _HAS_TERMIOS:
            line = input(prompt)
            if line:
                self.add_history(line)
            return line
        fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(fd)
        buffer: List[str] = []
        last_len = 0
        self._history_index = None

        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\n", "\r"):
                    sys.stdout.write("\n")
                    line = "".join(buffer)
                    if line:
                        self.add_history(line)
                    return line
                if ch == "\x7f":  # Backspace
                    if buffer:
                        buffer.pop()
                        last_len = self._redraw(prompt, buffer, last_len)
                    continue
                if ch == "\t":  # Tab completion
                    prefix = "".join(buffer)
                    last_word = prefix.split()[-1] if prefix else ""
                    matches = self._collect_matches(last_word)
                    if not matches:
                        continue
                    if len(matches) == 1:
                        completed = matches[0]
                    else:
                        shared_prefix = last_word
                        for idx in range(len(last_word), len(max(matches, key=len)) + 1):
                            candidates = {m[:idx] for m in matches if len(m) >= idx}
                            if len(candidates) == 1:
                                shared_prefix = candidates.pop()
                            else:
                                break
                        completed = shared_prefix
                        sys.stdout.write("\n" + "  ".join(sorted(matches)) + "\n")
                    if last_word:
                        buffer = buffer[: len(prefix) - len(last_word)] + list(completed)
                    else:
                        buffer = list(completed)
                    last_len = self._redraw(prompt, buffer, last_len)
                    continue
                if ch == "\x12":  # Ctrl+R reverse search
                    match = self._reverse_search(prompt, fd)
                    if match is not None:
                        buffer = list(match)
                        last_len = self._redraw(prompt, buffer, last_len)
                    else:
                        last_len = self._redraw(prompt, buffer, last_len)
                    continue
                if ch == "\x1b":  # Escape sequences (arrow keys)
                    seq = sys.stdin.read(2)
                    if seq == "[A":  # Up
                        if self._history:
                            if self._history_index is None:
                                self._history_index = len(self._history) - 1
                            elif self._history_index > 0:
                                self._history_index -= 1
                            buffer = list(self._history[self._history_index])
                            last_len = self._redraw(prompt, buffer, last_len)
                    elif seq == "[B":  # Down
                        if self._history_index is not None:
                            if self._history_index < len(self._history) - 1:
                                self._history_index += 1
                                buffer = list(self._history[self._history_index])
                            else:
                                self._history_index = None
                                buffer = []
                            last_len = self._redraw(prompt, buffer, last_len)
                    continue
                buffer.append(ch)
                last_len = self._redraw(prompt, buffer, last_len)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_settings)


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


@dataclass(frozen=True)
class StackFrame:
    name: str
    namespace: Optional[str]
    pos: SourcePos

    @property
    def qualified_name(self) -> str:
        return f"{self.namespace}.{self.name}" if self.namespace else self.name


@dataclass
class TinyLangError(Exception):
    message: str
    pos: SourcePos = field(default_factory=SourcePos.origin)
    code: str = "E000"
    hint: Optional[str] = None
    stack: Tuple[StackFrame, ...] = field(default_factory=tuple)

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
    if "exponent for ^ must be an integer" in lower_msg:
        return "E004", "Use an integer exponent (cast with `int(...)` if necessary) when using the ^ operator."
    if "len expects a sized value" in lower_msg:
        return "E005", "Pass a list, string, heap pointer, or other sized value to `len`."
    if "destructuring call" in lower_msg and "must include output" in lower_msg:
        return "E006", "Add the missing binding(s) to the destructuring pattern so each referenced argument is captured."
    if "type mismatch" in lower_msg:
        return "E009", "Adjust the annotation or the provided value so they agree."
    if "not all paths" in lower_msg and "return" in lower_msg:
        return "E010", "Add return statements for every branch or supply a default return value."
    return "E000", None

# ----- Lexer -----

KEYWORDS = {
    "define",
    "print",
    "if",
    "else",
    "while",
    "fn",
    "import",
    "return",
    "operator",
    "new",
    "type",
    "class",
    "namespace",
    "as",
    "spawn",
    "true",
    "false",
    "and",
    "or",
    "not",
    "Null",
    "try",
    "catch",
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
class TryCatch(IR):
    body: List[IR]
    err_name: Optional[str]
    handler: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Param:
    name: str
    type: Optional[str] = None


@dataclass
class Fn(IR):
    name: str
    params: List[Param]
    body: List[IR]
    namespace: Optional[str] = None
    return_type: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodDef(IR):
    class_name: str
    name: str
    params: List[Param]
    body: List[IR]
    return_type: Optional[str] = None
    namespace: Optional[str] = None
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
class Import(IR):
    module: str
    alias: Optional[str] = None
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
class Null(IR):
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
        if self.tok.kind == "KW" and self.tok.text == "try":
            kw = self._eat("KW", "try")
            body = self.parse_block()
            self._eat("KW", "catch")
            err_name = None
            if self._accept("SYM", "("):
                err_name = self._eat("NAME").text
                self._eat("SYM", ")")
            else:
                err_name = self._eat("NAME").text
            handler = self.parse_block()
            return TryCatch(body, err_name, handler, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "import":
            kw = self._eat("KW", "import")
            module = self.parse_module_path()
            alias: Optional[str] = None
            if self.tok.kind == "KW" and self.tok.text == "as":
                self._eat("KW", "as")
                alias = self._eat("NAME").text
            self._eat("SYM", ";")
            return Import(module, alias, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "namespace":
            kw = self._eat("KW", "namespace")
            name = self.parse_qualified_name()
            body = self.parse_block()
            return Namespace(name, body, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "fn":
            kw = self._eat("KW", "fn")
            name_tok = self._eat("NAME")
            params = self.parse_param_list()
            return_type = None
            if self._accept("OP", "-"):
                self._eat("OP", ">")
                return_type = self._eat_name_or_kw().text
            body = self.parse_block()
            return Fn(name_tok.text, params, body, return_type=return_type, pos=kw.pos)
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
                    return_type = None
                    if self._accept("OP", "-"):
                        self._eat("OP", ">")
                        return_type = self._eat_name_or_kw().text
                    body = self.parse_block()
                    methods.append(
                        MethodDef(cname_tok.text, mname_tok.text, params, body, return_type=return_type, pos=mname_tok.pos)
                    )
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

    def parse_param(self) -> Param:
        name_tok = self._eat("NAME")
        annotation = None
        if self._accept("SYM", ":"):
            annotation = self._eat_name_or_kw().text
        return Param(name_tok.text, annotation)

    def parse_param_list(self) -> List[Param]:
        self._eat("SYM", "(")
        params: List[Param] = []
        if not (self.tok.kind == "SYM" and self.tok.text == ")"):
            params.append(self.parse_param())
            while self._accept("SYM", ","):
                params.append(self.parse_param())
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
        if self.tok.kind == "KW" and self.tok.text == "Null":
            kw = self._eat("KW")
            return Null(pos=kw.pos)
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

    def parse_module_path(self) -> str:
        prefix = ""
        while self._accept("SYM", "."):
            prefix += "."
        if self.tok.kind != "NAME":
            raise self._error("expected NAME", self.tok.pos)
        parts = [self._eat("NAME").text]
        while self._accept("SYM", "."):
            parts.append(self._eat("NAME").text)
        return prefix + ".".join(parts)

    def parse_qualified_name(self) -> str:
        parts = [self._eat("NAME").text]
        while self._accept("SYM", "."):
            parts.append(self._eat("NAME").text)
        return ".".join(parts)


# ----- Linter -----


def _param_names(params: List[Param]) -> List[str]:
    return [p.name for p in params]


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
    elif isinstance(s, TryCatch):
        for t in s.body:
            lint_stmt_reads(t, reads)
        handler_reads: Dict[str, int] = {}
        for t in s.handler:
            lint_stmt_reads(t, handler_reads)
        if s.err_name:
            # Mark the catch binding as referenced if it is consumed inside the handler
            if handler_reads.get(s.err_name, 0) == 0:
                handler_reads[s.err_name] = 0
        for name, count in handler_reads.items():
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, Return):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, OpDef):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp)
        miss = []
        if not s.a_name.startswith("_") and tmp.get(s.a_name, 0) == 0:
            miss.append(s.a_name)
        if not s.b_name.startswith("_") and tmp.get(s.b_name, 0) == 0:
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
        param_names = _param_names(s.params)
        miss = [p for p in param_names if not p.startswith("_") and tmp.get(p, 0) == 0]
        if miss:
            raise RuntimeError(
                f"unused parameter(s) in method {s.class_name}.{s.name}: {', '.join(miss)}"
            )
        for name, count in tmp.items():
            if name in set(param_names):
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, Fn):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp)
        param_names = _param_names(s.params)
        for name, count in tmp.items():
            if name in set(param_names):
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, ClassDef):
        for m in s.methods:
            lint_stmt_reads(m, reads)
    elif isinstance(s, Namespace):
        for t in s.body:
            lint_stmt_reads(t, reads)
    elif isinstance(s, CallStmt):
        for arg in s.args:
            uses_in_expr(arg, reads)


def lint_fn_params_used(fn: Fn, source: Optional[str] = None) -> None:
    reads: Dict[str, int] = {}
    for st in fn.body:
        lint_stmt_reads(st, reads)
    param_names = _param_names(fn.params)
    unused = [p for p in param_names if not p.startswith("_") and reads.get(p, 0) == 0]
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
    lint_param_mutations_returned(fn.body, set(param_names), fn.name, is_method=False, source=source, pos=fn.pos)
    lint_destruct_call_outputs(fn.body, source)
    lint_return_signatures(fn.body, fn.name, is_method=False, source=source, pos=fn.pos)
    lint_return_exhaustiveness(
        fn.body, fn.name, expected_return=fn.return_type, is_method=False, source=source, pos=fn.pos
    )
    lint_locals_used(fn.body, source)


def lint_method_params_used(md: MethodDef, source: Optional[str] = None) -> None:
    reads: Dict[str, int] = {}
    for st in md.body:
        lint_stmt_reads(st, reads)
    param_names = _param_names(md.params)
    unused = [p for p in param_names if not p.startswith("_") and reads.get(p, 0) == 0]
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
        md.body, set(param_names), f"{md.class_name}.{md.name}", is_method=True, source=source, pos=md.pos
    )
    lint_destruct_call_outputs(md.body, source)
    lint_return_signatures(md.body, f"{md.class_name}.{md.name}", is_method=True, source=source, pos=md.pos)
    lint_return_exhaustiveness(
        md.body,
        f"{md.class_name}.{md.name}",
        expected_return=md.return_type,
        is_method=True,
        source=source,
        pos=md.pos,
    )
    lint_locals_used(md.body, source)


def lint_locals_used(stmts: List[IR], source: Optional[str] = None) -> None:
    defs: Dict[str, SourcePos] = {}
    uses: Dict[str, int] = {}

    def collect_defs(block: List[IR]) -> None:
        for idx, s in enumerate(block):
            if isinstance(s, Let):
                defs[s.name] = s.pos
            elif isinstance(s, Import):
                defs[_import_binding_name(s.module, s.alias)] = s.pos
            elif isinstance(s, DestructAssign):
                for nm in s.names:
                    defs[nm] = s.pos
            elif isinstance(s, TryCatch):
                collect_defs(s.body)
                if s.err_name:
                    defs[s.err_name] = s.pos
                collect_defs(s.handler)
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
    unused = [n for n in defs if not n.startswith("_") and uses.get(n, 0) == 0]
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


def _collect_function_signatures(stmts: List[IR], prefix: str = "") -> Dict[str, Optional[str]]:
    sigs: Dict[str, Optional[str]] = {}

    def qualify(name: str) -> str:
        return f"{prefix}.{name}" if prefix else name

    for st in stmts:
        if isinstance(st, Fn):
            sigs[qualify(st.name)] = st.return_type
        elif isinstance(st, Namespace):
            nested_prefix = qualify(st.name)
            sigs.update(_collect_function_signatures(st.body, prefix=nested_prefix))
    return sigs


def lint_bare_call_results(
    stmts: List[IR], signatures: Dict[str, Optional[str]], source: Optional[str] = None
) -> None:
    disallowed: set[str] = {name for name, ret in signatures.items() if ret not in {None, "Null"}}

    def visit(block: List[IR]) -> None:
        for st in block:
            if isinstance(st, CallStmt):
                if st.name in disallowed:
                    hint = "Assign the return value or explicitly acknowledge it with `_ = ...;`."
                    msg = f"call to {st.name} returns a value that is ignored"
                    if source is None:
                        raise RuntimeError(msg)
                    raise TinyLangError(
                        format_error(source, st.pos, msg, code="E011", hint=hint),
                        st.pos,
                        code="E011",
                        hint=hint,
                    )
            if isinstance(st, If):
                visit(st.then)
                visit(st.els)
            elif isinstance(st, While):
                visit(st.body)
            elif isinstance(st, TryCatch):
                visit(st.body)
                visit(st.handler)
            elif isinstance(st, Namespace):
                visit(st.body)
            elif isinstance(st, ClassDef):
                for method in st.methods:
                    visit(method.body)

    visit(stmts)


def lint_import_style(stmts: List[IR], source: Optional[str] = None) -> None:
    imports: List[Import] = []

    for st in stmts:
        if isinstance(st, Import):
            imports.append(st)
        else:
            break

    ordered = sorted(imports, key=lambda imp: (imp.module, imp.alias or ""))
    if imports and [(imp.module, imp.alias) for imp in imports] != [(imp.module, imp.alias) for imp in ordered]:
        first_misordered = imports[0]
        hint = "Sort the leading import block alphabetically to keep module headers consistent."
        msg = "imports are not sorted alphabetically"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, first_misordered.pos, msg, code="E012", hint=hint),
            first_misordered.pos,
            code="E012",
            hint=hint,
        )

    for st in stmts:
        if isinstance(st, Namespace):
            lint_import_style(st.body, source)


def lint_destruct_call_outputs(stmts: List[IR], source: Optional[str] = None) -> None:
    for st in stmts:
        lint_destruct_call_outputs_stmt(st, source)


def _return_signature(expr: IR) -> Tuple[str, ...]:
    if isinstance(expr, ObjLit):
        return tuple(name for name, _ in expr.fields)
    if isinstance(expr, NewLit):
        return tuple(str(i) for i in range(len(expr.items)))
    return ("<scalar>",)


def _format_signature(sig: Tuple[str, ...]) -> str:
    if sig == ("<scalar>",):
        return "single value"
    return "{" + ", ".join(sig) + "}"


def _block_guarantees_return(stmts: List[IR]) -> bool:
    for st in stmts:
        if isinstance(st, Return):
            return True
        if isinstance(st, If):
            if _block_guarantees_return(st.then) and _block_guarantees_return(st.els):
                return True
        if isinstance(st, TryCatch):
            if _block_guarantees_return(st.body) and _block_guarantees_return(st.handler):
                return True
        elif isinstance(st, While):
            continue
        elif isinstance(st, (Fn, MethodDef, ClassDef, Namespace)):
            continue
    return False


def lint_return_signatures(
    stmts: List[IR],
    fn_name: str,
    *,
    is_method: bool,
    source: Optional[str] = None,
    pos: SourcePos,
) -> None:
    expected: Optional[Tuple[str, ...]] = None
    hint = "Ensure every return statement uses the same tuple/record structure (fields and order)."

    def visit(block: List[IR]) -> None:
        nonlocal expected
        for st in block:
            if isinstance(st, Return):
                sig = _return_signature(st.expr)
                if expected is None:
                    expected = sig
                elif sig != expected:
                    kind = "method" if is_method else "function"
                    msg = (
                        f"inconsistent return signature in {kind} {fn_name}: "
                        f"expected {_format_signature(expected)} but found {_format_signature(sig)}"
                    )
                    if source is None:
                        raise RuntimeError(msg)
                    raise TinyLangError(format_error(source, st.pos, msg, code="E007", hint=hint), st.pos, code="E007", hint=hint)
            elif isinstance(st, If):
                visit(st.then)
                visit(st.els)
            elif isinstance(st, While):
                visit(st.body)
            elif isinstance(st, TryCatch):
                visit(st.body)
                visit(st.handler)

    visit(stmts)


def lint_return_exhaustiveness(
    stmts: List[IR],
    fn_name: str,
    *,
    expected_return: Optional[str],
    is_method: bool,
    source: Optional[str],
    pos: SourcePos,
) -> None:
    if expected_return is None:
        return
    if _block_guarantees_return(stmts):
        return
    kind = "method" if is_method else "function"
    msg = f"not all paths in {kind} {fn_name} return a value for annotated type {expected_return}"
    if source is None:
        raise RuntimeError(msg)
    raise TinyLangError(
        format_error(
            source,
            pos,
            msg,
            code="E010",
            hint="Add return statements for every branch or provide a default return to satisfy the annotation.",
        ),
        pos,
        code="E010",
        hint="Add return statements for every branch or provide a default return to satisfy the annotation.",
    )


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
            if isinstance(st, TryCatch):
                lint_no_consecutive_definitions(st.body)
                lint_no_consecutive_definitions(st.handler)
                prev = None
                continue

            current: Optional[str] = None
            if isinstance(st, Let):
                current = st.name

            if current is not None and prev == current:
                raise RuntimeError(f"variable {current} defined twice in a row")

            prev = current if current is not None else None

    check_block(stmts)


def lint_destruct_call_outputs_stmt(st: IR, source: Optional[str]) -> None:
    if isinstance(st, DestructAssign):
        check_destruct_call_expr(st.expr, set(st.names), source=source, pos=st.pos)
    elif isinstance(st, If):
        lint_destruct_call_outputs(st.then, source)
        lint_destruct_call_outputs(st.els, source)
    elif isinstance(st, While):
        lint_destruct_call_outputs(st.body, source)
    elif isinstance(st, Fn):
        lint_destruct_call_outputs(st.body, source)
    elif isinstance(st, MethodDef):
        lint_destruct_call_outputs(st.body, source)
    elif isinstance(st, ClassDef):
        for m in st.methods:
            lint_destruct_call_outputs_stmt(m, source)
    elif isinstance(st, Namespace):
        lint_destruct_call_outputs(st.body, source)
    elif isinstance(st, TryCatch):
        lint_destruct_call_outputs(st.body, source)
        lint_destruct_call_outputs(st.handler, source)


def check_destruct_call_expr(expr: IR, names: set[str], *, source: Optional[str], pos: SourcePos) -> None:
    if isinstance(expr, Call):
        skip = {"heap_set", "heap_get", "delete", "tag", "__new", "new"}
        if expr.name in skip:
            return
        missing = sorted({arg.name for arg in expr.args if isinstance(arg, Var) and arg.name not in names})
        if missing:
            msg = f"destructuring call to {expr.name} must include output for argument(s): {', '.join(missing)}"
            if source:
                raise TinyLangError(
                    format_error(
                        source,
                        pos,
                        msg,
                        code="E006",
                        hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
                    ),
                    pos,
                    code="E006",
                    hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
                )
            raise RuntimeError(msg)
    elif isinstance(expr, MethodCall):
        missing = sorted({arg.name for arg in expr.args if isinstance(arg, Var) and arg.name not in names})
        if missing:
            msg = f"destructuring method call to {expr.name} must include output for argument(s): {', '.join(missing)}"
            if source:
                raise TinyLangError(
                    format_error(
                        source,
                        pos,
                        msg,
                        code="E006",
                        hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
                    ),
                    pos,
                    code="E006",
                    hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
                )
            raise RuntimeError(msg)


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
        elif isinstance(st, TryCatch):
            for branch_stmt in st.body:
                visit(branch_stmt)
            for branch_stmt in st.handler:
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


def _import_binding_name(module: str, alias: Optional[str]) -> str:
    if alias:
        return alias
    stripped = module.lstrip(".") or module
    return stripped.split(".")[-1]


class ModuleResolver:
    def __init__(self, search_paths: Optional[List[Path]] = None):
        env_paths = os.environ.get("TINYPATH", "")
        configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
        default_roots = [Path.cwd(), Path(__file__).parent]
        self.search_paths: List[Path] = search_paths or configured_paths + default_roots
        self.cache: Dict[Path, NamespaceRef] = {}
        self._in_progress: List[Path] = []

    def _resolve_name(self, raw: str, caller_namespace: Optional[str], pos: Optional[SourcePos]) -> str:
        leading = len(raw) - len(raw.lstrip("."))
        if leading == 0:
            return raw
        if not caller_namespace:
            raise TinyLangError(
                format_error("", pos or SourcePos.origin(), "relative import outside a module", code="E008"),
                pos or SourcePos.origin(),
                code="E008",
            )
        base = caller_namespace.split(".")
        if leading > len(base):
            raise TinyLangError(
                format_error(
                    "",
                    pos or SourcePos.origin(),
                    "relative import traverses beyond module root",
                    code="E008",
                ),
                pos or SourcePos.origin(),
                code="E008",
            )
        trimmed = base[: len(base) - leading]
        remainder = raw.lstrip(".")
        if remainder:
            trimmed.append(remainder)
        return ".".join(part for part in trimmed if part)

    def _candidate_paths(self, module_name: str, caller_path: Optional[Path]) -> List[Path]:
        rel_path = Path(*module_name.split("."))
        candidates: List[Path] = []
        roots: List[Path] = []
        if caller_path:
            roots.append(caller_path.parent)
        roots.extend(self.search_paths)
        for root in roots:
            candidates.append((root / rel_path).with_suffix(".tiny"))
        return candidates

    def import_module(
        self,
        name: str,
        runtime: "Runtime",
        *,
        caller_namespace: Optional[str],
        caller_path: Optional[Path],
        pos: Optional[SourcePos] = None,
    ) -> NamespaceRef:
        resolved_name = self._resolve_name(name, caller_namespace, pos)
        for candidate in self._candidate_paths(resolved_name, caller_path):
            resolved_path = candidate.resolve()
            if resolved_path in self.cache:
                return self.cache[resolved_path]
            if resolved_path.exists():
                if resolved_path in self._in_progress:
                    raise TinyLangError(
                        format_error(
                            "",
                            pos or SourcePos.origin(),
                            f"circular import involving {resolved_path}",
                            code="E008",
                        ),
                        pos or SourcePos.origin(),
                        code="E008",
                    )
                self._in_progress.append(resolved_path)
                try:
                    module_env = Environment(parent=None, namespace=resolved_name)
                    compile_and_run(
                        resolved_path.read_text(encoding="utf-8"),
                        env=module_env,
                        runtime=runtime,
                        module_namespace=resolved_name,
                        module_path=resolved_path,
                        module_resolver=self,
                    )
                    ns_ref = NamespaceRef(runtime, resolved_name)
                    self.cache[resolved_path] = ns_ref
                    return ns_ref
                finally:
                    self._in_progress.remove(resolved_path)
        raise TinyLangError(
            format_error(
                "", pos or SourcePos.origin(), f"module '{name}' not found on search path", code="E008"
            ),
            pos or SourcePos.origin(),
            code="E008",
        )


@dataclass
class SpawnHandle:
    thread: threading.Thread
    done: threading.Event
    cancelled: threading.Event
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
        self.global_env: Optional["Environment"] = None
        self.error_messages: List[str] = []
        self.source = source
        self.source_map: Dict[Optional[str], str] = {None: source}
        self.namespace_envs: Dict[str, "Environment"] = {}
        self.module_resolver: ModuleResolver = ModuleResolver()
        self.current_module_path: Optional[Path] = None
        self.current_module_namespace: Optional[str] = None
        self.call_stack: List[StackFrame] = []

    @staticmethod
    def _qualify_name(name: str, namespace: Optional[str]) -> str:
        return f"{namespace}.{name}" if namespace else name

    def _source_for_namespace(self, namespace: Optional[str]) -> str:
        with self._lock:
            if namespace in self.source_map:
                return self.source_map[namespace]
        return self.source

    def _format_stacktrace(self, stack: Sequence[StackFrame]) -> str:
        if not stack:
            return ""
        lines = ["Stack trace:"]
        for frame in reversed(stack):
            lines.append(f"  at {frame.qualified_name} (line {frame.pos.line}, col {frame.pos.col})")
        return "\n".join(lines)

    def _record_error(
        self,
        msg: str,
        pos: Optional[SourcePos] = None,
        *,
        code: str = "E000",
        hint: Optional[str] = None,
        formatted: Optional[str] = None,
    ) -> None:
        if formatted is None:
            source = self._source_for_namespace(self.current_module_namespace if pos is not None else None)
            base = format_error(source, pos, msg, code=code, hint=hint) if pos is not None else msg
            stack_part = self._format_stacktrace(self.call_stack)
            formatted = f"{base}\n{stack_part}" if stack_part else base
        with self._lock:
            # Only keep the most recent runtime error so `errorMessage` reflects
            # the latest failure instead of accumulating older ones.
            self.error_messages = [formatted]

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
        source = self._source_for_namespace(self.current_module_namespace)
        formatted = format_error(source, pos, msg, code=code, hint=hint)
        stack = tuple(self.call_stack)
        if stack:
            formatted = f"{formatted}\n{self._format_stacktrace(stack)}"
        self._record_error(msg, pos, code=code, hint=hint, formatted=formatted)
        return TinyLangError(formatted, pos, code=code, hint=hint, stack=stack)

    def _ensure_error_has_stack(self, err: TinyLangError) -> TinyLangError:
        if err.stack:
            return err
        stack = tuple(self.call_stack)
        if not stack:
            return err
        err.stack = stack
        err.message = f"{err.message}\n{self._format_stacktrace(stack)}"
        return err

    @staticmethod
    def _error_value(err: TinyLangError) -> Dict[str, Any]:
        stack_strings = [
            f"{frame.qualified_name} (line {frame.pos.line}, col {frame.pos.col})" for frame in err.stack
        ]
        return {
            "__tag__": "Error",
            "code": err.code,
            "message": str(err),
            "hint": err.hint,
            "stack": stack_strings,
        }

    @property
    def error_message(self) -> Optional[str]:
        with self._lock:
            if not self.error_messages:
                return None
            return self.error_messages[-1]

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
        if isinstance(v, BaseView):
            return v.class_name
        try:
            iv = int(v)
            with self._lock:
                if iv in self.ptr_tags:
                    return self.ptr_tags[iv]
        except Exception:
            pass
        return None

    def _value_type_name(self, value: Any) -> Optional[str]:
        tag = self.__get_tag(value)
        if tag:
            return tag
        if value is None:
            return "Null"
        if isinstance(value, bool):
            return "Bool"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "string"
        return type(value).__name__

    def _type_matches(self, expected: str, value: Any) -> bool:
        actual = self._value_type_name(value)
        if actual is None:
            return False
        expected_norm = expected.strip()
        actual_norm = actual.strip() if isinstance(actual, str) else str(actual)
        if expected_norm == actual_norm or expected_norm.lower() == actual_norm.lower():
            return True
        if expected_norm.lower() == "number" and actual_norm.lower() in {"number", "int", "float"}:
            return True
        if expected_norm.lower() == "string" and actual_norm.lower() == "string":
            return True
        if expected_norm.lower() in {"bool", "boolean"} and actual_norm.lower() in {"bool", "boolean"}:
            return True
        if expected_norm == "Null" and value is None:
            return True
        return False

    def _enforce_annotation(self, expected: str, value: Any, *, label: str, pos: SourcePos) -> None:
        if not self._type_matches(expected, value):
            actual = self._value_type_name(value) or type(value).__name__
            raise self._error(
                f"type mismatch for {label}: expected {expected} but got {actual}",
                pos,
                code="E009",
                hint="Adjust the type annotation or pass a compatible value to satisfy the hint.",
            )

    @staticmethod
    def _number_fields(val: Any) -> Optional[Dict[str, Any]]:
        if isinstance(val, dict) and val.get("__tag__") == "Number":
            return val.get("__fields__", {}).get("Number")
        return None

    @staticmethod
    def _make_number(value: Any, error: str) -> Dict[str, Any]:
        return {"__tag__": "Number", "__fields__": {"Number": {"value": value, "error": error}}}

    @staticmethod
    def _intervall_fields(val: Any) -> Optional[Dict[str, Any]]:
        if isinstance(val, dict) and val.get("__tag__") == "NumberIntervall":
            return val.get("__fields__", {}).get("NumberIntervall")
        return None

    @staticmethod
    def _make_intervall(lower: Any, upper: Any, error: str) -> Dict[str, Any]:
        return {
            "__tag__": "NumberIntervall",
            "__fields__": {"NumberIntervall": {"lower": lower, "upper": upper, "error": error}},
        }

    def _number_to_intervall(self, value: Any) -> Optional[Dict[str, Any]]:
        fields = self._number_fields(value)
        if fields is None:
            return None
        err = fields.get("error", "normal") or "normal"
        if err in {"plus_infinity", "minus_infinity", "any_number"}:
            return self._make_intervall(0, 0, err)
        lower = fields.get("value", 0)
        upper = fields.get("value", 0)
        return self._make_intervall(lower, upper, "normal")

    def _coerce_to_number(self, val: Any) -> Any:
        if val is None:
            return self._make_number(0, "normal")
        if self.__get_tag(val) == "Number":
            return val
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return self._make_number(val, "normal")
        return val

    def _coerce_to_intervall(self, val: Any) -> Any:
        if val is None:
            return self._make_intervall(0, 0, "normal")
        if self.__get_tag(val) == "NumberIntervall":
            return val
        from_number = self._number_to_intervall(val)
        if from_number is not None:
            return from_number
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return self._make_intervall(val, val, "normal")
        return val

    def _coerce_numeric_operands(
        self, op: str, a: Any, b: Any, ta: Optional[str], tb: Optional[str]
    ) -> Tuple[Any, Any]:
        arithmetic_ops = {"+", "-", "*", "/", "^"}
        if op not in arithmetic_ops:
            return a, b
        if ta == "NumberIntervall" or tb == "NumberIntervall":
            return self._coerce_to_intervall(a), self._coerce_to_intervall(b)
        if ta == "Number" or tb == "Number":
            return self._coerce_to_number(a), self._coerce_to_number(b)
        return a, b

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
        if a is None:
            a = 0
        if b is None:
            b = 0
        ta = self.__get_tag(a)
        tb = self.__get_tag(b)
        a, b = self._coerce_numeric_operands(op, a, b, ta, tb)
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
        if isinstance(target_obj, NamespaceRef):
            env = self.namespace_envs.get(target_obj.name)
            if env and env.contains(key):
                return env.get(key)
            qualified = self._qualify_name(key, target_obj.name)
            with self._lock:
                if qualified in self.functions:
                    return NamespaceRef(self, qualified)
            self._record_error(f"unknown field {key}", pos)
            return None
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
        call_env = Environment(parent=self.global_env, namespace=fn.namespace)
        for param, arg in zip(fn.params, args):
            if param.type:
                self._enforce_annotation(param.type, arg, label=f"parameter {param.name} in function {fn.name}", pos=fn.pos)
            call_env.values[param.name] = arg
        frame = StackFrame(fn.name, fn.namespace, fn.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = fn.namespace or prev_namespace
        try:
            res = self.eval_block(fn.body, call_env, fn.namespace)
            if isinstance(res, ReturnSignal):
                value = res.value
                if fn.return_type:
                    self._enforce_annotation(fn.return_type, value, label=f"return value for function {fn.name}", pos=fn.pos)
                return value
            if fn.return_type:
                self._enforce_annotation(fn.return_type, res, label=f"return value for function {fn.name}", pos=fn.pos)
            return res
        except TinyLangError as err:
            raise self._ensure_error_has_stack(err) from err
        finally:
            self.call_stack.pop()
            self.current_module_namespace = prev_namespace

    def _run_spawn(self, fn: Fn, args: List[Any], handle: SpawnHandle) -> None:
        try:
            if handle.cancelled.is_set():
                handle.error = RuntimeError("spawn cancelled")
                return
            result = self._invoke_function(fn, args)
            if handle.cancelled.is_set():
                handle.error = RuntimeError("spawn cancelled")
            else:
                handle.result = result
        except Exception as exc:  # noqa: BLE001
            handle.error = exc
        finally:
            handle.done.set()

    def _join_status(self, handle: SpawnHandle, *, done: bool) -> Dict[str, Any]:
        return {
            "__tag__": "JoinStatus",
            "done": done,
            "cancelled": handle.cancelled.is_set(),
            "error": str(handle.error) if handle.error else None,
            "result": None if handle.error or not done or handle.cancelled.is_set() else handle.result,
        }

    def cancel_handle(self, handle: Any) -> bool:
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("cancel expects a spawn handle")
        already = handle.cancelled.is_set()
        handle.cancelled.set()
        return not already

    def join_handle(
        self,
        handle: Any,
        *,
        timeout_ms: Optional[float] = None,
        cancel_on_timeout: bool = False,
        want_status: bool = False,
    ) -> Any:
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("join expects a spawn handle")

        timeout = None if timeout_ms is None else max(0.0, timeout_ms / 1000.0)
        finished = handle.done.wait(timeout)
        if not finished:
            if cancel_on_timeout:
                self.cancel_handle(handle)
            if want_status:
                return self._join_status(handle, done=False)
            return None

        handle.thread.join()
        if handle.cancelled.is_set():
            if want_status:
                return self._join_status(handle, done=True)
            raise handle.error or RuntimeError("join cancelled")
        if handle.error:
            if want_status:
                return self._join_status(handle, done=True)
            raise handle.error
        if want_status:
            return self._join_status(handle, done=True)
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
            return self._invoke_function(fn, args)
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
        env.values[md.params[0].name] = self_value  # self
        for base in self.class_mro(cname)[1:]:
            env.values[base] = BaseView(target_obj, base)
        for param, arg in zip(md.params[1:], args):
            if param.type:
                self._enforce_annotation(param.type, arg, label=f"parameter {param.name} in method {md.class_name}.{md.name}", pos=md.pos)
            env.values[param.name] = arg
        frame = StackFrame(f"{md.class_name}.{md.name}", md.namespace, md.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = md.namespace or prev_namespace
        try:
            res = self.eval_block(md.body, env)
            if isinstance(res, ReturnSignal):
                value = res.value
                if md.return_type:
                    self._enforce_annotation(md.return_type, value, label=f"return value for method {md.class_name}.{md.name}", pos=md.pos)
                return value
            if md.return_type:
                self._enforce_annotation(md.return_type, res, label=f"return value for method {md.class_name}.{md.name}", pos=md.pos)
            return res
        except TinyLangError as err:
            raise self._ensure_error_has_stack(err) from err
        finally:
            self.call_stack.pop()
            self.current_module_namespace = prev_namespace

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

                def _format_float(val: float) -> str:
                    abs_val = abs(val)
                    if abs_val >= 1e-9:
                        rounded = round(val, 12)
                        if abs(rounded - val) <= abs_val * 1e-12:
                            val = rounded
                    return str(val)

                return f"{_format_float(center)} +/- {_format_float(radius)}"
        if isinstance(val, bool):
            return "true" if val else "false"
        if val is None:
            return "Null"
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
            elif isinstance(s, TryCatch):
                try:
                    res = self.eval_block(s.body, env, namespace)
                    if isinstance(res, ReturnSignal):
                        return res
                except TinyLangError as err:
                    if s.err_name:
                        env.values[s.err_name] = self._error_value(self._ensure_error_has_stack(err))
                    res = self.eval_block(s.handler, env, namespace)
                    if isinstance(res, ReturnSignal):
                        return res
            elif isinstance(s, Namespace):
                qualified = self._qualify_name(s.name, namespace)
                child_env = Environment(parent=env, namespace=qualified)
                env.values[s.name] = NamespaceRef(self, qualified)
                self.namespace_envs[qualified] = child_env
                self.eval_block(s.body, child_env, qualified)
            elif isinstance(s, Import):
                binding = _import_binding_name(s.module, s.alias)
                ns_ref = self.module_resolver.import_module(
                    s.module,
                    self,
                    caller_namespace=namespace or env.namespace,
                    caller_path=self.current_module_path,
                    pos=s.pos,
                )
                env.values[binding] = ns_ref
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
                    m.namespace = namespace
                    self.register_method(m)
            elif isinstance(s, MethodDef):
                s.namespace = namespace
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
            if isinstance(e, Null):
                return None
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
                    if not (1 <= len(e.args) <= 3):
                        raise RuntimeError("join expects between 1 and 3 arguments")
                    handle = self.eval_expr(e.args[0], env)
                    if len(e.args) == 1:
                        return self.join_handle(handle)
                    try:
                        timeout_ms = float(self.eval_expr(e.args[1], env))
                    except Exception:
                        raise RuntimeError("join timeout must be numeric")
                    cancel_on_timeout = False
                    if len(e.args) == 3:
                        cancel_on_timeout = bool(self.eval_expr(e.args[2], env))
                    return self.join_handle(
                        handle,
                        timeout_ms=timeout_ms,
                        cancel_on_timeout=cancel_on_timeout,
                        want_status=True,
                    )
                if e.name == "cancel":
                    if len(e.args) != 1:
                        raise RuntimeError("cancel expects 1 argument")
                    return self.cancel_handle(self.eval_expr(e.args[0], env))
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
                cancelled = threading.Event()

                def run_task() -> None:
                    self._run_spawn(fn, arg_values, handle)

                handle = SpawnHandle(
                    thread=threading.Thread(target=run_task), done=done, cancelled=cancelled
                )
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


def compile_and_run(
    src: str,
    env: Optional[Environment] = None,
    runtime: Optional[Runtime] = None,
    *,
    module_namespace: Optional[str] = None,
    module_path: Optional[Path] = None,
    module_resolver: Optional[ModuleResolver] = None,
) -> str:
    parser = Parser(Lexer(src), src)
    stmts = parser.parse()
    runtime = runtime or Runtime(src)
    runtime.source_map[module_namespace] = src
    prev_source = runtime.source
    runtime.source = src
    previous_path = runtime.current_module_path
    previous_namespace = runtime.current_module_namespace
    runtime.current_module_path = module_path
    runtime.current_module_namespace = module_namespace
    if module_resolver is not None:
        runtime.module_resolver = module_resolver
    runtime.output.clear()
    runtime.error_messages.clear()

    # lint functions + top level locals
    lint_import_style(stmts, src)
    lint_destruct_call_outputs(stmts, src)
    lint_no_consecutive_definitions(stmts)
    lint_locals_used(stmts, src)
    signatures = _collect_function_signatures(stmts)
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
    lint_bare_call_results(stmts, signatures, src)

    env = env or Environment(parent=None, namespace=module_namespace)
    if module_namespace:
        runtime.namespace_envs[module_namespace] = env
    runtime.global_env = env
    register_stdlib(runtime, env, NamespaceRef)
    try:
        for st in stmts:
            runtime.eval_stmt(st, env, namespace=module_namespace)
    finally:
        runtime.current_module_path = previous_path
        runtime.current_module_namespace = previous_namespace
        runtime.source = prev_source
    return "".join(runtime.output)


def run_file(path: str) -> str:
    path_obj = Path(path)
    resolved = path_obj.resolve()
    try:
        rel = resolved.relative_to(Path.cwd())
        namespace = ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001
        namespace = resolved.stem
    with open(path, "r", encoding="utf-8") as f:
        return compile_and_run(f.read(), module_namespace=namespace, module_path=resolved)


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


def _configure_readline(
    history_path: Path, scope_provider: Callable[[], List[str]] = lambda: sorted(KEYWORDS | BUILTINS)
) -> None:
    if readline is None:
        return
    readline.set_completer_delims(" \t\n")

    def completer(text: str, state: int) -> Optional[str]:
        completions = sorted(set(scope_provider()))
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


def _resolve_read_fn():
    if isinstance(readline, _FallbackReadline):
        return readline.readline
    return input


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
    mode_group.add_argument(
        "--format",
        dest="format_file",
        metavar="FILE",
        help="Format the given TinyLanguage source file and print the result",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the TinyLanguage source file to execute",
    )
    args = parser.parse_args(argv)

    if args.format_file is not None:
        from formatter import format_source

        with open(args.format_file, "r", encoding="utf-8") as handle:
            print(format_source(handle.read()), end="")
        return 0

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
        env = Environment(parent=None, namespace=None)
        runtime = Runtime("")
        scope_provider = lambda: list(KEYWORDS | BUILTINS | set(env.all_names()))
        _configure_readline(history_path, scope_provider)
        read_fn = _resolve_read_fn()
        try:
            while True:
                src = _read_repl_command(read_fn)
                if src is None:
                    print()
                    break
                if not src.strip():
                    continue
                if readline is not None:
                    try:
                        readline.add_history(src)
                    except Exception:
                        pass
                try:
                    output = compile_and_run(src, env=env, runtime=runtime)
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


__all__ = ["compile_and_run", "run_file", "main", "ModuleResolver"]
