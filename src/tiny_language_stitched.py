# --- segment: tiny_language_preamble.py ---
"""Platform shims and interactive helpers shared across TinyLanguage tools.

This module centralizes readline fallbacks, terminal capability detection, and
argument parsing helpers that would otherwise be duplicated between the REPL
and CLI layers. The lightweight implementations are designed to degrade
gracefully on platforms without ``termios`` support while still providing
history and completion hooks when available.
"""

from __future__ import annotations

import argparse  # required to keep stitched globals available
import difflib
import importlib.util  # required to keep stitched globals available
import math  # required to keep stitched globals available
import os  # required to keep stitched globals available
import sys
import threading  # required to keep stitched globals available
from pathlib import Path
try:  # pragma: no cover - platform-specific imports
    import termios  # type: ignore
    import tty  # type: ignore
    _HAS_TERMIOS = True
except ImportError:  # pragma: no cover - Windows and other platforms without termios
    termios = None  # type: ignore
    tty = None  # type: ignore
    _HAS_TERMIOS = False

from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from tiny_errors import SourcePos, SourceSpan, StackFrame, TinyLangError, _line_info, format_error

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
        """Gather completion candidates from the configured completer."""

        if self._completions is None:  # No completer means no matches
            return []
        matches: List[str] = []  # Accumulate completion strings
        idx = 0  # State counter required by readline-compatible completers
        while True:
            candidate = self._completions(text, idx)  # Ask completer for the idx-th match
            if candidate is None:  # A "None" sentinel marks the end
                break
            matches.append(candidate)
            idx += 1
        return matches

    def _redraw(self, prompt: str, buffer: List[str], last_len: int) -> int:
        """Render the current prompt + buffer, padding leftover characters if needed."""

        sys.stdout.write("\r")  # Start at the beginning of the line
        rendered = prompt + "".join(buffer)  # Prompt plus current text
        sys.stdout.write(rendered)
        if last_len > len(buffer):  # Clear any extra characters from a previous render
            sys.stdout.write(" " * (last_len - len(buffer)))
        sys.stdout.write("\r")  # Return to the line start again
        sys.stdout.write(prompt + "".join(buffer))  # Write prompt and buffer
        sys.stdout.flush()
        return len(buffer)

    def _reverse_search(self, prompt: str, fd: int) -> Optional[str]:
        """Implement a simple reverse-i-search inspired by readline."""

        if not _HAS_TERMIOS:  # Without termios support, we cannot drive raw input
            return None
        sys.stdout.write("\n(reverse-search): ")  # Start a new prompt line
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, self._old_settings)  # Restore cooked mode
        try:
            query = sys.stdin.readline().rstrip("\n")  # Grab the search term
        finally:
            tty.setraw(fd)  # Return to raw mode for normal handling
        if not query:  # Empty search means abort
            return None
        for entry in reversed(self._history):  # Walk history from newest to oldest
            if query in entry:
                return entry  # Return the first entry that contains the query
        return None

    def readline(self, prompt: str = "") -> str:
        if not _HAS_TERMIOS:
            line = input(prompt)  # Fall back to default input() when raw mode is unavailable
            if line:
                self.add_history(line)  # Persist history in the in-memory buffer
            return line
        fd = sys.stdin.fileno()  # Grab the file descriptor to toggle terminal modes
        self._old_settings = termios.tcgetattr(fd)  # Remember previous termios state
        buffer: List[str] = []  # Characters typed so far
        last_len = 0  # Track the previous render length for erasing
        self._history_index = None  # Reset history navigation state

        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            tty.setraw(fd)  # Switch to raw mode to intercept keystrokes
            while True:
                ch = sys.stdin.read(1)  # Read a single byte
                if ch in ("\n", "\r"):
                    sys.stdout.write("\n")  # Move to the next line
                    line = "".join(buffer)  # Turn the buffer into a full string
                    if line:
                        self.add_history(line)  # Save successful entries
                    return line
                if ch == "\x7f":  # Backspace
                    if buffer:
                        buffer.pop()  # Remove the last character
                        last_len = self._redraw(prompt, buffer, last_len)  # Refresh the line
                    continue
                if ch == "\t":  # Tab completion
                    prefix = "".join(buffer)
                    last_word = prefix.split()[-1] if prefix else ""  # Only complete the final token
                    matches = self._collect_matches(last_word)
                    if not matches:
                        continue  # Nothing to complete
                    if len(matches) == 1:
                        completed = matches[0]  # Single match, accept immediately
                    else:
                        shared_prefix = last_word  # Find longest shared prefix for multiple matches
                        for idx in range(len(last_word), len(max(matches, key=len)) + 1):
                            candidates = {m[:idx] for m in matches if len(m) >= idx}
                            if len(candidates) == 1:
                                shared_prefix = candidates.pop()
                            else:
                                break
                        completed = shared_prefix
                        sys.stdout.write("\n" + "  ".join(sorted(matches)) + "\n")  # Show options
                    if last_word:
                        buffer = buffer[: len(prefix) - len(last_word)] + list(completed)
                    else:
                        buffer = list(completed)
                    last_len = self._redraw(prompt, buffer, last_len)
                    continue
                if ch == "\x12":  # Ctrl+R reverse search
                    match = self._reverse_search(prompt, fd)
                    if match is not None:
                        buffer = list(match)  # Replace buffer with the match
                        last_len = self._redraw(prompt, buffer, last_len)
                    else:
                        last_len = self._redraw(prompt, buffer, last_len)
                    continue
                if ch == "\x1b":  # Escape sequences (arrow keys)
                    seq = sys.stdin.read(2)  # Read the remaining bytes of the escape code
                    if seq == "[A":  # Up
                        if self._history:
                            if self._history_index is None:
                                self._history_index = len(self._history) - 1  # Start at the newest entry
                            elif self._history_index > 0:
                                self._history_index -= 1  # Move further back in history
                            buffer = list(self._history[self._history_index])
                            last_len = self._redraw(prompt, buffer, last_len)
                    elif seq == "[B":  # Down
                        if self._history_index is not None:
                            if self._history_index < len(self._history) - 1:
                                self._history_index += 1  # Move forward in history
                                buffer = list(self._history[self._history_index])
                            else:
                                self._history_index = None  # Clear history selection at the end
                                buffer = []
                            last_len = self._redraw(prompt, buffer, last_len)
                    continue
                buffer.append(ch)  # Normal character: append to buffer
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


def _closest_match(name: str, candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _classify_error(msg: str, candidates: Optional[List[str]] = None) -> Tuple[str, Optional[str]]:
    lower_msg = msg.lower()
    if "return value must be bound" in lower_msg or "must be returned" in lower_msg:
        return "E001", "Bind the return value, e.g. `def result = call();`, or add a return that includes the mutated data."
    if lower_msg.startswith("unused"):
        return "E002", "Remove the unused binding or reference it."
    if "unknown variable" in lower_msg:
        suggestion = _closest_match(msg.split()[-1], candidates or []) if candidates is not None else None
        base_hint = "Declare the variable first, e.g. `def name = ...;`."
        if suggestion:
            return "E003", f"Did you mean `{suggestion}`? {base_hint}"
        return "E003", base_hint
    if "exponent for ^ must be an integer" in lower_msg:
        return "E004", "Use an integer exponent (cast with `int(...)` if necessary) when using the ^ operator."
    if "fractional exponent for ^ requires a non-negative base" in lower_msg:
        return "E004", "Use a non-negative base or an integer exponent when using the ^ operator."
    if "len expects a sized value" in lower_msg:
        return "E005", "Pass a list, string, heap pointer, or other sized value to `len`."
    if "destructuring call" in lower_msg and "must include output" in lower_msg:
        return "E006", "Add the missing binding(s) to the destructuring pattern so each referenced argument is captured."
    if "type mismatch" in lower_msg:
        return "E009", "Adjust the annotation or the provided value so they agree."
    if "not all paths" in lower_msg and "return" in lower_msg:
        return "E010", "Add return statements for every branch or supply a default return value."
    return "E000", None

# --- segment: tiny_language_lexer.py ---
"""Tokenizer that emits TinyLanguage tokens with source positions.

The lexer handles keywords, operators, literals, and comments, producing
``Token`` instances that carry start/stop positions for detailed error
reporting. It intentionally keeps the rules compact so additional language
features can extend ``KEYWORDS`` and ``SYMBOLS`` without rewriting the core
scanner.
"""

from dataclasses import dataclass

from tiny_errors import SourcePos, SourceSpan
from tiny_language_preamble import TinyLangError, format_error

# ----- Lexer -----

KEYWORDS = {
    "def",
    "print",
    "if",
    "else",
    "while",
    "switch",
    "default",
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
    "async",
    "await",
    "task",
    "true",
    "false",
    "flush",
    "and",
    "or",
    "not",
    "Null",
    "try",
    "catch",
    "match",
    "case",
}

BUILTINS = {"Collections", "Math", "String", "len", "print"}


@dataclass
class Token:
    kind: str
    text: str
    start: SourcePos
    stop: SourcePos

    @property
    def pos(self) -> SourcePos:
        return self.start

    @property
    def span(self) -> SourceSpan:
        return SourceSpan(self.start, self.stop)


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
            pos = SourcePos(self.line, self.col)
            return Token("EOF", "", pos, pos)
        c = self.s[self.i]
        start_line = self.line
        start_col = self.col
        pos = SourcePos(start_line, start_col)

        if c == "&" and self.i + 1 < self.n and self.s[self.i + 1] == "&":
            self._advance(2)
            stop = SourcePos(start_line, start_col + 1)
            return Token("OP", "&&", pos, stop)
        if c == "|" and self.i + 1 < self.n and self.s[self.i + 1] == "|":
            self._advance(2)
            stop = SourcePos(start_line, start_col + 1)
            return Token("OP", "||", pos, stop)
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
            stop = SourcePos(start_line, start_col + consumed - 1)
            return Token(kind, txt, pos, stop)
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
            if j < self.n and self.s[j] in "eE":
                exp_start = j
                k = j + 1
                if k < self.n and self.s[k] in "+-":
                    k += 1
                exp_digits = k
                while k < self.n and self.s[k].isdigit():
                    k += 1
                if k == exp_digits:
                    exp_end = max(exp_digits - 1, exp_start)
                    exp_start_pos = SourcePos(start_line, start_col + (exp_start - self.i))
                    exp_stop_pos = SourcePos(start_line, start_col + (exp_end - self.i))
                    span = SourceSpan(exp_start_pos, exp_stop_pos)
                    raise TinyLangError(
                        format_error(self.s, span, "invalid exponent in number literal"),
                        exp_start_pos,
                        span=span,
                    )
                j = k
            txt = self.s[self.i:j]
            consumed = j - self.i
            self.i = j
            self.col += consumed
            stop = SourcePos(start_line, start_col + consumed - 1)
            return Token("NUMBER", txt, pos, stop)
        if c in (">", "<", "=", "!"):
            if self.i + 1 < self.n and self.s[self.i + 1] == "=":
                self.i += 2
                self.col += 2
                stop = SourcePos(start_line, start_col + 1)
                return Token("OP", c + "=", pos, stop)
        if c in "+-*/><^!%":
            self._advance()
            return Token("OP", c, pos, SourcePos(start_line, start_col))
        if c in "(){}[];,=:.,?":
            self._advance()
            return Token("SYM", c, pos, SourcePos(start_line, start_col))
        span = SourceSpan(pos, pos)
        raise TinyLangError(
            format_error(self.s, span, f"lexing error: unexpected character '{c}'"), pos, span=span
        )

    def _read_string(self) -> Token:
        start_line = self.line
        start_col = self.col
        pos0 = SourcePos(start_line, start_col)
        self._advance()  # skip opening quote
        buf = []
        while self.i < self.n:
            c = self.s[self.i]
            if c == '"':
                self._advance()
                stop = SourcePos(self.line, self.col - 1)
                return Token("STRING", "".join(buf), pos0, stop)
            if c == "\\":
                slash_pos = SourcePos(self.line, self.col)
                self._advance()
                if self.i >= self.n:
                    span = SourceSpan(slash_pos, slash_pos)
                    raise TinyLangError(
                        format_error(self.s, span, "unterminated escape in string"),
                        slash_pos,
                        span=span,
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
        span = SourceSpan(pos0, pos0)
        if self.i >= self.n:
            end_line = self.line
            end_col = max(self.col - 1, 1)
            span = SourceSpan(pos0, SourcePos(end_line, end_col))
        raise TinyLangError(
            format_error(self.s, span, "unterminated string literal"), pos0, span=span
        )

# --- segment: tiny_language_ast.py ---
"""Abstract syntax tree nodes for the TinyLanguage front-end.

The dataclasses here intentionally stay lightweight so the lexer, parser, and
transpilers can share a common shape without depending on runtime state. Each
node carries a ``SourcePos`` to keep error reporting consistent across
compilation stages.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from tiny_errors import SourcePos, SourceSpan

# ----- AST Nodes -----


class IR:
    """Base class for all TinyLanguage AST nodes."""

    pos: SourcePos
    span: Optional[SourceSpan] = None


@dataclass
class Let(IR):
    """Declaration that binds an immutable name to an expression."""

    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)
    name_span: Optional[SourceSpan] = None


@dataclass
class Assign(IR):
    """Reassignment of an existing variable."""

    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)
    name_span: Optional[SourceSpan] = None


@dataclass
class FieldAssign(IR):
    """Assign into a field on an object literal or class instance."""

    obj: IR
    name: str
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Print(IR):
    """Print one or more expressions in order."""

    exprs: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Flush(IR):
    """Flush buffered output streams."""

    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class If(IR):
    """Conditional branch with optional else body."""

    cond: IR
    then: List[IR]
    els: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class While(IR):
    """Loop that repeats while the condition evaluates truthy."""

    cond: IR
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class SwitchCase:
    """Single case within a switch statement."""

    value: Optional[IR]
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Switch(IR):
    """Switch statement that dispatches based on value equality."""

    expr: IR
    cases: List[SwitchCase]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class TryCatch(IR):
    """Exception handling block with optional error binding."""

    body: List[IR]
    err_name: Optional[str]
    handler: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class TaskBlock(IR):
    """Structured concurrency block that scopes spawned tasks."""

    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Param:
    """Function or method parameter with an optional type hint."""

    name: str
    type: Optional[str] = None


@dataclass
class Fn(IR):
    """Function declaration with parameters and optional return type."""

    name: str
    params: List[Param]
    body: List[IR]
    return_param_names: Set[str] = field(default_factory=set)
    namespace: Optional[str] = None
    return_type: Optional[str] = None
    inferred_return_type: Optional[str] = None
    is_async: bool = False
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodDef(IR):
    """Method definition inside a class, mirroring ``Fn`` with a receiver."""

    class_name: str
    name: str
    params: List[Param]
    body: List[IR]
    return_param_names: Set[str] = field(default_factory=set)
    return_type: Optional[str] = None
    inferred_return_type: Optional[str] = None
    namespace: Optional[str] = None
    is_async: bool = False
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Namespace(IR):
    """Group of statements that share a namespace qualifier."""

    name: str
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Return(IR):
    """Return a value from the current function or method."""

    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Import(IR):
    """Import another module, optionally with an alias."""

    module: str
    alias: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)
    module_span: Optional[SourceSpan] = None
    binding_span: Optional[SourceSpan] = None


@dataclass
class CallStmt(IR):
    """Standalone call where the result is intentionally discarded."""

    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class OpDef(IR):
    """Operator overload expressed as a function body."""

    op: str
    a_name: str
    a_type: str
    b_name: str
    b_type: str
    body: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class DestructAssign(IR):
    """Destructure a record-like value into multiple bindings."""

    names: List[str]
    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)
    name_spans: List[SourceSpan] = field(default_factory=list)


@dataclass
class TypeVariant:
    """Single variant inside an algebraic data type definition."""

    name: str
    fields: List[Tuple[str, str]]


@dataclass
class TypeDef(IR):
    """Record type or algebraic data type definition."""

    name: str
    fields: Optional[List[Tuple[str, str]]] = None
    variants: Optional[List[TypeVariant]] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ClassDef(IR):
    """Class declaration including fields, methods, and bases."""

    name: str
    fields: List[Tuple[str, str]]
    methods: List["MethodDef"]
    bases: List[str]
    pos: SourcePos = field(default_factory=SourcePos.origin)


# Expressions
@dataclass
class Num(IR):
    """Numeric literal preserved as text for formatting purposes."""

    txt: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Str(IR):
    """String literal node."""

    txt: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Bool(IR):
    """Boolean literal node."""

    value: bool
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Null(IR):
    """Null literal node."""

    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Var(IR):
    """Identifier reference."""

    name: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Call(IR):
    """Function call expression."""

    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class New(IR):
    """Heap allocation of a fixed-size buffer."""

    size: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class NewLit(IR):
    """Heap allocation expression (vector or tuple literal)."""

    items: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Bin(IR):
    """Binary operator application."""

    op: str
    a: IR
    b: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ObjLit(IR):
    """Inline object literal with named fields."""

    fields: List[Tuple[str, IR]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Field(IR):
    """Field access on a struct or object."""

    obj: IR
    name: str
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MethodCall(IR):
    """Method invocation on an object."""

    obj: IR
    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class ClassNew(IR):
    """Instantiate a class with an initializer field list."""

    name: str
    init: List[Tuple[str, IR]]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Spawn(IR):
    """Spawn a concurrent task that evaluates a function call."""

    name: str
    args: List[IR]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Await(IR):
    """Await the result of a previously spawned task."""

    expr: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class MatchCase:
    """Single case within a ``match`` expression."""

    pattern: "Pattern"
    body: IR
    pos: SourcePos = field(default_factory=SourcePos.origin)


class Pattern:
    """Base class for match patterns."""

    pos: SourcePos


@dataclass
class VariantPattern(Pattern):
    """Match against a tagged union variant and bind fields."""

    variant: str
    bindings: Dict[str, Optional[str]]
    positional_bindings: Optional[List[Optional[str]]] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class WildcardPattern(Pattern):
    """Catch-all pattern that can optionally bind the matched value."""

    name: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class Match(IR):
    """Match expression that dispatches over variants."""

    expr: IR
    cases: List[MatchCase]
    pos: SourcePos = field(default_factory=SourcePos.origin)


@dataclass
class VariantCtor(IR):
    """Constructor call for a specific variant of an algebraic data type."""

    variant: str
    fields: List[Tuple[str, IR]]
    type_name: Optional[str] = None
    pos: SourcePos = field(default_factory=SourcePos.origin)

# --- segment: tiny_language_parser.py ---
"""Parser that turns TinyLanguage tokens into AST nodes.

The parser consumes tokens from ``Lexer`` and builds the lightweight IR objects
defined in ``tiny_language_ast.py``. Error spans are attached eagerly so later
stages (linter, runtime) can surface precise diagnostics without re-parsing the
source text.
"""

# ----- Parser -----


class Parser:
    def __init__(self, lx: Lexer, source: str):
        self.lx = lx
        self.source = source
        self.tok = lx.next_token()
        self._last_tok = Token("<start>", "", SourcePos.origin(), SourcePos.origin())
        self._allow_variant_ctor = True

    @staticmethod
    def _attach_span(node: IR, start: SourcePos, stop: SourcePos) -> IR:
        node.span = SourceSpan(start, stop)
        try:
            current_pos = node.pos  # type: ignore[attr-defined]
        except Exception:
            current_pos = None
        if current_pos is None or current_pos == SourcePos.origin():
            node.pos = start
        return node

    @staticmethod
    def _node_start(node: IR) -> SourcePos:
        span = getattr(node, "span", None)
        return span.start if span is not None else getattr(node, "pos")

    @staticmethod
    def _node_stop(node: IR) -> SourcePos:
        span = getattr(node, "span", None)
        return span.stop if span is not None else getattr(node, "pos")

    @classmethod
    def _span_cover(cls, a: IR, b: IR) -> SourceSpan:
        start = cls._node_start(a)
        stop = cls._node_stop(b)
        return SourceSpan(start, stop)

    def _error(self, message: str, pos: SourcePos, span: Optional[SourceSpan] = None) -> TinyLangError:
        code, hint = _classify_error(message)
        effective_pos = span.start if span else pos
        rendered = format_error(self.source, span or pos, message, code=code, hint=hint)
        return TinyLangError(rendered, effective_pos, code=code, hint=hint, span=span)

    @staticmethod
    def _tok_span(tok: Token) -> SourceSpan:
        return SourceSpan(tok.start, tok.stop)

    def _eat(self, kind: str, text: Optional[str] = None) -> Token:
        if self.tok.kind != kind or (text is not None and self.tok.text != text):
            raise self._error(f"expected {kind}{' '+text if text else ''}", self.tok.pos, self._tok_span(self.tok))
        t = self.tok
        self.tok = self.lx.next_token()
        self._last_tok = t
        return t

    def _eat_name_or_kw(self) -> Token:
        if self.tok.kind in {"NAME", "KW"}:
            t = self.tok
            self.tok = self.lx.next_token()
            self._last_tok = t
            return t
        raise self._error("expected NAME", self.tok.pos, self._tok_span(self.tok))

    def _accept(self, kind: str, text: Optional[str] = None) -> bool:
        if self.tok.kind == kind and (text is None or self.tok.text == text):
            t = self.tok
            self.tok = self.lx.next_token()
            self._last_tok = t
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
        if self.tok.kind == "KW" and self.tok.text == "def":
            kw = self._eat("KW", "def")
            if self.tok.kind == "KW":
                name_tok = self._eat("KW")
            else:
                name_tok = self._eat("NAME")
            self._eat("SYM", "=")
            expr = self.parse_expr()
            semi = self._eat("SYM", ";")
            name_span = self._tok_span(name_tok)
            return self._attach_span(
                Let(name_tok.text, expr, pos=kw.pos, name_span=name_span), kw.start, semi.stop
            )
        if self.tok.kind == "KW" and self.tok.text == "print":
            kw = self._eat("KW", "print")
            self._eat("SYM", "(")
            exprs: List[IR] = []
            if not (self.tok.kind == "SYM" and self.tok.text == ")"):
                exprs.append(self.parse_expr())
                while self._accept("SYM", ","):
                    exprs.append(self.parse_expr())
            self._eat("SYM", ")")
            semi = self._eat("SYM", ";")
            return self._attach_span(Print(exprs, pos=kw.pos), kw.start, semi.stop)
        if self.tok.kind == "KW" and self.tok.text == "flush":
            kw = self._eat("KW", "flush")
            self._eat("SYM", "(")
            self._eat("SYM", ")")
            semi = self._eat("SYM", ";")
            return self._attach_span(Flush(pos=kw.pos), kw.start, semi.stop)
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
            return self._attach_span(If(cond, then, els, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "while":
            kw = self._eat("KW", "while")
            self._eat("SYM", "(")
            cond = self.parse_expr()
            self._eat("SYM", ")")
            body = self.parse_block()
            return self._attach_span(While(cond, body, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "switch":
            kw = self._eat("KW", "switch")
            self._eat("SYM", "(")
            target = self.parse_expr()
            self._eat("SYM", ")")
            self._eat("SYM", "{")
            cases: List[SwitchCase] = []
            has_default = False
            while not self._accept("SYM", "}"):
                if self.tok.kind == "KW" and self.tok.text == "case":
                    case_kw = self._eat("KW", "case")
                    value = self.parse_expr()
                    self._eat("SYM", ":")
                    body = self.parse_block()
                    cases.append(
                        self._attach_span(
                            SwitchCase(value, body, pos=case_kw.pos),
                            case_kw.start,
                            self._last_tok.stop,
                        )
                    )
                    continue
                if self.tok.kind == "KW" and self.tok.text == "default":
                    default_kw = self._eat("KW", "default")
                    if has_default:
                        raise self._error("duplicate default case", default_kw.pos, self._tok_span(default_kw))
                    has_default = True
                    self._eat("SYM", ":")
                    body = self.parse_block()
                    cases.append(
                        self._attach_span(
                            SwitchCase(None, body, pos=default_kw.pos),
                            default_kw.start,
                            self._last_tok.stop,
                        )
                    )
                    continue
                raise self._error("expected case or default", self.tok.pos, self._tok_span(self.tok))
            return self._attach_span(Switch(target, cases, pos=kw.pos), kw.start, self._last_tok.stop)
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
            return self._attach_span(TryCatch(body, err_name, handler, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "task":
            kw = self._eat("KW", "task")
            body = self.parse_block()
            return self._attach_span(TaskBlock(body, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "import":
            kw = self._eat("KW", "import")
            module, module_span = self.parse_module_path()
            alias: Optional[str] = None
            binding_span = module_span
            if self.tok.kind == "KW" and self.tok.text == "as":
                self._eat("KW", "as")
                alias_tok = self._eat("NAME")
                alias = alias_tok.text
                binding_span = self._tok_span(alias_tok)
            semi = self._eat("SYM", ";")
            return self._attach_span(
                Import(
                    module,
                    alias,
                    pos=kw.pos,
                    module_span=module_span,
                    binding_span=binding_span,
                ),
                kw.start,
                semi.stop,
            )
        if self.tok.kind == "KW" and self.tok.text == "namespace":
            kw = self._eat("KW", "namespace")
            name = self.parse_qualified_name()
            body = self.parse_block()
            return self._attach_span(Namespace(name, body, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text in {"fn", "async"}:
            is_async = False
            if self.tok.text == "async":
                self._eat("KW", "async")
                is_async = True
                fn_kw = self._eat("KW", "fn")
            else:
                fn_kw = self._eat("KW", "fn")
            name_tok = self._eat("NAME")
            params = self.parse_param_list()
            return_type = None
            if self._accept("OP", "-"):
                self._eat("OP", ">")
                return_type = self.parse_type_annotation()
            body = self.parse_block()
            return_params = self._collect_return_param_usage(body, {p.name for p in params})
            return self._attach_span(
                Fn(
                    name_tok.text,
                    params,
                    body,
                    return_param_names=return_params,
                    return_type=return_type,
                    is_async=is_async,
                    pos=fn_kw.pos,
                ),
                fn_kw.start,
                self._last_tok.stop,
            )
        if self.tok.kind == "KW" and self.tok.text == "return":
            kw = self._eat("KW", "return")
            expr = self.parse_expr()
            semi = self._eat("SYM", ";")
            return self._attach_span(Return(expr, pos=kw.pos), kw.start, semi.stop)
        if self.tok.kind == "KW" and self.tok.text == "type":
            kw = self._eat("KW", "type")
            name_tok = self._eat("NAME")

            def _parse_product_fields() -> Tuple[List[Tuple[str, str]], Token]:
                self._eat("SYM", "{")
                fields: List[Tuple[str, str]] = []
                semi = self._last_tok
                while not self._accept("SYM", "}"):
                    fname = self._eat("NAME").text
                    self._eat("SYM", ":")
                    ftype = self._eat_name_or_kw().text
                    semi = self._eat("SYM", ";")
                    fields.append((fname, ftype))
                return fields, semi

            def _parse_sum_variants() -> Tuple[List[TypeVariant], Token, Optional[List[Tuple[str, str]]]]:
                self._eat("SYM", "{")
                variants: List[TypeVariant] = []
                semi = self._last_tok
                # Distinguish between legacy product types (field list) and
                # sum types (variant list) by peeking for an early ':'.
                if self.tok.kind == "NAME":
                    first_name_tok = self._eat("NAME")
                    if self._accept("SYM", ":"):
                        first_type = self._eat_name_or_kw().text
                        semi = self._eat("SYM", ";")
                        fields: List[Tuple[str, str]] = [(first_name_tok.text, first_type)]
                        while not self._accept("SYM", "}"):
                            fname = self._eat("NAME").text
                            self._eat("SYM", ":")
                            ftype = self._eat_name_or_kw().text
                            semi = self._eat("SYM", ";")
                            fields.append((fname, ftype))
                        return [], semi, fields
                    # otherwise treat it as a variant name and fall through
                    variants.append(TypeVariant(first_name_tok.text, self.parse_variant_fields()))
                    semi = self._eat("SYM", ";")
                elif self.tok.kind == "KW" and self.tok.text == "def":
                    self._eat("KW", "def")
                    self._eat("NAME")
                    self._eat("SYM", "=")
                    vname = self._eat("NAME").text
                    vfields = self.parse_variant_fields()
                    semi = self._eat("SYM", ";")
                    variants.append(TypeVariant(vname, vfields))
                while not self._accept("SYM", "}"):
                    if self._accept("KW", "def"):
                        self._eat("NAME")
                        self._eat("SYM", "=")
                    vname = self._eat("NAME").text
                    vfields = self.parse_variant_fields()
                    semi = self._eat("SYM", ";")
                    variants.append(TypeVariant(vname, vfields))
                return variants, semi, None

            if self._accept("SYM", "="):
                kind_tok = self._eat_name_or_kw()
                kind = kind_tok.text
                if kind == "product":
                    fields, semi = _parse_product_fields()
                    return self._attach_span(TypeDef(name_tok.text, fields=fields, pos=kw.pos), kw.start, semi.stop)
                if kind == "sum":
                    variants, semi, legacy_fields = _parse_sum_variants()
                    if legacy_fields is not None:
                        return self._attach_span(TypeDef(name_tok.text, fields=legacy_fields, pos=kw.pos), kw.start, semi.stop)
                    return self._attach_span(TypeDef(name_tok.text, variants=variants, pos=kw.pos), kw.start, self._last_tok.stop)
                raise self._error(f"unknown type kind {kind!r}", kind_tok.pos, self._tok_span(kind_tok))

            # Backwards-compatible parsing without an explicit '=' keyword.
            variants = []
            parsed_variants, semi, legacy_fields = _parse_sum_variants()
            if legacy_fields is not None:
                return self._attach_span(TypeDef(name_tok.text, fields=legacy_fields, pos=kw.pos), kw.start, semi.stop)
            return self._attach_span(TypeDef(name_tok.text, variants=parsed_variants, pos=kw.pos), kw.start, self._last_tok.stop)
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
                if self.tok.kind == "KW" and self.tok.text in {"fn", "async"}:
                    is_async = False
                    if self.tok.text == "async":
                        self._eat("KW", "async")
                        is_async = True
                        fn_kw = self._eat("KW", "fn")
                    else:
                        fn_kw = self._eat("KW", "fn")
                    mname_tok = self._eat_name_or_kw()
                    params = self.parse_param_list()
                    return_type = None
                    if self._accept("OP", "-"):
                        self._eat("OP", ">")
                        return_type = self.parse_type_annotation()
                    body = self.parse_block()
                    return_params = self._collect_return_param_usage(body, {p.name for p in params})
                    methods.append(
                        MethodDef(
                            cname_tok.text,
                            mname_tok.text,
                            params,
                            body,
                            return_param_names=return_params,
                            return_type=return_type,
                            namespace=cname_tok.text,
                            is_async=is_async,
                            pos=fn_kw.pos,
                        )
                    )
                else:
                    fname = self._eat("NAME").text
                    self._eat("SYM", ":")
                    ftype = self._eat("NAME").text
                    self._eat("SYM", ";")
                    fields.append((fname, ftype))
            self._eat("SYM", "}")
            return self._attach_span(ClassDef(cname_tok.text, fields, methods, bases, pos=kw.pos), kw.start, self._last_tok.stop)
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
            return self._attach_span(
                OpDef(op_tok.text, a_name, a_type, b_name, b_type, body, pos=kw.pos), kw.start, self._last_tok.stop
            )
        # destructuring or assignment/field assignment
        if self.tok.kind == "SYM" and self.tok.text == "{":
            names, start_pos, name_spans = self.parse_destruct_names()
            self._eat("SYM", "=")
            expr = self.parse_expr()
            semi = self._eat("SYM", ";")
            return self._attach_span(
                DestructAssign(names, expr, pos=start_pos, name_spans=name_spans), start_pos, semi.stop
            )
        if self.tok.kind == "NAME":
            # look ahead for field assignment or normal assignment/call
            name_tok = self.tok
            self._eat("NAME")
            if self._accept("SYM", "."):
                field_name = self._eat_name_or_kw().text
                if self._accept("SYM", "="):
                    expr = self.parse_expr()
                    semi = self._eat("SYM", ";")
                    return self._attach_span(
                        FieldAssign(Var(name_tok.text, pos=name_tok.pos), field_name, expr, pos=name_tok.pos),
                        name_tok.start,
                        semi.stop,
                    )
                # method call statement
                args = self.parse_arg_list()
                semi = self._eat("SYM", ";")
                return self._attach_span(
                    CallStmt(f"{name_tok.text}.{field_name}", args, pos=name_tok.pos), name_tok.start, semi.stop
                )
            if self._accept("SYM", "="):
                expr = self.parse_expr()
                semi = self._eat("SYM", ";")
                name_span = self._tok_span(name_tok)
                return self._attach_span(
                    Assign(name_tok.text, expr, pos=name_tok.pos, name_span=name_span), name_tok.start, semi.stop
                )
            # call statement on identifier
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                semi = self._eat("SYM", ";")
                return self._attach_span(CallStmt(name_tok.text, args, pos=name_tok.pos), name_tok.start, semi.stop)
            raise self._error("unexpected token after name", name_tok.pos, self._tok_span(name_tok))
        raise self._error(f"unexpected token {self.tok.kind}", self.tok.pos, self._tok_span(self.tok))

    def parse_param(self) -> Param:
        name_tok = self._eat("NAME")
        annotation = None
        if self._accept("SYM", ":"):
            annotation = self.parse_type_annotation()
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

    def _collect_return_param_usage(self, stmts: List[IR], param_names: Set[str]) -> Set[str]:
        used: Set[str] = set()

        def visit_expr(expr: IR) -> None:
            if isinstance(expr, Var):
                if expr.name in param_names:
                    used.add(expr.name)
                return
            if isinstance(expr, Field):
                visit_expr(expr.obj)
                return
            if isinstance(expr, MethodCall):
                visit_expr(expr.obj)
                for arg in expr.args:
                    visit_expr(arg)
                return
            if isinstance(expr, Call):
                if expr.name in param_names:
                    used.add(expr.name)
                for arg in expr.args:
                    visit_expr(arg)
                return
            if isinstance(expr, Spawn):
                for arg in expr.args:
                    visit_expr(arg)
                return
            if isinstance(expr, Await):
                visit_expr(expr.expr)
                return
            if isinstance(expr, Bin):
                visit_expr(expr.a)
                visit_expr(expr.b)
                return
            if isinstance(expr, ObjLit):
                for _, val in expr.fields:
                    visit_expr(val)
                return
            if isinstance(expr, VariantCtor):
                for _, val in expr.fields:
                    visit_expr(val)
                return
            if isinstance(expr, ClassNew):
                for _, val in expr.init:
                    visit_expr(val)
                return
            if isinstance(expr, NewLit):
                for val in expr.items:
                    visit_expr(val)
                return
            if isinstance(expr, Match):
                visit_expr(expr.expr)
                for case in expr.cases:
                    visit_expr(case.body)
                return

        def visit_stmt(stmt: IR) -> None:
            if isinstance(stmt, Return):
                visit_expr(stmt.expr)
            elif isinstance(stmt, If):
                for child in stmt.then:
                    visit_stmt(child)
                for child in stmt.els:
                    visit_stmt(child)
            elif isinstance(stmt, While):
                for child in stmt.body:
                    visit_stmt(child)
            elif isinstance(stmt, Switch):
                visit_expr(stmt.expr)
                for case in stmt.cases:
                    if case.value is not None:
                        visit_expr(case.value)
                    for child in case.body:
                        visit_stmt(child)
            elif isinstance(stmt, TryCatch):
                for child in stmt.body:
                    visit_stmt(child)
                for child in stmt.handler:
                    visit_stmt(child)
            elif isinstance(stmt, TaskBlock):
                for child in stmt.body:
                    visit_stmt(child)
            elif isinstance(stmt, Namespace):
                for child in stmt.body:
                    visit_stmt(child)
            elif isinstance(stmt, Fn) or isinstance(stmt, MethodDef):
                return

        for st in stmts:
            visit_stmt(st)
        return used

    def parse_type_annotation(self) -> str:
        name = self._eat_name_or_kw().text
        if self._accept("SYM", "?"):
            return f"{name}?"
        return name

    def parse_arg_list(self) -> List[IR]:
        self._eat("SYM", "(")
        args: List[IR] = []
        if not (self.tok.kind == "SYM" and self.tok.text == ")"):
            args.append(self.parse_expr())
            while self._accept("SYM", ","):
                args.append(self.parse_expr())
        self._eat("SYM", ")")
        return args

    def parse_destruct_names(self) -> Tuple[List[str], SourcePos, List[SourceSpan]]:
        start_tok = self._eat("SYM", "{")
        names: List[str] = []
        spans: List[SourceSpan] = []
        first = self._eat("NAME")
        names.append(first.text)
        spans.append(self._tok_span(first))
        while self._accept("SYM", ","):
            name_tok = self._eat("NAME")
            names.append(name_tok.text)
            spans.append(self._tok_span(name_tok))
        self._eat("SYM", "}")
        return names, start_tok.pos, spans

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
            left = self._attach_span(Bin("or", left, right, pos=op_tok.pos), self._span_cover(left, right).start, self._span_cover(left, right).stop)
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
            span = self._span_cover(left, right)
            left = self._attach_span(Bin("and", left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_compare(self) -> IR:
        left = self.parse_term()
        while self.tok.kind == "OP" and self.tok.text in (">", ">=", "<", "<=", "==", "!="):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_term()
            span = self._span_cover(left, right)
            left = self._attach_span(Bin(op, left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_term(self) -> IR:
        left = self.parse_factor()
        while self.tok.kind == "OP" and self.tok.text in ("+", "-"):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_factor()
            span = self._span_cover(left, right)
            left = self._attach_span(Bin(op, left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_factor(self) -> IR:
        left = self.parse_power()
        while self.tok.kind == "OP" and self.tok.text in ("*", "/", "%"):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_power()
            span = self._span_cover(left, right)
            left = self._attach_span(Bin(op, left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_power(self) -> IR:
        left = self.parse_unary()
        if self.tok.kind == "OP" and self.tok.text == "^":
            op_tok = self._eat("OP")
            right = self.parse_power()
            span = self._span_cover(left, right)
            return self._attach_span(Bin("^", left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_unary(self) -> IR:
        if self.tok.kind == "OP" and self.tok.text == "-":
            op_tok = self._eat("OP")
            rhs = self.parse_unary()
            span = self._span_cover(Num("0", pos=op_tok.pos), rhs)
            return self._attach_span(Bin("-", Num("0", pos=op_tok.pos), rhs, pos=op_tok.pos), span.start, span.stop)
        if (self.tok.kind == "KW" and self.tok.text == "not") or (
            self.tok.kind == "OP" and self.tok.text == "!"
        ):
            op_tok = self.tok
            self._eat(self.tok.kind)
            rhs = self.parse_unary()
            span = self._span_cover(Num("0", pos=op_tok.pos), rhs)
            return self._attach_span(Bin("not", Num("0", pos=op_tok.pos), rhs, pos=op_tok.pos), span.start, span.stop)
        return self.parse_postfix()

    def parse_postfix(self) -> IR:
        expr = self.parse_primary()
        while True:
            if self.tok.kind == "SYM" and self.tok.text == ".":
                dot_tok = self._eat("SYM", ".")
                name_tok = self._eat_name_or_kw()
                if self.tok.kind == "SYM" and self.tok.text == "(":
                    args = self.parse_arg_list()
                    expr = self._attach_span(
                        MethodCall(expr, name_tok.text, args, pos=dot_tok.pos),
                        self._node_start(expr),
                        self._last_tok.stop,
                    )
                else:
                    expr = self._attach_span(
                        Field(expr, name_tok.text, pos=dot_tok.pos),
                        self._node_start(expr),
                        name_tok.stop,
                    )
                continue
            break
        return expr

    def parse_match(self) -> Match:
        kw = self._eat("KW", "match")
        prev_allow = self._allow_variant_ctor
        self._allow_variant_ctor = False
        try:
            target = self.parse_expr()
        finally:
            self._allow_variant_ctor = prev_allow
        self._eat("SYM", "{")
        cases: List[MatchCase] = []
        while not self._accept("SYM", "}"):
            if not (self.tok.kind == "KW" and self.tok.text == "case"):
                raise self._error("expected case", self.tok.pos, self._tok_span(self.tok))
            self._eat("KW", "case")
            pattern = self.parse_pattern()
            if self._accept("SYM", ":"):
                pass
            elif self._accept("SYM", "="):
                if not self._accept("OP", ">"):
                    raise self._error("expected '=>'", self.tok.pos, self._tok_span(self.tok))
            else:
                raise self._error("expected ':' or '=>'", self.tok.pos, self._tok_span(self.tok))
            body = self.parse_expr()
            semi = self._eat("SYM", ";")
            cases.append(self._attach_span(MatchCase(pattern, body, pos=pattern.pos), pattern.pos, semi.stop))
        return self._attach_span(Match(target, cases, pos=kw.pos), kw.start, self._last_tok.stop)

    def parse_pattern(self) -> Pattern:
        if self.tok.kind == "NAME" and self.tok.text == "_":
            tok = self._eat("NAME")
            return self._attach_span(WildcardPattern(name=None, pos=tok.pos), tok.start, tok.stop)
        if self.tok.kind != "NAME":
            raise self._error("expected pattern", self.tok.pos, self._tok_span(self.tok))
        vname_tok = self._eat("NAME")
        bindings: Dict[str, Optional[str]] = {}
        positional: Optional[List[Optional[str]]] = None
        if self._accept("SYM", "{"):
            while not self._accept("SYM", "}"):
                fname = self._eat("NAME").text
                bind_name: Optional[str] = fname
                if self._accept("SYM", ":"):
                    bind_tok = self._eat_name_or_kw()
                    bind_name = None if bind_tok.text == "_" else bind_tok.text
                bindings[fname] = bind_name
                if self._accept("SYM", "}"):
                    break
                if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                    raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
        elif self._accept("SYM", "("):
            positional = []
            while not self._accept("SYM", ")"):
                bind_tok = self._eat_name_or_kw()
                positional.append(None if bind_tok.text == "_" else bind_tok.text)
                if self._accept("SYM", ")"):
                    break
                if not (self._accept("SYM", ",") or self._accept("SYM", ";")):
                    raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
        return self._attach_span(
            VariantPattern(vname_tok.text, bindings, positional_bindings=positional, pos=vname_tok.pos),
            vname_tok.start,
            self._last_tok.stop,
        )

    def parse_primary(self) -> IR:
        if self._accept("SYM", "("):
            inner = self.parse_expr()
            self._eat("SYM", ")")
            return inner
        if self.tok.kind == "KW" and self.tok.text == "await":
            kw = self._eat("KW", "await")
            expr = self.parse_expr()
            end = self._node_stop(expr)
            return self._attach_span(Await(expr, pos=kw.pos), kw.start, end)
        if self.tok.kind == "KW" and self.tok.text == "match":
            return self.parse_match()
        if self.tok.kind == "NUMBER":
            t = self._eat("NUMBER")
            return self._attach_span(Num(t.text, pos=t.pos), t.start, t.stop)
        if self.tok.kind == "STRING":
            t = self._eat("STRING")
            return self._attach_span(Str(t.text, pos=t.pos), t.start, t.stop)
        if self.tok.kind == "KW" and self.tok.text in {"true", "false"}:
            kw = self.tok
            val = kw.text == "true"
            self._eat("KW")
            return self._attach_span(Bool(val, pos=kw.pos), kw.start, kw.stop)
        if self.tok.kind == "KW" and self.tok.text == "Null":
            kw = self._eat("KW")
            return self._attach_span(Null(pos=kw.pos), kw.start, kw.stop)
        if self.tok.kind in {"NAME", "KW"}:
            name_tok = self._eat(self.tok.kind)
            name = name_tok.text
            if name == "spawn":
                target = self._eat_name_or_kw().text
                args = self.parse_arg_list()
                return self._attach_span(Spawn(target, args, pos=name_tok.pos), name_tok.start, self._last_tok.stop)
            if name == "new" and self.tok.kind == "SYM" and self.tok.text == "[":
                start_tok = self._eat("SYM", "[")
                items: List[IR] = []
                if not (self.tok.kind == "SYM" and self.tok.text == "]"):
                    items.append(self.parse_expr())
                    while self._accept("SYM", ","):
                        items.append(self.parse_expr())
                self._eat("SYM", "]")
                return self._attach_span(NewLit(items, pos=start_tok.pos), start_tok.start, self._last_tok.stop)
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                return self._attach_span(Call(name, args, pos=name_tok.pos), name_tok.start, self._last_tok.stop)
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
                        raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
                return self._attach_span(ClassNew(cname, init, pos=name_tok.pos), name_tok.start, self._last_tok.stop)
            if self._allow_variant_ctor and self.tok.kind == "SYM" and self.tok.text == "{":
                fields = self.parse_variant_init_fields()
                return self._attach_span(VariantCtor(name, fields, pos=name_tok.pos), name_tok.start, self._last_tok.stop)
            return self._attach_span(Var(name, pos=name_tok.pos), name_tok.start, name_tok.stop)
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
                    raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
            return self._attach_span(ObjLit(fields, pos=start_tok.pos), start_tok.start, self._last_tok.stop)
        raise self._error(f"unexpected token {self.tok.kind}", self.tok.pos, self._tok_span(self.tok))

    def parse_field_name(self) -> str:
        name = self._eat("NAME").text
        if self._accept("SYM", "."):
            sub = self._eat("NAME").text
            return f"{name}.{sub}"
        return name

    def parse_variant_fields(self) -> List[Tuple[str, str]]:
        fields: List[Tuple[str, str]] = []
        if self._accept("SYM", "{") or self._accept("SYM", "("):
            closing = "}" if self._last_tok.text == "{" else ")"
            while not self._accept("SYM", closing):
                fname = self._eat("NAME").text
                self._eat("SYM", ":")
                ftype = self._eat_name_or_kw().text
                fields.append((fname, ftype))
                if self._accept("SYM", closing):
                    break
                if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                    raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
        return fields

    def parse_variant_init_fields(self) -> List[Tuple[str, IR]]:
        start_tok = self._eat("SYM", "{")
        fields: List[Tuple[str, IR]] = []
        while not self._accept("SYM", "}"):
            fname = self._eat("NAME").text
            self._eat("SYM", ":")
            fexpr = self.parse_expr()
            fields.append((fname, fexpr))
            if self._accept("SYM", "}"):
                break
            if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
        return fields

    def parse_module_path(self) -> Tuple[str, SourceSpan]:
        prefix = ""
        start_tok: Optional[Token] = None
        while self._accept("SYM", "."):
            start_tok = start_tok or self._last_tok
            prefix += "."
        if self.tok.kind != "NAME":
            raise self._error("expected NAME", self.tok.pos, self._tok_span(self.tok))
        first_tok = self._eat("NAME")
        parts = [first_tok.text]
        last_tok = first_tok
        while self._accept("SYM", "."):
            last_tok = self._eat("NAME")
            parts.append(last_tok.text)
        start = (start_tok or first_tok).start
        span = SourceSpan(start, last_tok.stop)
        return prefix + ".".join(parts), span

    def parse_qualified_name(self) -> str:
        parts = [self._eat("NAME").text]
        while self._accept("SYM", "."):
            parts.append(self._eat("NAME").text)
        return ".".join(parts)

# --- segment: tiny_language_codegen_py.py ---
"""Python code generation backend for TinyLanguage AST nodes.

The goal of this module is to turn TinyLanguage's intermediate
representation into a standalone Python module that can be compiled with
``compile``/``exec`` or written to disk. The generated code executes on top
of the existing ``Runtime`` and standard library to keep semantics aligned
with the interpreter, but it skips the interpreter's AST walking at
runtime.

The backend is intentionally minimal: it focuses on expressions and
statements that cover the tutorial-style examples (literals, arithmetic,
``if``/``while``, functions, and print). Constructs like pattern
matching, classes, async, and namespaces are intentionally unsupported for
now and will raise ``NotImplementedError`` during generation.
"""

import ast
from typing import TYPE_CHECKING, Iterable, List


class PythonCodeGenerator:
    """Generate Python ``ast.Module`` objects from TinyLanguage statements."""

    def __init__(self) -> None:
        self._function_counter = 0

    def module_for_program(self, stmts: List["IR"], *, module_name: str = "tiny_codegen_module") -> ast.Module:
        """Convert a sequence of TinyLanguage statements into a Python module.

        The resulting module exposes a ``tiny_main()`` function that returns
        the collected program output as a string. A fresh ``Runtime`` and
        ``Environment`` are created inside that function so callers can
        ``exec`` the compiled code directly.
        """

        main_body: List[ast.stmt] = []
        main_body.extend(self._bootstrap_runtime())

        # Helper dispatch to resolve native vs. user-defined functions.
        main_body.append(self._call_helper())

        # Emit function definitions first to make them available to later
        # statements regardless of declaration order.
        function_defs: List[ast.stmt] = []
        remaining: List["IR"] = []
        for stmt in stmts:
            if isinstance(stmt, Fn):
                function_defs.extend(self._emit_function(stmt))
            else:
                remaining.append(stmt)
        main_body.extend(function_defs)

        for stmt in remaining:
            main_body.extend(self._emit_stmt(stmt, env_name="env"))

        main_body.append(
            ast.Return(
                value=ast.Call(
                    func=ast.Attribute(value=ast.Constant(value=""), attr="join", ctx=ast.Load()),
                    args=[ast.Attribute(value=ast.Name(id="runtime", ctx=ast.Load()), attr="output", ctx=ast.Load())],
                    keywords=[],
                )
            )
        )

        main_func = ast.FunctionDef(
            name="tiny_main",
            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=main_body,
            decorator_list=[],
        )

        module = ast.Module(
            body=[self._import_runtime(), main_func],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)
        return module

    def to_source(self, module: ast.AST) -> str:
        """Return formatted Python source for the given module AST."""

        return ast.unparse(module)

    # ----- Imports and helpers -----
    def _import_runtime(self) -> ast.ImportFrom:
        return ast.ImportFrom(
            module="tiny_language",
            names=[
                ast.alias(name="Environment", asname=None),
                ast.alias(name="NamespaceRef", asname=None),
                ast.alias(name="Runtime", asname=None),
                ast.alias(name="register_stdlib", asname=None),
            ],
            level=0,
        )

    def _bootstrap_runtime(self) -> List[ast.stmt]:
        return [
            ast.Assign(
                targets=[ast.Name(id="runtime", ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id="Runtime", ctx=ast.Load()), args=[ast.Constant(value="")], keywords=[]),
            ),
            ast.Assign(
                targets=[ast.Name(id="env", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="Environment", ctx=ast.Load()),
                    args=[ast.Constant(value=None)],
                    keywords=[ast.keyword(arg="namespace", value=ast.Constant(value=None))],
                ),
            ),
            ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="register_stdlib", ctx=ast.Load()),
                    args=[
                        ast.Name(id="runtime", ctx=ast.Load()),
                        ast.Name(id="env", ctx=ast.Load()),
                        ast.Name(id="NamespaceRef", ctx=ast.Load()),
                    ],
                    keywords=[],
                )
            ),
            ast.Assign(
                targets=[ast.Name(id="functions", ctx=ast.Store())],
                value=ast.Dict(keys=[], values=[]),
            ),
        ]

    def _call_helper(self) -> ast.stmt:
        args = ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="name"),
                ast.arg(arg="arguments"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        )
        body: List[ast.stmt] = [
            ast.If(
                test=ast.Call(
                    func=ast.Attribute(value=ast.Name(id="functions", ctx=ast.Load()), attr="__contains__", ctx=ast.Load()),
                    args=[ast.Name(id="name", ctx=ast.Load())],
                    keywords=[],
                ),
                body=[
                    ast.Return(
                        value=ast.Call(
                            func=ast.Subscript(
                                value=ast.Name(id="functions", ctx=ast.Load()),
                                slice=ast.Index(value=ast.Name(id="name", ctx=ast.Load())),
                                ctx=ast.Load(),
                            ),
                            args=[ast.Starred(value=ast.Name(id="arguments", ctx=ast.Load()), ctx=ast.Load())],
                            keywords=[],
                        )
                    )
                ],
                orelse=[],
            ),
            ast.If(
                test=ast.Call(
                    func=ast.Attribute(
                        value=ast.Attribute(value=ast.Name(id="runtime", ctx=ast.Load()), attr="native_functions", ctx=ast.Load()),
                        attr="__contains__",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Name(id="name", ctx=ast.Load())],
                    keywords=[],
                ),
                body=[
                    ast.Return(
                        value=ast.Call(
                            func=ast.Subscript(
                                value=ast.Attribute(value=ast.Name(id="runtime", ctx=ast.Load()), attr="native_functions", ctx=ast.Load()),
                                slice=ast.Index(value=ast.Name(id="name", ctx=ast.Load())),
                                ctx=ast.Load(),
                            ),
                            args=[ast.Starred(value=ast.Name(id="arguments", ctx=ast.Load()), ctx=ast.Load())],
                            keywords=[],
                        )
                    )
                ],
                orelse=[],
            ),
            ast.Raise(
                exc=ast.Call(
                    func=ast.Name(id="RuntimeError", ctx=ast.Load()),
                    args=[ast.BinOp(left=ast.Constant(value="unknown function "), op=ast.Add(), right=ast.Name(id="name", ctx=ast.Load()))],
                    keywords=[],
                ),
                cause=None,
            ),
        ]
        return ast.FunctionDef(name="_call_fn", args=args, body=body, decorator_list=[])

    # ----- Statement and expression translation -----
    def _emit_function(self, fn: "Fn") -> List[ast.stmt]:
        env_name = f"env_fn_{self._function_counter}"
        self._function_counter += 1
        params = [ast.arg(arg=p.name) for p in fn.params]
        body: List[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id=env_name, ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="Environment", ctx=ast.Load()),
                    args=[ast.Name(id="env", ctx=ast.Load())],
                    keywords=[ast.keyword(arg="namespace", value=ast.Constant(value=fn.namespace))],
                ),
            )
        ]
        for p in fn.params:
            body.append(
                ast.Assign(
                    targets=[ast.Subscript(value=ast.Attribute(value=ast.Name(id=env_name, ctx=ast.Load()), attr="values", ctx=ast.Load()), slice=ast.Index(value=ast.Constant(value=p.name)), ctx=ast.Store())],
                    value=ast.Name(id=p.name, ctx=ast.Load()),
                )
            )
        for st in fn.body:
            body.extend(self._emit_stmt(st, env_name=env_name))
        fn_def = ast.FunctionDef(
            name=fn.name,
            args=ast.arguments(posonlyargs=[], args=params, kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=body,
            decorator_list=[],
        )
        register = ast.Assign(
            targets=[ast.Subscript(value=ast.Name(id="functions", ctx=ast.Load()), slice=ast.Index(value=ast.Constant(value=fn.name)), ctx=ast.Store())],
            value=ast.Name(id=fn.name, ctx=ast.Load()),
        )
        return [fn_def, register]

    def _emit_stmt(self, stmt: "IR", *, env_name: str) -> List[ast.stmt]:
        if isinstance(stmt, Let):
            return [
                ast.Assign(
                    targets=[ast.Subscript(value=ast.Attribute(value=ast.Name(id=env_name, ctx=ast.Load()), attr="values", ctx=ast.Load()), slice=ast.Index(value=ast.Constant(value=stmt.name)), ctx=ast.Store())],
                    value=self._emit_expr(stmt.expr, env_name=env_name),
                )
            ]
        if isinstance(stmt, Assign):
            return [
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(value=ast.Name(id=env_name, ctx=ast.Load()), attr="set", ctx=ast.Load()),
                        args=[ast.Constant(value=stmt.name), self._emit_expr(stmt.expr, env_name=env_name)],
                        keywords=[],
                    )
                )
            ]
        if isinstance(stmt, Print):
            vals = [self._emit_expr(expr, env_name=env_name) for expr in stmt.exprs]
            joined = ast.Call(
                func=ast.Attribute(value=ast.Constant(value=" "), attr="join", ctx=ast.Load()),
                args=[
                    ast.ListComp(
                        elt=ast.Call(
                            func=ast.Attribute(value=ast.Name(id="runtime", ctx=ast.Load()), attr="format_value", ctx=ast.Load()),
                            args=[ast.Name(id="_val", ctx=ast.Load())],
                            keywords=[],
                        ),
                        generators=[ast.comprehension(target=ast.Name(id="_val", ctx=ast.Store()), iter=ast.List(elts=vals, ctx=ast.Load()), ifs=[], is_async=0)],
                    )
                ],
                keywords=[],
            )
            return [
                ast.Assign(targets=[ast.Name(id="_text", ctx=ast.Store())], value=joined),
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(value=ast.Attribute(value=ast.Name(id="runtime", ctx=ast.Load()), attr="output", ctx=ast.Load()), attr="append", ctx=ast.Load()),
                        args=[ast.BinOp(left=ast.Name(id="_text", ctx=ast.Load()), op=ast.Add(), right=ast.Constant(value="\n"))],
                        keywords=[],
                    )
                ),
            ]
        if isinstance(stmt, Flush):
            return [
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(value=ast.Name(id="runtime", ctx=ast.Load()), attr="flush_streams", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    )
                )
            ]
        if isinstance(stmt, If):
            return [
                ast.If(
                    test=ast.Call(
                        func=ast.Attribute(value=ast.Name(id="runtime", ctx=ast.Load()), attr="_is_truthy", ctx=ast.Load()),
                        args=[self._emit_expr(stmt.cond, env_name=env_name)],
                        keywords=[],
                    ),
                    body=self._emit_block(stmt.then, env_name=env_name),
                    orelse=self._emit_block(stmt.els, env_name=env_name),
                )
            ]
        if isinstance(stmt, While):
            return [
                ast.While(
                    test=ast.Call(
                        func=ast.Attribute(value=ast.Name(id="runtime", ctx=ast.Load()), attr="_is_truthy", ctx=ast.Load()),
                        args=[self._emit_expr(stmt.cond, env_name=env_name)],
                        keywords=[],
                    ),
                    body=self._emit_block(stmt.body, env_name=env_name),
                    orelse=[],
                )
            ]
        if isinstance(stmt, Return):
            return [ast.Return(value=self._emit_expr(stmt.expr, env_name=env_name))]
        if isinstance(stmt, CallStmt):
            return [ast.Expr(value=self._emit_expr(Call(stmt.name, stmt.args), env_name=env_name))]
        raise NotImplementedError(f"statement {type(stmt).__name__} is not supported by the Python backend yet")

    def _emit_block(self, block: Iterable["IR"], *, env_name: str) -> List[ast.stmt]:
        stmts: List[ast.stmt] = []
        for st in block:
            stmts.extend(self._emit_stmt(st, env_name=env_name))
        return stmts

    def _emit_expr(self, expr: "IR", *, env_name: str) -> ast.expr:
        if isinstance(expr, Num):
            if "." in expr.txt or "e" in expr.txt or "E" in expr.txt:
                value = float(expr.txt)
                if ("e" in expr.txt or "E" in expr.txt) and "." not in expr.txt and value.is_integer():
                    value = int(value)
            else:
                value = int(expr.txt)
            return ast.Constant(value=value)
        if isinstance(expr, Str):
            return ast.Constant(value=expr.txt)
        if isinstance(expr, Bool):
            return ast.Constant(value=expr.value)
        if isinstance(expr, Null):
            return ast.Constant(value=None)
        if isinstance(expr, Var):
            return ast.Call(
                func=ast.Attribute(value=ast.Name(id=env_name, ctx=ast.Load()), attr="get", ctx=ast.Load()),
                args=[ast.Constant(value=expr.name)],
                keywords=[],
            )
        if isinstance(expr, Call):
            args = [self._emit_expr(arg, env_name=env_name) for arg in expr.args]
            return ast.Call(
                func=ast.Name(id="_call_fn", ctx=ast.Load()),
                args=[ast.Constant(value=expr.name), ast.List(elts=args, ctx=ast.Load())],
                keywords=[],
            )
        if isinstance(expr, Bin):
            return ast.BinOp(left=self._emit_expr(expr.a, env_name=env_name), op=self._bin_op(expr.op), right=self._emit_expr(expr.b, env_name=env_name))
        if isinstance(expr, NewLit):
            return ast.List(elts=[self._emit_expr(item, env_name=env_name) for item in expr.items], ctx=ast.Load())
        if isinstance(expr, ObjLit):
            return ast.Dict(keys=[ast.Constant(value=k) for k, _ in expr.fields], values=[self._emit_expr(v, env_name=env_name) for _, v in expr.fields])
        raise NotImplementedError(f"expression {type(expr).__name__} is not supported by the Python backend yet")

    def _bin_op(self, op: str) -> ast.operator:
        mapping = {
            "+": ast.Add(),
            "-": ast.Sub(),
            "*": ast.Mult(),
            "/": ast.Div(),
            "%": ast.Mod(),
            "^": ast.Pow(),
        }
        if op in mapping:
            return mapping[op]
        raise NotImplementedError(f"binary operator {op} is not supported in Python backend yet")


if TYPE_CHECKING:  # pragma: no cover - only used for type checking
    from tiny_language_ast import (
        Bin,
        Bool,
        Call,
        CallStmt,
        Flush,
        Fn,
        IR,
        Let,
        NewLit,
        Null,
        Num,
        ObjLit,
        Print,
        Return,
        Str,
        Var,
        While,
        If,
    )

# --- segment: tiny_language_codegen_native.py ---
"""Experimental native code generator and bytecode VM for TinyLanguage.

This module translates a subset of the AST into a small stack-based
bytecode and executes it with a tiny VM. It is intentionally scoped to
cover the tutorial-style examples first (literals, arithmetic, control
flow, simple functions, and `print`). Unsupported constructs raise
``NotImplementedError`` so gaps remain visible with precise source positions.
"""

from typing import Dict, List, Optional

from native_ir import ClassIR, FunctionIR, Instruction, Opcode, OperatorOverloadIR, ProgramIR, TypeIR
from tiny_errors import SourcePos, SourceSpan, format_error


class NativeCodeGenerator:
    """Convert TinyLanguage AST nodes into bytecode instructions."""

    def __init__(
        self,
        *,
        allow_heap: bool = False,
        allow_match: bool = False,
        module_namespace: str | None = None,
        source: str | None = None,
    ) -> None:
        self._allow_heap = allow_heap
        self._allow_match = allow_match
        self._module_namespace = module_namespace
        self._tmp_index = 0
        self._variant_fields: Dict[str, List[str]] = {}
        self._async_functions: set[str] = set()
        self._task_scope_depth = 0
        self._source = source

    def compile_program(self, stmts: List["IR"]) -> ProgramIR:
        functions: Dict[str, FunctionIR] = {}
        entry_instructions: List[Instruction] = []
        classes: Dict[str, ClassIR] = {}
        types: Dict[str, TypeIR] = {}
        operator_overloads: List[OperatorOverloadIR] = []
        self._async_functions = {
            self._qualify_name(stmt.name) for stmt in stmts if isinstance(stmt, Fn) and stmt.is_async
        }
        self._task_scope_depth = 0

        for stmt in stmts:
            if isinstance(stmt, Fn):
                functions[self._qualify_name(stmt.name)] = self._compile_function(stmt)
            elif isinstance(stmt, OpDef):
                overload_name = self._operator_name(stmt)
                functions[overload_name] = self._compile_operator(stmt, overload_name)
                operator_overloads.append(
                    OperatorOverloadIR(
                        op=stmt.op, a_type=stmt.a_type, b_type=stmt.b_type, func_name=overload_name
                    )
                )
            elif isinstance(stmt, ClassDef):
                self._register_class(stmt, classes)
                for method in stmt.methods:
                    functions[self._method_name(method.class_name, method.name)] = self._compile_method(method)
            elif isinstance(stmt, MethodDef):
                self._register_method_class(stmt, classes)
                functions[self._method_name(stmt.class_name, stmt.name)] = self._compile_method(stmt)
            elif isinstance(stmt, TypeDef):
                if not self._allow_match:
                    raise self._error("native codegen does not yet support type definitions", node=stmt)
                self._register_type(stmt, types)
            else:
                raw = self._compile_stmt(stmt)
                entry_instructions.extend(self._shift_labels(raw, len(entry_instructions)))

        entry_instructions.append(self._instr(Opcode.RETURN))
        return ProgramIR(
            entry=entry_instructions,
            functions=functions,
            classes=classes,
            types=types,
            operator_overloads=operator_overloads,
        )

    def _compile_function(self, fn: "Fn") -> FunctionIR:
        body_instrs: List[Instruction] = []
        self._task_scope_depth = 0
        for stmt in fn.body:
            raw = self._compile_stmt(stmt)
            body_instrs.extend(self._shift_labels(raw, len(body_instrs)))
        body_instrs.append(self._instr(Opcode.RETURN, node=fn))
        return FunctionIR(
            name=self._qualify_name(fn.name),
            params=[param.name for param in fn.params],
            instructions=body_instrs,
        )

    def _compile_method(self, md: "MethodDef") -> FunctionIR:
        body_instrs: List[Instruction] = []
        self._task_scope_depth = 0
        for stmt in md.body:
            raw = self._compile_stmt(stmt)
            body_instrs.extend(self._shift_labels(raw, len(body_instrs)))
        body_instrs.append(self._instr(Opcode.RETURN, node=md))
        return FunctionIR(
            name=self._method_name(md.class_name, md.name),
            params=[param.name for param in md.params],
            instructions=body_instrs,
        )

    def _compile_operator(self, opdef: "OpDef", name: str) -> FunctionIR:
        body_instrs: List[Instruction] = []
        self._task_scope_depth = 0
        for stmt in opdef.body:
            raw = self._compile_stmt(stmt)
            body_instrs.extend(self._shift_labels(raw, len(body_instrs)))
        body_instrs.append(self._instr(Opcode.RETURN, node=opdef))
        return FunctionIR(name=name, params=[opdef.a_name, opdef.b_name], instructions=body_instrs)

    def _shift_labels(self, instructions: List[Instruction], offset: int) -> List[Instruction]:
        shifted: List[Instruction] = []
        for instr in instructions:
            if instr.op in {Opcode.JUMP, Opcode.JUMP_IF_FALSE} and instr.arg is not None:
                shifted.append(Instruction(instr.op, instr.arg + offset, span=instr.span))
            else:
                shifted.append(instr)
        return shifted

    def _compile_stmt(self, stmt: "IR") -> List[Instruction]:
        if isinstance(stmt, Let):
            return self._compile_binding(stmt.name, stmt.expr, stmt)
        if isinstance(stmt, Assign):
            return self._compile_binding(stmt.name, stmt.expr, stmt)
        if isinstance(stmt, Import):
            binding = self._import_binding_name(stmt.module, stmt.alias)
            return [
                self._instr(Opcode.PUSH_CONST, stmt.module, stmt),
                self._instr(Opcode.CALL, ("__import", 1), stmt),
                self._instr(Opcode.STORE, binding, stmt),
            ]
        if isinstance(stmt, Print):
            instructions: List[Instruction] = []
            for expr in stmt.exprs:
                instructions.extend(self._compile_expr(expr))
            instructions.append(self._instr(Opcode.PRINT, len(stmt.exprs), stmt))
            return instructions
        if isinstance(stmt, Flush):
            return [self._instr(Opcode.FLUSH, node=stmt)]
        if isinstance(stmt, If):
            return self._compile_if(stmt)
        if isinstance(stmt, While):
            return self._compile_while(stmt)
        if isinstance(stmt, Return):
            instructions: List[Instruction] = []
            instructions.extend(self._compile_expr(stmt.expr))
            if self._task_scope_depth:
                instructions.extend(self._task_scope_exit_instrs())
            instructions.append(self._instr(Opcode.RETURN, node=stmt))
            return instructions
        if isinstance(stmt, CallStmt):
            if "." in stmt.name:
                obj_name, method_name = stmt.name.split(".", 1)
                expr = MethodCall(Var(obj_name, pos=stmt.pos), method_name, stmt.args, pos=stmt.pos)
            else:
                expr = Call(self._qualify_name(stmt.name), stmt.args, pos=stmt.pos)
            instructions = self._compile_expr(expr)
            instructions.append(self._instr(Opcode.POP, node=stmt))
            return instructions
        if isinstance(stmt, FieldAssign):
            instructions = self._compile_expr(stmt.obj)
            instructions.append(self._instr(Opcode.PUSH_CONST, stmt.name, stmt))
            instructions.extend(self._compile_expr(stmt.expr))
            instructions.append(self._instr(Opcode.CALL, ("__field_set", 3), stmt))
            instructions.append(self._instr(Opcode.POP, node=stmt))
            return instructions
        if isinstance(stmt, TaskBlock):
            instructions: List[Instruction] = [self._instr(Opcode.CALL, ("__task_scope_enter", 0), stmt)]
            self._task_scope_depth += 1
            for inner in stmt.body:
                nested = self._compile_stmt(inner)
                instructions.extend(self._shift_labels(nested, len(instructions)))
            self._task_scope_depth -= 1
            instructions.append(self._instr(Opcode.CALL, ("__task_scope_exit", 0), stmt))
            return instructions
        raise self._error(f"native codegen does not yet support {type(stmt).__name__}", node=stmt)

    def _compile_if(self, stmt: "If") -> List[Instruction]:
        instructions = self._compile_expr(stmt.cond)
        jump_false_index = len(instructions)
        instructions.append(self._instr(Opcode.JUMP_IF_FALSE, None, stmt))

        then_block = []
        for inner in stmt.then:
            nested = self._compile_stmt(inner)
            then_block.extend(self._shift_labels(nested, len(instructions) + len(then_block)))
        then_block.append(self._instr(Opcode.JUMP, None, stmt))

        else_block = []
        for inner in stmt.els:
            nested = self._compile_stmt(inner)
            else_block.extend(self._shift_labels(nested, len(instructions) + len(then_block) + len(else_block)))

        else_start = len(instructions) + len(then_block)
        instructions[jump_false_index] = Instruction(
            Opcode.JUMP_IF_FALSE, else_start, span=instructions[jump_false_index].span
        )

        end_of_then = len(instructions) + len(then_block) + len(else_block)
        then_block[-1] = Instruction(Opcode.JUMP, end_of_then, span=then_block[-1].span)

        instructions.extend(then_block)
        instructions.extend(else_block)
        return instructions

    def _compile_while(self, stmt: "While") -> List[Instruction]:
        instructions: List[Instruction] = []
        loop_start = 0
        cond_instrs = self._compile_expr(stmt.cond)
        instructions.extend(cond_instrs)
        jump_out_index = len(instructions)
        instructions.append(self._instr(Opcode.JUMP_IF_FALSE, None, stmt))

        body_instrs: List[Instruction] = []
        for inner in stmt.body:
            nested = self._compile_stmt(inner)
            body_instrs.extend(self._shift_labels(nested, len(instructions) + len(body_instrs)))
        body_instrs.append(self._instr(Opcode.JUMP, loop_start, stmt))

        loop_exit = len(instructions) + len(body_instrs)
        instructions[jump_out_index] = Instruction(
            Opcode.JUMP_IF_FALSE, loop_exit, span=instructions[jump_out_index].span
        )

        instructions.extend(body_instrs)
        return instructions

    def _compile_binding(self, name: str, expr: "IR", node: Optional["IR"] = None) -> List[Instruction]:
        instructions = self._compile_expr(expr)
        instructions.append(self._instr(Opcode.STORE, name, node or expr))
        return instructions

    def _compile_expr(self, expr: "IR") -> List[Instruction]:
        if isinstance(expr, Num):
            if "." in expr.txt or "e" in expr.txt or "E" in expr.txt:
                value = float(expr.txt)
                if ("e" in expr.txt or "E" in expr.txt) and "." not in expr.txt and value.is_integer():
                    value = int(value)
            else:
                value = int(expr.txt)
            return [self._instr(Opcode.PUSH_CONST, value, expr)]
        if isinstance(expr, Str):
            return [self._instr(Opcode.PUSH_CONST, expr.txt, expr)]
        if isinstance(expr, Bool):
            return [self._instr(Opcode.PUSH_CONST, expr.value, expr)]
        if isinstance(expr, Null):
            return [self._instr(Opcode.PUSH_CONST, None, expr)]
        if isinstance(expr, New):
            if not self._allow_heap:
                raise self._error("native codegen does not yet support heap allocations", node=expr)
            instructions = self._compile_expr(expr.size)
            instructions.append(self._instr(Opcode.CALL, ("__new", 1), expr))
            return instructions
        if isinstance(expr, NewLit):
            if not self._allow_heap:
                raise self._error("native codegen does not yet support heap allocations", node=expr)
            temp_name = self._next_tmp()
            instructions: List[Instruction] = [
                self._instr(Opcode.PUSH_CONST, len(expr.items), expr),
                self._instr(Opcode.CALL, ("__new", 1), expr),
                self._instr(Opcode.STORE, temp_name, expr),
            ]
            for idx, item in enumerate(expr.items):
                instructions.append(self._instr(Opcode.LOAD, temp_name, item))
                instructions.append(self._instr(Opcode.PUSH_CONST, idx, item))
                instructions.extend(self._compile_expr(item))
                instructions.append(self._instr(Opcode.CALL, ("heap_set", 3), item))
                instructions.append(self._instr(Opcode.POP, node=item))
            instructions.append(self._instr(Opcode.LOAD, temp_name, expr))
            return instructions
        if isinstance(expr, Var):
            return [self._instr(Opcode.LOAD, expr.name, expr)]
        if isinstance(expr, Field):
            instructions = self._compile_expr(expr.obj)
            instructions.append(self._instr(Opcode.PUSH_CONST, expr.name, expr))
            instructions.append(self._instr(Opcode.CALL, ("__field_get", 2), expr))
            return instructions
        if isinstance(expr, MethodCall):
            instructions = self._compile_expr(expr.obj)
            instructions.append(self._instr(Opcode.PUSH_CONST, expr.name, expr))
            for arg in expr.args:
                instructions.extend(self._compile_expr(arg))
            instructions.append(self._instr(Opcode.CALL, ("__method_call", 2 + len(expr.args)), expr))
            return instructions
        if isinstance(expr, ClassNew):
            instructions: List[Instruction] = [self._instr(Opcode.PUSH_CONST, expr.name, expr)]
            for name, value in expr.init:
                instructions.append(self._instr(Opcode.PUSH_CONST, name, expr))
                instructions.extend(self._compile_expr(value))
            instructions.append(self._instr(Opcode.CALL, ("__class_new", 1 + 2 * len(expr.init)), expr))
            return instructions
        if isinstance(expr, VariantCtor):
            if not self._allow_match:
                raise self._error("native codegen does not yet support variant constructors", node=expr)
            return self._compile_variant_ctor(expr)
        if isinstance(expr, Match):
            if not self._allow_match:
                raise self._error("native codegen does not yet support match expressions", node=expr)
            return self._compile_match(expr)
        if isinstance(expr, Spawn):
            return self._compile_spawn(self._qualify_name(expr.name), expr.args, node=expr)
        if isinstance(expr, Await):
            instructions = self._compile_expr(expr.expr)
            instructions.append(self._instr(Opcode.CALL, ("join", 1), expr))
            return instructions
        if isinstance(expr, Bin):
            instructions = self._compile_expr(expr.a)
            instructions.extend(self._compile_expr(expr.b))
            instructions.append(self._instr(Opcode.BINARY, expr.op, expr))
            return instructions
        if isinstance(expr, Call):
            if expr.name == "flush":
                if expr.args:
                    raise self._error("flush expects no arguments", node=expr)
                return [self._instr(Opcode.FLUSH, None, expr), self._instr(Opcode.PUSH_CONST, None, expr)]
            if expr.name in {"__new", "new", "heap_get", "heap_set", "delete"} and not self._allow_heap:
                raise self._error("native codegen does not yet support heap allocations", node=expr)
            call_name = self._qualify_name(expr.name)
            if call_name in self._async_functions:
                return self._compile_spawn(call_name, expr.args, node=expr)
            instructions: List[Instruction] = []
            for arg in expr.args:
                instructions.extend(self._compile_expr(arg))
            instructions.append(self._instr(Opcode.CALL, (call_name, len(expr.args)), expr))
            return instructions
        raise self._error(
            f"native codegen does not yet support expression {type(expr).__name__}",
            node=expr,
        )

    def _next_tmp(self) -> str:
        self._tmp_index += 1
        return f"__tmp_heap_{self._tmp_index}"

    def _compile_variant_ctor(self, expr: "VariantCtor") -> List[Instruction]:
        instructions: List[Instruction] = [
            self._instr(Opcode.PUSH_CONST, expr.variant, expr),
            self._instr(Opcode.PUSH_CONST, expr.type_name, expr),
        ]
        for name, value in expr.fields:
            instructions.append(self._instr(Opcode.PUSH_CONST, name, expr))
            instructions.extend(self._compile_expr(value))
        instructions.append(self._instr(Opcode.CALL, ("__variant_new", 2 + 2 * len(expr.fields)), expr))
        return instructions

    def _compile_spawn(self, name: str, args: List["IR"], *, node: Optional["IR"] = None) -> List[Instruction]:
        instructions: List[Instruction] = [self._instr(Opcode.PUSH_CONST, name, node)]
        for arg in args:
            instructions.extend(self._compile_expr(arg))
        instructions.append(self._instr(Opcode.CALL, ("__spawn", 1 + len(args)), node))
        return instructions

    def _compile_match(self, expr: "Match") -> List[Instruction]:
        instructions = self._compile_expr(expr.expr)
        tmp_name = self._next_tmp()
        instructions.append(self._instr(Opcode.STORE, tmp_name, expr))
        result_tmp = self._next_tmp()

        end_jump_indices: List[int] = []
        for case in expr.cases:
            pattern = case.pattern
            if isinstance(pattern, VariantPattern):
                instructions.append(self._instr(Opcode.LOAD, tmp_name, case))
                instructions.append(self._instr(Opcode.CALL, ("__variant_tag", 1), case))
                instructions.append(self._instr(Opcode.PUSH_CONST, pattern.variant, pattern))
                instructions.append(self._instr(Opcode.BINARY, "==", case))
                jump_false_index = len(instructions)
                instructions.append(self._instr(Opcode.JUMP_IF_FALSE, None, case))
                instructions.append(self._instr(Opcode.LOAD, tmp_name, case))
                instructions.append(self._instr(Opcode.PUSH_CONST, pattern.variant, pattern))
                instructions.append(self._instr(Opcode.CALL, ("__variant_assume", 2), case))
                instructions.append(self._instr(Opcode.STORE, tmp_name, case))
                instructions.extend(self._compile_pattern_bindings(pattern, tmp_name))
                instructions.extend(self._compile_expr(case.body))
                instructions.append(self._instr(Opcode.STORE, result_tmp, case))
                end_jump_indices.append(len(instructions))
                instructions.append(self._instr(Opcode.JUMP, None, case))
                instructions[jump_false_index] = Instruction(
                    Opcode.JUMP_IF_FALSE, len(instructions), span=instructions[jump_false_index].span
                )
            elif isinstance(pattern, WildcardPattern):
                if pattern.name:
                    instructions.append(self._instr(Opcode.LOAD, tmp_name, case))
                    instructions.append(self._instr(Opcode.STORE, pattern.name, case))
                instructions.extend(self._compile_expr(case.body))
                instructions.append(self._instr(Opcode.STORE, result_tmp, case))
                end_jump_indices.append(len(instructions))
                instructions.append(self._instr(Opcode.JUMP, None, case))
            else:
                raise self._error(
                    f"native codegen does not yet support {type(pattern).__name__} patterns",
                    node=pattern,
                )

        instructions.append(self._instr(Opcode.LOAD, tmp_name, expr))
        instructions.append(self._instr(Opcode.CALL, ("__match_error", 1), expr))

        end_index = len(instructions)
        for jump_index in end_jump_indices:
            instructions[jump_index] = Instruction(Opcode.JUMP, end_index, span=instructions[jump_index].span)
        instructions.append(self._instr(Opcode.LOAD, result_tmp, expr))
        return instructions

    def _compile_pattern_bindings(self, pattern: "VariantPattern", tmp_name: str) -> List[Instruction]:
        instructions: List[Instruction] = []
        field_names: List[str] = []
        if pattern.positional_bindings is not None:
            field_names = self._variant_field_order(pattern.variant)
            if field_names is None:
                raise self._error(
                    f"native codegen requires type information for positional pattern {pattern.variant}",
                    node=pattern,
                )
            if len(pattern.positional_bindings) > len(field_names):
                raise RuntimeError(
                    f"positional pattern for {pattern.variant} has too many fields ({len(pattern.positional_bindings)})"
                )
            for index, bind in enumerate(pattern.positional_bindings):
                if bind is None:
                    continue
                instructions.append(self._instr(Opcode.LOAD, tmp_name, pattern))
                instructions.append(self._instr(Opcode.PUSH_CONST, field_names[index], pattern))
                instructions.append(self._instr(Opcode.CALL, ("__variant_get", 2), pattern))
                instructions.append(self._instr(Opcode.STORE, bind, pattern))
        for fname, bind in pattern.bindings.items():
            if bind is None:
                continue
            instructions.append(self._instr(Opcode.LOAD, tmp_name, pattern))
            instructions.append(self._instr(Opcode.PUSH_CONST, fname, pattern))
            instructions.append(self._instr(Opcode.CALL, ("__variant_get", 2), pattern))
            instructions.append(self._instr(Opcode.STORE, bind, pattern))
        return instructions

    def _qualify_name(self, name: str) -> str:
        if not self._module_namespace or "." in name:
            return name
        return f"{self._module_namespace}.{name}"

    @staticmethod
    def _import_binding_name(module: str, alias: str | None) -> str:
        if alias:
            return alias
        stripped = module.lstrip(".") or module
        return stripped.split(".")[-1]

    @staticmethod
    def _method_name(class_name: str, method_name: str) -> str:
        return f"{class_name}.{method_name}"

    def _operator_name(self, opdef: "OpDef") -> str:
        return self._qualify_name(f"__op_{opdef.op}_{opdef.a_type}_{opdef.b_type}")

    def _register_class(self, stmt: "ClassDef", classes: Dict[str, ClassIR]) -> None:
        if stmt.name in classes:
            existing = classes[stmt.name]
            for fname, _ in stmt.fields:
                if fname not in existing.fields:
                    existing.fields.append(fname)
            if stmt.bases:
                existing.bases = list(stmt.bases)
            return
        classes[stmt.name] = ClassIR(
            name=stmt.name,
            fields=[fname for fname, _ in stmt.fields],
            bases=list(stmt.bases),
        )

    def _register_method_class(self, stmt: "MethodDef", classes: Dict[str, ClassIR]) -> None:
        if stmt.class_name not in classes:
            classes[stmt.class_name] = ClassIR(name=stmt.class_name, fields=[])

    def _register_type(self, stmt: "TypeDef", types: Dict[str, TypeIR]) -> None:
        if stmt.variants:
            variants = {variant.name: list(variant.fields) for variant in stmt.variants}
            types[stmt.name] = TypeIR(name=stmt.name, variants=variants)
            for variant_name, fields in variants.items():
                self._variant_fields[variant_name] = [fname for fname, _ in fields]
        elif stmt.fields is not None:
            types[stmt.name] = TypeIR(name=stmt.name, fields=list(stmt.fields))
            self._variant_fields[stmt.name] = [fname for fname, _ in stmt.fields]
        else:
            types[stmt.name] = TypeIR(name=stmt.name)

    def _variant_field_order(self, variant: str) -> List[str] | None:
        return self._variant_fields.get(variant)

    def _task_scope_exit_instrs(self) -> List[Instruction]:
        return [self._instr(Opcode.CALL, ("__task_scope_exit", 0)) for _ in range(self._task_scope_depth)]

    def _error(
        self,
        message: str,
        *,
        node: Optional["IR"] = None,
        span: Optional[SourceSpan] = None,
    ) -> NotImplementedError:
        resolved_span = span or getattr(node, "span", None)
        pos = resolved_span.start if resolved_span is not None else getattr(node, "pos", SourcePos.origin())
        rendered = message
        if self._source is not None:
            rendered = format_error(self._source, resolved_span or pos, message)
        return NotImplementedError(rendered)

    @staticmethod
    def _span_for(node: "IR") -> Optional[SourceSpan]:
        span = getattr(node, "span", None)
        if span is not None:
            return span
        pos = getattr(node, "pos", None)
        if isinstance(pos, SourcePos):
            return SourceSpan(pos, pos)
        return None

    def _instr(self, op: Opcode, arg: object | None = None, node: Optional["IR"] = None) -> Instruction:
        return Instruction(op, arg, span=self._span_for(node) if node is not None else None)

# --- segment: tiny_language_codegen_c.py ---
"""C backend prototype for TinyLanguage.

This module emits a self-contained C program that embeds the native bytecode
and a tiny stack-based VM. The generator only targets the same subset supported
by ``NativeCodeGenerator`` (literals, arithmetic, control flow, functions, and
print). The resulting C source is meant for inspection or piping into a system
compiler like ``clang`` or ``gcc``.
"""

import json
import textwrap
from dataclasses import dataclass, field
from typing import Iterable, List

from native_ir import Instruction, Opcode, ProgramIR
from tiny_errors import SourcePos, TinyLangError, format_error


@dataclass
class _FunctionBlock:
    name: str
    params: List[str]
    instructions: List[Instruction]


@dataclass
class _ProgramLayout:
    entry: List[Instruction]
    functions: List[_FunctionBlock]
    strings: List[str] = field(default_factory=list)


class CCodeGenerator:
    """Translate ``ProgramIR`` into C source with an embedded VM."""

    def __init__(self, *, source: str | None = None) -> None:
        self._source = source

    def compile_program(self, program: ProgramIR) -> str:
        layout = self._collect_program(program)
        lines: List[str] = []
        lines.extend(self._header())
        lines.append("")
        lines.extend(self._emit_runtime())
        lines.append("")
        lines.extend(self._emit_data(layout))
        lines.append("")
        lines.extend(self._emit_main())
        return "\n".join(lines)

    def _format_opcode(self, op: Opcode) -> str:
        return op.value if isinstance(op, Opcode) else str(op)

    def _supported_opcodes(self) -> str:
        return ", ".join(self._format_opcode(op) for op in Opcode)

    def _unsupported_opcode(self, instr: Instruction) -> None:
        op_name = self._format_opcode(instr.op)
        message = (
            f"C backend does not support opcode {op_name}. Supported opcodes: {self._supported_opcodes()}."
        )
        raise self._error(message, instr)

    def _error(self, message: str, instr: Instruction) -> TinyLangError:
        span = instr.span
        pos = span.start if span is not None else SourcePos.origin()
        rendered = message
        if self._source is not None:
            rendered = format_error(self._source, span or pos, message)
        return TinyLangError(rendered, pos, span=span)

    def _collect_program(self, program: ProgramIR) -> _ProgramLayout:
        functions = [
            _FunctionBlock(name=fn.name, params=list(fn.params), instructions=list(fn.instructions))
            for fn in program.functions.values()
        ]
        strings: List[str] = []
        for instr in program.entry:
            strings.extend(self._strings_for_instruction(instr))
        for fn in functions:
            for instr in fn.instructions:
                strings.extend(self._strings_for_instruction(instr))
        return _ProgramLayout(entry=list(program.entry), functions=functions, strings=sorted(set(strings)))

    def _strings_for_instruction(self, instr: Instruction) -> List[str]:
        strings: List[str] = []
        if instr.op in {Opcode.LOAD, Opcode.STORE, Opcode.BINARY}:
            strings.append(str(instr.arg))
        elif instr.op == Opcode.CALL:
            name, _argc = instr.arg
            strings.append(str(name))
        elif instr.op == Opcode.PUSH_CONST and isinstance(instr.arg, str):
            strings.append(instr.arg)
        return strings

    def _header(self) -> List[str]:
        return [
            "#include <math.h>",
            "#include <stdbool.h>",
            "#include <stdint.h>",
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "#include <string.h>",
        ]

    def _emit_runtime(self) -> List[str]:
        runtime = r"""
        typedef enum {
            OP_PUSH_CONST,
            OP_LOAD,
            OP_STORE,
            OP_BINARY,
            OP_PRINT,
            OP_FLUSH,
            OP_JUMP,
            OP_JUMP_IF_FALSE,
            OP_CALL,
            OP_POP,
            OP_RETURN
        } Opcode;

        typedef enum {
            VAL_NULL,
            VAL_BOOL,
            VAL_INT,
            VAL_DOUBLE,
            VAL_STRING
        } ValueType;

        typedef struct {
            ValueType type;
            union {
                bool bool_value;
                int64_t int_value;
                double double_value;
                const char *string_value;
            } as;
        } Value;

        typedef struct {
            const char *name;
            int argc;
        } CallArg;

        typedef enum {
            ARG_NONE,
            ARG_INT,
            ARG_STRING,
            ARG_CALL,
            ARG_VALUE
        } ArgKind;

        typedef struct {
            ArgKind kind;
            union {
                int64_t int_value;
                const char *string_value;
                CallArg call_value;
                Value value;
            } as;
        } Arg;

        typedef struct {
            Opcode op;
            Arg arg;
        } Instruction;

        typedef struct {
            const char *name;
            Value value;
        } Binding;

        typedef struct {
            Binding *items;
            int count;
            int capacity;
        } Env;

        typedef struct {
            const char *name;
            const char **params;
            int param_count;
            Instruction *instructions;
            int instruction_count;
        } Function;

        typedef struct {
            Instruction *instructions;
            int instruction_count;
            int ip;
            Env *locals;
            bool is_global;
        } Frame;

        typedef struct {
            Instruction *entry;
            int entry_count;
            Function *functions;
            int function_count;
            Env globals;
        } Program;

        typedef struct {
            Value *items;
            int count;
            int capacity;
        } Stack;

        #define ARG_NONE_VALUE (Arg){ARG_NONE}
        #define ARG_INT_VALUE(v) (Arg){ARG_INT, .as.int_value = (v)}
        #define ARG_STRING_VALUE(v) (Arg){ARG_STRING, .as.string_value = (v)}
        #define ARG_CALL_VALUE(name, argc) (Arg){ARG_CALL, .as.call_value = {(name), (argc)}}
        #define ARG_VALUE_VALUE(v) (Arg){ARG_VALUE, .as.value = (v)}

        #define VAL_NULL_VALUE (Value){VAL_NULL}
        #define VAL_BOOL_VALUE(v) (Value){VAL_BOOL, .as.bool_value = (v)}
        #define VAL_INT_VALUE(v) (Value){VAL_INT, .as.int_value = (v)}
        #define VAL_DOUBLE_VALUE(v) (Value){VAL_DOUBLE, .as.double_value = (v)}
        #define VAL_STRING_VALUE(v) (Value){VAL_STRING, .as.string_value = (v)}

        static void env_init(Env *env) {
            env->items = NULL;
            env->count = 0;
            env->capacity = 0;
        }

        static int env_find(Env *env, const char *name) {
            for (int i = 0; i < env->count; i++) {
                if (strcmp(env->items[i].name, name) == 0) {
                    return i;
                }
            }
            return -1;
        }

        static void env_set(Env *env, const char *name, Value value) {
            int index = env_find(env, name);
            if (index >= 0) {
                env->items[index].value = value;
                return;
            }
            if (env->count >= env->capacity) {
                env->capacity = env->capacity < 8 ? 8 : env->capacity * 2;
                env->items = realloc(env->items, sizeof(Binding) * env->capacity);
            }
            env->items[env->count].name = name;
            env->items[env->count].value = value;
            env->count += 1;
        }

        static bool env_get(Env *env, const char *name, Value *out) {
            int index = env_find(env, name);
            if (index >= 0) {
                *out = env->items[index].value;
                return true;
            }
            return false;
        }

        static void stack_init(Stack *stack) {
            stack->items = NULL;
            stack->count = 0;
            stack->capacity = 0;
        }

        static void stack_push(Stack *stack, Value value) {
            if (stack->count >= stack->capacity) {
                stack->capacity = stack->capacity < 8 ? 8 : stack->capacity * 2;
                stack->items = realloc(stack->items, sizeof(Value) * stack->capacity);
            }
            stack->items[stack->count++] = value;
        }

        static Value stack_pop(Stack *stack) {
            if (stack->count == 0) {
                fprintf(stderr, "Runtime error: pop from empty stack\n");
                exit(1);
            }
            return stack->items[--stack->count];
        }

        static bool value_truthy(Value value) {
            switch (value.type) {
                case VAL_NULL: return false;
                case VAL_BOOL: return value.as.bool_value;
                case VAL_INT: return value.as.int_value != 0;
                case VAL_DOUBLE: return value.as.double_value != 0.0;
                case VAL_STRING: return value.as.string_value && value.as.string_value[0] != '\0';
            }
            return false;
        }

        static void print_value(Value value) {
            switch (value.type) {
                case VAL_NULL:
                    printf("null");
                    break;
                case VAL_BOOL:
                    printf(value.as.bool_value ? "true" : "false");
                    break;
                case VAL_INT:
                    printf("%lld", (long long)value.as.int_value);
                    break;
                case VAL_DOUBLE:
                    printf("%.15g", value.as.double_value);
                    break;
                case VAL_STRING:
                    printf("%s", value.as.string_value ? value.as.string_value : "");
                    break;
            }
        }

        static Value make_bool(bool value) { return VAL_BOOL_VALUE(value); }

        static Value value_binary_op(Value left, Value right, const char *op) {
            if (strcmp(op, "&&") == 0 || strcmp(op, "and") == 0) {
                return make_bool(value_truthy(left) && value_truthy(right));
            }
            if (strcmp(op, "||") == 0 || strcmp(op, "or") == 0) {
                return make_bool(value_truthy(left) || value_truthy(right));
            }
            if (left.type == VAL_STRING && right.type == VAL_STRING && strcmp(op, "+") == 0) {
                size_t left_len = strlen(left.as.string_value);
                size_t right_len = strlen(right.as.string_value);
                char *joined = malloc(left_len + right_len + 1);
                memcpy(joined, left.as.string_value, left_len);
                memcpy(joined + left_len, right.as.string_value, right_len);
                joined[left_len + right_len] = '\0';
                return VAL_STRING_VALUE(joined);
            }
            bool use_double = left.type == VAL_DOUBLE || right.type == VAL_DOUBLE || strcmp(op, "/") == 0;
            double left_num = (left.type == VAL_DOUBLE) ? left.as.double_value : (double)left.as.int_value;
            double right_num = (right.type == VAL_DOUBLE) ? right.as.double_value : (double)right.as.int_value;
            if (strcmp(op, "+") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(left_num + right_num) : VAL_INT_VALUE((int64_t)(left_num + right_num));
            }
            if (strcmp(op, "-") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(left_num - right_num) : VAL_INT_VALUE((int64_t)(left_num - right_num));
            }
            if (strcmp(op, "*") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(left_num * right_num) : VAL_INT_VALUE((int64_t)(left_num * right_num));
            }
            if (strcmp(op, "/") == 0) {
                return VAL_DOUBLE_VALUE(left_num / right_num);
            }
            if (strcmp(op, "%") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(fmod(left_num, right_num)) : VAL_INT_VALUE((int64_t)left_num % (int64_t)right_num);
            }
            if (strcmp(op, "^") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(pow(left_num, right_num)) : VAL_INT_VALUE((int64_t)pow(left_num, right_num));
            }
            if (strcmp(op, "==") == 0) {
                if (left.type == VAL_STRING && right.type == VAL_STRING) {
                    return make_bool(strcmp(left.as.string_value, right.as.string_value) == 0);
                }
                return make_bool(left_num == right_num);
            }
            if (strcmp(op, "!=") == 0) {
                if (left.type == VAL_STRING && right.type == VAL_STRING) {
                    return make_bool(strcmp(left.as.string_value, right.as.string_value) != 0);
                }
                return make_bool(left_num != right_num);
            }
            if (strcmp(op, "<") == 0) { return make_bool(left_num < right_num); }
            if (strcmp(op, ">") == 0) { return make_bool(left_num > right_num); }
            if (strcmp(op, "<=") == 0) { return make_bool(left_num <= right_num); }
            if (strcmp(op, ">=") == 0) { return make_bool(left_num >= right_num); }
            fprintf(stderr, "Runtime error: unsupported operator %s\n", op);
            exit(1);
        }

        static Function *find_function(Program *program, const char *name) {
            for (int i = 0; i < program->function_count; i++) {
                if (strcmp(program->functions[i].name, name) == 0) {
                    return &program->functions[i];
                }
            }
            return NULL;
        }

        static Value execute_frame(Program *program, Frame *frame) {
            Stack stack;
            stack_init(&stack);
            while (frame->ip < frame->instruction_count) {
                Instruction instr = frame->instructions[frame->ip++];
                switch (instr.op) {
                    case OP_PUSH_CONST:
                        stack_push(&stack, instr.arg.as.value);
                        break;
                    case OP_LOAD: {
                        Value value;
                        if (env_get(frame->locals, instr.arg.as.string_value, &value) ||
                            env_get(&program->globals, instr.arg.as.string_value, &value)) {
                            stack_push(&stack, value);
                        } else {
                            fprintf(stderr, "Runtime error: unknown variable %s\n", instr.arg.as.string_value);
                            exit(1);
                        }
                        break;
                    }
                    case OP_STORE: {
                        Value value = stack_pop(&stack);
                        env_set(frame->locals, instr.arg.as.string_value, value);
                        if (frame->is_global) {
                            env_set(&program->globals, instr.arg.as.string_value, value);
                        }
                        break;
                    }
                    case OP_BINARY: {
                        Value right = stack_pop(&stack);
                        Value left = stack_pop(&stack);
                        stack_push(&stack, value_binary_op(left, right, instr.arg.as.string_value));
                        break;
                    }
                    case OP_PRINT: {
                        int count = (int)instr.arg.as.int_value;
                        Value *values = malloc(sizeof(Value) * count);
                        for (int i = count - 1; i >= 0; i--) {
                            values[i] = stack_pop(&stack);
                        }
                        for (int i = 0; i < count; i++) {
                            print_value(values[i]);
                            if (i < count - 1) {
                                printf(" ");
                            }
                        }
                        free(values);
                        printf("\n");
                        break;
                    }
                    case OP_FLUSH:
                        fflush(stdout);
                        break;
                    case OP_JUMP:
                        frame->ip = (int)instr.arg.as.int_value;
                        break;
                    case OP_JUMP_IF_FALSE: {
                        Value cond = stack_pop(&stack);
                        if (!value_truthy(cond)) {
                            frame->ip = (int)instr.arg.as.int_value;
                        }
                        break;
                    }
                    case OP_CALL: {
                        Function *fn = find_function(program, instr.arg.as.call_value.name);
                        if (!fn) {
                            fprintf(stderr, "Runtime error: unknown function %s\n", instr.arg.as.call_value.name);
                            exit(1);
                        }
                        if (fn->param_count != instr.arg.as.call_value.argc) {
                            fprintf(stderr, "Runtime error: function %s expects %d args, got %d\n", fn->name, fn->param_count, instr.arg.as.call_value.argc);
                            exit(1);
                        }
                        Env locals;
                        env_init(&locals);
                        for (int i = fn->param_count - 1; i >= 0; i--) {
                            Value arg_val = stack_pop(&stack);
                            env_set(&locals, fn->params[i], arg_val);
                        }
                        Frame call_frame;
                        call_frame.instructions = fn->instructions;
                        call_frame.instruction_count = fn->instruction_count;
                        call_frame.ip = 0;
                        call_frame.locals = &locals;
                        call_frame.is_global = false;
                        Value result = execute_frame(program, &call_frame);
                        stack_push(&stack, result);
                        break;
                    }
                    case OP_POP:
                        stack_pop(&stack);
                        break;
                    case OP_RETURN:
                        if (stack.count > 0) {
                            return stack_pop(&stack);
                        }
                        return VAL_NULL_VALUE;
                }
            }
            return VAL_NULL_VALUE;
        }

        static Value execute_program(Program *program) {
            Frame frame;
            frame.instructions = program->entry;
            frame.instruction_count = program->entry_count;
            frame.ip = 0;
            frame.locals = &program->globals;
            frame.is_global = true;
            return execute_frame(program, &frame);
        }
        """
        return textwrap.dedent(runtime).strip().splitlines()

    def _emit_data(self, layout: _ProgramLayout) -> List[str]:
        lines: List[str] = []
        for index, fn in enumerate(layout.functions):
            symbol = self._fn_symbol(index)
            params = ", ".join(self._c_string(param) for param in fn.params)
            lines.append(f"static const char *params_{symbol}[] = {{{params}}};")
            lines.append(f"static Instruction instructions_{symbol}[] = {{")
            lines.extend(self._emit_instructions(fn.instructions, indent="    "))
            lines.append("};")
            lines.append("")
        lines.append("static Instruction entry_instructions[] = {")
        lines.extend(self._emit_instructions(layout.entry, indent="    "))
        lines.append("};")
        lines.append("")
        if layout.functions:
            lines.append("static Function functions[] = {")
            for index, fn in enumerate(layout.functions):
                symbol = self._fn_symbol(index)
                lines.append(
                    "    {" + f"{self._c_string(fn.name)}, params_{symbol}, {len(fn.params)}, "
                    f"instructions_{symbol}, {len(fn.instructions)}" + "},"
                )
            lines.append("};")
            lines.append("static int function_count = (int)(sizeof(functions) / sizeof(functions[0]));")
        else:
            lines.append("static Function *functions = NULL;")
            lines.append("static int function_count = 0;")
        return lines

    def _fn_symbol(self, index: int) -> str:
        return f"fn_{index}"

    def _emit_instructions(self, instructions: Iterable[Instruction], *, indent: str) -> List[str]:
        lines: List[str] = []
        for instr in instructions:
            lines.append(f"{indent}{self._instruction_literal(instr)},")
        return lines

    def _instruction_literal(self, instr: Instruction) -> str:
        if instr.op == Opcode.PUSH_CONST:
            return f"{{OP_PUSH_CONST, {self._arg_value(instr.arg)}}}"
        if instr.op == Opcode.LOAD:
            return f"{{OP_LOAD, {self._arg_string(instr.arg)}}}"
        if instr.op == Opcode.STORE:
            return f"{{OP_STORE, {self._arg_string(instr.arg)}}}"
        if instr.op == Opcode.BINARY:
            return f"{{OP_BINARY, {self._arg_string(instr.arg)}}}"
        if instr.op == Opcode.PRINT:
            return f"{{OP_PRINT, {self._arg_int(int(instr.arg))}}}"
        if instr.op == Opcode.FLUSH:
            return "{OP_FLUSH, ARG_NONE_VALUE}"
        if instr.op == Opcode.JUMP:
            return f"{{OP_JUMP, {self._arg_int(int(instr.arg))}}}"
        if instr.op == Opcode.JUMP_IF_FALSE:
            return f"{{OP_JUMP_IF_FALSE, {self._arg_int(int(instr.arg))}}}"
        if instr.op == Opcode.CALL:
            name, argc = instr.arg
            return f"{{OP_CALL, {self._arg_call(str(name), int(argc))}}}"
        if instr.op == Opcode.POP:
            return "{OP_POP, ARG_NONE_VALUE}"
        if instr.op == Opcode.RETURN:
            return "{OP_RETURN, ARG_NONE_VALUE}"
        self._unsupported_opcode(instr)

    def _arg_int(self, value: int) -> str:
        return f"ARG_INT_VALUE({value})"

    def _arg_string(self, value: str) -> str:
        return f"ARG_STRING_VALUE({self._c_string(value)})"

    def _arg_call(self, name: str, argc: int) -> str:
        return f"ARG_CALL_VALUE({self._c_string(name)}, {argc})"

    def _arg_value(self, value: object) -> str:
        return f"ARG_VALUE_VALUE({self._value_literal(value)})"

    def _value_literal(self, value: object) -> str:
        if value is None:
            return "VAL_NULL_VALUE"
        if isinstance(value, bool):
            return f"VAL_BOOL_VALUE({'true' if value else 'false'})"
        if isinstance(value, int) and not isinstance(value, bool):
            return f"VAL_INT_VALUE({value})"
        if isinstance(value, float):
            return f"VAL_DOUBLE_VALUE({value})"
        if isinstance(value, str):
            return f"VAL_STRING_VALUE({self._c_string(value)})"
        raise NotImplementedError(f"unsupported constant {value!r}")

    def _c_string(self, value: str) -> str:
        return json.dumps(value)

    def _emit_main(self) -> List[str]:
        return [
            "int main(void) {",
            "    Program program;",
            "    program.entry = entry_instructions;",
            "    program.entry_count = (int)(sizeof(entry_instructions) / sizeof(entry_instructions[0]));",
            "    program.functions = functions;",
            "    program.function_count = function_count;",
            "    env_init(&program.globals);",
            "    execute_program(&program);",
            "    return 0;",
            "}",
        ]

# --- segment: tiny_language_codegen_llvm.py ---
"""Lightweight LLVM IR prototype for TinyLanguage.

The goal of this prototype is to expose a minimal code path that can translate
the native stack-based IR into a textual LLVM module. It intentionally supports
the constructs needed for the tutorial-style examples (numeric literals,
assignments, arithmetic, comparisons, simple control flow, and `print`) and
will raise ``TinyLangError`` for everything else. The output is meant for
inspection or piping into external tools like ``llc`` rather than for
production-grade code generation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from native_ir import FunctionIR, Instruction, Opcode, OperatorOverloadIR, ProgramIR
from tiny_errors import format_error


@dataclass
class _StackValue:
    """Keep track of a value's type and SSA name for LLVM emission."""

    name: str
    ty: str
    source: Optional[str] = None
    literal: Optional[int] = None
    literal_str: Optional[str] = None
    class_name: Optional[str] = None
    variant_name: Optional[str] = None


@dataclass(frozen=True)
class _ResolvedFunctionSignature:
    param_types: Dict[str, str]
    return_type: str


@dataclass
class _FunctionSignature:
    param_types: Dict[str, Optional[str]]
    return_type: Optional[str]


@dataclass
class _TypeValue:
    ty: Optional[str]
    source: Optional[str] = None
    literal: Optional[int] = None
    literal_str: Optional[str] = None
    class_name: Optional[str] = None
    variant_name: Optional[str] = None


class LLVMCodeGenerator:
    """Translate ``ProgramIR`` instructions into textual LLVM IR."""

    def __init__(
        self,
        *,
        target_triple: Optional[str] = None,
        data_layout: Optional[str] = None,
        module_inits: Optional[Dict[str, str]] = None,
        source: Optional[str] = None,
    ) -> None:
        self._tmp_index = 0
        self._label_index = 0
        self._stack: List[_StackValue] = []
        self._allocas: Dict[str, str] = {}
        self._var_types: Dict[str, str] = {}
        self._var_literals: Dict[str, int] = {}
        self._var_classes: Dict[str, str] = {}
        self._var_variants: Dict[str, str] = {}
        self._prologue: List[str] = []
        self._body: List[str] = []
        self._string_constants: Dict[str, Tuple[str, int]] = {}
        self._string_defs: List[str] = []
        self._function_signatures: Dict[str, _ResolvedFunctionSignature] = {}
        self._current_return_type: Optional[str] = None
        self._current_instruction: Optional[Instruction] = None
        self._heap_cell_types: Dict[Tuple[str, int], str] = {}
        self._class_layouts: Dict[str, List[Tuple[str, str]]] = {}
        self._class_mros: Dict[str, List[str]] = {}
        self._class_ids: Dict[str, int] = {}
        self._class_methods: Dict[str, Dict[str, str]] = {}
        self._class_field_types: Dict[Tuple[str, int], str] = {}
        self._variant_fields: Dict[str, List[str]] = {}
        self._variant_field_types: Dict[Tuple[str, str], str] = {}
        self._variant_to_type: Dict[str, str] = {}
        self._target_triple = target_triple
        self._data_layout = data_layout
        self._operator_overloads: Dict[Tuple[str, str, str], str] = {}
        self._module_inits: Dict[str, str] = module_inits or {}
        self._python_modules: set[str] = set()
        self._source = source

    def _format_opcode(self, op: Opcode) -> str:
        return op.value if isinstance(op, Opcode) else str(op)

    def _supported_opcodes(self) -> str:
        return ", ".join(self._format_opcode(op) for op in Opcode)

    def _instruction_context(self, instr: Optional[Instruction] = None) -> str:
        if instr is None:
            return ""
        op_name = self._format_opcode(instr.op)
        if instr.arg is None:
            return f" (instruction: {op_name})"
        return f" (instruction: {op_name} {instr.arg!r})"

    def _lowering_error(self, reason: str, instr: Optional[Instruction] = None) -> None:
        context = self._instruction_context(instr or self._current_instruction)
        message = f"LLVM prototype missing lowering: {reason}{context}"
        if self._source is not None and instr is not None and instr.span is not None:
            message = format_error(self._source, instr.span, message)
        raise NotImplementedError(message)

    def _unsupported_opcode(self, instr: Instruction) -> None:
        op_name = self._format_opcode(instr.op)
        self._lowering_error(
            f"opcode {op_name} not supported. Supported opcodes: {self._supported_opcodes()}.",
            instr,
        )

    def compile_program(self, program: ProgramIR) -> str:
        """Return LLVM IR for the given native ``ProgramIR``.

        The LLVM prototype supports top-level code plus simple user-defined
        functions and calls over the numeric subset. Complex types remain out of
        scope so gaps stay visible during experimentation.
        """

        self._register_type_metadata(program)
        self._register_class_metadata(program)
        self._operator_overloads = self._register_operator_overloads(program.operator_overloads)
        self._class_field_types.clear()
        self._python_modules.clear()
        self._function_signatures = self._infer_signatures(program)
        self._string_constants.clear()
        self._string_defs.clear()

        function_blocks: List[List[str]] = []
        for func in program.functions.values():
            function_blocks.append(self._compile_function(func, self._function_signatures[func.name]))
        entry_block = self._compile_entry(program.entry)

        lines: List[str] = []
        lines.extend(self._header())
        lines.extend(self._string_defs)
        for block in function_blocks:
            lines.extend(block)
        lines.extend(entry_block)
        return "\n".join(lines)

    def _compile_entry(self, instructions: List[Instruction]) -> List[str]:
        self._tmp_index = 0
        self._label_index = 0
        self._stack.clear()
        self._allocas.clear()
        self._var_types.clear()
        self._var_literals.clear()
        self._var_classes.clear()
        self._var_variants.clear()
        self._prologue.clear()
        self._body.clear()
        self._current_return_type = None
        self._heap_cell_types.clear()

        block_starts = self._collect_block_starts(instructions)
        label_map = self._label_map(block_starts)
        self._emit_blocks(instructions, block_starts, label_map, allow_return=False, exit_label="exit")

        lines: List[str] = []
        lines.append("define i32 @tiny_main() {")
        lines.append("entry:")
        lines.extend(self._prologue)
        lines.append(f"  br label %{label_map[0]}")
        lines.extend(self._body)
        lines.append("exit:")
        lines.append("  ret i32 0")
        lines.append("}")
        return lines

    def _compile_function(self, func: FunctionIR, signature: _ResolvedFunctionSignature) -> List[str]:
        self._tmp_index = 0
        self._label_index = 0
        self._stack.clear()
        self._allocas.clear()
        self._var_types.clear()
        self._var_literals.clear()
        self._var_classes.clear()
        self._var_variants.clear()
        self._prologue.clear()
        self._body.clear()
        self._current_return_type = signature.return_type
        self._heap_cell_types.clear()

        params: List[Tuple[str, str]] = [(name, signature.param_types[name]) for name in func.params]
        for name, ty in params:
            addr_name = f"{name}.addr"
            arg_name = f"{name}.arg"
            self._allocas[name] = addr_name
            self._var_types[name] = ty
            self._prologue.append(f"  %{addr_name} = alloca {ty}")
            self._prologue.append(f"  store {ty} %{arg_name}, {ty}* %{addr_name}")
        if "." in func.name and func.params:
            self._var_classes[func.params[0]] = func.name.split(".", 1)[0]

        block_starts = self._collect_block_starts(func.instructions)
        label_map = self._label_map(block_starts)
        self._emit_blocks(func.instructions, block_starts, label_map, allow_return=True, exit_label="exit")

        param_sig = ", ".join(f"{ty} %{name}.arg" for name, ty in params)
        lines: List[str] = []
        lines.append(f"define {signature.return_type} @{func.name}({param_sig}) {{")
        lines.append("entry:")
        lines.extend(self._prologue)
        lines.append(f"  br label %{label_map[0]}")
        lines.extend(self._body)
        lines.append("exit:")
        lines.append(f"  ret {signature.return_type} {self._zero_value(signature.return_type)}")
        lines.append("}")
        return lines

    def _zero_value(self, ty: str) -> str:
        if ty == "double":
            return "0.0"
        if ty == "i1":
            return "0"
        if ty == "i64":
            return "0"
        raise NotImplementedError(f"zero literal not supported for type {ty}")

    def _collect_block_starts(self, instructions: List[Instruction]) -> List[int]:
        starts = {0}
        for idx, instr in enumerate(instructions):
            if instr.op == Opcode.JUMP:
                if instr.arg is not None:
                    target = int(instr.arg)
                    if target != len(instructions):
                        starts.add(target)
            elif instr.op == Opcode.JUMP_IF_FALSE:
                if instr.arg is not None:
                    target = int(instr.arg)
                    if target != len(instructions):
                        starts.add(target)
                if idx + 1 < len(instructions):
                    starts.add(idx + 1)
        return sorted(starts)

    def _label_map(self, block_starts: List[int]) -> Dict[int, str]:
        return {start: f"block{start}" for start in block_starts}

    def _emit_blocks(
        self,
        instructions: List[Instruction],
        block_starts: List[int],
        label_map: Dict[int, str],
        allow_return: bool,
        exit_label: str,
    ) -> None:
        for index, start in enumerate(block_starts):
            if self._stack:
                raise NotImplementedError("LLVM prototype cannot carry stack values across basic blocks")
            self._body.append(f"{label_map[start]}:")
            end = block_starts[index + 1] if index + 1 < len(block_starts) else len(instructions)
            terminated = self._emit_block_body(instructions, start, end, label_map, allow_return, exit_label)
            if not terminated:
                if self._stack:
                    raise NotImplementedError("LLVM prototype cannot carry stack values across basic blocks")
                next_label = (
                    label_map[block_starts[index + 1]] if index + 1 < len(block_starts) else exit_label
                )
                self._body.append(f"  br label %{next_label}")

    def _emit_block_body(
        self,
        instructions: List[Instruction],
        start: int,
        end: int,
        label_map: Dict[int, str],
        allow_return: bool,
        exit_label: str,
    ) -> bool:
        self._stack.clear()
        for idx in range(start, end):
            instr = instructions[idx]
            self._current_instruction = instr
            if instr.op == Opcode.JUMP:
                if self._stack:
                    self._lowering_error("cannot carry stack values across basic blocks", instr)
                target = int(instr.arg)
                target_label = "exit" if target == len(instructions) else label_map[target]
                self._body.append(f"  br label %{target_label}")
                return True
            if instr.op == Opcode.JUMP_IF_FALSE:
                cond_name = self._pop_condition()
                if self._stack:
                    self._lowering_error("cannot carry stack values across basic blocks", instr)
                target = int(instr.arg)
                target_label = exit_label if target == len(instructions) else label_map[target]
                fallthrough = idx + 1
                fallthrough_label = exit_label if fallthrough == len(instructions) else label_map[fallthrough]
                self._body.append(f"  br i1 {cond_name}, label %{fallthrough_label}, label %{target_label}")
                return True
            if instr.op == Opcode.RETURN:
                if not allow_return:
                    continue
                if not self._stack:
                    self._lowering_error("return requires a value", instr)
                value = self._stack.pop()
                self._body.append(f"  ret {value.ty} {value.name}")
                return True
            self._emit_instruction(instr)
        return False

    # ----- Instruction handlers -----

    def _emit_instruction(self, instr: Instruction) -> None:
        if instr.op == Opcode.PUSH_CONST:
            self._push_const(instr.arg)
        elif instr.op == Opcode.LOAD:
            self._load_var(instr.arg)
        elif instr.op == Opcode.STORE:
            self._store_var(instr.arg)
        elif instr.op == Opcode.BINARY:
            self._binary_op(instr.arg)
        elif instr.op == Opcode.PRINT:
            self._print_values(int(instr.arg))
        elif instr.op == Opcode.POP:
            self._pop_value()
        elif instr.op == Opcode.FLUSH:
            self._flush_output()
        elif instr.op == Opcode.CALL:
            self._call_function(instr.arg)
        elif instr.op == Opcode.RETURN:
            # The surrounding function emits a single final return, so intermediate
            # returns are ignored for now.
            return
        else:
            self._unsupported_opcode(instr)

    def _push_const(self, value: object) -> None:
        if value is None:
            self._stack.append(_StackValue(name="null", ty="i8*"))
        elif isinstance(value, bool):
            self._stack.append(_StackValue(name="1" if value else "0", ty="i1"))
        elif isinstance(value, int):
            self._stack.append(_StackValue(name=str(value), ty="i64", literal=value))
        elif isinstance(value, float):
            self._stack.append(_StackValue(name=f"{value:.6e}", ty="double"))
        elif isinstance(value, str):
            name, length = self._string_constant(value)
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = getelementptr inbounds [{length} x i8], [{length} x i8]* @{name}, i32 0, i32 0"
            )
            self._stack.append(_StackValue(name=dest, ty="i8*", literal_str=value))
        else:
            self._lowering_error(
                f"constants of type {type(value).__name__} are not supported",
            )

    def _load_var(self, name: str) -> None:
        if name in {"Map", "Set", "Deque", "Async", "Python"}:
            self._stack.append(_StackValue(name=name, ty="i64", class_name=name))
            return
        ty = self._var_types.get(name)
        if ty is None:
            self._lowering_error(f"unknown variable {name}")
        dest = self._next_tmp()
        self._body.append(f"  {dest} = load {ty}, {ty}* %{self._allocas[name]}")
        literal = self._var_literals.get(name)
        class_name = self._var_classes.get(name)
        variant_name = self._var_variants.get(name)
        self._stack.append(
            _StackValue(
                name=dest,
                ty=ty,
                source=name,
                literal=literal,
                class_name=class_name,
                variant_name=variant_name,
            )
        )

    def _store_var(self, name: str) -> None:
        if not self._stack:
            raise RuntimeError("store requested with empty stack")
        value = self._stack.pop()
        if name not in self._allocas:
            self._allocas[name] = name
            self._var_types[name] = value.ty
            self._prologue.append(f"  %{name} = alloca {value.ty}")
        if value.ty == "i64" and value.literal is not None:
            self._var_literals[name] = value.literal
        else:
            self._var_literals.pop(name, None)
        if value.class_name:
            self._var_classes[name] = value.class_name
        else:
            self._var_classes.pop(name, None)
        if value.variant_name:
            self._var_variants[name] = value.variant_name
        else:
            self._var_variants.pop(name, None)
        if value.source and value.source != name:
            for (ptr_name, idx), cell_ty in list(self._heap_cell_types.items()):
                if ptr_name == value.source:
                    self._heap_cell_types[(name, idx)] = cell_ty
        self._body.append(f"  store {value.ty} {value.name}, {value.ty}* %{self._allocas[name]}")

    def _binary_op(self, op: str) -> None:
        right = self._stack.pop()
        left = self._stack.pop()
        if left.ty != right.ty:
            self._lowering_error(
                f"mixed-type arithmetic not supported ({left.ty} vs {right.ty})"
            )

        overload_name = self._operator_overloads.get((op, left.ty, right.ty))
        if overload_name is not None:
            signature = self._function_signatures.get(overload_name)
            if signature is None:
                self._lowering_error(f"unknown operator overload {overload_name}")
            if len(signature.param_types) != 2:
                self._lowering_error(
                    f"operator overload {overload_name} expects 2 args, got {len(signature.param_types)}"
                )
            rendered_args: List[str] = []
            for (param_name, param_type), arg in zip(signature.param_types.items(), (left, right)):
                if arg.ty != param_type:
                    self._lowering_error(
                        f"argument for {overload_name}.{param_name} expected {param_type}, got {arg.ty}"
                    )
                rendered_args.append(f"{param_type} {arg.name}")
            dest = self._next_tmp()
            args_text = ", ".join(rendered_args)
            self._body.append(f"  {dest} = call {signature.return_type} @{overload_name}({args_text})")
            self._stack.append(_StackValue(name=dest, ty=signature.return_type))
            return

        if op in {"+", "-", "*", "/", "%"}:
            self._emit_arithmetic_op(op, left, right)
            return
        if op in {"==", "!=", "<", ">", "<=", ">="}:
            self._emit_comparison(op, left, right)
            return
        self._lowering_error(f"operator {op} not supported")

    def _emit_arithmetic_op(self, op: str, left: _StackValue, right: _StackValue) -> None:
        ty = left.ty
        dest = self._next_tmp()
        if ty == "double":
            instr = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv", "%": "frem"}.get(op)
        else:
            instr = {"+": "add", "-": "sub", "*": "mul", "/": "sdiv", "%": "srem"}.get(op)
        if instr is None:
            self._lowering_error(f"operator {op} not supported for type {ty}")
        self._body.append(f"  {dest} = {instr} {ty} {left.name}, {right.name}")
        self._stack.append(_StackValue(name=dest, ty=ty))

    def _emit_comparison(self, op: str, left: _StackValue, right: _StackValue) -> None:
        ty = left.ty
        dest = self._next_tmp()
        if ty == "double":
            predicate = {
                "==": "oeq",
                "!=": "one",
                "<": "olt",
                ">": "ogt",
                "<=": "ole",
                ">=": "oge",
            }.get(op)
            if predicate is None:
                self._lowering_error(f"comparison {op} not supported for type {ty}")
            self._body.append(f"  {dest} = fcmp {predicate} {ty} {left.name}, {right.name}")
        elif ty == "i8*":
            predicate = {"==": "eq", "!=": "ne"}.get(op)
            if predicate is None:
                self._lowering_error(f"comparison {op} not supported for type {ty}")
            self._body.append(f"  {dest} = icmp {predicate} {ty} {left.name}, {right.name}")
        else:
            predicate = {
                "==": "eq",
                "!=": "ne",
                "<": "slt",
                ">": "sgt",
                "<=": "sle",
                ">=": "sge",
            }.get(op)
            if predicate is None:
                self._lowering_error(f"comparison {op} not supported for type {ty}")
            self._body.append(f"  {dest} = icmp {predicate} {ty} {left.name}, {right.name}")
        self._stack.append(_StackValue(name=dest, ty="i1"))

    def _print_values(self, count: int) -> None:
        if count <= 0:
            return
        values = [self._stack.pop() for _ in range(count)][::-1]
        for value in values:
            fmt, fmt_len = self._format_for_type(value.ty)
            fmt_ptr = self._next_tmp()
            self._body.append(
                f"  {fmt_ptr} = getelementptr inbounds [{fmt_len} x i8], [{fmt_len} x i8]* @{fmt}, i32 0, i32 0"
            )
            if value.ty == "i1":
                widened = self._next_tmp()
                self._body.append(f"  {widened} = zext i1 {value.name} to i64")
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i64 {widened})")
            elif value.ty == "i8*":
                is_null = self._next_tmp()
                null_label = self._next_label("print.null")
                value_label = self._next_label("print.str")
                done_label = self._next_label("print.done")
                self._body.append(f"  {is_null} = icmp eq i8* {value.name}, null")
                self._body.append(f"  br i1 {is_null}, label %{null_label}, label %{value_label}")
                self._body.append(f"{null_label}:")
                null_name, null_len = self._string_constant("Null")
                null_ptr = self._next_tmp()
                self._body.append(
                    f"  {null_ptr} = getelementptr inbounds [{null_len} x i8], [{null_len} x i8]* @{null_name}, i32 0, i32 0"
                )
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i8* {null_ptr})")
                self._body.append(f"  br label %{done_label}")
                self._body.append(f"{value_label}:")
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i8* {value.name})")
                self._body.append(f"  br label %{done_label}")
                self._body.append(f"{done_label}:")
            else:
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, {value.ty} {value.name})")

    def _pop_value(self) -> None:
        if not self._stack:
            raise RuntimeError("cannot POP from an empty LLVM prototype stack")
        self._stack.pop()

    def _flush_output(self) -> None:
        self._body.append("  call i32 @fflush(i8* null)")

    def _value_payload(self, value: _StackValue) -> str:
        if value.ty == "i64":
            return value.name
        dest = self._next_tmp()
        if value.ty == "i1":
            self._body.append(f"  {dest} = zext i1 {value.name} to i64")
            return dest
        if value.ty == "double":
            self._body.append(f"  {dest} = bitcast double {value.name} to i64")
            return dest
        if value.ty == "i8*":
            self._body.append(f"  {dest} = ptrtoint i8* {value.name} to i64")
            return dest
        self._lowering_error(f"cannot lower payload for type {value.ty}")
        return dest

    def _payload_to_value(self, payload: str, target_ty: str) -> _StackValue:
        if target_ty == "i64":
            return _StackValue(name=payload, ty="i64")
        dest = self._next_tmp()
        if target_ty == "i1":
            self._body.append(f"  {dest} = trunc i64 {payload} to i1")
            return _StackValue(name=dest, ty="i1")
        if target_ty == "double":
            self._body.append(f"  {dest} = bitcast i64 {payload} to double")
            return _StackValue(name=dest, ty="double")
        if target_ty == "i8*":
            self._body.append(f"  {dest} = inttoptr i64 {payload} to i8*")
            return _StackValue(name=dest, ty="i8*")
        self._lowering_error(f"cannot unbox payload for type {target_ty}")
        return _StackValue(name=payload, ty=target_ty)

    def _spawn_wrapper_name(self, ty: str) -> str:
        wrappers = {
            "i64": "__spawn_i64",
            "double": "__spawn_double",
            "i1": "__spawn_bool",
            "i8*": "__spawn_str",
        }
        if ty not in wrappers:
            self._lowering_error(f"spawn not supported for type {ty}")
        return wrappers[ty]

    def _join_wrapper_name(self, ty: str) -> str:
        wrappers = {
            "i64": "__join_i64",
            "double": "__join_double",
            "i1": "__join_bool",
            "i8*": "__join_str",
        }
        if ty not in wrappers:
            self._lowering_error(f"join not supported for type {ty}")
        return wrappers[ty]

    def _emit_direct_call(self, resolved_name: str, args: List[_StackValue]) -> _StackValue:
        signature = self._function_signatures.get(resolved_name)
        if signature is None:
            signature = self._builtin_signature(resolved_name)
        if signature is None:
            self._lowering_error(f"unknown function {resolved_name}")
        if len(args) != len(signature.param_types):
            self._lowering_error(
                f"function {resolved_name} expects {len(signature.param_types)} args, got {len(args)}"
            )
        rendered_args: List[str] = []
        for (param_name, param_type), arg in zip(signature.param_types.items(), args):
            if arg.ty != param_type:
                self._lowering_error(
                    f"argument for {resolved_name}.{param_name} expected {param_type}, got {arg.ty}"
                )
            rendered_args.append(f"{param_type} {arg.name}")
        dest = self._next_tmp()
        args_text = ", ".join(rendered_args)
        self._body.append(f"  {dest} = call {signature.return_type} @{resolved_name}({args_text})")
        return _StackValue(name=dest, ty=signature.return_type)

    def _emit_spawn_call(self, args: List[_StackValue]) -> None:
        if not args:
            self._lowering_error("__spawn expects at least 1 arg")
        target_name = self._literal_string(args[0], context="__spawn")
        call_args = args[1:]
        result = self._emit_direct_call(target_name, call_args)
        wrapper = self._spawn_wrapper_name(result.ty)
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call {result.ty} @{wrapper}({result.ty} {result.name})")
        self._stack.append(_StackValue(name=dest, ty=result.ty))

    def _emit_join_call(self, args: List[_StackValue]) -> None:
        if len(args) not in {1, 2, 3}:
            self._lowering_error("join expects between 1 and 3 args")
        handle = args[0]
        wrapper = self._join_wrapper_name(handle.ty)
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call {handle.ty} @{wrapper}({handle.ty} {handle.name})")
        self._stack.append(_StackValue(name=dest, ty=handle.ty))

    def _emit_async_token(self, args: List[_StackValue]) -> None:
        if args:
            self._lowering_error("Async.token expects 0 args")
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i64 @__async_token()")
        self._stack.append(_StackValue(name=dest, ty="i64"))

    def _emit_async_cancel(self, args: List[_StackValue]) -> None:
        if len(args) not in {1, 2}:
            self._lowering_error("Async.cancel expects 1 or 2 args")
        token = args[0]
        if token.ty != "i64":
            self._lowering_error("Async.cancel expects a token handle")
        reason = "null"
        if len(args) == 2:
            if args[1].ty != "i8*":
                self._lowering_error("Async.cancel reason must be a string or Null")
            reason = args[1].name
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i1 @__async_cancel(i64 {token.name}, i8* {reason})")
        self._stack.append(_StackValue(name=dest, ty="i1"))

    def _emit_async_is_cancelled(self, args: List[_StackValue]) -> None:
        if len(args) != 1:
            self._lowering_error("Async.is_cancelled expects 1 arg")
        token = args[0]
        if token.ty != "i64":
            self._lowering_error("Async.is_cancelled expects a token handle")
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i1 @__async_is_cancelled(i64 {token.name})")
        self._stack.append(_StackValue(name=dest, ty="i1"))

    def _emit_async_reason(self, args: List[_StackValue]) -> None:
        if len(args) != 1:
            self._lowering_error("Async.reason expects 1 arg")
        token = args[0]
        if token.ty != "i64":
            self._lowering_error("Async.reason expects a token handle")
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i8* @__async_reason(i64 {token.name})")
        self._stack.append(_StackValue(name=dest, ty="i8*"))

    def _emit_async_link(self, args: List[_StackValue]) -> None:
        if len(args) != 2:
            self._lowering_error("Async.link expects 2 args")
        token = args[0]
        if token.ty != "i64":
            self._lowering_error("Async.link expects a token handle")
        payload = self._value_payload(args[1])
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i1 @__async_link(i64 {token.name}, i64 {payload})")
        self._stack.append(_StackValue(name=dest, ty="i1"))

    def _call_function(self, call_spec: Tuple[str, int]) -> None:
        name, argc = call_spec
        args = [self._stack.pop() for _ in range(argc)][::-1]
        if name == "__import":
            self._emit_import_call(args)
            return
        if name == "__spawn":
            self._emit_spawn_call(args)
            return
        if name == "join":
            self._emit_join_call(args)
            return
        if name == "Async.token":
            self._emit_async_token(args)
            return
        if name == "Async.cancel":
            self._emit_async_cancel(args)
            return
        if name == "Async.is_cancelled":
            self._emit_async_is_cancelled(args)
            return
        if name == "Async.reason":
            self._emit_async_reason(args)
            return
        if name == "Async.link":
            self._emit_async_link(args)
            return
        if name.startswith("Map."):
            self._emit_map_call(name, args)
            return
        if name.startswith("Set."):
            self._emit_set_call(name, args)
            return
        if name.startswith("Deque."):
            self._emit_deque_call(name, args)
            return
        if name.startswith("Python.") and name not in {"Python.import_module", "Python.call"}:
            dotted = name[len("Python.") :]
            if "." not in dotted:
                self._lowering_error("Python call expects a module-qualified name")
            module_name, attr_name = dotted.rsplit(".", 1)
            self._emit_python_direct_call(module_name, attr_name, args)
            return
        if name == "__variant_assume":
            if len(args) != 2:
                self._lowering_error("__variant_assume expects 2 args")
            variant_name = self._literal_string(args[1], context="__variant_assume")
            value = args[0]
            self._stack.append(
                _StackValue(
                    name=value.name,
                    ty=value.ty,
                    source=value.source,
                    literal=value.literal,
                    literal_str=value.literal_str,
                    class_name=value.class_name,
                    variant_name=variant_name,
                )
            )
            return
        if name == "__variant_new":
            self._emit_variant_new(args)
            return
        if name == "__variant_tag":
            self._emit_variant_tag(args)
            return
        if name == "__variant_get":
            self._emit_variant_get(args)
            return
        if name == "Python.import_module":
            self._emit_python_import(args)
            return
        if name == "Python.call":
            self._emit_python_call(args)
            return
        if name == "__match_error":
            self._emit_match_error(args)
            return
        if name == "__class_new":
            self._emit_class_new(args)
            return
        if name == "__field_get":
            self._emit_field_get(args)
            return
        if name == "__field_set":
            self._emit_field_set(args)
            return
        if name == "__method_call":
            self._emit_method_call(args)
            return
        resolved_name = name
        if name == "heap_set":
            resolved_name = self._resolve_heap_set_name(args)
        elif name == "heap_get":
            resolved_name = self._resolve_heap_get_name(args)
        result = self._emit_direct_call(resolved_name, args)
        self._stack.append(result)
        if name == "heap_set":
            self._record_heap_cell_type(args)

    def _emit_map_call(self, name: str, args: List[_StackValue]) -> None:
        method = name.split(".", 1)[1]
        if method == "new":
            if args:
                self._lowering_error("Map.new expects 0 args")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_new()")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "len":
            if len(args) != 1:
                self._lowering_error("Map.len expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_len(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "set":
            if len(args) != 3:
                self._lowering_error("Map.set expects 3 args")
            key_payload = self._value_payload(args[1])
            value_payload = self._value_payload(args[2])
            self._body.append(
                f"  call i64 @__map_set(i64 {args[0].name}, i64 {key_payload}, i64 {value_payload})"
            )
            self._stack.append(args[2])
            return
        if method == "get":
            if len(args) not in {2, 3}:
                self._lowering_error("Map.get expects 2 or 3 args")
            key_payload = self._value_payload(args[1])
            default_ty = args[2].ty if len(args) == 3 else "i64"
            default_payload = self._value_payload(args[2]) if len(args) == 3 else "0"
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i64 @__map_get(i64 {args[0].name}, i64 {key_payload}, i64 {default_payload})"
            )
            self._stack.append(self._payload_to_value(dest, default_ty))
            return
        if method == "has":
            if len(args) != 2:
                self._lowering_error("Map.has expects 2 args")
            key_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i1 @__map_has(i64 {args[0].name}, i64 {key_payload})")
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "delete":
            if len(args) != 2:
                self._lowering_error("Map.delete expects 2 args")
            key_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i1 @__map_delete(i64 {args[0].name}, i64 {key_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "keys":
            if len(args) != 1:
                self._lowering_error("Map.keys expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_keys(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "values":
            if len(args) != 1:
                self._lowering_error("Map.values expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_values(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "entries":
            if len(args) != 1:
                self._lowering_error("Map.entries expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_entries(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "from_entries":
            if len(args) != 1:
                self._lowering_error("Map.from_entries expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_from_entries(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        self._lowering_error(f"unknown Map method {method}")

    def _emit_set_call(self, name: str, args: List[_StackValue]) -> None:
        method = name.split(".", 1)[1]
        if method == "new":
            if args:
                self._lowering_error("Set.new expects 0 args")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__set_new()")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "from_list":
            if len(args) != 1:
                self._lowering_error("Set.from_list expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__set_from_list(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "len":
            if len(args) != 1:
                self._lowering_error("Set.len expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__set_len(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "add":
            if len(args) != 2:
                self._lowering_error("Set.add expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i1 @__set_add(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "delete":
            if len(args) != 2:
                self._lowering_error("Set.delete expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i1 @__set_delete(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "has":
            if len(args) != 2:
                self._lowering_error("Set.has expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i1 @__set_has(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "to_list":
            if len(args) != 1:
                self._lowering_error("Set.to_list expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__set_to_list(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        self._lowering_error(f"unknown Set method {method}")

    def _emit_deque_call(self, name: str, args: List[_StackValue]) -> None:
        method = name.split(".", 1)[1]
        if method == "new":
            if len(args) > 1:
                self._lowering_error("Deque.new expects 0 or 1 args")
            dest = self._next_tmp()
            if args:
                self._body.append(f"  {dest} = call i64 @__deque_from_list(i64 {args[0].name})")
            else:
                self._body.append(f"  {dest} = call i64 @__deque_new()")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "len":
            if len(args) != 1:
                self._lowering_error("Deque.len expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_len(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "push_left":
            if len(args) != 2:
                self._lowering_error("Deque.push_left expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i64 @__deque_push_left(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "push_right":
            if len(args) != 2:
                self._lowering_error("Deque.push_right expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i64 @__deque_push_right(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "pop_left":
            if len(args) != 1:
                self._lowering_error("Deque.pop_left expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_pop_left(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "pop_right":
            if len(args) != 1:
                self._lowering_error("Deque.pop_right expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_pop_right(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "peek_left":
            if len(args) != 1:
                self._lowering_error("Deque.peek_left expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_peek_left(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "peek_right":
            if len(args) != 1:
                self._lowering_error("Deque.peek_right expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_peek_right(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "to_list":
            if len(args) != 1:
                self._lowering_error("Deque.to_list expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_to_list(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        self._lowering_error(f"unknown Deque method {method}")

    def _emit_class_new(self, args: List[_StackValue]) -> None:
        if not args:
            self._lowering_error("__class_new expects at least 1 arg")
        class_name = self._literal_string(args[0], context="__class_new")
        layout = self._class_layouts.get(class_name)
        if layout is None:
            self._lowering_error(f"unknown class {class_name}")
        if (len(args) - 1) % 2 != 0:
            self._lowering_error("__class_new expects field name/value pairs")
        size = len(layout) + 1
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i64 @__new(i64 {size})")
        ptr = _StackValue(name=dest, ty="i64", source=dest, class_name=class_name)
        class_id = self._class_ids[class_name]
        self._emit_heap_set(ptr, 0, self._const_i64(class_id))
        for index in range(1, len(args), 2):
            field_name = self._literal_string(args[index], context="__class_new")
            value = args[index + 1]
            field_index = self._class_field_index(class_name, field_name)
            self._emit_heap_set(ptr, field_index, value)
            self._class_field_types[(class_name, field_index)] = value.ty
        self._stack.append(_StackValue(name=dest, ty="i64", source=dest, class_name=class_name))

    def _emit_import_call(self, args: List[_StackValue]) -> None:
        if len(args) != 1:
            self._lowering_error("__import expects 1 arg")
        module_name = self._literal_string(args[0], context="__import")
        init_name = self._module_inits.get(module_name)
        if init_name is None:
            self._lowering_error(f"unknown module {module_name}")
        init_signature = self._function_signatures.get(init_name)
        if init_signature is None:
            self._lowering_error(f"missing module init function {init_name}")
        if init_signature.param_types:
            self._lowering_error(f"module init {init_name} expects no args")
        self._body.append(f"  {self._next_tmp()} = call {init_signature.return_type} @{init_name}()")
        name, length = self._string_constant(module_name)
        dest = self._next_tmp()
        self._body.append(
            f"  {dest} = getelementptr inbounds [{length} x i8], [{length} x i8]* @{name}, i32 0, i32 0"
        )
        self._stack.append(_StackValue(name=dest, ty="i8*", literal_str=module_name, class_name=module_name))

    def _emit_python_import(self, args: List[_StackValue]) -> None:
        if len(args) not in {1, 2}:
            self._lowering_error("Python.import_module expects 1 or 2 args")
        module_name = self._literal_string(args[0], context="Python.import_module")
        allowlist = args[1] if len(args) == 2 else None
        if allowlist is None or (allowlist.ty == "i8*" and allowlist.name == "null"):
            allow_ptr = "0"
        else:
            allow_ptr = allowlist.name
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i64 @__py_import_module(i8* {args[0].name}, i64 {allow_ptr})")
        self._python_modules.add(module_name)
        self._stack.append(_StackValue(name=dest, ty="i64", class_name=module_name))

    def _emit_python_call(
        self,
        args: List[_StackValue],
        *,
        module_name_override: Optional[str] = None,
    ) -> None:
        if len(args) < 2 or len(args) > 4:
            self._lowering_error("Python.call expects 2 to 4 args")
        module_arg = args[0]
        attr_arg = args[1]
        module_name = module_name_override or self._literal_string(module_arg, context="Python.call")
        attr_name = self._literal_string(attr_arg, context="Python.call")
        call_args = args[2] if len(args) >= 3 else None
        opts = args[3] if len(args) == 4 else None
        if opts is None or (opts.ty == "i8*" and opts.name == "null"):
            allow_ptr = "0"
        else:
            allow_ptr = opts.name
        if call_args is None or (call_args.ty == "i8*" and call_args.name == "null"):
            args_ptr = "0"
            types_ptr = "0"
        else:
            args_ptr = call_args.name
            types_ptr = self._emit_python_arg_types(call_args)
        name, length = self._string_constant(module_name)
        module_ptr = self._next_tmp()
        self._body.append(
            f"  {module_ptr} = getelementptr inbounds [{length} x i8], [{length} x i8]* @{name}, i32 0, i32 0"
        )
        attr_name_const, attr_len = self._string_constant(attr_name)
        attr_ptr = self._next_tmp()
        self._body.append(
            f"  {attr_ptr} = getelementptr inbounds [{attr_len} x i8], [{attr_len} x i8]* @{attr_name_const}, i32 0, i32 0"
        )
        dest = self._next_tmp()
        self._body.append(
            f"  {dest} = call i64 @__py_call(i8* {module_ptr}, i8* {attr_ptr}, i64 {args_ptr}, i64 {types_ptr}, i64 {allow_ptr})"
        )
        self._stack.append(_StackValue(name=dest, ty="i64"))

    def _emit_python_direct_call(
        self,
        module_name: str,
        attr_name: str,
        args: List[_StackValue],
    ) -> None:
        if args:
            size = len(args)
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__new(i64 {size})")
            ptr = _StackValue(name=dest, ty="i64", source=dest)
            for index, value in enumerate(args):
                self._emit_heap_set(ptr, index, value)
            arg_list = ptr
        else:
            arg_list = _StackValue(name="null", ty="i8*")
        self._emit_python_call(
            [
                _StackValue(name="null", ty="i8*", literal_str=module_name),
                _StackValue(name="null", ty="i8*", literal_str=attr_name),
                arg_list,
            ],
            module_name_override=module_name,
        )

    def _emit_python_arg_types(self, args_list: _StackValue) -> str:
        if args_list.source is None:
            return "0"
        size = self._heap_list_length(args_list.source)
        if size is None:
            return "0"
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i64 @__new(i64 {size})")
        ptr = _StackValue(name=dest, ty="i64", source=dest)
        for index in range(size):
            tag = self._python_type_tag(args_list.source, index)
            self._emit_heap_set(ptr, index, self._const_i64(tag))
        return dest

    def _heap_list_length(self, ptr_name: str) -> Optional[int]:
        candidates = [idx for (name, idx) in self._heap_cell_types.keys() if name == ptr_name]
        if not candidates:
            return None
        return max(candidates) + 1

    def _python_type_tag(self, ptr_name: str, idx: int) -> int:
        ty = self._heap_cell_types.get((ptr_name, idx))
        if ty == "double":
            return 1
        if ty == "i1":
            return 2
        if ty == "i8*":
            return 3
        return 0

    def _emit_field_get(self, args: List[_StackValue]) -> None:
        if len(args) != 2:
            self._lowering_error("__field_get expects 2 args")
        obj, field_name = args
        class_name = obj.class_name
        if class_name is None:
            self._lowering_error("field access on unknown class value")
        if class_name in self._module_inits:
            self._lowering_error("field access on module values is not supported yet")
        field_literal = self._literal_string(field_name, context="__field_get")
        field_index = self._class_field_index(class_name, field_literal)
        resolved_name = self._resolve_class_heap_get_name(class_name, field_index)
        dest = self._next_tmp()
        arg_text = f"i64 {obj.name}, i64 {field_index}"
        self._body.append(f"  {dest} = call {self._heap_get_return_type(resolved_name)} @{resolved_name}({arg_text})")
        self._stack.append(
            _StackValue(name=dest, ty=self._heap_get_return_type(resolved_name))
        )

    def _emit_field_set(self, args: List[_StackValue]) -> None:
        if len(args) != 3:
            self._lowering_error("__field_set expects 3 args")
        obj, field_name, value = args
        class_name = obj.class_name
        if class_name is None:
            self._lowering_error("field access on unknown class value")
        field_literal = self._literal_string(field_name, context="__field_set")
        field_index = self._class_field_index(class_name, field_literal)
        self._emit_heap_set(obj, field_index, value)
        self._class_field_types[(class_name, field_index)] = value.ty
        self._stack.append(value)

    def _emit_method_call(self, args: List[_StackValue]) -> None:
        if len(args) < 2:
            self._lowering_error("__method_call expects at least 2 args")
        obj, method_name, *rest = args
        class_name = obj.class_name
        if class_name == "Async":
            method_literal = self._literal_string(method_name, context="__method_call")
            if method_literal == "token":
                self._emit_async_token(rest)
                return
            if method_literal == "cancel":
                self._emit_async_cancel(rest)
                return
            if method_literal == "is_cancelled":
                self._emit_async_is_cancelled(rest)
                return
            if method_literal == "reason":
                self._emit_async_reason(rest)
                return
            if method_literal == "link":
                self._emit_async_link(rest)
                return
            self._lowering_error(f"unknown Async method {method_literal}")
        if class_name == "Python":
            method_literal = self._literal_string(method_name, context="__method_call")
            if method_literal == "import_module":
                self._emit_python_import(rest)
                return
            if method_literal == "call":
                self._emit_python_call(rest)
                return
            self._lowering_error(f"unknown Python method {method_literal}")
        if class_name in {"Map", "Set", "Deque"}:
            method_literal = self._literal_string(method_name, context="__method_call")
            if class_name == "Map":
                self._emit_map_call(f"Map.{method_literal}", rest)
            elif class_name == "Set":
                self._emit_set_call(f"Set.{method_literal}", rest)
            else:
                self._emit_deque_call(f"Deque.{method_literal}", rest)
            return
        if class_name in self._python_modules:
            method_literal = self._literal_string(method_name, context="__method_call")
            self._emit_python_call(
                [
                    _StackValue(name=obj.name, ty=obj.ty, class_name=class_name, literal_str=class_name),
                    _StackValue(name=method_name.name, ty=method_name.ty, literal_str=method_literal),
                    *rest,
                ],
                module_name_override=class_name,
            )
            return
        if class_name in self._module_inits:
            method_literal = self._literal_string(method_name, context="__method_call")
            target_name = f"{class_name}.{method_literal}"
            signature = self._function_signatures.get(target_name)
            if signature is None:
                self._lowering_error(f"unknown function {target_name}")
            if len(rest) != len(signature.param_types):
                self._lowering_error(
                    f"function {target_name} expects {len(signature.param_types)} args, got {len(rest)}"
                )
            rendered_args: List[str] = []
            for (param_name, param_type), arg in zip(signature.param_types.items(), rest):
                if arg.ty != param_type:
                    self._lowering_error(
                        f"argument for {target_name}.{param_name} expected {param_type}, got {arg.ty}"
                    )
                rendered_args.append(f"{param_type} {arg.name}")
            dest = self._next_tmp()
            args_text = ", ".join(rendered_args)
            self._body.append(f"  {dest} = call {signature.return_type} @{target_name}({args_text})")
            self._stack.append(_StackValue(name=dest, ty=signature.return_type))
            return
        if class_name is None:
            self._lowering_error("method call on unknown class value")
        method_literal = self._literal_string(method_name, context="__method_call")
        target_name = self._resolve_method_target(class_name, method_literal)
        signature = self._function_signatures.get(target_name)
        if signature is None:
            self._lowering_error(f"unknown function {target_name}")
        call_args = [obj] + list(rest)
        if len(call_args) != len(signature.param_types):
            self._lowering_error(
                f"function {target_name} expects {len(signature.param_types)} args, got {len(call_args)}"
            )
        rendered_args: List[str] = []
        for (param_name, param_type), arg in zip(signature.param_types.items(), call_args):
            if arg.ty != param_type:
                self._lowering_error(
                    f"argument for {target_name}.{param_name} expected {param_type}, got {arg.ty}"
                )
            rendered_args.append(f"{param_type} {arg.name}")
        dest = self._next_tmp()
        args_text = ", ".join(rendered_args)
        self._body.append(f"  {dest} = call {signature.return_type} @{target_name}({args_text})")
        self._stack.append(_StackValue(name=dest, ty=signature.return_type))

    def _emit_variant_new(self, args: List[_StackValue]) -> None:
        if len(args) < 2:
            self._lowering_error("__variant_new expects at least 2 args (variant, type_name)")
        variant_name = self._literal_string(args[0], context="__variant_new")
        type_name = args[1].literal_str
        if type_name is None:
            type_name = self._variant_to_type.get(variant_name)
        fields = self._variant_fields.get(variant_name)
        if fields is None:
            self._lowering_error(f"unknown variant {variant_name}")
        if (len(args) - 2) % 2 != 0:
            self._lowering_error("__variant_new expects field name/value pairs")
        provided_fields = {}
        for index in range(2, len(args), 2):
            field_name = self._literal_string(args[index], context="__variant_new")
            provided_fields[field_name] = args[index + 1]
        missing = sorted(set(fields) - set(provided_fields.keys()))
        extra = sorted(set(provided_fields.keys()) - set(fields))
        if missing:
            self._lowering_error(f"missing field(s) for variant {variant_name}: {', '.join(missing)}")
        if extra:
            self._lowering_error(f"unknown field(s) for variant {variant_name}: {', '.join(extra)}")
        size = len(fields) + 1
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i64 @__new(i64 {size})")
        ptr = _StackValue(name=dest, ty="i64", source=dest, variant_name=variant_name)
        self._emit_heap_set(ptr, 0, _StackValue(name=args[0].name, ty="i8*", literal_str=variant_name))
        for idx, field_name in enumerate(fields, start=1):
            value = provided_fields[field_name]
            self._emit_heap_set(ptr, idx, value)
        if type_name is not None:
            self._variant_to_type.setdefault(variant_name, type_name)
        self._stack.append(_StackValue(name=dest, ty="i64", variant_name=variant_name))

    def _emit_variant_tag(self, args: List[_StackValue]) -> None:
        if len(args) != 1:
            self._lowering_error("__variant_tag expects 1 arg")
        value = args[0]
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i8* @heap_get_str(i64 {value.name}, i64 0)")
        self._stack.append(_StackValue(name=dest, ty="i8*", literal_str=value.variant_name))

    def _emit_variant_get(self, args: List[_StackValue]) -> None:
        if len(args) != 2:
            self._lowering_error("__variant_get expects 2 args")
        value, field_name_value = args
        field_name = self._literal_string(field_name_value, context="__variant_get")
        variant_name = self._resolve_variant_name(value)
        if variant_name is None:
            self._lowering_error("variant access on unknown tagged value")
        field_index = self._variant_field_index(variant_name, field_name)
        field_type = self._variant_field_type(variant_name, field_name)
        resolved_name = self._resolve_variant_heap_get_name(field_type)
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call {field_type} @{resolved_name}(i64 {value.name}, i64 {field_index})")
        self._stack.append(_StackValue(name=dest, ty=field_type))

    def _emit_match_error(self, args: List[_StackValue]) -> None:
        if len(args) != 1:
            self._lowering_error("__match_error expects 1 arg")
        arg = args[0]
        self._body.append(f"  call void @__match_error(i64 {arg.name})")

    # ----- Helpers -----

    def _pop_condition(self) -> str:
        if not self._stack:
            raise RuntimeError("branch requested with empty stack")
        cond = self._stack.pop()
        if cond.ty == "i1":
            return cond.name
        if cond.ty == "i64":
            dest = self._next_tmp()
            self._body.append(f"  {dest} = icmp ne i64 {cond.name}, 0")
            return dest
        if cond.ty == "double":
            dest = self._next_tmp()
            self._body.append(f"  {dest} = fcmp one double {cond.name}, 0.0")
            return dest
        self._lowering_error(f"conditional branches for type {cond.ty} not supported")

    def _resolve_variant_name(self, value: _StackValue) -> Optional[str]:
        if value.variant_name:
            return value.variant_name
        if value.source:
            return self._var_variants.get(value.source)
        return None

    def _literal_string(self, value: _StackValue, *, context: str) -> str:
        if value.literal_str is None:
            self._lowering_error(f"{context} expects a string literal")
        return value.literal_str

    def _const_i64(self, value: int) -> _StackValue:
        return _StackValue(name=str(value), ty="i64", literal=value)

    def _emit_heap_set(self, ptr: _StackValue, idx: int, value: _StackValue) -> None:
        idx_value = self._const_i64(idx)
        args = [ptr, idx_value, value]
        resolved_name = self._resolve_heap_set_name(args)
        signature = self._builtin_signature(resolved_name)
        if signature is None:
            self._lowering_error(f"unknown function {resolved_name}")
        rendered_args: List[str] = []
        for (param_name, param_type), arg in zip(signature.param_types.items(), args):
            if arg.ty != param_type:
                self._lowering_error(
                    f"argument for {resolved_name}.{param_name} expected {param_type}, got {arg.ty}"
                )
            rendered_args.append(f"{param_type} {arg.name}")
        dest = self._next_tmp()
        args_text = ", ".join(rendered_args)
        self._body.append(f"  {dest} = call {signature.return_type} @{resolved_name}({args_text})")
        self._record_heap_cell_type(args)

    def _resolve_class_heap_get_name(self, class_name: str, field_index: int) -> str:
        cell_type = self._class_field_types.get((class_name, field_index))
        if cell_type == "i8*":
            return "heap_get_str"
        if cell_type == "double":
            return "heap_get_double"
        if cell_type == "i1":
            return "heap_get_bool"
        return "heap_get"

    def _heap_get_return_type(self, name: str) -> str:
        if name == "heap_get_str":
            return "i8*"
        if name == "heap_get_double":
            return "double"
        if name == "heap_get_bool":
            return "i1"
        return "i64"

    def _resolve_variant_heap_get_name(self, field_type: str) -> str:
        if field_type == "i8*":
            return "heap_get_str"
        if field_type == "double":
            return "heap_get_double"
        if field_type == "i1":
            return "heap_get_bool"
        return "heap_get"

    def _variant_field_index(self, variant_name: str, field_name: str) -> int:
        fields = self._variant_fields.get(variant_name)
        if fields is None:
            self._lowering_error(f"unknown variant {variant_name}")
        if field_name not in fields:
            self._lowering_error(f"field {field_name} missing for variant {variant_name}")
        return fields.index(field_name) + 1

    def _variant_field_type(self, variant_name: str, field_name: str) -> str:
        return self._variant_field_types.get((variant_name, field_name), "i64")

    def _split_field_name(self, field_name: str) -> Tuple[Optional[str], str]:
        if "." in field_name:
            owner, rest = field_name.split(".", 1)
            return owner, rest
        return None, field_name

    def _class_field_index(self, class_name: str, field_name: str) -> int:
        layout = self._class_layouts.get(class_name)
        if layout is None:
            self._lowering_error(f"unknown class {class_name}")
        owner_hint, raw_name = self._split_field_name(field_name)
        matches = [
            (idx, owner)
            for idx, (owner, fname) in enumerate(layout)
            if fname == raw_name
        ]
        if owner_hint:
            for idx, owner in matches:
                if owner == owner_hint:
                    return idx + 1
            self._lowering_error(f"unknown field {raw_name} for base class {owner_hint}")
        if matches:
            for idx, owner in matches:
                if owner == class_name:
                    return idx + 1
            if len(matches) == 1:
                return matches[0][0] + 1
            self._lowering_error(f"ambiguous field {raw_name} on class {class_name}")
        self._lowering_error(f"unknown field {raw_name} for class {class_name}")
        raise RuntimeError("unreachable")

    def _resolve_method_target(self, class_name: str, method_name: str) -> str:
        mro = self._class_mros.get(class_name)
        if mro is None:
            self._lowering_error(f"unknown class {class_name}")
        for cls in mro:
            methods = self._class_methods.get(cls, {})
            target = methods.get(method_name)
            if target is not None:
                return target
        self._lowering_error(f"no method {method_name} for class {class_name}")
        raise RuntimeError("unreachable")

    def _next_tmp(self) -> str:
        self._tmp_index += 1
        return f"%t{self._tmp_index}"

    def _next_label(self, prefix: str) -> str:
        self._label_index += 1
        return f"{prefix}.{self._label_index}"

    def _format_for_type(self, ty: str) -> tuple[str, int]:
        if ty == "double":
            return ".fmt_double", 5
        if ty in {"i64", "i1"}:
            return ".fmt_i64", 5
        if ty == "i8*":
            return ".fmt_str", 4
        self._lowering_error(f"printing values of type {ty} not supported")

    def _header(self) -> List[str]:
        lines: List[str] = []
        if self._data_layout:
            lines.append(f'target datalayout = "{self._data_layout}"')
        if self._target_triple:
            lines.append(f'target triple = "{self._target_triple}"')
        lines.extend(
            [
            "@.fmt_i64 = private unnamed_addr constant [5 x i8] c\"%ld\\0A\\00\"",
            "@.fmt_double = private unnamed_addr constant [5 x i8] c\"%lf\\0A\\00\"",
            "@.fmt_str = private unnamed_addr constant [4 x i8] c\"%s\\0A\\00\"",
            "@.heap_bounds_err = private unnamed_addr constant [54 x i8] c\"heap access error: index %ld out of range (size %ld)\\0A\\00\"",
            "@.match_error_fmt = private unnamed_addr constant [33 x i8] c\"non-exhaustive match for tag %s\\0A\\00\"",
            "@.deque_empty_err = private unnamed_addr constant [16 x i8] c\"deque is empty\\0A\\00\"",
            "declare i32 @printf(i8*, ...)",
            "declare i32 @fflush(i8*)",
            "declare i8* @calloc(i64, i64)",
            "declare void @free(i8*)",
            "declare void @exit(i32)",
            "declare i64 @__py_import_module(i8*, i64)",
            "declare i64 @__py_call(i8*, i8*, i64, i64, i64)",
            ]
        )
        lines.extend(self._runtime_helpers())
        return lines

    def _runtime_helpers(self) -> List[str]:
        return [
            "define i64 @__new(i64 %size) {",
            "entry:",
            "  %alloc_size = add i64 %size, 1",
            "  %ptr = call i8* @calloc(i64 %alloc_size, i64 8)",
            "  %base = bitcast i8* %ptr to i64*",
            "  store i64 %size, i64* %base",
            "  %data = getelementptr i64, i64* %base, i64 1",
            "  %int = ptrtoint i64* %data to i64",
            "  ret i64 %int",
            "}",
            "define i64 @new(i64 %size) {",
            "entry:",
            "  %ptr = call i64 @__new(i64 %size)",
            "  ret i64 %ptr",
            "}",
            "define i64 @__heap_bounds_error(i64 %idx, i64 %size) {",
            "entry:",
            "  %fmt = getelementptr [54 x i8], [54 x i8]* @.heap_bounds_err, i64 0, i64 0",
            "  %_printed = call i32 (i8*, ...) @printf(i8* %fmt, i64 %idx, i64 %size)",
            "  %_flushed = call i32 @fflush(i8* null)",
            "  call void @exit(i32 1)",
            "  ret i64 0",
            "}",
            "define i64 @heap_get(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %data = inttoptr i64 %ptr to i64*",
            "  %base = getelementptr i64, i64* %data, i64 -1",
            "  %size = load i64, i64* %base",
            "  %neg = icmp slt i64 %idx, 0",
            "  %oob = icmp sge i64 %idx, %size",
            "  %bad = or i1 %neg, %oob",
            "  br i1 %bad, label %err, label %ok",
            "err:",
            "  %_ignored = call i64 @__heap_bounds_error(i64 %idx, i64 %size)",
            "  ret i64 0",
            "ok:",
            "  %offset = getelementptr i64, i64* %data, i64 %idx",
            "  %value = load i64, i64* %offset",
            "  ret i64 %value",
            "}",
            "define i64 @heap_set(i64 %ptr, i64 %idx, i64 %value) {",
            "entry:",
            "  %data = inttoptr i64 %ptr to i64*",
            "  %base = getelementptr i64, i64* %data, i64 -1",
            "  %size = load i64, i64* %base",
            "  %neg = icmp slt i64 %idx, 0",
            "  %oob = icmp sge i64 %idx, %size",
            "  %bad = or i1 %neg, %oob",
            "  br i1 %bad, label %err, label %ok",
            "err:",
            "  %_ignored = call i64 @__heap_bounds_error(i64 %idx, i64 %size)",
            "  ret i64 0",
            "ok:",
            "  %offset = getelementptr i64, i64* %data, i64 %idx",
            "  store i64 %value, i64* %offset",
            "  ret i64 0",
            "}",
            "define i8* @heap_get_str(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %raw = call i64 @heap_get(i64 %ptr, i64 %idx)",
            "  %cast = inttoptr i64 %raw to i8*",
            "  ret i8* %cast",
            "}",
            "define double @heap_get_double(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %raw = call i64 @heap_get(i64 %ptr, i64 %idx)",
            "  %cast = bitcast i64 %raw to double",
            "  ret double %cast",
            "}",
            "define i1 @heap_get_bool(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %raw = call i64 @heap_get(i64 %ptr, i64 %idx)",
            "  %cast = trunc i64 %raw to i1",
            "  ret i1 %cast",
            "}",
            "define i64 @heap_set_str(i64 %ptr, i64 %idx, i8* %value) {",
            "entry:",
            "  %cast = ptrtoint i8* %value to i64",
            "  %_ignored = call i64 @heap_set(i64 %ptr, i64 %idx, i64 %cast)",
            "  ret i64 0",
            "}",
            "define i64 @heap_set_double(i64 %ptr, i64 %idx, double %value) {",
            "entry:",
            "  %cast = bitcast double %value to i64",
            "  %_ignored = call i64 @heap_set(i64 %ptr, i64 %idx, i64 %cast)",
            "  ret i64 0",
            "}",
            "define i64 @heap_set_bool(i64 %ptr, i64 %idx, i1 %value) {",
            "entry:",
            "  %cast = zext i1 %value to i64",
            "  %_ignored = call i64 @heap_set(i64 %ptr, i64 %idx, i64 %cast)",
            "  ret i64 0",
            "}",
            "define i64 @heap_len(i64 %ptr) {",
            "entry:",
            "  %data = inttoptr i64 %ptr to i64*",
            "  %base = getelementptr i64, i64* %data, i64 -1",
            "  %size = load i64, i64* %base",
            "  ret i64 %size",
            "}",
            "define i64 @delete(i64 %ptr) {",
            "entry:",
            "  %data = inttoptr i64 %ptr to i64*",
            "  %base = getelementptr i64, i64* %data, i64 -1",
            "  %raw = bitcast i64* %base to i8*",
            "  call void @free(i8* %raw)",
            "  ret i64 0",
            "}",
            "define i64 @__spawn_i64(i64 %value) {",
            "entry:",
            "  ret i64 %value",
            "}",
            "define double @__spawn_double(double %value) {",
            "entry:",
            "  ret double %value",
            "}",
            "define i1 @__spawn_bool(i1 %value) {",
            "entry:",
            "  ret i1 %value",
            "}",
            "define i8* @__spawn_str(i8* %value) {",
            "entry:",
            "  ret i8* %value",
            "}",
            "define i64 @__join_i64(i64 %value) {",
            "entry:",
            "  ret i64 %value",
            "}",
            "define double @__join_double(double %value) {",
            "entry:",
            "  ret double %value",
            "}",
            "define i1 @__join_bool(i1 %value) {",
            "entry:",
            "  ret i1 %value",
            "}",
            "define i8* @__join_str(i8* %value) {",
            "entry:",
            "  ret i8* %value",
            "}",
            "define i64 @__async_token() {",
            "entry:",
            "  %token = call i64 @__new(i64 2)",
            "  %_ignored0 = call i64 @heap_set(i64 %token, i64 0, i64 0)",
            "  %_ignored1 = call i64 @heap_set(i64 %token, i64 1, i64 0)",
            "  ret i64 %token",
            "}",
            "define i1 @__async_is_cancelled(i64 %token) {",
            "entry:",
            "  %flag = call i64 @heap_get(i64 %token, i64 0)",
            "  %is_set = icmp ne i64 %flag, 0",
            "  ret i1 %is_set",
            "}",
            "define i1 @__async_cancel(i64 %token, i8* %reason) {",
            "entry:",
            "  %flag = call i64 @heap_get(i64 %token, i64 0)",
            "  %already = icmp ne i64 %flag, 0",
            "  br i1 %already, label %done, label %set",
            "set:",
            "  %_set_flag = call i64 @heap_set(i64 %token, i64 0, i64 1)",
            "  %reason_int = ptrtoint i8* %reason to i64",
            "  %_set_reason = call i64 @heap_set(i64 %token, i64 1, i64 %reason_int)",
            "  br label %done",
            "done:",
            "  %res = phi i1 [false, %entry], [true, %set]",
            "  ret i1 %res",
            "}",
            "define i8* @__async_reason(i64 %token) {",
            "entry:",
            "  %raw = call i64 @heap_get(i64 %token, i64 1)",
            "  %ptr = inttoptr i64 %raw to i8*",
            "  ret i8* %ptr",
            "}",
            "define i1 @__async_link(i64 %token, i64 %handle) {",
            "entry:",
            "  %flag = call i64 @heap_get(i64 %token, i64 0)",
            "  %cancelled = icmp ne i64 %flag, 0",
            "  %linked = xor i1 %cancelled, true",
            "  ret i1 %linked",
            "}",
            "define void @__match_error(i64 %ptr) {",
            "entry:",
            "  %tag = call i8* @heap_get_str(i64 %ptr, i64 0)",
            "  %fmt = getelementptr [33 x i8], [33 x i8]* @.match_error_fmt, i64 0, i64 0",
            "  %_printed = call i32 (i8*, ...) @printf(i8* %fmt, i8* %tag)",
            "  %_flushed = call i32 @fflush(i8* null)",
            "  call void @exit(i32 1)",
            "  ret void",
            "}",
            "define void @__deque_empty_error() {",
            "entry:",
            "  %fmt = getelementptr [16 x i8], [16 x i8]* @.deque_empty_err, i64 0, i64 0",
            "  %_printed = call i32 (i8*, ...) @printf(i8* %fmt)",
            "  %_flushed = call i32 @fflush(i8* null)",
            "  call void @exit(i32 1)",
            "  ret void",
            "}",
            "define i64 @__map_new() {",
            "entry:",
            "  %map = call i64 @__new(i64 2)",
            "  %entries = call i64 @__new(i64 0)",
            "  %_ignored0 = call i64 @heap_set(i64 %map, i64 0, i64 0)",
            "  %_ignored1 = call i64 @heap_set(i64 %map, i64 1, i64 %entries)",
            "  ret i64 %map",
            "}",
            "define i64 @__map_len(i64 %map) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  ret i64 %len",
            "}",
            "define i64 @__map_find(i64 %entries, i64 %len, i64 %key) {",
            "entry:",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %next_loop]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %not_found, label %check",
            "check:",
            "  %idx = mul i64 %i, 2",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %idx)",
            "  %eq = icmp eq i64 %cur, %key",
            "  br i1 %eq, label %found, label %next_loop",
            "next_loop:",
            "  %next = add i64 %i, 1",
            "  br label %loop",
            "found:",
            "  ret i64 %i",
            "not_found:",
            "  ret i64 -1",
            "}",
            "define i64 @__map_get(i64 %map, i64 %key, i64 %default) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %idx = call i64 @__map_find(i64 %entries, i64 %len, i64 %key)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %ok, label %missing",
            "ok:",
            "  %pos = mul i64 %idx, 2",
            "  %val_idx = add i64 %pos, 1",
            "  %val = call i64 @heap_get(i64 %entries, i64 %val_idx)",
            "  ret i64 %val",
            "missing:",
            "  ret i64 %default",
            "}",
            "define i1 @__map_has(i64 %map, i64 %key) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %idx = call i64 @__map_find(i64 %entries, i64 %len, i64 %key)",
            "  %found = icmp sge i64 %idx, 0",
            "  ret i1 %found",
            "}",
            "define i1 @__map_delete(i64 %map, i64 %key) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %idx = call i64 @__map_find(i64 %entries, i64 %len, i64 %key)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %do_delete, label %not_found",
            "do_delete:",
            "  %new_len = sub i64 %len, 1",
            "  %new_size = mul i64 %new_len, 2",
            "  %new_entries = call i64 @__new(i64 %new_size)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %do_delete], [%next, %copy_next]",
            "  %write = phi i64 [0, %do_delete], [%write_next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %check",
            "check:",
            "  %skip = icmp eq i64 %i, %idx",
            "  br i1 %skip, label %skip_entry, label %copy_entry",
            "skip_entry:",
            "  %next_skip = add i64 %i, 1",
            "  %write_keep = add i64 %write, 0",
            "  br label %copy_next",
            "copy_entry:",
            "  %src_pos = mul i64 %i, 2",
            "  %src_val = add i64 %src_pos, 1",
            "  %key_val = call i64 @heap_get(i64 %entries, i64 %src_pos)",
            "  %val_val = call i64 @heap_get(i64 %entries, i64 %src_val)",
            "  %dst_pos = mul i64 %write, 2",
            "  %dst_val = add i64 %dst_pos, 1",
            "  %_k = call i64 @heap_set(i64 %new_entries, i64 %dst_pos, i64 %key_val)",
            "  %_v = call i64 @heap_set(i64 %new_entries, i64 %dst_val, i64 %val_val)",
            "  %next_copy = add i64 %i, 1",
            "  %write_adv = add i64 %write, 1",
            "  br label %copy_next",
            "copy_next:",
            "  %next = phi i64 [%next_skip, %skip_entry], [%next_copy, %copy_entry]",
            "  %write_next = phi i64 [%write_keep, %skip_entry], [%write_adv, %copy_entry]",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %map, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %map, i64 1, i64 %new_entries)",
            "  ret i1 1",
            "not_found:",
            "  ret i1 0",
            "}",
            "define i64 @__map_set(i64 %map, i64 %key, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %idx = call i64 @__map_find(i64 %entries, i64 %len, i64 %key)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %update, label %extend",
            "update:",
            "  %pos = mul i64 %idx, 2",
            "  %val_idx = add i64 %pos, 1",
            "  %_u = call i64 @heap_set(i64 %entries, i64 %val_idx, i64 %value)",
            "  ret i64 %value",
            "extend:",
            "  %new_len = add i64 %len, 1",
            "  %new_size = mul i64 %new_len, 2",
            "  %new_entries = call i64 @__new(i64 %new_size)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %extend], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %src_pos = mul i64 %i, 2",
            "  %src_val = add i64 %src_pos, 1",
            "  %key_val = call i64 @heap_get(i64 %entries, i64 %src_pos)",
            "  %val_val = call i64 @heap_get(i64 %entries, i64 %src_val)",
            "  %_k = call i64 @heap_set(i64 %new_entries, i64 %src_pos, i64 %key_val)",
            "  %_v = call i64 @heap_set(i64 %new_entries, i64 %src_val, i64 %val_val)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %key_pos = mul i64 %len, 2",
            "  %val_pos = add i64 %key_pos, 1",
            "  %_nk = call i64 @heap_set(i64 %new_entries, i64 %key_pos, i64 %key)",
            "  %_nv = call i64 @heap_set(i64 %new_entries, i64 %val_pos, i64 %value)",
            "  %_l = call i64 @heap_set(i64 %map, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %map, i64 1, i64 %new_entries)",
            "  ret i64 %value",
            "}",
            "define i64 @__map_keys(i64 %map) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %keys = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %src = mul i64 %i, 2",
            "  %key_val = call i64 @heap_get(i64 %entries, i64 %src)",
            "  %_k = call i64 @heap_set(i64 %keys, i64 %i, i64 %key_val)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %keys",
            "}",
            "define i64 @__map_values(i64 %map) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %values = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %src = mul i64 %i, 2",
            "  %val_idx = add i64 %src, 1",
            "  %val = call i64 @heap_get(i64 %entries, i64 %val_idx)",
            "  %_v = call i64 @heap_set(i64 %values, i64 %i, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %values",
            "}",
            "define i64 @__map_entries(i64 %map) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %out = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %src = mul i64 %i, 2",
            "  %val_idx = add i64 %src, 1",
            "  %key_val = call i64 @heap_get(i64 %entries, i64 %src)",
            "  %val = call i64 @heap_get(i64 %entries, i64 %val_idx)",
            "  %pair = call i64 @__new(i64 2)",
            "  %_k = call i64 @heap_set(i64 %pair, i64 0, i64 %key_val)",
            "  %_v = call i64 @heap_set(i64 %pair, i64 1, i64 %val)",
            "  %_o = call i64 @heap_set(i64 %out, i64 %i, i64 %pair)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %out",
            "}",
            "define i64 @__map_from_entries(i64 %entries_list) {",
            "entry:",
            "  %map = call i64 @__map_new()",
            "  %len = call i64 @heap_len(i64 %entries_list)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %pair = call i64 @heap_get(i64 %entries_list, i64 %i)",
            "  %key_val = call i64 @heap_get(i64 %pair, i64 0)",
            "  %val_val = call i64 @heap_get(i64 %pair, i64 1)",
            "  %_ignored = call i64 @__map_set(i64 %map, i64 %key_val, i64 %val_val)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %map",
            "}",
            "define i64 @__set_new() {",
            "entry:",
            "  %set = call i64 @__new(i64 2)",
            "  %entries = call i64 @__new(i64 0)",
            "  %_ignored0 = call i64 @heap_set(i64 %set, i64 0, i64 0)",
            "  %_ignored1 = call i64 @heap_set(i64 %set, i64 1, i64 %entries)",
            "  ret i64 %set",
            "}",
            "define i64 @__set_len(i64 %set) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  ret i64 %len",
            "}",
            "define i64 @__set_find(i64 %entries, i64 %len, i64 %value) {",
            "entry:",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %next_loop]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %not_found, label %check",
            "check:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %eq = icmp eq i64 %cur, %value",
            "  br i1 %eq, label %found, label %next_loop",
            "next_loop:",
            "  %next = add i64 %i, 1",
            "  br label %loop",
            "found:",
            "  ret i64 %i",
            "not_found:",
            "  ret i64 -1",
            "}",
            "define i1 @__set_has(i64 %set, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  %entries = call i64 @heap_get(i64 %set, i64 1)",
            "  %idx = call i64 @__set_find(i64 %entries, i64 %len, i64 %value)",
            "  %found = icmp sge i64 %idx, 0",
            "  ret i1 %found",
            "}",
            "define i1 @__set_add(i64 %set, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  %entries = call i64 @heap_get(i64 %set, i64 1)",
            "  %idx = call i64 @__set_find(i64 %entries, i64 %len, i64 %value)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %already, label %extend",
            "already:",
            "  ret i1 0",
            "extend:",
            "  %new_len = add i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %extend], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_n = call i64 @heap_set(i64 %new_entries, i64 %len, i64 %value)",
            "  %_l = call i64 @heap_set(i64 %set, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %set, i64 1, i64 %new_entries)",
            "  ret i1 1",
            "}",
            "define i1 @__set_delete(i64 %set, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  %entries = call i64 @heap_get(i64 %set, i64 1)",
            "  %idx = call i64 @__set_find(i64 %entries, i64 %len, i64 %value)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %do_delete, label %not_found",
            "do_delete:",
            "  %new_len = sub i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %do_delete], [%next, %copy_next]",
            "  %write = phi i64 [0, %do_delete], [%write_next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %check",
            "check:",
            "  %skip = icmp eq i64 %i, %idx",
            "  br i1 %skip, label %skip_entry, label %copy_entry",
            "skip_entry:",
            "  %next_skip = add i64 %i, 1",
            "  %write_keep = add i64 %write, 0",
            "  br label %copy_next",
            "copy_entry:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %write, i64 %cur)",
            "  %next_copy = add i64 %i, 1",
            "  %write_adv = add i64 %write, 1",
            "  br label %copy_next",
            "copy_next:",
            "  %next = phi i64 [%next_skip, %skip_entry], [%next_copy, %copy_entry]",
            "  %write_next = phi i64 [%write_keep, %skip_entry], [%write_adv, %copy_entry]",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %set, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %set, i64 1, i64 %new_entries)",
            "  ret i1 1",
            "not_found:",
            "  ret i1 0",
            "}",
            "define i64 @__set_to_list(i64 %set) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  %entries = call i64 @heap_get(i64 %set, i64 1)",
            "  %out = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %out, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %out",
            "}",
            "define i64 @__set_from_list(i64 %list) {",
            "entry:",
            "  %set = call i64 @__set_new()",
            "  %len = call i64 @heap_len(i64 %list)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %val = call i64 @heap_get(i64 %list, i64 %i)",
            "  %_ignored = call i1 @__set_add(i64 %set, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %set",
            "}",
            "define i64 @__deque_new() {",
            "entry:",
            "  %deque = call i64 @__new(i64 2)",
            "  %entries = call i64 @__new(i64 0)",
            "  %_ignored0 = call i64 @heap_set(i64 %deque, i64 0, i64 0)",
            "  %_ignored1 = call i64 @heap_set(i64 %deque, i64 1, i64 %entries)",
            "  ret i64 %deque",
            "}",
            "define i64 @__deque_from_list(i64 %list) {",
            "entry:",
            "  %deque = call i64 @__new(i64 2)",
            "  %len = call i64 @heap_len(i64 %list)",
            "  %entries = call i64 @__new(i64 %len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %entry], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %val = call i64 @heap_get(i64 %list, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %entries, i64 %i, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %entries)",
            "  ret i64 %deque",
            "}",
            "define i64 @__deque_len(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  ret i64 %len",
            "}",
            "define i64 @__deque_push_left(i64 %deque, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %new_len = add i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  %_v = call i64 @heap_set(i64 %new_entries, i64 0, i64 %value)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %entry], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %val = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %dst = add i64 %i, 1",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %dst, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %new_entries)",
            "  ret i64 %new_len",
            "}",
            "define i64 @__deque_push_right(i64 %deque, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %new_len = add i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %entry], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %val = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %i, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_v = call i64 @heap_set(i64 %new_entries, i64 %len, i64 %value)",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %new_entries)",
            "  ret i64 %new_len",
            "}",
            "define i64 @__deque_pop_left(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %empty = icmp eq i64 %len, 0",
            "  br i1 %empty, label %err, label %ok",
            "err:",
            "  call void @__deque_empty_error()",
            "  ret i64 0",
            "ok:",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %val = call i64 @heap_get(i64 %entries, i64 0)",
            "  %new_len = sub i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %ok], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %new_len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %src = add i64 %i, 1",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %src)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %new_entries)",
            "  ret i64 %val",
            "}",
            "define i64 @__deque_pop_right(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %empty = icmp eq i64 %len, 0",
            "  br i1 %empty, label %err, label %ok",
            "err:",
            "  call void @__deque_empty_error()",
            "  ret i64 0",
            "ok:",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %last = sub i64 %len, 1",
            "  %val = call i64 @heap_get(i64 %entries, i64 %last)",
            "  %new_len = sub i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %ok], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %new_len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %new_entries)",
            "  ret i64 %val",
            "}",
            "define i64 @__deque_peek_left(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %empty = icmp eq i64 %len, 0",
            "  br i1 %empty, label %err, label %ok",
            "err:",
            "  call void @__deque_empty_error()",
            "  ret i64 0",
            "ok:",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %val = call i64 @heap_get(i64 %entries, i64 0)",
            "  ret i64 %val",
            "}",
            "define i64 @__deque_peek_right(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %empty = icmp eq i64 %len, 0",
            "  br i1 %empty, label %err, label %ok",
            "err:",
            "  call void @__deque_empty_error()",
            "  ret i64 0",
            "ok:",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %last = sub i64 %len, 1",
            "  %val = call i64 @heap_get(i64 %entries, i64 %last)",
            "  ret i64 %val",
            "}",
            "define i64 @__deque_to_list(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %out = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %out, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %out",
            "}",
        ]

    def _register_type_metadata(self, program: ProgramIR) -> None:
        self._variant_fields.clear()
        self._variant_field_types.clear()
        self._variant_to_type.clear()

        for type_name, type_def in program.types.items():
            if type_def.variants:
                for variant_name, fields in type_def.variants.items():
                    self._variant_to_type[variant_name] = type_name
                    self._variant_fields[variant_name] = [fname for fname, _ in fields]
                    for fname, ftype in fields:
                        llvm_type = self._llvm_type_from_annotation(ftype) or "i64"
                        self._variant_field_types[(variant_name, fname)] = llvm_type
            elif type_def.fields is not None:
                variant_name = type_def.name
                self._variant_to_type[variant_name] = type_name
                self._variant_fields[variant_name] = [fname for fname, _ in type_def.fields]
                for fname, ftype in type_def.fields:
                    llvm_type = self._llvm_type_from_annotation(ftype) or "i64"
                    self._variant_field_types[(variant_name, fname)] = llvm_type

    def _register_class_metadata(self, program: ProgramIR) -> None:
        self._class_layouts.clear()
        self._class_mros.clear()
        self._class_ids.clear()
        self._class_methods.clear()

        for func_name in program.functions:
            if "." not in func_name:
                continue
            class_name, method_name = func_name.split(".", 1)
            self._class_methods.setdefault(class_name, {})[method_name] = func_name

        def build_mro(name: str) -> List[str]:
            cached = self._class_mros.get(name)
            if cached is not None:
                return cached
            class_def = program.classes.get(name)
            if class_def is None:
                self._class_mros[name] = [name]
                return [name]
            mro: List[str] = [name]
            for base in class_def.bases:
                if base not in program.classes:
                    self._lowering_error(f"unknown base class {base} for {name}")
                for ancestor in build_mro(base):
                    if ancestor not in mro:
                        mro.append(ancestor)
            self._class_mros[name] = mro
            return mro

        for class_name in program.classes:
            build_mro(class_name)

        for class_name, mro in self._class_mros.items():
            layout: List[Tuple[str, str]] = []
            for cls in mro:
                class_def = program.classes.get(cls)
                if class_def is None:
                    continue
                for field in class_def.fields:
                    layout.append((cls, field))
            self._class_layouts[class_name] = layout

        for idx, class_name in enumerate(sorted(program.classes.keys()), start=1):
            self._class_ids[class_name] = idx

    def _infer_signatures(self, program: ProgramIR) -> Dict[str, _ResolvedFunctionSignature]:
        signatures: Dict[str, _FunctionSignature] = {}
        for func in program.functions.values():
            signatures[func.name] = _FunctionSignature(
                param_types={name: None for name in func.params},
                return_type=None,
            )
        for overload in program.operator_overloads:
            func = program.functions.get(overload.func_name)
            if func is None or len(func.params) != 2:
                continue
            signature = signatures.get(overload.func_name)
            if signature is None:
                continue
            a_ty = self._llvm_type_from_annotation(overload.a_type)
            b_ty = self._llvm_type_from_annotation(overload.b_type)
            if a_ty and signature.param_types.get(func.params[0]) is None:
                signature.param_types[func.params[0]] = a_ty
            if b_ty and signature.param_types.get(func.params[1]) is None:
                signature.param_types[func.params[1]] = b_ty
        if not signatures:
            return {}

        for _ in range(len(signatures) + 1):
            changed = False
            for func in program.functions.values():
                if self._infer_function_signature(func, signatures):
                    changed = True
            if not changed:
                break

        resolved: Dict[str, _ResolvedFunctionSignature] = {}
        for name, signature in signatures.items():
            param_types = {param: ty or "i64" for param, ty in signature.param_types.items()}
            return_type = signature.return_type or "i64"
            resolved[name] = _ResolvedFunctionSignature(param_types=param_types, return_type=return_type)
        return resolved

    def _infer_function_signature(
        self, func: FunctionIR, signatures: Dict[str, _FunctionSignature]
    ) -> bool:
        changed = False
        stack: List[_TypeValue] = []
        locals_types: Dict[str, Optional[str]] = {}
        locals_literals: Dict[str, int] = {}
        locals_classes: Dict[str, str] = {}
        locals_variants: Dict[str, str] = {}
        heap_cell_types: Dict[Tuple[str, int], str] = {}
        signature = signatures[func.name]
        if "." in func.name and func.params:
            locals_classes[func.params[0]] = func.name.split(".", 1)[0]

        def set_param_type(param_name: str, ty: str) -> None:
            nonlocal changed
            existing = signature.param_types.get(param_name)
            if existing is None:
                signature.param_types[param_name] = ty
                changed = True
            elif existing != ty:
                raise NotImplementedError(
                    f"mixed-type parameter {param_name} in LLVM prototype: {existing} vs {ty}"
                )

        def set_return_type(ty: str) -> None:
            nonlocal changed
            if signature.return_type is None:
                signature.return_type = ty
                changed = True
            elif signature.return_type != ty:
                raise NotImplementedError(
                    f"mixed-type return in LLVM prototype: {signature.return_type} vs {ty}"
                )

        def resolve_variant_name(value: _TypeValue) -> Optional[str]:
            if value.variant_name:
                return value.variant_name
            if value.source:
                return locals_variants.get(value.source)
            return None

        for instr in func.instructions:
            if instr.op == Opcode.PUSH_CONST:
                if instr.arg is None:
                    stack.append(_TypeValue("i8*"))
                elif isinstance(instr.arg, bool):
                    stack.append(_TypeValue("i1"))
                elif isinstance(instr.arg, int):
                    stack.append(_TypeValue("i64", literal=instr.arg))
                elif isinstance(instr.arg, float):
                    stack.append(_TypeValue("double"))
                elif isinstance(instr.arg, str):
                    stack.append(_TypeValue("i8*", literal_str=instr.arg))
                else:
                    raise NotImplementedError(
                        f"constants of type {type(instr.arg).__name__} are not supported in LLVM prototype"
                    )
            elif instr.op == Opcode.LOAD:
                name = instr.arg
                if name in locals_types:
                    literal = locals_literals.get(name)
                    stack.append(
                        _TypeValue(
                            locals_types[name],
                            source=name,
                            literal=literal,
                            class_name=locals_classes.get(name),
                            variant_name=locals_variants.get(name),
                        )
                    )
                elif name in signature.param_types:
                    stack.append(
                        _TypeValue(
                            signature.param_types[name],
                            source=name,
                            class_name=locals_classes.get(name),
                            variant_name=locals_variants.get(name),
                        )
                    )
                else:
                    raise NotImplementedError(f"unknown variable {name} in LLVM prototype")
            elif instr.op == Opcode.STORE:
                value = stack.pop()
                ty = value.ty
                if ty is None and value.source and value.source in signature.param_types:
                    ty = signature.param_types[value.source]
                locals_types[instr.arg] = ty
                if ty == "i64" and value.literal is not None:
                    locals_literals[instr.arg] = value.literal
                else:
                    locals_literals.pop(instr.arg, None)
                if value.class_name:
                    locals_classes[instr.arg] = value.class_name
                else:
                    locals_classes.pop(instr.arg, None)
                if value.variant_name:
                    locals_variants[instr.arg] = value.variant_name
                else:
                    locals_variants.pop(instr.arg, None)
                if value.source and value.source != instr.arg:
                    for (ptr_name, idx), cell_ty in list(heap_cell_types.items()):
                        if ptr_name == value.source:
                            heap_cell_types[(instr.arg, idx)] = cell_ty
            elif instr.op == Opcode.BINARY:
                right = stack.pop()
                left = stack.pop()
                left_ty = left.ty
                right_ty = right.ty
                if left_ty and right_ty and left_ty != right_ty:
                    raise NotImplementedError("mixed-type arithmetic is not yet supported in LLVM prototype")
                known_ty = left_ty or right_ty
                if left_ty is None and left.source and known_ty:
                    set_param_type(left.source, known_ty)
                    left_ty = known_ty
                if right_ty is None and right.source and known_ty:
                    set_param_type(right.source, known_ty)
                    right_ty = known_ty
                op = instr.arg
                overload_name = None
                if known_ty is not None:
                    overload_name = self._operator_overloads.get((op, known_ty, known_ty))
                if overload_name is not None:
                    overload_sig = signatures.get(overload_name)
                    if overload_sig is None:
                        raise NotImplementedError(f"unknown operator overload {overload_name}")
                    stack.append(_TypeValue(overload_sig.return_type))
                    continue
                if op in {"+", "-", "*", "/", "%"}:
                    stack.append(_TypeValue(known_ty))
                elif op in {"==", "!=", "<", ">", "<=", ">="}:
                    stack.append(_TypeValue("i1"))
                else:
                    raise NotImplementedError(f"operator {op} not supported in LLVM prototype")
            elif instr.op == Opcode.PRINT:
                for _ in range(int(instr.arg)):
                    stack.pop()
            elif instr.op == Opcode.FLUSH:
                continue
            elif instr.op == Opcode.POP:
                stack.pop()
            elif instr.op == Opcode.JUMP:
                stack.clear()
            elif instr.op == Opcode.JUMP_IF_FALSE:
                if stack:
                    stack.pop()
                stack.clear()
            elif instr.op == Opcode.CALL:
                name, argc = instr.arg
                args = [stack.pop() for _ in range(argc)][::-1]
                if name == "__import":
                    if len(args) != 1:
                        raise NotImplementedError("__import expects 1 arg")
                    module_name = args[0].literal_str
                    if module_name is None:
                        raise NotImplementedError("__import expects a string literal module name")
                    stack.append(_TypeValue("i8*", literal_str=module_name, class_name=module_name))
                    continue
                if name == "Python.import_module":
                    if len(args) not in {1, 2}:
                        raise NotImplementedError("Python.import_module expects 1 or 2 args")
                    module_name = args[0].literal_str
                    if module_name is None:
                        raise NotImplementedError("Python.import_module expects a string literal module name")
                    self._python_modules.add(module_name)
                    stack.append(_TypeValue("i64", class_name=module_name))
                    continue
                if name == "Python.call":
                    if len(args) < 2 or len(args) > 4:
                        raise NotImplementedError("Python.call expects 2 to 4 args")
                    stack.append(_TypeValue("i64"))
                    continue
                if name.startswith("Python.") and name not in {"Python.import_module", "Python.call"}:
                    stack.append(_TypeValue("i64"))
                    continue
                if name == "__spawn":
                    if not args:
                        raise NotImplementedError("__spawn expects at least 1 arg")
                    target_name = args[0].literal_str
                    if target_name is None:
                        raise NotImplementedError("__spawn expects a string literal target name")
                    call_args = args[1:]
                    callee = signatures.get(target_name)
                    if callee is None:
                        builtin = self._builtin_signature(target_name)
                        if builtin is None:
                            raise NotImplementedError(f"unknown function {target_name} in LLVM prototype")
                        for param_ty, arg in zip(builtin.param_types.values(), call_args):
                            if param_ty and arg.ty and param_ty != arg.ty:
                                raise NotImplementedError(
                                    f"argument type mismatch for {target_name}: {param_ty} vs {arg.ty}"
                                )
                        stack.append(_TypeValue(builtin.return_type))
                        continue
                    for param_name, arg in zip(callee.param_types.keys(), call_args):
                        expected = callee.param_types[param_name]
                        if expected is None and arg.ty:
                            callee.param_types[param_name] = arg.ty
                            changed = True
                        if arg.ty is None and arg.source and expected:
                            set_param_type(arg.source, expected)
                        if expected and arg.ty and expected != arg.ty:
                            raise NotImplementedError(
                                f"argument type mismatch for {target_name}.{param_name}: {expected} vs {arg.ty}"
                            )
                    stack.append(_TypeValue(callee.return_type))
                    continue
                if name == "join":
                    if len(args) not in {1, 2, 3}:
                        raise NotImplementedError("join expects between 1 and 3 args")
                    stack.append(_TypeValue(args[0].ty))
                    continue
                if name == "__variant_assume":
                    if len(args) != 2:
                        raise NotImplementedError("__variant_assume expects 2 args")
                    variant_name = args[1].literal_str
                    if variant_name is None:
                        raise NotImplementedError("__variant_assume expects a string literal variant name")
                    value = args[0]
                    stack.append(
                        _TypeValue(
                            value.ty,
                            source=value.source,
                            literal=value.literal,
                            literal_str=value.literal_str,
                            class_name=value.class_name,
                            variant_name=variant_name,
                        )
                    )
                    continue
                if name == "__variant_new":
                    if len(args) < 2:
                        raise NotImplementedError("__variant_new expects at least 2 args")
                    variant_name = args[0].literal_str
                    if variant_name is None:
                        raise NotImplementedError("__variant_new expects a string literal variant name")
                    stack.append(_TypeValue("i64", variant_name=variant_name))
                    continue
                if name == "__variant_tag":
                    if len(args) != 1:
                        raise NotImplementedError("__variant_tag expects 1 arg")
                    stack.append(_TypeValue("i8*", literal_str=args[0].variant_name))
                    continue
                if name == "__variant_get":
                    if len(args) != 2:
                        raise NotImplementedError("__variant_get expects 2 args")
                    field_name = args[1].literal_str
                    if field_name is None:
                        raise NotImplementedError("__variant_get expects a string literal field name")
                    variant_name = resolve_variant_name(args[0])
                    if variant_name is None:
                        field_type = None
                        for (candidate_variant, candidate_field), ty in self._variant_field_types.items():
                            if candidate_field == field_name:
                                if field_type is None:
                                    field_type = ty
                                elif field_type != ty:
                                    raise NotImplementedError(
                                        f"ambiguous field {field_name} across variants in LLVM prototype"
                                    )
                        stack.append(_TypeValue(field_type or "i64"))
                    else:
                        field_type = self._variant_field_types.get((variant_name, field_name), "i64")
                        stack.append(_TypeValue(field_type))
                    continue
                if name == "__match_error":
                    if len(args) != 1:
                        raise NotImplementedError("__match_error expects 1 arg")
                    continue
                if name == "__class_new":
                    if not args:
                        raise NotImplementedError("__class_new expects at least 1 arg")
                    class_name_value = args[0].literal_str
                    if class_name_value is None:
                        raise NotImplementedError("__class_new expects a string literal class name")
                    if (len(args) - 1) % 2 != 0:
                        raise NotImplementedError("__class_new expects field name/value pairs")
                    for index in range(1, len(args), 2):
                        field_name = args[index].literal_str
                        if field_name is None:
                            raise NotImplementedError("__class_new expects string literal field names")
                        value = args[index + 1]
                        if value.ty is not None:
                            field_index = self._class_field_index(class_name_value, field_name)
                            existing = self._class_field_types.get((class_name_value, field_index))
                            if existing is None:
                                self._class_field_types[(class_name_value, field_index)] = value.ty
                                changed = True
                            elif existing != value.ty:
                                raise NotImplementedError(
                                    f"mixed-type field {class_name_value}.{field_name} in LLVM prototype"
                                )
                    stack.append(_TypeValue("i64", class_name=class_name_value))
                    continue
                if name == "__field_get":
                    if len(args) != 2:
                        raise NotImplementedError("__field_get expects 2 args")
                    obj, field_name = args
                    class_name_value = obj.class_name
                    field_literal = field_name.literal_str
                    if class_name_value is None or field_literal is None:
                        raise NotImplementedError("__field_get expects class value and field name literal")
                    if class_name_value in self._module_inits:
                        raise NotImplementedError("module field access is not yet supported in LLVM prototype")
                    field_index = self._class_field_index(class_name_value, field_literal)
                    field_type = self._class_field_types.get((class_name_value, field_index), "i64")
                    stack.append(_TypeValue(field_type))
                    continue
                if name == "__field_set":
                    if len(args) != 3:
                        raise NotImplementedError("__field_set expects 3 args")
                    obj, field_name, value = args
                    class_name_value = obj.class_name
                    field_literal = field_name.literal_str
                    if class_name_value is None or field_literal is None:
                        raise NotImplementedError("__field_set expects class value and field name literal")
                    field_index = self._class_field_index(class_name_value, field_literal)
                    if value.ty is not None:
                        existing = self._class_field_types.get((class_name_value, field_index))
                        if existing is None:
                            self._class_field_types[(class_name_value, field_index)] = value.ty
                            changed = True
                        elif existing != value.ty:
                            raise NotImplementedError(
                                f"mixed-type field {class_name_value}.{field_literal} in LLVM prototype"
                            )
                    stack.append(value)
                    continue
                if name == "__method_call":
                    if len(args) < 2:
                        raise NotImplementedError("__method_call expects at least 2 args")
                    obj, method_name, *rest = args
                    class_name_value = obj.class_name
                    method_literal = method_name.literal_str
                    if class_name_value is None or method_literal is None:
                        raise NotImplementedError("__method_call expects class value and method name literal")
                    if class_name_value == "Python":
                        if method_literal == "import_module":
                            if len(rest) not in {1, 2}:
                                raise NotImplementedError("Python.import_module expects 1 or 2 args")
                            module_name = rest[0].literal_str
                            if module_name is None:
                                raise NotImplementedError(
                                    "Python.import_module expects a string literal module name"
                                )
                            self._python_modules.add(module_name)
                            stack.append(_TypeValue("i64", class_name=module_name))
                            continue
                        if method_literal == "call":
                            if len(rest) < 2 or len(rest) > 4:
                                raise NotImplementedError("Python.call expects 2 to 4 args")
                            stack.append(_TypeValue("i64"))
                            continue
                        raise NotImplementedError(f"unknown Python method {method_literal}")
                    if class_name_value in {"Map", "Set", "Deque"}:
                        call_name = f"{class_name_value}.{method_literal}"
                        args = rest
                        name = call_name
                        if name.startswith("Map."):
                            method = name.split(".", 1)[1]
                            if method == "set" and len(args) >= 3:
                                stack.append(_TypeValue(args[2].ty))
                            elif method == "get" and len(args) == 3:
                                stack.append(_TypeValue(args[2].ty))
                            elif method in {"has", "delete"}:
                                stack.append(_TypeValue("i1"))
                            elif method in {"len"}:
                                stack.append(_TypeValue("i64"))
                            elif method in {"new", "keys", "values", "entries", "from_entries"}:
                                stack.append(_TypeValue("i64"))
                            else:
                                stack.append(_TypeValue("i64"))
                            continue
                        if name.startswith("Set."):
                            method = name.split(".", 1)[1]
                            if method in {"add", "delete", "has"}:
                                stack.append(_TypeValue("i1"))
                            elif method in {"new", "from_list", "to_list"}:
                                stack.append(_TypeValue("i64"))
                            else:
                                stack.append(_TypeValue("i64"))
                            continue
                        if name.startswith("Deque."):
                            stack.append(_TypeValue("i64"))
                            continue
                    if class_name_value in self._python_modules:
                        stack.append(_TypeValue("i64"))
                        continue
                    if class_name_value in self._module_inits:
                        target_name = f"{class_name_value}.{method_literal}"
                        signature = signatures.get(target_name)
                        if signature is None:
                            raise NotImplementedError(f"unknown function {target_name} in LLVM prototype")
                        if len(rest) != len(signature.param_types):
                            raise NotImplementedError(
                                f"function {target_name} expects {len(signature.param_types)} args, got {len(rest)}"
                            )
                        for param_name, arg in zip(signature.param_types.keys(), rest):
                            expected = signature.param_types[param_name]
                            if expected is None and arg.ty:
                                signature.param_types[param_name] = arg.ty
                                changed = True
                            if arg.ty is None and arg.source and expected:
                                set_param_type(arg.source, expected)
                            if expected and arg.ty and expected != arg.ty:
                                raise NotImplementedError(
                                    f"argument type mismatch for {target_name}.{param_name}: {expected} vs {arg.ty}"
                                )
                        stack.append(_TypeValue(signature.return_type))
                        continue
                    target_name = self._resolve_method_target(class_name_value, method_literal)
                    callee = signatures.get(target_name)
                    if callee is None:
                        raise NotImplementedError(f"unknown function {target_name}")
                    method_args = [obj] + list(rest)
                    for param_name, arg in zip(callee.param_types.keys(), method_args):
                        expected = callee.param_types[param_name]
                        if expected is None and arg.ty:
                            callee.param_types[param_name] = arg.ty
                            changed = True
                        if arg.ty is None and arg.source and expected:
                            set_param_type(arg.source, expected)
                        if expected and arg.ty and expected != arg.ty:
                            raise NotImplementedError(
                                f"argument type mismatch for {target_name}.{param_name}: {expected} vs {arg.ty}"
                            )
                    stack.append(_TypeValue(callee.return_type))
                    continue
                if name.startswith("Map."):
                    method = name.split(".", 1)[1]
                    if method == "set" and len(args) >= 3:
                        stack.append(_TypeValue(args[2].ty))
                    elif method == "get" and len(args) == 3:
                        stack.append(_TypeValue(args[2].ty))
                    elif method in {"has", "delete"}:
                        stack.append(_TypeValue("i1"))
                    elif method in {"len"}:
                        stack.append(_TypeValue("i64"))
                    elif method in {"new", "keys", "values", "entries", "from_entries"}:
                        stack.append(_TypeValue("i64"))
                    else:
                        stack.append(_TypeValue("i64"))
                    continue
                if name.startswith("Set."):
                    method = name.split(".", 1)[1]
                    if method in {"add", "delete", "has"}:
                        stack.append(_TypeValue("i1"))
                    elif method in {"new", "from_list", "to_list"}:
                        stack.append(_TypeValue("i64"))
                    else:
                        stack.append(_TypeValue("i64"))
                    continue
                if name.startswith("Deque."):
                    method = name.split(".", 1)[1]
                    if method in {"new", "from_list", "to_list", "len", "push_left", "push_right"}:
                        stack.append(_TypeValue("i64"))
                    elif method in {"pop_left", "pop_right", "peek_left", "peek_right"}:
                        stack.append(_TypeValue("i64"))
                    else:
                        stack.append(_TypeValue("i64"))
                    continue
                if name == "heap_set":
                    self._record_heap_cell_type_inference(args, heap_cell_types)
                    stack.append(_TypeValue("i64"))
                    continue
                if name == "heap_get":
                    known = self._heap_cell_type_from_inference(args, heap_cell_types)
                    stack.append(_TypeValue(known or "i64"))
                    continue
                callee = signatures.get(name)
                if callee is None:
                    builtin = self._builtin_signature(name)
                    if builtin is None:
                        raise NotImplementedError(f"unknown function {name} in LLVM prototype")
                    for param_ty, arg in zip(builtin.param_types.values(), args):
                        if param_ty and arg.ty and param_ty != arg.ty:
                            raise NotImplementedError(
                                f"argument type mismatch for {name}: {param_ty} vs {arg.ty}"
                            )
                    stack.append(_TypeValue(builtin.return_type))
                    continue
                for param_name, arg in zip(callee.param_types.keys(), args):
                    expected = callee.param_types[param_name]
                    if expected is None and arg.ty:
                        callee.param_types[param_name] = arg.ty
                        changed = True
                    if arg.ty is None and arg.source and expected:
                        set_param_type(arg.source, expected)
                    if expected and arg.ty and expected != arg.ty:
                        raise NotImplementedError(
                            f"argument type mismatch for {name}.{param_name}: {expected} vs {arg.ty}"
                        )
                stack.append(_TypeValue(callee.return_type))
            elif instr.op == Opcode.RETURN:
                if stack:
                    value = stack.pop()
                    if value.ty is None and value.source and signature.return_type:
                        set_param_type(value.source, signature.return_type)
                        value = _TypeValue(signature.return_type)
                    if value.ty:
                        set_return_type(value.ty)
                stack.clear()
            else:
                self._unsupported_opcode(instr)

        return changed

    def _builtin_signature(self, name: str) -> Optional[_ResolvedFunctionSignature]:
        if name in {"__new", "new"}:
            return _ResolvedFunctionSignature(param_types={"size": "i64"}, return_type="i64")
        if name == "heap_get":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64", "idx": "i64"}, return_type="i64")
        if name == "heap_get_str":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64", "idx": "i64"}, return_type="i8*")
        if name == "heap_get_double":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64", "idx": "i64"}, return_type="double")
        if name == "heap_get_bool":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64", "idx": "i64"}, return_type="i1")
        if name == "heap_set":
            return _ResolvedFunctionSignature(
                param_types={"ptr": "i64", "idx": "i64", "value": "i64"}, return_type="i64"
            )
        if name == "heap_set_str":
            return _ResolvedFunctionSignature(
                param_types={"ptr": "i64", "idx": "i64", "value": "i8*"}, return_type="i64"
            )
        if name == "heap_set_double":
            return _ResolvedFunctionSignature(
                param_types={"ptr": "i64", "idx": "i64", "value": "double"}, return_type="i64"
            )
        if name == "heap_set_bool":
            return _ResolvedFunctionSignature(
                param_types={"ptr": "i64", "idx": "i64", "value": "i1"}, return_type="i64"
            )
        if name == "delete":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64"}, return_type="i64")
        return None

    def _register_operator_overloads(
        self, overloads: List[OperatorOverloadIR]
    ) -> Dict[Tuple[str, str, str], str]:
        registered: Dict[Tuple[str, str, str], str] = {}
        for overload in overloads:
            a_ty = self._llvm_type_from_annotation(overload.a_type)
            b_ty = self._llvm_type_from_annotation(overload.b_type)
            if a_ty is None or b_ty is None:
                continue
            registered[(overload.op, a_ty, b_ty)] = overload.func_name
        return registered

    def _llvm_type_from_annotation(self, name: str) -> Optional[str]:
        normalized = name.lower()
        if normalized in {"number", "int", "integer"}:
            return "i64"
        if normalized in {"float", "double"}:
            return "double"
        if normalized in {"bool", "boolean"}:
            return "i1"
        if normalized in {"string", "str"}:
            return "i8*"
        if normalized == "null":
            return "i8*"
        return None

    def _resolve_heap_set_name(self, args: List[_StackValue]) -> str:
        if len(args) != 3:
            return "heap_set"
        value = args[2]
        if value.ty == "i8*":
            return "heap_set_str"
        if value.ty == "double":
            return "heap_set_double"
        if value.ty == "i1":
            return "heap_set_bool"
        return "heap_set"

    def _resolve_heap_get_name(self, args: List[_StackValue]) -> str:
        if len(args) != 2:
            return "heap_get"
        ptr = args[0]
        idx = args[1]
        key = self._heap_cell_key(ptr, idx)
        if key is None:
            return "heap_get"
        cell_type = self._heap_cell_types.get(key)
        if cell_type == "i8*":
            return "heap_get_str"
        if cell_type == "double":
            return "heap_get_double"
        if cell_type == "i1":
            return "heap_get_bool"
        return "heap_get"

    def _heap_cell_key(self, ptr: _StackValue, idx: _StackValue) -> Optional[Tuple[str, int]]:
        if ptr.source is None:
            return None
        if idx.ty != "i64" or idx.literal is None:
            return None
        return (ptr.source, idx.literal)

    def _record_heap_cell_type(self, args: List[_StackValue]) -> None:
        if len(args) != 3:
            return
        ptr, idx, value = args
        key = self._heap_cell_key(ptr, idx)
        if key is None:
            return
        self._heap_cell_types[key] = value.ty

    def _record_heap_cell_type_inference(
        self, args: List[_TypeValue], heap_cell_types: Dict[Tuple[str, int], str]
    ) -> None:
        if len(args) != 3:
            return
        ptr, idx, value = args
        if ptr.source is None or idx.literal is None:
            return
        if idx.ty != "i64" or value.ty is None:
            return
        heap_cell_types[(ptr.source, idx.literal)] = value.ty

    def _heap_cell_type_from_inference(
        self, args: List[_TypeValue], heap_cell_types: Dict[Tuple[str, int], str]
    ) -> Optional[str]:
        if len(args) != 2:
            return None
        ptr, idx = args
        if ptr.source is None or idx.literal is None or idx.ty != "i64":
            return None
        return heap_cell_types.get((ptr.source, idx.literal))

    def _string_constant(self, value: str) -> Tuple[str, int]:
        cached = self._string_constants.get(value)
        if cached:
            return cached
        encoded = value.encode("utf-8")
        escaped = "".join(self._escape_byte(byte) for byte in encoded)
        length = len(encoded) + 1
        name = f".str{len(self._string_constants)}"
        self._string_constants[value] = (name, length)
        self._string_defs.append(
            f"@{name} = private unnamed_addr constant [{length} x i8] c\"{escaped}\\00\""
        )
        return name, length

    def _escape_byte(self, value: int) -> str:
        if value in {0x5C, 0x22}:
            return f"\\{value:02X}"
        if 0x20 <= value <= 0x7E:
            return chr(value)
        return f"\\{value:02X}"

# --- segment: tiny_language_linter.py ---
"""Static checks for TinyLanguage programs prior to execution.

The linter enforces style and safety rules such as unused bindings, consistent
import ordering, and exhaustiveness expectations. It runs immediately after
parsing so later stages can assume the IR has already been validated for common
footguns.
"""

from typing import Any, Dict, List, Optional, Set, Union

from tiny_language_ast import *
from tiny_language_preamble import TinyLangError, format_error
from tiny_errors import SourcePos, SourceSpan

# ----- Linter -----


def _param_names(params: List[Param]) -> List[str]:
    return [p.name for p in params]


def _node_span(obj: Any) -> Optional[SourceSpan]:
    if isinstance(obj, SourceSpan):
        return obj
    return getattr(obj, "span", None)


def _node_pos(obj: Any) -> SourcePos:
    if isinstance(obj, SourceSpan):
        return obj.start
    if isinstance(obj, SourcePos):
        return obj
    return getattr(obj, "pos", SourcePos.origin())


def _lint_error(
    source: Optional[str],
    node: Any,
    message: str,
    *,
    code: str = "E000",
    hint: Optional[str] = None,
) -> TinyLangError:
    span = _node_span(node)
    pos = _node_pos(node)
    if source is None:
        loc = span.start if span is not None else pos
        rendered = f"[{code}] {message} (line {loc.line}, col {loc.col})"
        if hint:
            rendered = f"{rendered}\n  Hint: {hint}"
    else:
        rendered = format_error(source, span or pos, message, code=code, hint=hint)
    return TinyLangError(rendered, pos, code=code, hint=hint, span=span)


def _collect_names_in_expr(e: IR, names: Set[str]) -> None:
    if isinstance(e, Var):
        names.add(e.name)
    elif isinstance(e, Bin):
        _collect_names_in_expr(e.a, names)
        _collect_names_in_expr(e.b, names)
    elif isinstance(e, Call):
        for a in e.args:
            _collect_names_in_expr(a, names)
    elif isinstance(e, Spawn):
        for a in e.args:
            _collect_names_in_expr(a, names)
    elif isinstance(e, Await):
        _collect_names_in_expr(e.expr, names)
    elif isinstance(e, New):
        _collect_names_in_expr(e.size, names)
    elif isinstance(e, NewLit):
        for it in e.items:
            _collect_names_in_expr(it, names)
    elif isinstance(e, Field):
        _collect_names_in_expr(e.obj, names)
    elif isinstance(e, MethodCall):
        _collect_names_in_expr(e.obj, names)
        for a in e.args:
            _collect_names_in_expr(a, names)
    elif isinstance(e, ClassNew):
        for _, v in e.init:
            _collect_names_in_expr(v, names)
    elif isinstance(e, ObjLit):
        for _, v in e.fields:
            _collect_names_in_expr(v, names)
    elif isinstance(e, Match):
        _collect_names_in_expr(e.expr, names)
        for case in e.cases:
            _collect_names_in_expr(case.body, names)
    elif isinstance(e, VariantCtor):
        for _, v in e.fields:
            _collect_names_in_expr(v, names)


def uses_in_expr(e: IR, reads: Dict[str, int]) -> None:
    if isinstance(e, Var):
        reads[e.name] = reads.get(e.name, 0) + 1
    elif isinstance(e, Bin):
        uses_in_expr(e.a, reads)
        uses_in_expr(e.b, reads)
    elif isinstance(e, Call):
        reads[e.name] = reads.get(e.name, 0) + 1
        for a in e.args:
            uses_in_expr(a, reads)
    elif isinstance(e, Spawn):
        reads[e.name] = reads.get(e.name, 0) + 1
        for a in e.args:
            uses_in_expr(a, reads)
    elif isinstance(e, Await):
        uses_in_expr(e.expr, reads)
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
    elif isinstance(e, Match):
        uses_in_expr(e.expr, reads)
        for case in e.cases:
            case_reads: Dict[str, int] = {}
            uses_in_expr(case.body, case_reads)
            for name, count in case_reads.items():
                reads[name] = max(reads.get(name, 0), count)
    elif isinstance(e, VariantCtor):
        for _, v in e.fields:
            uses_in_expr(v, reads)


def lint_stmt_reads(s: IR, reads: Dict[str, int], source: Optional[str] = None) -> None:
    if isinstance(s, (Let, Assign)):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, FieldAssign):
        uses_in_expr(s.obj, reads)
        uses_in_expr(s.expr, reads)
    elif isinstance(s, Print):
        for expr in s.exprs:
            uses_in_expr(expr, reads)
    elif isinstance(s, Flush):
        pass
    elif isinstance(s, If):
        uses_in_expr(s.cond, reads)
        for t in s.then:
            lint_stmt_reads(t, reads, source)
        for t in s.els:
            lint_stmt_reads(t, reads, source)
    elif isinstance(s, While):
        uses_in_expr(s.cond, reads)
        for t in s.body:
            lint_stmt_reads(t, reads, source)
    elif isinstance(s, Switch):
        uses_in_expr(s.expr, reads)
        for case in s.cases:
            if case.value is not None:
                uses_in_expr(case.value, reads)
            for t in case.body:
                lint_stmt_reads(t, reads, source)
    elif isinstance(s, TryCatch):
        for t in s.body:
            lint_stmt_reads(t, reads, source)
        handler_reads: Dict[str, int] = {}
        for t in s.handler:
            lint_stmt_reads(t, handler_reads, source)
        if s.err_name:
            # Mark the catch binding as referenced if it is consumed inside the handler
            if handler_reads.get(s.err_name, 0) == 0:
                handler_reads[s.err_name] = 0
        for name, count in handler_reads.items():
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, TaskBlock):
        for t in s.body:
            lint_stmt_reads(t, reads, source)
    elif isinstance(s, Return):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, OpDef):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp, source)
        miss = []
        if not s.a_name.startswith("_") and tmp.get(s.a_name, 0) == 0:
            miss.append(s.a_name)
        if not s.b_name.startswith("_") and tmp.get(s.b_name, 0) == 0:
            miss.append(s.b_name)
        if miss:
            raise _lint_error(
                source,
                s,
                f"unused operator parameter(s) in op {s.op}: {', '.join(miss)}",
                code="E002",
                hint="Remove the unused parameters or reference them in the operator body.",
            )
        for name, count in tmp.items():
            if name in {s.a_name, s.b_name}:
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, DestructAssign):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, MethodDef):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp, source)
        param_names = _param_names(s.params)
        miss = [p for p in param_names if not p.startswith("_") and tmp.get(p, 0) == 0]
        if miss:
            raise _lint_error(
                source,
                s,
                f"unused parameter(s) in method {s.class_name}.{s.name}: {', '.join(miss)}",
                code="E002",
                hint="Remove the unused parameter or reference it.",
            )
        for name, count in tmp.items():
            if name in set(param_names):
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, Fn):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp, source)
        param_names = _param_names(s.params)
        for name, count in tmp.items():
            if name in set(param_names):
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, ClassDef):
        for m in s.methods:
            lint_stmt_reads(m, reads, source)
    elif isinstance(s, Namespace):
        for t in s.body:
            lint_stmt_reads(t, reads, source)
    elif isinstance(s, CallStmt):
        for arg in s.args:
            uses_in_expr(arg, reads)


def lint_fn_params_used(fn: Fn, source: Optional[str] = None) -> None:
    reads: Dict[str, int] = {}
    for st in fn.body:
        lint_stmt_reads(st, reads, source)
    param_names = _param_names(fn.params)
    unused = [p for p in param_names if p != "self" and not p.startswith("_") and reads.get(p, 0) == 0]
    if unused:
        msg = f"unused parameter(s) in function {fn.name}: {', '.join(unused)}"
        raise _lint_error(source, fn, msg, code="E002", hint="Remove the unused parameter or reference it.")
    lint_param_mutations_returned(fn.body, set(param_names), fn.name, is_method=False, source=source, pos=fn.pos)
    lint_destruct_call_outputs(fn.body, source)
    lint_return_signatures(fn.body, fn.name, is_method=False, source=source, pos=fn.pos)
    lint_return_exhaustiveness(
        fn.body, fn.name, expected_return=fn.return_type, is_method=False, source=source, location=fn
    )
    lint_locals_used(fn.body, source)


def lint_method_params_used(md: MethodDef, source: Optional[str] = None) -> None:
    reads: Dict[str, int] = {}
    for st in md.body:
        lint_stmt_reads(st, reads, source)
    param_names = _param_names(md.params)
    unused = [p for p in param_names if p != "self" and not p.startswith("_") and reads.get(p, 0) == 0]
    if unused:
        msg = f"unused parameter(s) in method {md.class_name}.{md.name}: {', '.join(unused)}"
        raise _lint_error(source, md, msg, code="E002", hint="Remove the unused parameter or reference it.")
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
        location=md,
    )
    lint_locals_used(md.body, source)


def lint_locals_used(stmts: List[IR], source: Optional[str] = None) -> None:
    Location = Union[SourcePos, SourceSpan]
    unused: List[tuple[str, Location]] = []
    partial: List[tuple[str, Location]] = []

    def names_in_expr(expr: IR) -> Set[str]:
        reads: Dict[str, int] = {}
        uses_in_expr(expr, reads)
        return set(reads)

    def _mark_used(state: Dict[str, tuple[Location, bool, bool]], name: str):
        if name in state:
            pos, _, _ = state[name]
            state[name] = (pos, True, True)

    def _mark_captured_uses(block: List[IR], state: Dict[str, tuple[Location, bool, bool]]):
        reads: Dict[str, int] = {}
        for st in block:
            lint_stmt_reads(st, reads, source)
        for nm, (pos, used_all, used_any) in list(state.items()):
            if nm in reads:
                state[nm] = (pos, True, True)

    def _merge_states(states: List[Dict[str, tuple[Location, bool, bool]]]) -> List[Dict[str, tuple[Location, bool, bool]]]:
        if not states:
            return []
        merged: Dict[str, tuple[Location, bool, bool]] = {}
        for st in states:
            for name, (pos, used_all, used_any) in st.items():
                if name not in merged:
                    merged[name] = (pos, used_all, used_any)
                else:
                    prev_pos, prev_all, prev_any = merged[name]
                    merged[name] = (prev_pos, prev_all and used_all, prev_any or used_any)
        return [merged]

    def analyze_block(block: List[IR], initial_states: List[Dict[str, tuple[Location, bool, bool]]]):
        active_states = [dict(state) for state in initial_states]
        terminated_states: List[Dict[str, tuple[Location, bool, bool]]] = []

        for st in block:
            next_active: List[Dict[str, tuple[Location, bool, bool]]] = []
            for state in active_states:
                if isinstance(st, Let):
                    new_state = dict(state)
                    for nm in names_in_expr(st.expr):
                        _mark_used(new_state, nm)
                    new_state[st.name] = (st.name_span or st.pos, False, False)
                    next_active.append(new_state)
                elif isinstance(st, Import):
                    new_state = dict(state)
                    new_state[_import_binding_name(st.module, st.alias)] = (st.binding_span or st.pos, False, False)
                    next_active.append(new_state)
                elif isinstance(st, DestructAssign):
                    new_state = dict(state)
                    for nm, span in zip(st.names, st.name_spans):
                        new_state[nm] = (span, False, False)
                    for nm in names_in_expr(st.expr):
                        _mark_used(new_state, nm)
                    next_active.append(new_state)
                elif isinstance(st, Assign):
                    new_state = dict(state)
                    for nm in names_in_expr(st.expr):
                        _mark_used(new_state, nm)
                    next_active.append(new_state)
                elif isinstance(st, FieldAssign):
                    new_state = dict(state)
                    for nm in names_in_expr(st.obj):
                        _mark_used(new_state, nm)
                    for nm in names_in_expr(st.expr):
                        _mark_used(new_state, nm)
                    next_active.append(new_state)
                elif isinstance(st, Print):
                    new_state = dict(state)
                    for expr in st.exprs:
                        for nm in names_in_expr(expr):
                            _mark_used(new_state, nm)
                    next_active.append(new_state)
                elif isinstance(st, Flush):
                    next_active.append(dict(state))
                elif isinstance(st, CallStmt):
                    new_state = dict(state)
                    for arg in st.args:
                        for nm in names_in_expr(arg):
                            _mark_used(new_state, nm)
                    next_active.append(new_state)
                elif isinstance(st, Return):
                    new_state = dict(state)
                    for nm in names_in_expr(st.expr):
                        _mark_used(new_state, nm)
                    terminated_states.append(new_state)
                elif isinstance(st, If):
                    cond_state = dict(state)
                    for nm in names_in_expr(st.cond):
                        _mark_used(cond_state, nm)

                    cond_is_bool = isinstance(st.cond, Bool)
                    cond_truthy = cond_is_bool and st.cond.value

                    if cond_is_bool and cond_truthy:
                        if st.els:
                            lint_locals_used(st.els, source)
                        then_active, then_term = analyze_block(st.then, [cond_state])
                        next_active.extend(then_active)
                        terminated_states.extend(then_term)
                    elif cond_is_bool and not cond_truthy:
                        if st.then:
                            lint_locals_used(st.then, source)
                        else_active, else_term = analyze_block(st.els, [cond_state])
                        next_active.extend(else_active or [dict(cond_state)])
                        terminated_states.extend(else_term)
                    else:
                        then_active, then_term = analyze_block(st.then, [cond_state])
                        else_active, else_term = analyze_block(st.els, [cond_state])
                        for act in then_active + else_active:
                            next_active.append(act)
                        terminated_states.extend(then_term + else_term)
                elif isinstance(st, While):
                    cond_state = dict(state)
                    for nm in names_in_expr(st.cond):
                        _mark_used(cond_state, nm)
                    if isinstance(st.cond, Bool) and not st.cond.value:
                        lint_locals_used(st.body, source)
                        next_active.append(cond_state)
                    else:
                        body_active, body_term = analyze_block(st.body, [cond_state])
                        next_active.extend(body_active)
                        terminated_states.extend(body_term)
                elif isinstance(st, Switch):
                    switch_state = dict(state)
                    for nm in names_in_expr(st.expr):
                        _mark_used(switch_state, nm)
                    for case in st.cases:
                        if case.value is not None:
                            for nm in names_in_expr(case.value):
                                _mark_used(switch_state, nm)
                    has_default = any(case.value is None for case in st.cases)
                    for case in st.cases:
                        body_active, body_term = analyze_block(case.body, [dict(switch_state)])
                        next_active.extend(body_active)
                        terminated_states.extend(body_term)
                    if not has_default:
                        next_active.append(dict(switch_state))
                elif isinstance(st, TryCatch):
                    body_active, body_term = analyze_block(st.body, [dict(state)])
                    handler_state = dict(state)
                    if st.err_name:
                        handler_state[st.err_name] = (st.pos, False, False)
                    handler_active, handler_term = analyze_block(st.handler, [handler_state])
                    next_active.extend(body_active + handler_active)
                    terminated_states.extend(body_term + handler_term)
                elif isinstance(st, TaskBlock):
                    body_active, body_term = analyze_block(st.body, [dict(state)])
                    next_active.extend(body_active)
                    terminated_states.extend(body_term)
                elif isinstance(st, Namespace):
                    nested_state = dict(state)
                    _mark_captured_uses(st.body, nested_state)
                    lint_locals_used(st.body, source)
                    next_active.append(nested_state)
                elif isinstance(st, ClassDef):
                    nested_state = dict(state)
                    for m in st.methods:
                        _mark_captured_uses(m.body, nested_state)
                        lint_locals_used(m.body, source)
                    next_active.append(nested_state)
                elif isinstance(st, Fn):
                    nested_state = dict(state)
                    _mark_captured_uses(st.body, nested_state)
                    lint_locals_used(st.body, source)
                    next_active.append(nested_state)
                elif isinstance(st, MethodDef):
                    nested_state = dict(state)
                    _mark_captured_uses(st.body, nested_state)
                    lint_locals_used(st.body, source)
                    next_active.append(nested_state)
                else:
                    next_active.append(dict(state))

            active_states = _merge_states(next_active)

        return _merge_states(active_states), _merge_states(terminated_states)

    active, terminated = analyze_block(stmts, [dict()])
    all_states = active + terminated

    usage_summary: Dict[tuple[str, Location], Dict[str, bool]] = {}

    def _accumulate(states: List[Dict[str, tuple[Location, bool, bool]]], *, active_state: bool) -> None:
        for state in states:
            for name, (pos, used_all, used_any) in state.items():
                entry = usage_summary.setdefault(
                    (name, pos),
                    {
                        "used_any": False,
                        "active_all": True,
                        "active_present": False,
                    },
                )
                entry["used_any"] = entry["used_any"] or used_any
                if active_state:
                    entry["active_all"] = entry["active_all"] and used_all
                    entry["active_present"] = True

    _accumulate(active, active_state=True)
    _accumulate(terminated, active_state=False)

    for (name, pos), info in usage_summary.items():
        if name.startswith("_") or name.startswith("ignored") or (name.startswith("unused") and name != "unused"):
            continue

        used_any = info["used_any"]
        active_all = info["active_all"]
        active_present = info["active_present"]
        if not used_any:
            unused.append((name, pos))
            continue
        if active_present and not active_all:
            partial.append((name, pos))
            continue

    if unused:
        # Preserve the previous behavior of reporting all unused bindings together
        names = [name for name, _ in unused]
        pos = unused[0][1]
        msg = f"unused local binding(s): {', '.join(names)}"
        raise _lint_error(source, pos, msg, code="E002", hint="Remove the unused binding or reference it.")
    if partial:
        names = [name for name, _ in partial]
        pos = partial[0][1]
        msg = f"local binding(s) must be used on all control-flow paths: {', '.join(names)}"
        raise _lint_error(
            source,
            pos,
            msg,
            code="E002",
            hint="Ensure the binding is referenced on every path or remove it.",
        )


def lint_no_underscore_bindings(stmts: List[IR], source: Optional[str] = None) -> None:
    def check_name(name: str, node: Any) -> None:
        if name != "_":
            return
        raise _lint_error(
            source,
            node,
            "binding name '_' is reserved and cannot be declared",
            code="E016",
            hint="Rename the binding to something descriptive; '_' cannot be used as a binding name.",
        )

    def visit(block: List[IR]) -> None:
        for st in block:
            if isinstance(st, Let):
                check_name(st.name, st.name_span or st)
            elif isinstance(st, Assign):
                check_name(st.name, st.name_span or st)
            elif isinstance(st, DestructAssign):
                for name, span in zip(st.names, st.name_spans):
                    check_name(name, span or st)
            elif isinstance(st, Import):
                if st.alias != "_":
                    binding = _import_binding_name(st.module, st.alias)
                    check_name(binding, st.binding_span or st)
            elif isinstance(st, If):
                visit(st.then)
                visit(st.els)
            elif isinstance(st, While):
                visit(st.body)
            elif isinstance(st, Switch):
                for case in st.cases:
                    visit(case.body)
            elif isinstance(st, TryCatch):
                visit(st.body)
                visit(st.handler)
            elif isinstance(st, TaskBlock):
                visit(st.body)
            elif isinstance(st, Namespace):
                visit(st.body)
            elif isinstance(st, ClassDef):
                for method in st.methods:
                    visit(method.body)
            elif isinstance(st, Fn):
                visit(st.body)
            elif isinstance(st, MethodDef):
                visit(st.body)

    visit(stmts)


def _infer_expr_type(expr: IR, env: Dict[str, str]) -> Optional[str]:
    if isinstance(expr, Num):
        if "." in expr.txt or "e" in expr.txt or "E" in expr.txt:
            try:
                value = float(expr.txt)
            except ValueError:
                return "float"
            if ("e" in expr.txt or "E" in expr.txt) and "." not in expr.txt and value.is_integer():
                return "int"
            return "float"
        return "int"
    if isinstance(expr, Str):
        return "string"
    if isinstance(expr, Bool):
        return "Bool"
    if isinstance(expr, Null):
        return "Null"
    if isinstance(expr, Var):
        return env.get(expr.name)
    return None


def _types_match(expected: str, actual: str) -> bool:
    expected_norm = expected.strip()
    actual_norm = actual.strip()
    optional = expected_norm.endswith("?")
    base_expected = expected_norm[:-1].strip() if optional else expected_norm

    if optional and actual_norm.lower() == "null":
        return True
    if base_expected.lower() == actual_norm.lower():
        return True
    if base_expected.lower() == "number" and actual_norm.lower() in {"number", "int", "float"}:
        return True
    if base_expected.lower() == "string" and actual_norm.lower() == "string":
        return True
    if base_expected.lower() in {"bool", "boolean"} and actual_norm.lower() in {"bool", "boolean"}:
        return True
    if optional and actual_norm.lower() != "null":
        return _types_match(base_expected, actual)
    return False


def lint_assignment_types(stmts: List[IR], source: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> None:
    env = dict(env or {})

    def check_block(block: List[IR], local_env: Dict[str, str]) -> Dict[str, str]:
        for st in block:
            if isinstance(st, Let):
                inferred = _infer_expr_type(st.expr, local_env)
                if inferred:
                    local_env[st.name] = inferred
            elif isinstance(st, Assign):
                inferred = _infer_expr_type(st.expr, local_env)
                expected = local_env.get(st.name)
                if expected and inferred and not _types_match(expected, inferred):
                    msg = f"type change for variable {st.name}: expected {expected} but got {inferred}"
                    raise _lint_error(
                        source,
                        st,
                        msg,
                        code="E014",
                        hint="Use a new variable or cast explicitly if a different type is required.",
                    )
                if inferred:
                    local_env[st.name] = inferred
            elif isinstance(st, DestructAssign):
                inferred = _infer_expr_type(st.expr, local_env)
                if inferred:
                    for nm in st.names:
                        local_env[nm] = inferred
            elif isinstance(st, If):
                then_env = check_block(list(st.then), dict(local_env))
                else_env = check_block(list(st.els), dict(local_env))
                for name in list(local_env.keys()):
                    if name in then_env and name in else_env and then_env[name] == else_env[name]:
                        local_env[name] = then_env[name]
            elif isinstance(st, While):
                _ = check_block(list(st.body), dict(local_env))
            elif isinstance(st, Switch):
                case_envs: List[Dict[str, str]] = []
                for case in st.cases:
                    case_envs.append(check_block(list(case.body), dict(local_env)))
                if not any(case.value is None for case in st.cases):
                    case_envs.append(dict(local_env))
                for name in list(local_env.keys()):
                    if case_envs and all(name in env for env in case_envs):
                        distinct = {env[name] for env in case_envs}
                        if len(distinct) == 1:
                            local_env[name] = distinct.pop()
            elif isinstance(st, TryCatch):
                body_env = check_block(list(st.body), dict(local_env))
                handler_env = dict(local_env)
                if st.err_name:
                    handler_env[st.err_name] = "Error"
                handler_env = check_block(list(st.handler), handler_env)
                for name in list(local_env.keys()):
                    if name in body_env and name in handler_env and body_env[name] == handler_env[name]:
                        local_env[name] = body_env[name]
            elif isinstance(st, TaskBlock):
                local_env = check_block(list(st.body), local_env)
            elif isinstance(st, Namespace):
                check_block(list(st.body), {})
            elif isinstance(st, Fn):
                fn_env = {p.name: p.type for p in st.params if p.type}
                check_block(list(st.body), fn_env)
            elif isinstance(st, MethodDef):
                method_env = {p.name: p.type for p in st.params if p.type}
                check_block(list(st.body), method_env)
            elif isinstance(st, ClassDef):
                for method in st.methods:
                    method_env = {p.name: p.type for p in method.params if p.type}
                    check_block(list(method.body), method_env)
            elif isinstance(st, CallStmt):
                for arg in st.args:
                    inferred = _infer_expr_type(arg, local_env)
                    if isinstance(arg, Var) and inferred:
                        local_env[arg.name] = inferred
        return local_env

    check_block(stmts, env)


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


def _return_type_is_void(annotation: Optional[str]) -> bool:
    if annotation is None:
        return False
    normalized = annotation.strip().lower()
    return normalized in {"null", "null?"}


def _function_returns_value(fn: Fn) -> bool:
    if fn.return_type is not None:
        return not _return_type_is_void(fn.return_type)

    def visit(block: List[IR]) -> bool:
        for st in block:
            if isinstance(st, Return):
                return not isinstance(st.expr, Null)
            if isinstance(st, If):
                if visit(st.then) or visit(st.els):
                    return True
            elif isinstance(st, While):
                if visit(st.body):
                    return True
            elif isinstance(st, Switch):
                for case in st.cases:
                    if visit(case.body):
                        return True
            elif isinstance(st, TryCatch):
                if visit(st.body) or visit(st.handler):
                    return True
            elif isinstance(st, TaskBlock):
                if visit(st.body):
                    return True
            elif isinstance(st, (Fn, MethodDef, ClassDef, Namespace)):
                continue
        return False

    return visit(fn.body)


def _collect_function_return_values(stmts: List[IR], prefix: str = "") -> Dict[str, bool]:
    returns_value: Dict[str, bool] = {}

    def qualify(name: str) -> str:
        return f"{prefix}.{name}" if prefix else name

    for st in stmts:
        if isinstance(st, Fn):
            returns_value[qualify(st.name)] = _function_returns_value(st)
        elif isinstance(st, Namespace):
            nested_prefix = qualify(st.name)
            returns_value.update(_collect_function_return_values(st.body, prefix=nested_prefix))
    return returns_value


def lint_bare_call_results(
    stmts: List[IR], signatures: Dict[str, Optional[str]], source: Optional[str] = None
) -> None:
    del signatures
    returns_value = _collect_function_return_values(stmts)
    returns_value.update({"heap_set": True, "heap_get": True})
    allowed_call_stmts = {"delete", "tag", "join", "parse_program"}
    allowed_call_prefixes = (
        "Collections.",
        "Map.",
        "Set.",
        "Deque.",
        "Async.",
        "Result.",
        "String.",
        "Console.",
        "File.",
        "JSON.",
        "Python.",
        "Random.",
    )

    def _call_stmt_allowed(name: str) -> bool:
        if name in allowed_call_stmts:
            return True
        return any(name.startswith(prefix) for prefix in allowed_call_prefixes)

    def _call_returns_value(expr: IR) -> bool:
        if isinstance(expr, Call):
            return returns_value.get(expr.name, False)
        if isinstance(expr, MethodCall) and isinstance(expr.obj, Var):
            qualified = f"{expr.obj.name}.{expr.name}"
            return returns_value.get(qualified, False)
        return False

    def _binding_discarded(name: str) -> bool:
        if name == "_" or name.startswith("__"):
            return False
        return name.startswith("_")

    def visit(block: List[IR]) -> None:
        for st in block:
            if isinstance(st, CallStmt):
                if _call_stmt_allowed(st.name) or returns_value.get(st.name) is False:
                    continue
                hint = "Bind the return value, e.g. `def result = call();`, or add a return that includes the mutated data."
                msg = (
                    "call with return value must be bound; bare call statements are not allowed "
                    f"(offending call: {st.name}())"
                )
                raise _lint_error(source, st.pos, msg, code="E001", hint=hint)
            if isinstance(st, (Let, Assign)) and _binding_discarded(st.name) and _call_returns_value(st.expr):
                hint = "Bind the return value, e.g. `def result = call();`, or add a return that includes the mutated data."
                msg = (
                    "call with return value must be bound; bare call statements are not allowed "
                    f"(offending call: {st.expr.name}())"
                )
                raise _lint_error(source, st.pos, msg, code="E001", hint=hint)
            if isinstance(st, If):
                visit(st.then)
                visit(st.els)
            elif isinstance(st, While):
                visit(st.body)
            elif isinstance(st, Switch):
                for case in st.cases:
                    visit(case.body)
            elif isinstance(st, TryCatch):
                visit(st.body)
                visit(st.handler)
            elif isinstance(st, TaskBlock):
                visit(st.body)
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
        raise _lint_error(source, first_misordered, msg, code="E012", hint=hint)

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


def _is_optional_annotation(annotation: Optional[str]) -> bool:
    return bool(annotation and annotation.strip().endswith("?"))


def _block_guarantees_return(stmts: List[IR]) -> bool:
    for st in stmts:
        if isinstance(st, Return):
            return True
        if isinstance(st, If):
            if _block_guarantees_return(st.then) and _block_guarantees_return(st.els):
                return True
        if isinstance(st, Switch):
            has_default = any(case.value is None for case in st.cases)
            if has_default and all(_block_guarantees_return(case.body) for case in st.cases):
                return True
        if isinstance(st, TryCatch):
            if _block_guarantees_return(st.body) and _block_guarantees_return(st.handler):
                return True
        if isinstance(st, TaskBlock):
            if _block_guarantees_return(st.body):
                return True
        elif isinstance(st, While):
            continue
        elif isinstance(st, (Fn, MethodDef, ClassDef, Namespace)):
            continue
    return False


def _stmt_guarantees_exit(st: IR) -> bool:
    if isinstance(st, Return):
        return True
    if isinstance(st, If):
        return _block_guarantees_return(st.then) and _block_guarantees_return(st.els)
    if isinstance(st, Switch):
        has_default = any(case.value is None for case in st.cases)
        return has_default and all(_block_guarantees_return(case.body) for case in st.cases)
    if isinstance(st, TryCatch):
        return _block_guarantees_return(st.body) and _block_guarantees_return(st.handler)
    if isinstance(st, TaskBlock):
        return _block_guarantees_return(st.body)
    if isinstance(st, While):
        return isinstance(st.cond, Bool) and st.cond.value
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
                    raise _lint_error(source, st, msg, code="E007", hint=hint)
            elif isinstance(st, If):
                visit(st.then)
                visit(st.els)
            elif isinstance(st, While):
                visit(st.body)
            elif isinstance(st, Switch):
                for case in st.cases:
                    visit(case.body)
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
    location: Union[IR, SourcePos, SourceSpan],
) -> None:
    if expected_return is None:
        return
    if _is_optional_annotation(expected_return):
        return
    if _block_guarantees_return(stmts):
        return
    kind = "method" if is_method else "function"
    msg = f"not all paths in {kind} {fn_name} return a value for annotated type {expected_return}"
    raise _lint_error(
        source,
        location,
        msg,
        code="E010",
        hint="Add return statements for every branch or provide a default return to satisfy the annotation.",
    )


def lint_unreachable_code(stmts: List[IR], source: Optional[str] = None) -> None:
    def visit_block(block: List[IR]) -> None:
        terminated = False
        for st in block:
            if terminated:
                msg = "unreachable statement after a guaranteed exit"
                raise _lint_error(
                    source,
                    st,
                    msg,
                    code="E013",
                    hint="Remove the dead code or restructure control flow so it can be reached.",
                )

            if isinstance(st, If):
                visit_block(st.then)
                visit_block(st.els)
            elif isinstance(st, While):
                visit_block(st.body)
            elif isinstance(st, Switch):
                for case in st.cases:
                    visit_block(case.body)
            elif isinstance(st, TryCatch):
                visit_block(st.body)
                visit_block(st.handler)
            elif isinstance(st, TaskBlock):
                visit_block(st.body)
            elif isinstance(st, Fn):
                visit_block(st.body)
            elif isinstance(st, MethodDef):
                visit_block(st.body)
            elif isinstance(st, ClassDef):
                for m in st.methods:
                    visit_block(m.body)
            elif isinstance(st, Namespace):
                visit_block(st.body)

            if _stmt_guarantees_exit(st):
                terminated = True

    visit_block(stmts)


def lint_no_consecutive_definitions(stmts: List[IR], source: Optional[str] = None) -> None:
    prev: Optional[str] = None

    def check_block(block: List[IR]) -> None:
        nonlocal prev
        prev = None
        for st in block:
            if isinstance(st, (If, While, Switch)):
                if isinstance(st, If):
                    lint_no_consecutive_definitions(st.then, source)
                    lint_no_consecutive_definitions(st.els, source)
                elif isinstance(st, While):
                    lint_no_consecutive_definitions(st.body, source)
                else:
                    for case in st.cases:
                        lint_no_consecutive_definitions(case.body, source)
                prev = None
                continue
            if isinstance(st, Fn):
                lint_no_consecutive_definitions(st.body, source)
                prev = None
                continue
            if isinstance(st, MethodDef):
                lint_no_consecutive_definitions(st.body, source)
                prev = None
                continue
            if isinstance(st, ClassDef):
                for m in st.methods:
                    lint_no_consecutive_definitions(m.body, source)
                prev = None
                continue
            if isinstance(st, Namespace):
                lint_no_consecutive_definitions(st.body, source)
                prev = None
                continue
            if isinstance(st, TryCatch):
                lint_no_consecutive_definitions(st.body, source)
                lint_no_consecutive_definitions(st.handler, source)
                prev = None
                continue
            if isinstance(st, TaskBlock):
                lint_no_consecutive_definitions(st.body, source)
                prev = None
                continue

            current: Optional[str] = None
            if isinstance(st, Let):
                current = st.name

            if current is not None and prev == current:
                raise _lint_error(
                    source,
                    st,
                    f"variable {current} defined twice in a row",
                    code="E015",
                    hint="Rename the second binding or merge the declarations.",
                )

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
    elif isinstance(st, Switch):
        for case in st.cases:
            lint_destruct_call_outputs(case.body, source)
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
    elif isinstance(st, TaskBlock):
        lint_destruct_call_outputs(st.body, source)


def check_destruct_call_expr(expr: IR, names: set[str], *, source: Optional[str], pos: SourcePos) -> None:
    if isinstance(expr, Call):
        skip = {"heap_set", "heap_get", "delete", "tag", "__new", "new"}
        if expr.name in skip:
            return
        missing = sorted({arg.name for arg in expr.args if isinstance(arg, Var) and arg.name not in names})
        if missing:
            msg = f"destructuring call to {expr.name} must include output for argument(s): {', '.join(missing)}"
            raise _lint_error(
                source,
                pos,
                msg,
                code="E006",
                hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
            )
    elif isinstance(expr, MethodCall):
        missing = sorted({arg.name for arg in expr.args if isinstance(arg, Var) and arg.name not in names})
        if missing:
            msg = f"destructuring method call to {expr.name} must include output for argument(s): {', '.join(missing)}"
            raise _lint_error(
                source,
                pos,
                msg,
                code="E006",
                hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
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
        elif isinstance(st, TryCatch):
            for branch_stmt in st.body:
                visit(branch_stmt)
            for branch_stmt in st.handler:
                visit(branch_stmt)
        elif isinstance(st, TaskBlock):
            for body_stmt in st.body:
                visit(body_stmt)
        elif isinstance(st, While):
            for body_stmt in st.body:
                visit(body_stmt)
        elif isinstance(st, Switch):
            for case in st.cases:
                for body_stmt in case.body:
                    visit(body_stmt)

    for st in stmts:
        visit(st)

    missing = sorted(mutated - returned)
    if missing:
        kind = "method" if is_method else "function"
        msg = f"mutated parameter(s) in {kind} {fn_name} must be returned: {', '.join(missing)}"
        raise _lint_error(
            source,
            pos,
            msg,
            code="E001",
            hint="Return the mutated parameters so callers receive the updates.",
        )

# --- segment: tiny_language_runtime.py ---
"""Runtime helpers: module resolution, heap management, and async utilities.

This segment contains the import mechanics, concurrency primitives, and the core
runtime container used by the evaluator. Docstrings focus on public-facing
behaviors so integrators can navigate the stitched module without reading the
entire implementation.
"""

import logging
import time

from collections import defaultdict, deque

# ----- Runtime -----


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        super().__init__()
        self.value = value


@dataclass
class ScopeSnapshot:
    values: Dict[str, Any]
    types: Dict[str, str]


@dataclass
class DebugSnapshot:
    pos: SourcePos
    namespace: Optional[str]
    call_stack: Tuple[StackFrame, ...]
    scopes: List[ScopeSnapshot]


@dataclass
class StepRequest:
    mode: str
    depth: int


@dataclass
class ParameterBinding:
    name: str
    original: Any
    escaped: bool
    copied: bool


ParamKey = Tuple[str, int]


class Debugger:
    """Lightweight, synchronous debugger controller for stepping and breakpoints."""

    VALID_COMMANDS = {"continue", "step_in", "step_over", "step_out", "pause"}

    def __init__(
        self,
        on_pause: Optional[Callable[[DebugSnapshot], str]] = None,
        *,
        mirror_stdout: bool = True,
    ):
        self.breakpoints: Dict[Optional[str], Set[int]] = defaultdict(set)
        self.on_pause = on_pause
        self.command_queue: deque[str] = deque()
        self.snapshots: List[DebugSnapshot] = []
        self.pending_step: Optional[StepRequest] = None
        self.last_location: Optional[Tuple[Optional[str], int]] = None
        self.force_pause: bool = False
        # When False, the runtime will avoid mirroring program output to
        # ``stdout`` while debugging. This is useful for DAP transports that use
        # stdout for the protocol stream and expect program output to be emitted
        # via explicit ``output`` events instead of direct writes.
        self.mirror_stdout = mirror_stdout

    def set_breakpoints(self, namespace: Optional[str], lines: Set[int]) -> None:
        """Register breakpoints for a namespace (or ``None`` for the active module)."""

        self.breakpoints[namespace] = set(lines)

    def enqueue_commands(self, *commands: str) -> None:
        """Queue debugger commands to run in order as pauses are hit."""

        for cmd in commands:
            self._validate_command(cmd)
            self.command_queue.append(cmd)

    def request_pause(self) -> None:
        """Force the debugger to pause at the next opportunity."""

        self.force_pause = True

    def should_pause(self, pos: SourcePos, namespace: Optional[str], depth: int) -> bool:
        location = (namespace, pos.line)
        if self.force_pause:
            return True
        if pos.line in self.breakpoints.get(namespace, set()) or pos.line in self.breakpoints.get(None, set()):
            return True
        return self._matches_step(location, depth)

    def handle_pause(self, snapshot: DebugSnapshot, depth: int) -> None:
        self.snapshots.append(snapshot)
        self.last_location = (snapshot.namespace, snapshot.pos.line)
        # Clear any pending forced pause now that we've yielded control.
        self.force_pause = False
        command = self._next_command(snapshot)
        self.pending_step = self._step_for_command(command, depth)

    def _next_command(self, snapshot: DebugSnapshot) -> str:
        if self.on_pause is not None:
            command = self.on_pause(snapshot)
        elif self.command_queue:
            command = self.command_queue.popleft()
        else:
            command = "continue"
        self._validate_command(command)
        return command

    def _validate_command(self, command: str) -> None:
        if command not in self.VALID_COMMANDS:
            raise ValueError(f"invalid debugger command {command!r}; expected one of {sorted(self.VALID_COMMANDS)}")

    def _step_for_command(self, command: str, depth: int) -> Optional[StepRequest]:
        if command == "continue":
            return None
        if command == "step_in":
            return StepRequest("step_in", depth)
        if command == "step_over":
            return StepRequest("step_over", depth)
        if command == "step_out":
            return StepRequest("step_out", max(0, depth - 1))
        return None

    def _matches_step(self, location: Tuple[Optional[str], int], depth: int) -> bool:
        if self.pending_step is None:
            return False
        if self.pending_step.mode == "step_in":
            return location != self.last_location
        if self.pending_step.mode == "step_over":
            return depth <= self.pending_step.depth and location != self.last_location
        if self.pending_step.mode == "step_out":
            return depth <= self.pending_step.depth and location != self.last_location
        return False


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
    """Locate and load TinyLanguage modules from configurable search roots.

    The resolver accepts optional search paths (including the ``TINYPATH``
    environment variable) and memoizes successfully loaded modules so repeated
    imports are cheap. It also guards against circular imports by tracking the
    current resolution stack.
    """

    def __init__(self, search_paths: Optional[List[Path]] = None):
        env_paths = os.environ.get("TINYPATH", "")
        configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
        default_roots = [Path.cwd(), Path(__file__).parent]
        stdlib_root = Path(__file__).resolve().parents[1] / "stdlib"
        if stdlib_root.exists():
            default_roots.append(stdlib_root)
        self.search_paths: List[Path] = search_paths or configured_paths + default_roots
        self.cache: Dict[Path, NamespaceRef] = {}
        self._in_progress: List[Path] = []

    def _resolve_name(self, raw: str, caller_namespace: Optional[str], pos: Optional[Any]) -> str:
        """Normalize relative import names against the caller's namespace.

        A leading dot sequence (e.g. ``.foo`` or ``..bar.baz``) is expanded using
        the caller's module namespace. Errors include source span information to
        aid diagnostics in the parser and linter.
        """
        pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
        leading = len(raw) - len(raw.lstrip("."))
        if leading == 0:
            return raw
        if not caller_namespace:
            raise TinyLangError(
                "relative import outside a module",
                pos_for_error or SourcePos.origin(),
                code="E008",
                span=pos if isinstance(pos, SourceSpan) else None,
            )
        base = caller_namespace.split(".")
        if leading > len(base):
            raise TinyLangError(
                "relative import traverses beyond module root",
                pos_for_error or SourcePos.origin(),
                code="E008",
                span=pos if isinstance(pos, SourceSpan) else None,
            )
        trimmed = base[: len(base) - leading]
        remainder = raw.lstrip(".")
        if remainder:
            trimmed.append(remainder)
        return ".".join(part for part in trimmed if part)

    def _candidate_paths(self, module_name: str, caller_path: Optional[Path]) -> List[Path]:
        """Return possible filesystem paths for a module name.

        The search order starts next to the caller's module (for relative
        imports) before falling back to configured search roots. Each candidate
        mirrors Python's ``pkg.subpkg.module`` to ``pkg/subpkg/module.tiny``
        translation.
        """
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
        pos: Optional[Any] = None,
    ) -> NamespaceRef:
        """Import a module, executing it if necessary and caching the namespace."""
        resolved_name = self._resolve_name(name, caller_namespace, pos)
        pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
        frame_pos = pos_for_error or SourcePos.origin()
        for candidate in self._candidate_paths(resolved_name, caller_path):
            resolved_path = candidate.resolve()
            if resolved_path in self.cache:
                return self.cache[resolved_path]
            if resolved_path.exists():
                if resolved_path in self._in_progress:
                    raise TinyLangError(
                        f"circular import involving {resolved_path}",
                        pos_for_error or SourcePos.origin(),
                        code="E008",
                        span=pos if isinstance(pos, SourceSpan) else None,
                    )
                self._in_progress.append(resolved_path)
                module_frame: Optional[StackFrame] = None
                if runtime.debugger is not None:
                    module_frame = StackFrame(resolved_name or "<module>", resolved_name, frame_pos)
                    runtime.call_stack.append(module_frame)
                try:
                    module_env = Environment(parent=None, namespace=resolved_name, runtime=runtime)
                    previous_global_env = runtime.global_env
                    try:
                        compile_and_run(
                            resolved_path.read_text(encoding="utf-8"),
                            env=module_env,
                            runtime=runtime,
                            module_namespace=resolved_name,
                            module_path=resolved_path,
                            module_resolver=self,
                        )
                    finally:
                        runtime.global_env = previous_global_env
                    ns_ref = NamespaceRef(runtime, resolved_name)
                    self.cache[resolved_path] = ns_ref
                    return ns_ref
                finally:
                    if module_frame is not None:
                        runtime.call_stack.pop()
                    self._in_progress.remove(resolved_path)
        raise TinyLangError(
            f"module '{name}' not found on search path",
            pos or SourcePos.origin(),
            code="E008",
            span=pos if isinstance(pos, SourceSpan) else None,
        )


@dataclass
class SpawnHandle:
    thread: threading.Thread
    done: threading.Event
    cancelled: threading.Event
    result: Any = None
    error: Optional[BaseException] = None


@dataclass
class CancellationToken:
    """Coordinated cancellation primitive shared across spawned tasks."""

    cancelled: threading.Event = field(default_factory=threading.Event)
    reason: Optional[str] = None
    _linked: List[SpawnHandle] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def cancel(self, reason: Optional[str] = None) -> bool:
        """Mark the token as cancelled and propagate to linked handles."""
        with self._lock:
            already = self.cancelled.is_set()
            if already:
                return False
            self.reason = reason
            self.cancelled.set()
            for handle in list(self._linked):
                handle.cancelled.set()
            return True

    def link_handle(self, handle: SpawnHandle) -> bool:
        """Link a spawn handle so it reacts to future cancellations."""
        with self._lock:
            if handle in self._linked:
                return False
            if self.cancelled.is_set():
                handle.cancelled.set()
                return False
            self._linked.append(handle)
            return True


@dataclass
class TaskScope:
    """Track spawned handles that must resolve before exiting a task block."""

    handles: List[SpawnHandle] = field(default_factory=list)

    def add_handle(self, handle: SpawnHandle) -> None:
        if handle not in self.handles:
            self.handles.append(handle)


class Runtime:
    def __init__(self, source: str):
        self._lock = threading.RLock()
        self.heap: Dict[int, List[Any]] = {}
        self.allocations: Dict[int, int] = {}
        self.freed_allocations: Dict[int, int] = {}
        self.freed_ptrs: Set[int] = set()
        self.heap_cell_types: Dict[int, Dict[int, str]] = {}
        self.ptr_tags: Dict[int, str] = {}
        self.ops: Dict[Tuple[str, Optional[str], Optional[str]], Any] = {}
        self.methods: Dict[Tuple[str, str], MethodDef] = {}
        self.types: Dict[str, Dict[str, Any]] = {}
        self.variant_to_type: Dict[str, str] = {}
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
        self.debugger: Optional[Debugger] = None
        self.stream_output: bool = True
        self.streamed_output: bool = False
        env_copy_flag = os.environ.get("TINYLANG_COPY_ON_CALL", "").strip().lower()
        self.copy_on_call: bool = env_copy_flag in {"1", "true", "yes", "on"}
        self._parameter_binding_stack: threading.local = threading.local()
        self.trace_log_path: Optional[str] = os.environ.get("TINYLANG_TRACE_LOG")
        self.trace_every_statement: bool = os.environ.get("TINYLANG_TRACE_EVERY_STATEMENT", "0") == "1"
        self.trace_heartbeat_secs: float = float(os.environ.get("TINYLANG_TRACE_HEARTBEAT_SECS", "1.0"))
        self.trace_to_stdout: bool = os.environ.get("TINYLANG_TRACE_STDOUT", "0") not in {"0", "", "false", "False"}
        self._trace_logger: Optional[logging.Logger] = None
        self._last_trace_time: float = 0.0
        self._last_trace_location: Optional[Tuple[Optional[str], int]] = None
        self._last_emitted_output_idx: int = 0
        self._task_scopes: List[TaskScope] = []
        self.task_scope_timeout_ms: float = float(os.environ.get("TINYLANG_TASK_SCOPE_TIMEOUT_MS", "50"))
        if self.trace_log_path:
            self._setup_trace_logger()

    def _binding_stack(self) -> List[Dict[ParamKey, ParameterBinding]]:
        stack = getattr(self._parameter_binding_stack, "stack", None)
        if stack is None:
            stack = []
            self._parameter_binding_stack.stack = stack
        return stack

    def _push_task_scope(self) -> TaskScope:
        scope = TaskScope()
        self._task_scopes.append(scope)
        return scope

    def _pop_task_scope(self) -> None:
        if not self._task_scopes:
            return
        scope = self._task_scopes.pop()
        for handle in scope.handles:
            self.join_handle(handle, timeout_ms=self.task_scope_timeout_ms, cancel_on_timeout=True)

    def _register_task_handle(self, handle: SpawnHandle) -> None:
        if self._task_scopes:
            self._task_scopes[-1].add_handle(handle)

    def _push_parameter_scope(self, bindings: Dict[ParamKey, ParameterBinding]) -> None:
        self._binding_stack().append(bindings)

    def _pop_parameter_scope(self) -> None:
        stack = self._binding_stack()
        if stack:
            stack.pop()

    def _binding_key(self, value: Any) -> Optional[ParamKey]:
        if isinstance(value, BaseView):
            return self._binding_key(value.obj)
        if self._is_heap_pointer(value):
            return ("ptr", int(value))
        if isinstance(value, dict):
            return ("obj", id(value))
        if isinstance(value, list):
            return ("list", id(value))
        return None

    def _is_heap_pointer(self, value: Any) -> bool:
        if isinstance(value, bool):
            return False
        try:
            iv = int(value)
        except Exception:
            return False
        if isinstance(value, float) and not value.is_integer():
            return False
        with self._lock:
            return iv in self.heap

    def _is_mutable_argument(self, value: Any) -> bool:
        if self._is_heap_pointer(value):
            return True
        if isinstance(value, BaseView):
            return self._is_mutable_argument(value.obj)
        if isinstance(value, (dict, list)):
            return True
        return False

    def _deep_copy_value(
        self,
        value: Any,
        *,
        memo: Optional[Dict[int, Any]] = None,
        ptr_memo: Optional[Dict[int, Any]] = None,
        protected_keys: Optional[Set[ParamKey]] = None,
    ) -> Any:
        memo = memo or {}
        ptr_memo = ptr_memo or {}
        if protected_keys is not None:
            key = self._binding_key(value)
            if key:
                protected_keys.add(key)

        if isinstance(value, BaseView):
            copied_obj = self._deep_copy_value(value.obj, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys)
            return BaseView(copied_obj, value.class_name)

        if self._is_heap_pointer(value):
            ip = int(value)
            if ip in ptr_memo:
                return ptr_memo[ip]
            with self._lock:
                cells = list(self.heap.get(ip, []))
                cell_types = dict(self.heap_cell_types.get(ip, {}))
                tag = self.ptr_tags.get(ip)
            new_ptr = self.__new(len(cells))
            ptr_memo[ip] = new_ptr
            for idx, cell in enumerate(cells):
                copied_cell = self._deep_copy_value(
                    cell, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys
                )
                self.heap_set(new_ptr, idx, copied_cell)
                if idx in cell_types:
                    with self._lock:
                        self.heap_cell_types.setdefault(new_ptr, {})[idx] = cell_types[idx]
            if tag:
                with self._lock:
                    self.ptr_tags[new_ptr] = tag
            return new_ptr

        if isinstance(value, dict):
            obj_id = id(value)
            if obj_id in memo:
                return memo[obj_id]
            copied: Dict[str, Any] = {}
            memo[obj_id] = copied
            for key, val in value.items():
                if key == "__fields__" and isinstance(val, dict):
                    copied_fields: Dict[str, Dict[str, Any]] = {}
                    copied[key] = copied_fields
                    for cls, fmap in val.items():
                        copied_fields[cls] = {
                            fname: self._deep_copy_value(fval, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys)
                            for fname, fval in fmap.items()
                        }
                else:
                    copied[key] = self._deep_copy_value(
                        val, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys
                    )
            return copied

        if isinstance(value, list):
            list_id = id(value)
            if list_id in memo:
                return memo[list_id]
            copied_list: List[Any] = []
            memo[list_id] = copied_list
            copied_list.extend(
                self._deep_copy_value(item, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys)
                for item in value
            )
            return copied_list

        if isinstance(value, tuple):
            return tuple(
                self._deep_copy_value(item, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys)
                for item in value
            )

        return value

    def _lookup_protected_binding(self, target: Any) -> Optional[ParameterBinding]:
        key = self._binding_key(target)
        if key is None:
            return None
        for scope in reversed(self._binding_stack()):
            binding = scope.get(key)
            if binding:
                return binding
        return None

    def _guard_protected_mutation(self, target: Any, pos: Optional[Any]) -> None:
        if not self.copy_on_call:
            return
        binding = self._lookup_protected_binding(target)
        if binding is None or binding.escaped:
            return
        raise self._error(
            f"mutation of protected parameter {binding.name} is not allowed while copy-on-call is enabled",
            pos or SourcePos.origin(),
            hint="Return the argument or disable --copy-on-call to mutate caller-owned data.",
        )

    def _bind_parameters_to_env(
        self,
        params: List[Param],
        args: List[Any],
        env: "Environment",
        *,
        escaped_params: Set[str],
        pos: SourcePos,
        type_label: str,
        force_escaped: Optional[Set[str]] = None,
    ) -> Dict[ParamKey, ParameterBinding]:
        bindings: Dict[ParamKey, ParameterBinding] = {}
        memo: Dict[int, Any] = {}
        ptr_memo: Dict[int, Any] = {}
        forced = force_escaped or set()
        for param, arg in zip(params, args):
            if param.type:
                self._enforce_annotation(param.type, arg, label=f"parameter {param.name} in {type_label}", pos=pos)
            should_escape = param.name in escaped_params or param.name in forced
            is_mutable = self._is_mutable_argument(arg)
            protected_keys: Set[ParamKey] = set()
            bound_val = arg
            if self.copy_on_call and is_mutable and not should_escape:
                bound_val = self._deep_copy_value(
                    arg, memo=memo, ptr_memo=ptr_memo, protected_keys=protected_keys
                )
            env.define(param.name, bound_val, pos)
            if self.copy_on_call and is_mutable and not should_escape:
                for key in protected_keys:
                    bindings[key] = ParameterBinding(param.name, arg, escaped=False, copied=bound_val is not arg)
        return bindings

    def flush_streams(self) -> None:
        """Flush any mirrored stdout streams when streaming is enabled."""

        with self._lock:
            import sys

            mirror_stdout = bool(getattr(self.debugger, "mirror_stdout", False))
            if self.stream_output or mirror_stdout or self.trace_to_stdout:
                sys.stdout.flush()

            self._emit_output_to_debugger()

    def _emit_output_to_debugger(self) -> None:
        handler = getattr(self.debugger, "on_output", None)
        if handler is None:
            return

        new_output = "".join(self.output[self._last_emitted_output_idx :])
        if not new_output:
            return

        self._last_emitted_output_idx = len(self.output)
        handler(new_output)

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

    def _setup_trace_logger(self) -> None:
        Path(self.trace_log_path).parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(f"tiny_language.trace.{id(self)}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.handlers.clear()
        handler = logging.FileHandler(self.trace_log_path, mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        if self.trace_to_stdout:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(stream_handler)
        self._trace_logger = logger

    def _log_trace(self, node: IR, env: "Environment", namespace: Optional[str]) -> None:
        if self._trace_logger is None:
            return
        now = time.time()
        pos = getattr(node, "pos", SourcePos.origin()) or SourcePos.origin()
        location = (namespace, pos.line)
        should_log = self.trace_every_statement or now - self._last_trace_time >= self.trace_heartbeat_secs
        if not should_log and location == self._last_trace_location:
            return
        self._last_trace_time = now if should_log else self._last_trace_time
        self._last_trace_location = location
        stack_overview = " > ".join(frame.qualified_name for frame in self.call_stack) or "<root>"
        scope_keys = ", ".join(sorted(getattr(env, "values", {}).keys()))
        self._trace_logger.debug(
            "executing %s at %s:%d (col %d); depth=%d; stack=%s; env=%s",
            node.__class__.__name__,
            namespace or "<module>",
            pos.line,
            getattr(pos, "col", 0),
            len(self.call_stack),
            stack_overview,
            scope_keys,
        )

    def _capture_scopes(self, env: "Environment") -> List[ScopeSnapshot]:
        scopes: List[ScopeSnapshot] = []
        current: Optional["Environment"] = env
        while current:
            scopes.append(ScopeSnapshot(values=dict(current.values), types=dict(current.types)))
            current = current.parent
        return scopes

    def _maybe_pause(self, node: IR, env: "Environment", namespace: Optional[str]) -> None:
        self._log_trace(node, env, namespace)
        if self.debugger is None:
            return
        pos = getattr(node, "pos", SourcePos.origin()) or SourcePos.origin()
        depth = len(self.call_stack)
        if self.debugger.should_pause(pos, namespace, depth):
            snapshot = DebugSnapshot(
                pos=pos,
                namespace=namespace,
                call_stack=tuple(self.call_stack),
                scopes=self._capture_scopes(env),
            )
            if self._trace_logger is not None:
                self._trace_logger.debug(
                    "pause at %s:%d; depth=%d; pending_step=%s; breakpoints=%s",
                    namespace or "<module>",
                    pos.line,
                    depth,
                    getattr(self.debugger, "pending_step", None),
                    self.debugger.breakpoints,
                )
            self.debugger.handle_pause(snapshot, depth)

    @staticmethod
    def _pos_and_span(location: Optional[Any], span_override: Optional[SourceSpan] = None) -> Tuple[Optional[SourcePos], Optional[SourceSpan]]:
        resolved_span = span_override
        if resolved_span is None:
            if isinstance(location, SourceSpan):
                resolved_span = location
            elif location is not None:
                resolved_span = getattr(location, "span", None)
        if isinstance(location, SourcePos):
            resolved_pos = location
        elif location is not None:
            resolved_pos = getattr(location, "pos", None)
        else:
            resolved_pos = None
        if resolved_pos is None and resolved_span is not None:
            resolved_pos = resolved_span.start
        return resolved_pos, resolved_span

    @staticmethod
    def _format_location(pos: Optional[SourcePos], span: Optional[SourceSpan]) -> Optional[Union[SourcePos, SourceSpan]]:
        if pos is not None:
            return pos
        if span is not None:
            if span.start.line == span.stop.line:
                return span.start
            return span
        return pos

    def _record_error(
        self,
        msg: str,
        pos: Optional[Any] = None,
        *,
        code: str = "E000",
        hint: Optional[str] = None,
        formatted: Optional[str] = None,
        span: Optional[SourceSpan] = None,
    ) -> None:
        resolved_pos, resolved_span = self._pos_and_span(pos, span)
        location = self._format_location(resolved_pos, resolved_span)
        if formatted is None:
            source = self._source_for_namespace(self.current_module_namespace if location is not None else None)
            base = format_error(source, location, msg, code=code, hint=hint) if location is not None else msg
            stack_part = self._format_stacktrace(self.call_stack)
            formatted = f"{base}\n{stack_part}" if stack_part else base
        with self._lock:
            # Only keep the most recent runtime error so `errorMessage` reflects
            # the latest failure instead of accumulating older ones.
            self.error_messages = [formatted]

    def _error(
        self,
        msg: str,
        pos: Any,
        *,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        candidates: Optional[List[str]] = None,
        span: Optional[SourceSpan] = None,
        ) -> TinyLangError:
        resolved_pos, resolved_span = self._pos_and_span(pos, span)
        location = self._format_location(resolved_pos, resolved_span) or resolved_pos or SourcePos.origin()
        derived_code, derived_hint = _classify_error(msg, candidates)
        code = code or derived_code
        hint = hint or derived_hint
        source = self._source_for_namespace(self.current_module_namespace)
        formatted = format_error(source, location, msg, code=code, hint=hint)
        stack = tuple(self.call_stack)
        if stack:
            formatted = f"{formatted}\n{self._format_stacktrace(stack)}"
        self._record_error(msg, resolved_pos, code=code, hint=hint, formatted=formatted, span=resolved_span)
        return TinyLangError(formatted, resolved_pos or SourcePos.origin(), code=code, hint=hint, stack=stack, span=resolved_span)

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
            self.allocations[p] = int(n)
            self.freed_allocations.pop(p, None)
            self.heap_cell_types[p] = {}
            self.freed_ptrs.discard(p)
            return p

    @staticmethod
    def _pointer_label(p: Any) -> str:
        type_name = type(p).__name__
        if isinstance(p, (int, float)) and str(p).isnumeric():
            return str(int(p))
        return f"{p!r} ({type_name})"

    def _resolve_ptr(self, p: Any, pos: Optional[Any], *, op: str) -> Tuple[Optional[int], Optional[List[Any]]]:
        """Validate and resolve a heap pointer for the requested operation.

        Returns a tuple of `(pointer, cells)` where either entry may be `None` if
        validation failed and an error was recorded.
        """

        try:
            ip = int(p)
        except Exception:
            message = f"heap {op} error: pointer {self._pointer_label(p)} is not numeric"
            self._record_error(message, pos)
            return None, None

        if isinstance(p, float) and not p.is_integer():
            message = f"heap {op} error: pointer {self._pointer_label(p)} is not an integer pointer"
            self._record_error(message, pos)
            return None, None

        if ip < 1:
            message = (
                f"heap {op} error: pointer {ip} is invalid (must refer to a live positive allocation)"
            )
            self._record_error(message, pos)
            return None, None

        with self._lock:
            if ip in self.freed_ptrs:
                size_part = self.freed_allocations.get(ip)
                size_hint = f" (size {size_part})" if size_part is not None else ""
                message = f"heap {op} error: pointer {ip} was already freed{size_hint}"
                self._record_error(message, pos)
                return None, None
            try:
                cells = self.heap[ip]
            except KeyError:
                live = sorted(self.heap.keys())
                freed = sorted(self.freed_ptrs)
                details: List[str] = []
                if live:
                    details.append(f"live: {live}")
                if freed:
                    details.append(f"freed: {freed}")
                context = f" ({'; '.join(details)})" if details else ""
                message = f"heap {op} error: unknown pointer {ip}{context}"
                self._record_error(message, pos)
                return None, None
            return ip, cells

    def _parse_heap_index(self, i: Any, pos: Optional[Any]) -> Optional[int]:
        """Parse an index argument and record helpful errors when invalid."""

        try:
            idx = int(i)
        except Exception:
            message = f"heap access error: index {i!r} is not numeric"
            self._record_error(message, pos)
            return None

        if isinstance(i, float) and not i.is_integer():
            message = f"heap access error: index {self._pointer_label(i)} is not an integer index"
            self._record_error(message, pos)
            return None

        return idx

    def delete(self, p: Any, pos: Optional[Any] = None) -> Dict[str, Any]:
        ip, _ = self._resolve_ptr(p, pos, op="delete")
        if ip is None:
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": self.error_message or ""}}

        with self._lock:
            self.heap.pop(ip, None)
            self.heap_cell_types.pop(ip, None)
            self.ptr_tags.pop(ip, None)
            size = self.allocations.pop(ip, None)
            if size is not None:
                self.freed_allocations[ip] = size
            self.freed_ptrs.add(ip)
        return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}

    def heap_get(self, p: Any, i: Any, *, pos: Optional[Any] = None) -> Any:
        idx = self._parse_heap_index(i, pos)
        if idx is None:
            return None

        ip, cells = self._resolve_ptr(p, pos, op="access")
        if ip is None or cells is None:
            return None

        size = len(cells)
        if idx < 0 or idx >= size:
            range_hint = "empty allocation" if size == 0 else f"valid indices: 0..{size - 1}"
            self._record_error(
                f"heap access error: index {idx} out of range for pointer {ip} (size {size}; {range_hint})",
                pos,
            )
            return None
        return cells[idx]

    def heap_set(self, p: Any, i: Any, v: Any, *, pos: Optional[Any] = None) -> Dict[str, Any]:
        idx = self._parse_heap_index(i, pos)
        if idx is None:
            msg = self.error_message or ""
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": msg}}

        ip, cells = self._resolve_ptr(p, pos, op="access")
        if ip is None or cells is None:
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": self.error_message or ""}}

        size = len(cells)
        if idx < 0 or idx >= size:
            range_hint = "empty allocation" if size == 0 else f"valid indices: 0..{size - 1}"
            message = f"heap access error: index {idx} out of range for pointer {ip} (size {size}; {range_hint})"
            self._record_error(message, pos)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": message}}

        self._guard_protected_mutation(ip, pos)

        with self._lock:
            expected = self.heap_cell_types.get(ip, {}).get(idx)
            actual = self._value_type_name(v)
            if expected is not None and expected != actual:
                message = f"heap type mismatch at {ip}[{idx}]: expected {expected} but got {actual}"
                self._record_error(message, pos, code="E014")
                return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 1, "msg": message}}
            self.heap[ip][idx] = v
            self.heap_cell_types.setdefault(ip, {})[idx] = actual
        return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}

    def heap_leak_report(self) -> Dict[str, Any]:
        """Summarize live heap allocations for leak tracking in tests."""

        with self._lock:
            live = {ptr: len(cells) for ptr, cells in self.heap.items()}
            leak_count = len(live)
            return {
                "live": live,
                "count": leak_count,
                "total_cells": sum(live.values()),
                "allocations": dict(self.allocations),
                "freed_sizes": dict(self.freed_allocations),
                "freed": sorted(self.freed_ptrs),
                "freed_count": len(self.freed_ptrs),
                "has_leaks": leak_count > 0,
            }

    def tag(self, p: Any, typ: Any, *, pos: Optional[Any] = None) -> Dict[str, Any]:
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
        if isinstance(value, dict) and "__type__" in value:
            return str(value.get("__type__"))
        tag = self.__get_tag(value)
        if tag:
            return tag
        if value is None:
            return "Null"
        if isinstance(value, bool):
            return "Bool"
        if isinstance(value, int) and not isinstance(value, bool):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "string"
        return type(value).__name__

    def _infer_type_name(self, value: Any) -> str:
        """Return a type label for variables defined without annotations."""
        return self._value_type_name(value) or type(value).__name__

    @staticmethod
    def _normalize_numeric_type(type_name: str) -> str:
        return type_name

    def _check_assignment_type(
        self, env: "Environment", name: str, value: Any, pos: Any, *, local_only: bool = False
    ) -> None:
        expected = env.type_of(name, local_only=local_only)
        if expected is None:
            return
        if not self._type_matches(expected, value):
            actual = self._value_type_name(value) or type(value).__name__
            raise self._error(
                f"type change for variable {name}: expected {expected} but got {actual}",
                pos,
                code="E014",
                hint="Use a new variable or cast explicitly if a different type is required.",
            )

    def _type_matches(self, expected: str, value: Any) -> bool:
        actual = self._value_type_name(value)
        if actual is None:
            return False
        expected_norm = expected.strip()
        if expected_norm.lower() == "any":
            return True
        optional = expected_norm.endswith("?")
        base_expected = expected_norm[:-1].strip() if optional else expected_norm
        actual_norm = actual.strip() if isinstance(actual, str) else str(actual)
        if optional and actual_norm.lower() == "null":
            return True
        if base_expected == actual_norm or base_expected.lower() == actual_norm.lower():
            return True
        if base_expected.lower() == "number" and actual_norm.lower() in {"number", "int", "float"}:
            return True
        if base_expected.lower() == "string" and actual_norm.lower() == "string":
            return True
        if base_expected.lower() in {"bool", "boolean"} and actual_norm.lower() in {"bool", "boolean"}:
            return True
        if base_expected == "Null" and value is None:
            return True
        if optional and actual_norm.lower() != "null":
            return self._type_matches(base_expected, value)
        return False

    def _enforce_annotation(self, expected: str, value: Any, *, label: str, pos: Any) -> None:
        if not self._type_matches(expected, value):
            actual = self._value_type_name(value) or type(value).__name__
            raise self._error(
                f"type mismatch for {label}: expected {expected} but got {actual}",
                pos,
                code="E009",
                hint="Adjust the type annotation (use '?' to allow Null) or pass a compatible value to satisfy the hint.",
            )

    def _enforce_inferred_return(self, owner: Any, value: Any, *, label: str, pos: SourcePos) -> None:
        expected = getattr(owner, "inferred_return_type", None)
        inferred = self._normalize_numeric_type(self._infer_type_name(value))
        if expected is None:
            owner.inferred_return_type = inferred
            return
        expected_norm = self._normalize_numeric_type(expected)
        if expected_norm != expected:
            owner.inferred_return_type = expected_norm
        if self._type_matches(expected_norm, value):
            return
        actual = self._value_type_name(value) or type(value).__name__
        raise self._error(
            f"inferred return type for {label} changed: expected {expected_norm} but got {actual}",
            pos,
            code="E014",
            hint="Add an explicit return type annotation or keep return values consistent to avoid implicit type changes.",
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
                if not val_b.is_integer() and val_a < 0:
                    return mk("any_number")
                if val_b.is_integer():
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
            if isinstance(val_b, float) and not val_b.is_integer() and val_a < 0:
                return mk("any_number")
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
                if not b.is_integer() and a < 0:
                    raise RuntimeError("fractional exponent for ^ requires a non-negative base")
                if b.is_integer():
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

    def field_get(self, obj: Any, key: str, *, pos: Optional[Any] = None) -> Any:
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

    def field_set(self, obj: Any, key: str, val: Any, *, pos: Optional[Any] = None) -> None:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        self._guard_protected_mutation(target_obj, pos)
        if isinstance(target_obj, dict) and "__fields__" in target_obj:
            fmap = self._resolve_field_storage(target_obj, key, owner_hint, target_obj["__tag__"], allow_write=True)
            fmap[key] = val
            return
        target_obj[str(key)] = val

    def register_type(
        self,
        name: str,
        fields: Optional[List[Tuple[str, str]]] = None,
        variants: Optional[List[TypeVariant]] = None,
    ) -> None:
        variant_map: Dict[str, Dict[str, str]] = {}
        if variants:
            variant_map = {v.name: dict(v.fields) for v in variants}
        elif fields is not None:
            variant_map[name] = dict(fields)
        with self._lock:
            for vname in variant_map:
                self.variant_to_type[vname] = name
            self.types[str(name)] = {
                "kind": "sum" if variants else "product",
                "fields": variant_map.get(name, {}),
                "variants": variant_map,
            }

        def _register_constructor(target_name: str, field_defs: Dict[str, str]) -> None:
            field_order = list(field_defs.keys())

            def _ctor(*args: Any) -> Dict[str, Any]:
                if len(args) != len(field_order):
                    raise RuntimeError(
                        f"{target_name} expects {len(field_order)} argument(s); got {len(args)}"
                    )
                init = dict(zip(field_order, args))
                return self.instantiate_variant(target_name, init, type_name=name)

            self.register_native(target_name, _ctor)

        if variants:
            for vname, fields_map in variant_map.items():
                _register_constructor(vname, fields_map)
        elif fields is not None:
            _register_constructor(name, variant_map.get(name, {}))

    def _type_variants(self, name: str) -> Optional[Dict[str, Dict[str, str]]]:
        with self._lock:
            tinfo = self.types.get(name)
        if not tinfo:
            return None
        variants = tinfo.get("variants")
        if variants:
            return variants
        if tinfo.get("fields") is not None:
            return {name: tinfo.get("fields", {})}
        return None

    def instantiate_variant(
        self, variant: str, init: Dict[str, Any], *, type_name: Optional[str] = None, pos: Optional[Any] = None
    ) -> Dict[str, Any]:
        inferred_type = type_name or self.variant_to_type.get(variant)
        if inferred_type is None:
            raise self._error(f"unknown variant {variant}", pos)
        variants = self._type_variants(inferred_type)
        if not variants or variant not in variants:
            raise self._error(f"variant {variant} not allowed for type {inferred_type}", pos)
        expected_fields = variants.get(variant, {})
        missing = [f for f in expected_fields if f not in init]
        extra = [f for f in init if f not in expected_fields]
        if missing:
            raise self._error(f"missing field(s) for variant {variant}: {', '.join(missing)}", pos)
        if extra:
            raise self._error(f"unknown field(s) for variant {variant}: {', '.join(extra)}", pos)
        value: Dict[str, Any] = {"__tag__": variant, "__type__": inferred_type}
        value.update(init)
        return value

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
            op_env = Environment(parent=env, namespace=env.namespace, runtime=self)
            op_env.define(opdef.a_name, a_val, opdef.pos)
            op_env.define(opdef.b_name, b_val, opdef.pos)
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

    def eval_match(self, m: Match, value: Any, env: "Environment") -> Any:
        tag = self.__get_tag(value)
        if tag is None:
            raise self._error("match target is not tagged", m)

        type_name = None
        if isinstance(value, dict):
            type_name = value.get("__type__") or self.variant_to_type.get(tag)
        else:
            type_name = self.variant_to_type.get(tag)

        variants: Optional[Dict[str, Dict[str, str]]] = None
        expected: Optional[Set[str]] = None
        if type_name:
            variants = self._type_variants(str(type_name))
            if variants:
                expected = set(variants.keys())

        seen: Set[str] = set()
        has_wildcard = False
        for case in m.cases:
            if isinstance(case.pattern, WildcardPattern):
                has_wildcard = True
            elif isinstance(case.pattern, VariantPattern):
                if case.pattern.variant in seen:
                    raise self._error(f"duplicate case {case.pattern.variant}", case.pattern)
                seen.add(case.pattern.variant)
                if expected is not None and case.pattern.variant not in expected:
                    missing_case = case.pattern.variant
                    raise self._error(
                        f"unknown case(s) for sum type {type_name}: {missing_case} (unexpected case {missing_case} for type {type_name})",
                        case.pattern,
                    )

        if expected is not None and not has_wildcard:
            missing = expected - seen
            if missing:
                missing_list = ", ".join(sorted(missing))
                raise self._error(
                    f"non-exhaustive match for {type_name}: missing {missing_list} (missing cases: {missing_list})",
                    m,
                    hint="Add the missing branches or a trailing '_' catch-all case.",
                )

        for case in m.cases:
            pattern = case.pattern
            if isinstance(pattern, WildcardPattern):
                branch_env = Environment(parent=env, namespace=env.namespace, runtime=self)
                if pattern.name:
                    branch_env.define(pattern.name, value, pattern.pos)
                return self.eval_expr(case.body, branch_env)

            if isinstance(pattern, VariantPattern) and pattern.variant == tag:
                branch_env = Environment(parent=env, namespace=env.namespace, runtime=self)
                if pattern.positional_bindings:
                    # Map positional bindings onto the declared variant fields so
                    # ``case Circle(r) =>`` can bind ``r`` to the first field of
                    # ``Circle`` without requiring explicit ``field: value``
                    # syntax in the pattern.
                    field_order: List[str] = []
                    if variants and pattern.variant in variants:
                        field_order = list(variants[pattern.variant].keys())
                    elif isinstance(value, dict):
                        field_order = [k for k in value.keys() if k not in {"__tag__", "__type__"}]
                    if not field_order:
                        raise self._error(
                            f"cannot bind positional pattern for {pattern.variant} without type information",
                            pattern,
                        )
                    if len(pattern.positional_bindings) > len(field_order):
                        raise self._error(
                            f"positional pattern for {pattern.variant} has too many fields",
                            pattern,
                        )
                    for idx, bind in enumerate(pattern.positional_bindings):
                        if not bind:
                            continue
                        fname = field_order[idx]
                        if not isinstance(value, dict) or fname not in value:
                            raise self._error(f"field {fname} missing for variant {pattern.variant}", pattern)
                        branch_env.define(bind, value[fname], pattern.pos)
                for fname, bind in pattern.bindings.items():
                    if not isinstance(value, dict) or fname not in value:
                        raise self._error(f"field {fname} missing for variant {pattern.variant}", pattern)
                    if bind:
                        branch_env.define(bind, value[fname], pattern.pos)
                return self.eval_expr(case.body, branch_env)

        raise self._error(f"non-exhaustive match for tag {tag}", m)

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
        parent_env = self.global_env
        if fn.namespace and fn.namespace in self.namespace_envs:
            parent_env = self.namespace_envs[fn.namespace]
        call_env = Environment(parent=parent_env, namespace=fn.namespace, runtime=self)
        param_bindings = self._bind_parameters_to_env(
            fn.params,
            args,
            call_env,
            escaped_params=getattr(fn, "return_param_names", set()),
            pos=fn.pos,
            type_label=f"function {fn.name}",
        )
        frame = StackFrame(fn.name, fn.namespace, fn.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = fn.namespace or prev_namespace
        self._push_parameter_scope(param_bindings)
        try:
            res = self.eval_block(fn.body, call_env, fn.namespace)
            if isinstance(res, ReturnSignal):
                value = res.value
                if fn.return_type:
                    self._enforce_annotation(fn.return_type, value, label=f"return value for function {fn.name}", pos=fn.pos)
                else:
                    self._enforce_inferred_return(fn, value, label=f"function {fn.name}", pos=fn.pos)
                return value
            if fn.return_type:
                self._enforce_annotation(fn.return_type, res, label=f"return value for function {fn.name}", pos=fn.pos)
            else:
                self._enforce_inferred_return(fn, res, label=f"function {fn.name}", pos=fn.pos)
            return res
        except TinyLangError as err:
            raise self._ensure_error_has_stack(err) from err
        finally:
            self._pop_parameter_scope()
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

    def _start_task(self, fn: Fn, args: List[Any]) -> SpawnHandle:
        done = threading.Event()
        cancelled = threading.Event()
        placeholder_thread = threading.Thread(target=lambda: None)
        handle = SpawnHandle(thread=placeholder_thread, done=done, cancelled=cancelled)

        def run_task() -> None:
            self._run_spawn(fn, args, handle)

        worker = threading.Thread(target=run_task)
        handle.thread = worker
        worker.start()
        self._register_task_handle(handle)
        return handle

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

    def make_cancellation_token(self) -> CancellationToken:
        return CancellationToken()

    def cancel_token(self, token: Any, reason: Optional[str] = None) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("cancel_token expects a cancellation token")
        return token.cancel(reason)

    def token_cancelled(self, token: Any) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("token_cancelled expects a cancellation token")
        return token.cancelled.is_set()

    def token_reason(self, token: Any) -> Optional[str]:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("token_reason expects a cancellation token")
        return token.reason

    def link_token(self, token: Any, handle: Any) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("link_token expects a cancellation token")
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("link_token expects a spawn handle")
        return token.link_handle(handle)

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
        env = Environment(parent=self.global_env, runtime=self)
        self_value: Any = target_obj
        if md.class_name != cname:
            self_value = BaseView(target_obj, md.class_name)
        method_args = [self_value] + args
        forced_escape = {md.params[0].name} if md.params else set()
        param_bindings = self._bind_parameters_to_env(
            md.params,
            method_args,
            env,
            escaped_params=getattr(md, "return_param_names", set()),
            pos=md.pos,
            type_label=f"method {md.class_name}.{md.name}",
            force_escaped=forced_escape,
        )
        for base in self.class_mro(cname)[1:]:
            env.define(base, BaseView(target_obj, base), md.pos)
        frame = StackFrame(f"{md.class_name}.{md.name}", md.namespace, md.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = md.namespace or prev_namespace
        self._push_parameter_scope(param_bindings)
        try:
            res = self.eval_block(md.body, env)
            if isinstance(res, ReturnSignal):
                value = res.value
                if md.return_type:
                    self._enforce_annotation(md.return_type, value, label=f"return value for method {md.class_name}.{md.name}", pos=md.pos)
                else:
                    self._enforce_inferred_return(md, value, label=f"method {md.class_name}.{md.name}", pos=md.pos)
                return value
            if md.return_type:
                self._enforce_annotation(md.return_type, res, label=f"return value for method {md.class_name}.{md.name}", pos=md.pos)
            else:
                self._enforce_inferred_return(md, res, label=f"method {md.class_name}.{md.name}", pos=md.pos)
            return res
        except TinyLangError as err:
            raise self._ensure_error_has_stack(err) from err
        finally:
            self._pop_parameter_scope()
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
        variants = t.get("variants") or ({tname: t.get("fields", {})} if t.get("fields") is not None else {})
        if owner_hint:
            return variants.get(owner_hint, {}).get(field_name)
        if len(variants) == 1:
            return next(iter(variants.values())).get(field_name)
        hits = [fields.get(field_name) for fields in variants.values() if field_name in fields]
        if len(hits) == 1:
            return hits[0]
        return None

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

    

# --- segment: tiny_language_eval.py ---

# ----- Evaluation -----
# AST evaluator that executes statements against the runtime environment.
#
# These helpers interpret TinyLanguage IR directly, handling control flow,
# function calls, heap operations, and async primitives. They are stitched
# into the original monolithic interpreter so other modules can share the
# same execution semantics.

from typing import Any, List, Optional, Union

if "IR" not in globals():
    from tiny_language_ast import (
        Assign,
        Await,
        Bin,
        Bool,
        Call,
        CallStmt,
        ClassDef,
        ClassNew,
        DestructAssign,
        Field,
        FieldAssign,
        Flush,
        Fn,
        If,
        Import,
        IR,
        Let,
        Match,
        MethodCall,
        MethodDef,
        Namespace,
        New,
        NewLit,
        Null,
        Num,
        ObjLit,
        OpDef,
        Print,
        Return,
        Spawn,
        Str,
        Switch,
        TaskBlock,
        TryCatch,
        TypeDef,
        Var,
        VariantCtor,
        While,
    )

if "Runtime" not in globals():
    from tiny_language_runtime import NamespaceRef, ReturnSignal, Runtime

if "TinyLangError" not in globals():
    from tiny_language_preamble import TinyLangError

if "SourcePos" not in globals():
    from tiny_errors import SourcePos, SourceSpan

def _span_or_pos(node: IR) -> Union[SourcePos, SourceSpan]:
    span = getattr(node, "span", None)
    if span is not None:
        return span
    return getattr(node, "pos", SourcePos.origin())


def _prefer_named_span(node: IR, attr: str) -> Union[SourcePos, SourceSpan]:
    span = getattr(node, attr, None)
    if span is not None:
        return span
    return _span_or_pos(node)


def _return_type_is_void(annotation: Optional[str]) -> bool:
    if annotation is None:
        return False
    normalized = annotation.strip().lower()
    return normalized in {"null", "null?"}


def _block_returns_value(stmts: List[IR]) -> bool:
    for st in stmts:
        if isinstance(st, Return):
            return not isinstance(st.expr, Null)
        if isinstance(st, If):
            if _block_returns_value(st.then) or _block_returns_value(st.els):
                return True
        elif isinstance(st, While):
            if _block_returns_value(st.body):
                return True
        elif isinstance(st, Switch):
            for case in st.cases:
                if _block_returns_value(case.body):
                    return True
        elif isinstance(st, TryCatch):
            if _block_returns_value(st.body) or _block_returns_value(st.handler):
                return True
        elif isinstance(st, TaskBlock):
            if _block_returns_value(st.body):
                return True
    return False


def _fn_returns_value(fn: Fn) -> bool:
    if fn.return_type is not None:
        return not _return_type_is_void(fn.return_type)
    return _block_returns_value(fn.body)


_ALLOWED_CALL_PREFIXES = (
    "Collections.",
    "Map.",
    "Set.",
    "Deque.",
    "Async.",
    "Result.",
    "String.",
    "Console.",
    "File.",
    "JSON.",
    "Python.",
    "Random.",
)


def _call_stmt_allowed(name: str) -> bool:
    if name in {"heap_set", "heap_get", "delete", "tag", "join", "parse_program"}:
        return True
    return name.startswith(_ALLOWED_CALL_PREFIXES)

def eval_block(self, stmts: List[IR], env: "Environment", namespace: Optional[str] = None) -> Any:
    for st in stmts:
        res = self.eval_stmt(st, env, namespace)
        if isinstance(res, ReturnSignal):
            return res
    return None

def eval_stmt(self, s: IR, env: "Environment", namespace: Optional[str] = None) -> Any:
    self._maybe_pause(s, env, namespace)
    try:
        if isinstance(s, Let):
            env.define(s.name, self.eval_expr(s.expr, env), _prefer_named_span(s, "name_span"))
        elif isinstance(s, Assign):
            value = self.eval_expr(s.expr, env)
            if env.contains(s.name):
                env.assign(s.name, value, _prefer_named_span(s, "name_span"))
            else:
                env.define(s.name, value, _prefer_named_span(s, "name_span"))
        elif isinstance(s, FieldAssign):
            obj = self.eval_expr(s.obj, env)
            val = self.eval_expr(s.expr, env)
            self.field_set(obj, s.name, val, pos=_span_or_pos(s))
        elif isinstance(s, Print):
            vals = [self.eval_expr(expr, env) for expr in s.exprs]
            text = " ".join(self.format_value(v) for v in vals)
            with self._lock:
                self.output.append(f"{text}\n")
                mirror_stdout = bool(getattr(self.debugger, "mirror_stdout", False))
                trace_to_stdout = bool(getattr(self, "trace_to_stdout", False))
                if self.stream_output or mirror_stdout or trace_to_stdout:
                    import sys

                    sys.stdout.write(f"{text}\n")
                    sys.stdout.flush()
                    self.streamed_output = True
                else:
                    self._emit_output_to_debugger()
        elif isinstance(s, Flush):
            self.flush_streams()
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
        elif isinstance(s, Switch):
            target = self.eval_expr(s.expr, env)
            default_case = None
            matched = False
            for case in s.cases:
                if case.value is None:
                    default_case = case
                    continue
                case_value = self.eval_expr(case.value, env)
                is_match = self._Runtime__binop("==", target, case_value)
                if self._is_truthy(is_match):
                    matched = True
                    res = self.eval_block(case.body, env, namespace)
                    if isinstance(res, ReturnSignal):
                        return res
                    break
            if not matched and default_case is not None:
                res = self.eval_block(default_case.body, env, namespace)
                if isinstance(res, ReturnSignal):
                    return res
        elif isinstance(s, TryCatch):
            try:
                res = self.eval_block(s.body, env, namespace)
                if isinstance(res, ReturnSignal):
                    return res
            except TinyLangError as err:
                if s.err_name:
                    env.define(s.err_name, self._error_value(self._ensure_error_has_stack(err)), s.pos)
                res = self.eval_block(s.handler, env, namespace)
                if isinstance(res, ReturnSignal):
                    return res
        elif isinstance(s, TaskBlock):
            res = None
            err: Optional[BaseException] = None
            self._push_task_scope()
            try:
                res = self.eval_block(s.body, env, namespace)
            except Exception as exc:  # noqa: BLE001
                err = exc
            finally:
                try:
                    self._pop_task_scope()
                except Exception as cleanup_exc:  # noqa: BLE001
                    if err is None:
                        raise
                    raise err from cleanup_exc
            if err is not None:
                raise err
            if isinstance(res, ReturnSignal):
                return res
        elif isinstance(s, Namespace):
            qualified = self._qualify_name(s.name, namespace)
            child_env = Environment(parent=env, namespace=qualified, runtime=self)
            env.define(s.name, NamespaceRef(self, qualified), _span_or_pos(s))
            self.namespace_envs[qualified] = child_env
            self.eval_block(s.body, child_env, qualified)
        elif isinstance(s, Import):
            binding = _import_binding_name(s.module, s.alias)
            ns_ref = self.module_resolver.import_module(
                s.module,
                self,
                caller_namespace=namespace or env.namespace,
                caller_path=self.current_module_path,
                pos=_prefer_named_span(s, "module_span"),
            )
            env.define(binding, ns_ref, _prefer_named_span(s, "binding_span"))
        elif isinstance(s, Fn):
            s.namespace = namespace
            fn_name = self._qualify_name(s.name, namespace)
            with self._lock:
                self.functions[fn_name] = s
        elif isinstance(s, Return):
            return ReturnSignal(self.eval_expr(s.expr, env))
        elif isinstance(s, CallStmt):
            allowed = _call_stmt_allowed(s.name)
            if not allowed:
                _, fn = self._resolve_function(s.name, env)
                if fn is not None and not _fn_returns_value(fn):
                    self.eval_expr(Call(s.name, s.args, pos=s.pos), env)
                    return None
                raise RuntimeError(
                    f"call with return value must be bound; bare call statements are not allowed (offending call: {s.name}())"
                )
            self.eval_expr(Call(s.name, s.args, pos=s.pos), env)
        elif isinstance(s, OpDef):
            self.register_operator(s, env)
        elif isinstance(s, DestructAssign):
            val = self.eval_expr(s.expr, env)
            for nm, span in zip(s.names, s.name_spans or []):
                extracted = val[str(nm)]
                pos = span or _span_or_pos(s)
                if env.contains(nm):
                    env.assign(nm, extracted, pos)
                else:
                    env.define(nm, extracted, pos)
        elif isinstance(s, TypeDef):
            self.register_type(s.name, s.fields, s.variants)
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
        raise self._error(str(exc), s) from exc

def eval_expr(self, e: IR, env: "Environment") -> Any:
    try:
        if isinstance(e, Num):
            if "." in e.txt or "e" in e.txt or "E" in e.txt:
                value = float(e.txt)
                if ("e" in e.txt or "E" in e.txt) and "." not in e.txt and value.is_integer():
                    return int(value)
                return value
            return int(e.txt)
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
                e,
                candidates=env.all_names(),
            )
        if isinstance(e, Call):
            if e.name == "flush":
                if e.args:
                    raise RuntimeError("flush expects no arguments")
                self.flush_streams()
                return None
            if e.name == "__type_field_type":
                return self.type_field_type(str(self.eval_expr(e.args[0], env)), str(self.eval_expr(e.args[1], env)))
            if e.name == "__new":
                return self._Runtime__new(int(self.eval_expr(e.args[0], env)))
            if e.name == "new":
                return self._Runtime__new(int(self.eval_expr(e.args[0], env)))
            if e.name == "heap_get":
                return self.heap_get(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env), pos=e)
            if e.name == "heap_set":
                return self.heap_set(
                    self.eval_expr(e.args[0], env),
                    self.eval_expr(e.args[1], env),
                    self.eval_expr(e.args[2], env),
                    pos=e,
                )
            if e.name == "delete":
                return self.delete(self.eval_expr(e.args[0], env), pos=e)
            if e.name == "tag":
                return self.tag(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env), pos=e)
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
                if fn.is_async:
                    return self._start_task(fn, arg_values)
                return self._invoke_function(fn, arg_values)
            raise RuntimeError(f"unknown function {e.name}")
        if isinstance(e, Spawn):
            resolved_name, fn = self._resolve_function(e.name, env)
            if fn is None:
                raise RuntimeError(f"unknown function {e.name}")
            arg_values = [self.eval_expr(arg, env) for arg in e.args]
            return self._start_task(fn, arg_values)
        if isinstance(e, Await):
            handle = self.eval_expr(e.expr, env)
            return self.join_handle(handle)
        if isinstance(e, New):
            return self._Runtime__new(int(self.eval_expr(e.size, env)))
        if isinstance(e, NewLit):
            p = self._Runtime__new(len(e.items))
            for idx, item in enumerate(e.items):
                self.heap_set(p, idx, self.eval_expr(item, env), pos=e)
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
            return self._Runtime__binop(e.op, self.eval_expr(e.a, env), self.eval_expr(e.b, env))
        if isinstance(e, ObjLit):
            obj: Dict[str, Any] = {"__tag__": "Struct"}
            for k, v in e.fields:
                obj[k] = self.eval_expr(v, env)
            return obj
        if isinstance(e, VariantCtor):
            init = {k: self.eval_expr(v, env) for k, v in e.fields}
            return self.instantiate_variant(e.variant, init, type_name=e.type_name, pos=e)
        if isinstance(e, Match):
            val = self.eval_expr(e.expr, env)
            return self.eval_match(e, val, env)
        if isinstance(e, Field):
            obj = self.eval_expr(e.obj, env)
            return self.field_get(obj, e.name, pos=e)
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
        raise self._error(str(exc), e) from exc


Runtime.eval_block = eval_block
Runtime.eval_stmt = eval_stmt
Runtime.eval_expr = eval_expr


class Environment:
    def __init__(
        self, parent: Optional["Environment"], namespace: Optional[str] = None, runtime: Optional["Runtime"] = None
    ):
        self.parent = parent  # Outer lexical scope (if any)
        self.namespace = namespace  # Module/namespace name for namespacing lookups
        self.runtime = runtime or (parent.runtime if parent else None)
        self.values: Dict[str, Any] = {}  # Local symbol table
        self.types: Dict[str, str] = {}

    @staticmethod
    def _fallback_type_name(value: Any) -> str:
        if isinstance(value, dict) and "__type__" in value:
            return str(value.get("__type__"))
        if value is None:
            return "Null"
        if isinstance(value, bool):
            return "Bool"
        if isinstance(value, int) and not isinstance(value, bool):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "string"
        return type(value).__name__

    @staticmethod
    def _normalize_numeric_type(type_name: str) -> str:
        return type_name

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise RuntimeError(f"unknown variable {name}")

    def define(self, name: str, value: Any, pos: Union[SourcePos, SourceSpan]) -> None:
        if self.runtime:
            inferred = self.runtime._infer_type_name(value)
            self.types[name] = self._normalize_numeric_type(inferred)
        else:
            self.types[name] = self._fallback_type_name(value)
        self.values[name] = value

    def assign(self, name: str, value: Any, pos: Union[SourcePos, SourceSpan]) -> None:
        if name in self.values:
            if self.runtime:
                self.runtime._check_assignment_type(self, name, value, pos, local_only=True)
                inferred = self.runtime._infer_type_name(value)
                self.types[name] = self._normalize_numeric_type(inferred)
            else:
                self.types[name] = self._fallback_type_name(value)
            self.values[name] = value
        elif self.parent is not None:
            self.parent.assign(name, value, pos)
        else:
            self.define(name, value, pos)

    def contains(self, name: str) -> bool:
        if name in self.values:
            return True
        return self.parent.contains(name) if self.parent else False

    def type_of(self, name: str, *, local_only: bool = False) -> Optional[str]:
        if name in self.types:
            return self.types[name]
        if not local_only and self.parent is not None:
            return self.parent.type_of(name)
        return None

    def all_names(self) -> List[str]:
        names = list(self.values.keys())  # Start with current scope names
        if self.parent:
            names.extend(self.parent.all_names())  # Include ancestors
        return names

# --- segment: tiny_language_api.py ---
"""Convenience entrypoints for running, compiling, and interacting with TinyLanguage.

This module intentionally collects the most user-facing helpers so external callers
can import a single module when driving the interpreter, native backends, or the
REPL. Functions here prefer descriptive error messages over raw tracebacks and try
to keep a small, ergonomic surface area.
"""

# ----- Public API -----

import ast
import ctypes
import importlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from native_ir import FunctionIR, Instruction, Opcode, ProgramIR
from native_vm import NamespaceRef as NativeNamespaceRef, NativeVM
from native_python_bytecode import run_program_via_python_bytecode
from stdlib import register_stdlib
from tiny_errors import SourcePos, SourceSpan
from tiny_language_codegen_c import CCodeGenerator
from tiny_language_codegen_llvm import LLVMCodeGenerator
from tiny_language_highlighting import PYGMENTS_AVAILABLE, highlight_source

if "IR" not in globals():
    from tiny_language_ast import (
        Await,
        Bin,
        Bool,
        Call,
        CallStmt,
        ClassDef,
        ClassNew,
        DestructAssign,
        Field,
        FieldAssign,
        Flush,
        Fn,
        If,
        Import,
        IR,
        Let,
        Match,
        MatchCase,
        MethodCall,
        MethodDef,
        Namespace,
        New,
        NewLit,
        Null,
        Num,
        ObjLit,
        OpDef,
        Param,
        Print,
        Return,
        Spawn,
        Str,
        Switch,
        SwitchCase,
        TaskBlock,
        TryCatch,
        TypeDef,
        TypeVariant,
        Var,
        VariantCtor,
        VariantPattern,
        While,
        WildcardPattern,
    )

if "Environment" not in globals():
    from tiny_language_eval import Environment

if "Lexer" not in globals():
    from tiny_language_lexer import Lexer

if "Parser" not in globals():
    from tiny_language_parser import Parser

if "Runtime" not in globals():
    from tiny_language_runtime import Debugger, ModuleResolver, NamespaceRef, Runtime

if "TinyLangError" not in globals():
    from tiny_language_preamble import BUILTINS, KEYWORDS, TinyLangError, format_error

if "lint_import_style" not in globals():
    from tiny_language_linter import (
        _collect_function_signatures,
        lint_assignment_types,
        lint_bare_call_results,
        lint_destruct_call_outputs,
        lint_fn_params_used,
        lint_import_style,
        lint_locals_used,
        lint_method_params_used,
        lint_no_consecutive_definitions,
        lint_no_underscore_bindings,
        lint_unreachable_code,
    )

if "PythonCodeGenerator" not in globals():
    from tiny_language_codegen_py import PythonCodeGenerator

if "NativeCodeGenerator" not in globals():
    from tiny_language_codegen_native import NativeCodeGenerator


def _copy_on_call_default() -> bool:
    env_flag = os.environ.get("TINYLANG_COPY_ON_CALL", "").strip().lower()
    return env_flag in {"1", "true", "yes", "on"}


def _use_tiny_parser(preferred: Optional[bool] = None) -> bool:
    if preferred is not None:
        return preferred
    env_flag = os.environ.get("TINYLANG_USE_TINY_PARSER", "").strip().lower()
    return env_flag in {"1", "true", "yes", "on"}


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "src_tiny").is_dir():
            return parent
    raise FileNotFoundError("unable to locate src_tiny directory for TinyLanguage parser bootstrap")


@lru_cache(maxsize=1)
def _tiny_parser_bootstrap_source() -> str:
    root = _find_repo_root(Path(__file__).resolve())
    tiny_root = root / "src_tiny"
    ast_src = (tiny_root / "tiny_language_ast.tiny").read_text(encoding="utf-8")
    lexer_src = (tiny_root / "tiny_language_lexer.tiny").read_text(encoding="utf-8")
    parser_src = (tiny_root / "tiny_language_parser.tiny").read_text(encoding="utf-8")
    return "\n\n".join([ast_src, lexer_src, parser_src])


def _tiny_heap_value(runtime: "Runtime", value: object) -> object:
    if isinstance(value, int) and value in runtime.heap:
        return runtime.heap[value]
    return value


def _tiny_get_field(runtime: "Runtime", obj: object, name: str) -> object:
    if isinstance(obj, dict):
        fields = obj.get("__fields__")
        if isinstance(fields, dict):
            for field_map in fields.values():
                if name in field_map:
                    return field_map[name]
        if name in obj:
            return obj[name]
    return None


def _tiny_to_pos(runtime: "Runtime", value: object) -> SourcePos:
    if isinstance(value, SourcePos):
        return value
    if isinstance(value, dict) and value.get("__tag__") == "SourcePos":
        line = _tiny_get_field(runtime, value, "line")
        column = _tiny_get_field(runtime, value, "column")
        return SourcePos(int(line or 1), int(column or 1))
    return SourcePos.origin()


def _tiny_to_span(runtime: "Runtime", value: object) -> Optional[SourceSpan]:
    if value is None:
        return None
    if isinstance(value, SourceSpan):
        return value
    if isinstance(value, dict) and value.get("__tag__") == "SourceSpan":
        start = _tiny_to_pos(runtime, _tiny_get_field(runtime, value, "start"))
        stop = _tiny_to_pos(runtime, _tiny_get_field(runtime, value, "stop"))
        return SourceSpan(start, stop)
    return None


def _tiny_to_list(runtime: "Runtime", value: object) -> List[object]:
    if value is None:
        return []
    resolved = _tiny_heap_value(runtime, value)
    if isinstance(resolved, list):
        return list(resolved)
    if isinstance(resolved, tuple):
        return list(resolved)
    return []


def _tiny_to_set(runtime: "Runtime", value: object) -> set:
    if value is None:
        return set()
    resolved = _tiny_heap_value(runtime, value)
    if isinstance(resolved, set):
        return set(resolved)
    if isinstance(resolved, list):
        return set(resolved)
    return set()


def _tiny_to_dict(runtime: "Runtime", value: object) -> dict:
    if value is None:
        return {}
    resolved = _tiny_heap_value(runtime, value)
    if isinstance(resolved, dict):
        return dict(resolved)
    return {}


def _tiny_to_pairs(runtime: "Runtime", value: object, value_converter: Callable[[object], object]) -> List[tuple]:
    pairs = []
    for entry in _tiny_to_list(runtime, value):
        resolved = _tiny_heap_value(runtime, entry)
        if isinstance(resolved, list) and len(resolved) == 2:
            pairs.append((resolved[0], value_converter(resolved[1])))
    return pairs


def _tiny_to_python_ast(runtime: "Runtime", node: object) -> object:
    if isinstance(node, IR):
        return node
    if not isinstance(node, dict) or "__tag__" not in node:
        return node

    tag = node["__tag__"]
    span = _tiny_to_span(runtime, _tiny_get_field(runtime, node, "span"))

    def apply_span(obj: IR) -> IR:
        if span is not None:
            obj.span = span
        return obj

    if tag == "Let":
        name = _tiny_get_field(runtime, node, "name")
        expr = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "expr"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        name_span = _tiny_to_span(runtime, _tiny_get_field(runtime, node, "name_span"))
        return apply_span(Let(name, expr, pos=pos, name_span=name_span))
    if tag == "Assign":
        name = _tiny_get_field(runtime, node, "name")
        expr = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "expr"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        name_span = _tiny_to_span(runtime, _tiny_get_field(runtime, node, "name_span"))
        return apply_span(Assign(name, expr, pos=pos, name_span=name_span))
    if tag == "FieldAssign":
        obj = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "obj"))
        name = _tiny_get_field(runtime, node, "name")
        expr = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "expr"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(FieldAssign(obj, name, expr, pos=pos))
    if tag == "Print":
        exprs = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "exprs"))]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Print(exprs, pos=pos))
    if tag == "Flush":
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Flush(pos=pos))
    if tag == "If":
        cond = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "cond"))
        then = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "then"))]
        els = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "els"))]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(If(cond, then, els, pos=pos))
    if tag == "While":
        cond = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "cond"))
        body = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "body"))]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(While(cond, body, pos=pos))
    if tag == "Switch":
        expr = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "expr"))
        cases = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "cases"))
        ]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Switch(expr, cases, pos=pos))
    if tag == "TryCatch":
        body = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "body"))]
        handler = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "handler"))
        ]
        err_name = _tiny_get_field(runtime, node, "err_name")
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(TryCatch(body, err_name, handler, pos=pos))
    if tag == "TaskBlock":
        body = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "body"))]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(TaskBlock(body, pos=pos))
    if tag == "Param":
        name = _tiny_get_field(runtime, node, "name")
        type_hint = _tiny_get_field(runtime, node, "type_hint")
        return Param(name, type_hint or None)
    if tag == "Fn":
        name = _tiny_get_field(runtime, node, "name")
        params = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "params"))
        ]
        body = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "body"))]
        return_params = _tiny_to_set(runtime, _tiny_get_field(runtime, node, "return_param_names"))
        namespace = _tiny_get_field(runtime, node, "namespace_name") or None
        return_type = _tiny_get_field(runtime, node, "return_type") or None
        inferred_return_type = _tiny_get_field(runtime, node, "inferred_return_type") or None
        is_async = bool(_tiny_get_field(runtime, node, "is_async"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(
            Fn(
                name,
                params,
                body,
                return_param_names=set(return_params),
                namespace=namespace,
                return_type=return_type,
                inferred_return_type=inferred_return_type,
                is_async=is_async,
                pos=pos,
            )
        )
    if tag == "MethodDef":
        class_name = _tiny_get_field(runtime, node, "class_name")
        name = _tiny_get_field(runtime, node, "name")
        params = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "params"))
        ]
        body = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "body"))]
        return_params = _tiny_to_set(runtime, _tiny_get_field(runtime, node, "return_param_names"))
        return_type = _tiny_get_field(runtime, node, "return_type") or None
        inferred_return_type = _tiny_get_field(runtime, node, "inferred_return_type") or None
        namespace = _tiny_get_field(runtime, node, "namespace_name") or None
        is_async = bool(_tiny_get_field(runtime, node, "is_async"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(
            MethodDef(
                class_name,
                name,
                params,
                body,
                return_param_names=set(return_params),
                return_type=return_type,
                inferred_return_type=inferred_return_type,
                namespace=namespace,
                is_async=is_async,
                pos=pos,
            )
        )
    if tag == "Namespace":
        name = _tiny_get_field(runtime, node, "name")
        body = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "body"))]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Namespace(name, body, pos=pos))
    if tag == "Return":
        expr = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "expr"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Return(expr, pos=pos))
    if tag == "Import":
        module = _tiny_get_field(runtime, node, "module")
        alias = _tiny_get_field(runtime, node, "alias") or None
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        module_span = _tiny_to_span(runtime, _tiny_get_field(runtime, node, "module_span"))
        binding_span = _tiny_to_span(runtime, _tiny_get_field(runtime, node, "binding_span"))
        return apply_span(
            Import(module, alias, pos=pos, module_span=module_span, binding_span=binding_span)
        )
    if tag == "CallStmt":
        name = _tiny_get_field(runtime, node, "name")
        args = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "args"))
        ]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(CallStmt(name, args, pos=pos))
    if tag == "OpDef":
        op = _tiny_get_field(runtime, node, "op")
        a_name = _tiny_get_field(runtime, node, "a_name")
        a_type = _tiny_get_field(runtime, node, "a_type")
        b_name = _tiny_get_field(runtime, node, "b_name")
        b_type = _tiny_get_field(runtime, node, "b_type")
        body = [_tiny_to_python_ast(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "body"))]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(OpDef(op, a_name, a_type, b_name, b_type, body, pos=pos))
    if tag == "DestructAssign":
        names = [item for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "names"))]
        expr = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "expr"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        name_spans = [
            _tiny_to_span(runtime, item) for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "name_spans"))
        ]
        return apply_span(DestructAssign(names, expr, pos=pos, name_spans=[ns for ns in name_spans if ns is not None]))
    if tag == "TypeVariant":
        name = _tiny_get_field(runtime, node, "name")
        fields = _tiny_to_pairs(runtime, _tiny_get_field(runtime, node, "fields"), lambda v: v)
        return TypeVariant(name, fields)
    if tag == "TypeDef":
        name = _tiny_get_field(runtime, node, "name")
        fields_value = _tiny_get_field(runtime, node, "fields")
        variants_value = _tiny_get_field(runtime, node, "variants")
        fields = (
            _tiny_to_pairs(runtime, fields_value, lambda v: v)
            if fields_value is not None
            else None
        )
        variants = (
            [
                _tiny_to_python_ast(runtime, item)
                for item in _tiny_to_list(runtime, variants_value)
            ]
            if variants_value is not None
            else None
        )
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(TypeDef(name, fields=fields, variants=variants, pos=pos))
    if tag == "ClassDef":
        name = _tiny_get_field(runtime, node, "name")
        fields = _tiny_to_pairs(runtime, _tiny_get_field(runtime, node, "fields"), lambda v: v)
        methods = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "methods"))
        ]
        bases = [item for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "bases"))]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(ClassDef(name, fields, methods, bases, pos=pos))
    if tag == "Num":
        txt = _tiny_get_field(runtime, node, "txt")
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Num(txt, pos=pos))
    if tag == "Str":
        txt = _tiny_get_field(runtime, node, "txt")
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Str(txt, pos=pos))
    if tag == "Bool":
        value = bool(_tiny_get_field(runtime, node, "value"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Bool(value, pos=pos))
    if tag == "NullLit":
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Null(pos=pos))
    if tag == "Var":
        name = _tiny_get_field(runtime, node, "name")
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Var(name, pos=pos))
    if tag == "Call":
        name = _tiny_get_field(runtime, node, "name")
        args = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "args"))
        ]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Call(name, args, pos=pos))
    if tag == "Spawn":
        name = _tiny_get_field(runtime, node, "name")
        args = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "args"))
        ]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Spawn(name, args, pos=pos))
    if tag == "Await":
        expr = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "expr"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Await(expr, pos=pos))
    if tag == "New":
        size = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "size"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(New(size, pos=pos))
    if tag == "NewLit":
        items = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "items"))
        ]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(NewLit(items, pos=pos))
    if tag == "Bin":
        op = _tiny_get_field(runtime, node, "op")
        a = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "a"))
        b = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "b"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Bin(op, a, b, pos=pos))
    if tag == "ObjLit":
        fields = _tiny_to_pairs(runtime, _tiny_get_field(runtime, node, "fields"), lambda v: _tiny_to_python_ast(runtime, v))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(ObjLit(fields, pos=pos))
    if tag == "Field":
        obj = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "obj"))
        name = _tiny_get_field(runtime, node, "name")
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Field(obj, name, pos=pos))
    if tag == "MethodCall":
        obj = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "obj"))
        name = _tiny_get_field(runtime, node, "name")
        args = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "args"))
        ]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(MethodCall(obj, name, args, pos=pos))
    if tag == "ClassNew":
        name = _tiny_get_field(runtime, node, "name")
        init = _tiny_to_pairs(runtime, _tiny_get_field(runtime, node, "init"), lambda v: _tiny_to_python_ast(runtime, v))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(ClassNew(name, init, pos=pos))
    if tag == "MatchCase":
        pattern = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "pattern"))
        body = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "body"))
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(MatchCase(pattern, body, pos=pos))
    if tag == "SwitchCase":
        value = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "value"))
        body = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "body"))
        ]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(SwitchCase(value, body, pos=pos))
    if tag == "VariantPattern":
        variant = _tiny_get_field(runtime, node, "variant")
        bindings = _tiny_to_dict(runtime, _tiny_get_field(runtime, node, "bindings"))
        positional = _tiny_get_field(runtime, node, "positional_bindings")
        positional_bindings = (
            [item for item in _tiny_to_list(runtime, positional)] if positional is not None else None
        )
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(VariantPattern(variant, bindings, positional_bindings, pos=pos))
    if tag == "WildcardPattern":
        name = _tiny_get_field(runtime, node, "name") or None
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(WildcardPattern(name, pos=pos))
    if tag == "Match":
        expr = _tiny_to_python_ast(runtime, _tiny_get_field(runtime, node, "expr"))
        cases = [
            _tiny_to_python_ast(runtime, item)
            for item in _tiny_to_list(runtime, _tiny_get_field(runtime, node, "cases"))
        ]
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(Match(expr, cases, pos=pos))
    if tag == "VariantCtor":
        variant = _tiny_get_field(runtime, node, "variant")
        fields = _tiny_to_pairs(runtime, _tiny_get_field(runtime, node, "fields"), lambda v: _tiny_to_python_ast(runtime, v))
        type_name = _tiny_get_field(runtime, node, "type_name") or None
        pos = _tiny_to_pos(runtime, _tiny_get_field(runtime, node, "pos"))
        return apply_span(VariantCtor(variant, fields, type_name=type_name, pos=pos))
    return node


def _parse_with_tiny_parser(src: str) -> List["IR"]:
    program = _tiny_parser_bootstrap_source()
    program = f"{program}\n\ndef __tiny_ast = parse_program({json.dumps(src)});\n"
    parser = Parser(Lexer(program), program)
    stmts = parser.parse()
    runtime = Runtime(program)
    runtime.stream_output = False
    runtime._check_assignment_type = lambda *args, **kwargs: None  # type: ignore[assignment]
    env = Environment(parent=None, namespace=None, runtime=runtime)
    runtime.global_env = env
    register_stdlib(runtime, env, NamespaceRef)
    for stmt in stmts:
        runtime.eval_stmt(stmt, env)
    tiny_ast = env.get("__tiny_ast")
    return [
        _tiny_to_python_ast(runtime, stmt)
        for stmt in _tiny_to_list(runtime, tiny_ast)
    ]


def _parse_and_lint(src: str, *, use_tiny_parser: Optional[bool] = None) -> List["IR"]:
    """Return a parsed program after running all linter passes.

    The helper centralizes parser creation and the sequence of lints so every entry
    point (REPL, CLI, Python/native backends) benefits from the same validation
    rules. It keeps the order aligned with the standalone linter for predictable
    diagnostics.
    """
    if _use_tiny_parser(use_tiny_parser):
        stmts = _parse_with_tiny_parser(src)
    else:
        parser = Parser(Lexer(src), src)
        stmts = parser.parse()

    lint_import_style(stmts, src)
    lint_destruct_call_outputs(stmts, src)
    lint_no_consecutive_definitions(stmts, src)
    lint_no_underscore_bindings(stmts, src)
    lint_assignment_types(stmts, src)
    lint_locals_used(stmts, src)
    lint_unreachable_code(stmts, src)
    signatures = _collect_function_signatures(stmts)

    def lint_nested(block: List["IR"]) -> None:
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
    return stmts


def _lint_message(source: str) -> Optional[str]:
    """Return the linter error message for a source string, if any."""
    try:
        _parse_and_lint(source)
    except Exception as exc:  # pragma: no cover - passthrough for Tiny linter parity
        return str(exc)
    return None


class NativeModuleResolver:
    """Resolve TinyLanguage modules for the native backend."""

    def __init__(self, search_paths: Optional[List[Path]] = None) -> None:
        env_paths = os.environ.get("TINYPATH", "")
        configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
        default_roots = [Path.cwd(), Path(__file__).parent]
        stdlib_root = Path(__file__).resolve().parents[1] / "stdlib"
        if stdlib_root.exists():
            default_roots.append(stdlib_root)
        self.search_paths: List[Path] = search_paths or configured_paths + default_roots
        self.cache: dict[Path, NativeNamespaceRef] = {}
        self._in_progress: List[Path] = []

    def _resolve_name(self, raw: str, caller_namespace: Optional[str], pos: Optional[Any]) -> str:
        pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
        leading = len(raw) - len(raw.lstrip("."))
        if leading == 0:
            return raw
        if not caller_namespace:
            raise TinyLangError(
                "relative import outside a module",
                pos_for_error or SourcePos.origin(),
                code="E008",
                span=pos if isinstance(pos, SourceSpan) else None,
            )
        base = caller_namespace.split(".")
        if leading > len(base):
            raise TinyLangError(
                "relative import traverses beyond module root",
                pos_for_error or SourcePos.origin(),
                code="E008",
                span=pos if isinstance(pos, SourceSpan) else None,
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
        vm: NativeVM,
        *,
        caller_namespace: Optional[str],
        caller_path: Optional[Path],
        pos: Optional[Any] = None,
    ) -> NativeNamespaceRef:
        resolved_name = self._resolve_name(name, caller_namespace, pos)
        pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
        for candidate in self._candidate_paths(resolved_name, caller_path):
            resolved_path = candidate.resolve()
            cached = self.cache.get(resolved_path)
            if cached is not None:
                return cached
            if resolved_path.exists():
                if resolved_path in self._in_progress:
                    raise TinyLangError(
                        f"circular import involving {resolved_path}",
                        pos_for_error or SourcePos.origin(),
                        code="E008",
                        span=pos if isinstance(pos, SourceSpan) else None,
                    )
                self._in_progress.append(resolved_path)
                try:
                    module_env: dict[str, Any] = {}
                    source = resolved_path.read_text(encoding="utf-8")
                    stmts = _parse_and_lint(source)
                    program = NativeCodeGenerator(
                        allow_heap=True,
                        allow_match=True,
                        module_namespace=resolved_name,
                        source=source,
                    ).compile_program(
                        stmts
                    )
                    vm.load_module(resolved_name, program, module_env, resolved_path)
                    ns_ref = NativeNamespaceRef(resolved_name)
                    self.cache[resolved_path] = ns_ref
                    return ns_ref
                finally:
                    self._in_progress.remove(resolved_path)
        raise TinyLangError(
            f"module '{name}' not found on search path",
            pos or SourcePos.origin(),
            code="E008",
            span=pos if isinstance(pos, SourceSpan) else None,
        )


@dataclass(frozen=True)
class LLVMModuleInfo:
    name: str
    path: Path
    program: ProgramIR


class LLVMModuleResolver:
    """Resolve TinyLanguage modules for the LLVM backend."""

    def __init__(self, search_paths: Optional[List[Path]] = None) -> None:
        env_paths = os.environ.get("TINYPATH", "")
        configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
        default_roots = [Path.cwd(), Path(__file__).parent]
        stdlib_root = Path(__file__).resolve().parents[1] / "stdlib"
        if stdlib_root.exists():
            default_roots.append(stdlib_root)
        self.search_paths: List[Path] = search_paths or configured_paths + default_roots
        self.cache: dict[Path, LLVMModuleInfo] = {}
        self._in_progress: List[Path] = []

    def _resolve_name(self, raw: str, caller_namespace: Optional[str], pos: Optional[Any]) -> str:
        pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
        leading = len(raw) - len(raw.lstrip("."))
        if leading == 0:
            return raw
        if not caller_namespace:
            raise TinyLangError(
                "relative import outside a module",
                pos_for_error or SourcePos.origin(),
                code="E008",
                span=pos if isinstance(pos, SourceSpan) else None,
            )
        base = caller_namespace.split(".")
        if leading > len(base):
            raise TinyLangError(
                "relative import traverses beyond module root",
                pos_for_error or SourcePos.origin(),
                code="E008",
                span=pos if isinstance(pos, SourceSpan) else None,
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
        *,
        caller_namespace: Optional[str],
        caller_path: Optional[Path],
        pos: Optional[Any] = None,
    ) -> LLVMModuleInfo:
        resolved_name = self._resolve_name(name, caller_namespace, pos)
        pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
        for candidate in self._candidate_paths(resolved_name, caller_path):
            resolved_path = candidate.resolve()
            cached = self.cache.get(resolved_path)
            if cached is not None:
                return cached
            if resolved_path.exists():
                if resolved_path in self._in_progress:
                    raise TinyLangError(
                        f"circular import involving {resolved_path}",
                        pos_for_error or SourcePos.origin(),
                        code="E008",
                        span=pos if isinstance(pos, SourceSpan) else None,
                    )
                self._in_progress.append(resolved_path)
                try:
                    source = resolved_path.read_text(encoding="utf-8")
                    stmts = _parse_and_lint(source)
                    for stmt in stmts:
                        if isinstance(stmt, Import):
                            self.import_module(
                                stmt.module,
                                caller_namespace=resolved_name,
                                caller_path=resolved_path,
                                pos=stmt.module_span,
                            )
                    program = NativeCodeGenerator(
                        allow_heap=True,
                        allow_match=True,
                        module_namespace=resolved_name,
                        source=source,
                    ).compile_program(stmts)
                    module_info = LLVMModuleInfo(resolved_name, resolved_path, program)
                    self.cache[resolved_path] = module_info
                    return module_info
                finally:
                    self._in_progress.remove(resolved_path)
        raise TinyLangError(
            f"module '{name}' not found on search path",
            pos or SourcePos.origin(),
            code="E008",
            span=pos if isinstance(pos, SourceSpan) else None,
        )


def compile_and_run(
    src: str,
    env: Optional[Environment] = None,
    runtime: Optional[Runtime] = None,
    *,
    module_namespace: Optional[str] = None,
    module_path: Optional[Path] = None,
    module_resolver: Optional[ModuleResolver] = None,
    debugger: Optional[Debugger] = None,
    stream_output: bool = True,
    copy_on_call: Optional[bool] = None,
) -> str:
    """Compile and execute TinyLanguage source, returning concatenated output.

    Parameters mirror the runtime's expectations so callers can opt into
    preconfigured environments, namespace tracking for imports, or custom module
    resolution strategies. Any error raised during execution is intentionally
    allowed to propagate so the caller can render it with full context.
    """
    stmts = _parse_and_lint(src)
    runtime = runtime or Runtime(src)  # Reuse an existing runtime or create a fresh one
    if copy_on_call is not None:
        runtime.copy_on_call = copy_on_call
    runtime.stream_output = stream_output
    runtime.streamed_output = False
    if debugger is not None:
        runtime.debugger = debugger
    runtime.source_map[module_namespace] = src  # Track source text for later diagnostics
    prev_source = runtime.source  # Remember previous source to restore after module execution
    runtime.source = src  # Swap in the new source for this run
    previous_path = runtime.current_module_path  # Save module bookkeeping fields
    previous_namespace = runtime.current_module_namespace
    runtime.current_module_path = module_path
    runtime.current_module_namespace = module_namespace
    if module_resolver is not None:
        runtime.module_resolver = module_resolver  # Override resolver when running imports
    runtime.output.clear()  # Reset buffered program output
    runtime.error_messages.clear()  # Reset accumulated error messages
    runtime._last_emitted_output_idx = 0  # Clear debugger streaming cursor

    env = env or Environment(parent=None, namespace=module_namespace, runtime=runtime)  # Build module environment
    if module_namespace:
        runtime.namespace_envs[module_namespace] = env  # Register namespace for imports
    runtime.global_env = env  # Keep a reference for the runtime
    register_stdlib(runtime, env, NamespaceRef)  # Expose built-in functions and types
    try:
        for st in stmts:
            runtime.eval_stmt(st, env, namespace=module_namespace)  # Evaluate each top-level stmt
    finally:
        runtime.current_module_path = previous_path  # Restore runtime context even on errors
        runtime.current_module_namespace = previous_namespace
        runtime.source = prev_source
    return "".join(runtime.output)


def run_file(path: str, *, stream_output: bool = True, copy_on_call: Optional[bool] = None) -> str:
    """Execute a TinyLanguage source file and return its printed output."""
    path_obj = Path(path)  # Accept strings or Path-like objects
    resolved = path_obj.resolve()  # Normalize to an absolute path
    try:
        rel = resolved.relative_to(Path.cwd())  # Try to derive a module namespace from cwd
        namespace = ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001
        namespace = resolved.stem  # Fall back to filename when relative resolution fails
    runtime = Runtime(path_obj.read_text(encoding="utf-8"))
    with open(path, "r", encoding="utf-8") as f:
        output = compile_and_run(
            f.read(),
            runtime=runtime,
            module_namespace=namespace,
            module_path=resolved,
            stream_output=stream_output,
            copy_on_call=copy_on_call,
        )
    if stream_output and not runtime.streamed_output:
        print(output, end="")
    return output


def _format_error_for_source(source: str, err: TinyLangError) -> str:
    """Format an error with source context when available."""
    if "(line " in err.message:
        return err.message
    location = err.span if err.span is not None else err.pos
    return format_error(source, location, err.message, code=err.code, hint=err.hint)


def compile_to_python_ast(src: str) -> ast.AST:
    """Translate TinyLanguage code into an equivalent Python ``ast.AST`` module."""
    stmts = _parse_and_lint(src)
    return PythonCodeGenerator().module_for_program(stmts)


def compile_to_python_source(src: str) -> str:
    """Compile TinyLanguage code into runnable Python source text."""
    module = compile_to_python_ast(src)
    return PythonCodeGenerator().to_source(module)


def _module_namespace_for_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(Path.cwd())
        return ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001 - fall back if relative resolution fails
        return path.stem


def _merge_llvm_programs(
    program: ProgramIR,
    modules: List[LLVMModuleInfo],
) -> tuple[ProgramIR, dict[str, str]]:
    functions = dict(program.functions)
    classes = dict(program.classes)
    types = dict(program.types)
    operator_overloads = list(program.operator_overloads)
    module_inits: dict[str, str] = {}
    for module in modules:
        init_name = f"{module.name}.__init"
        module_inits[module.name] = init_name
        init_instrs = list(module.program.entry)
        if init_instrs and init_instrs[-1].op == Opcode.RETURN:
            init_instrs = init_instrs[:-1]
        init_instrs.append(Instruction(Opcode.PUSH_CONST, 0))
        init_instrs.append(Instruction(Opcode.RETURN))
        functions[init_name] = FunctionIR(name=init_name, params=[], instructions=init_instrs)
        functions.update(module.program.functions)
        classes.update(module.program.classes)
        types.update(module.program.types)
        operator_overloads.extend(module.program.operator_overloads)
    merged = ProgramIR(
        entry=program.entry,
        functions=functions,
        classes=classes,
        types=types,
        operator_overloads=operator_overloads,
    )
    return merged, module_inits


def compile_to_llvm_ir(
    src: str,
    *,
    target_triple: Optional[str] = None,
    data_layout: Optional[str] = None,
    llvm_opt: bool = False,
    module_namespace: Optional[str] = None,
    module_path: Optional[Path] = None,
    module_resolver: Optional[LLVMModuleResolver] = None,
) -> str:
    """Emit textual LLVM IR for the subset supported by the native backend."""
    stmts = _parse_and_lint(src)
    if module_path and module_namespace is None:
        module_namespace = _module_namespace_for_path(module_path)
    resolver = module_resolver or LLVMModuleResolver()
    for stmt in stmts:
        if isinstance(stmt, Import):
            resolver.import_module(
                stmt.module,
                caller_namespace=module_namespace,
                caller_path=module_path,
                pos=stmt.module_span,
            )
    program = NativeCodeGenerator(
        allow_heap=True,
        allow_match=True,
        module_namespace=module_namespace,
        source=src,
    ).compile_program(stmts)
    modules = list(resolver.cache.values())
    if modules:
        program, module_inits = _merge_llvm_programs(program, modules)
    else:
        module_inits = {}
    llvm_ir = LLVMCodeGenerator(
        target_triple=target_triple,
        data_layout=data_layout,
        module_inits=module_inits,
        source=src,
    ).compile_program(program)
    if llvm_opt:
        llvm_ir = _optimize_llvm_ir(llvm_ir)
    return llvm_ir


def compile_to_c_source(src: str) -> str:
    """Emit C source for the subset supported by the native backend."""
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator(allow_match=False, source=src).compile_program(stmts)
    return CCodeGenerator(source=src).compile_program(program)


def compile_to_llvm_ir_via_c(
    src: str,
    *,
    compiler: str = "clang",
    extra_args: Optional[List[str]] = None,
) -> str:
    """Emit LLVM IR by translating TinyLanguage to C and invoking clang."""
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        raise RuntimeError(f"compiler '{compiler}' not found on PATH (set --compiler or install clang)")
    c_source = compile_to_c_source(src)
    with tempfile.TemporaryDirectory() as tmpdir:
        c_path = Path(tmpdir) / "tiny_program.c"
        ll_path = Path(tmpdir) / "tiny_program.ll"
        c_path.write_text(c_source, encoding="utf-8")
        cmd = [compiler_path, "-S", "-emit-llvm", str(c_path), "-o", str(ll_path)]
        if extra_args:
            cmd.extend(extra_args)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on external toolchain
            stderr = exc.stderr.strip() if exc.stderr else "unknown compiler error"
            raise RuntimeError(f"failed to emit LLVM IR via {compiler}: {stderr}") from exc
        return ll_path.read_text(encoding="utf-8")


def compile_to_llvm_bitcode_via_c(
    src: str,
    *,
    compiler: str = "clang",
    extra_args: Optional[List[str]] = None,
) -> bytes:
    """Emit LLVM bitcode by translating TinyLanguage to C and invoking clang."""
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        raise RuntimeError(f"compiler '{compiler}' not found on PATH (set --compiler or install clang)")
    c_source = compile_to_c_source(src)
    with tempfile.TemporaryDirectory() as tmpdir:
        c_path = Path(tmpdir) / "tiny_program.c"
        bc_path = Path(tmpdir) / "tiny_program.bc"
        c_path.write_text(c_source, encoding="utf-8")
        cmd = [compiler_path, "-c", "-emit-llvm", str(c_path), "-o", str(bc_path)]
        if extra_args:
            cmd.extend(extra_args)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on external toolchain
            stderr = exc.stderr.strip() if exc.stderr else "unknown compiler error"
            raise RuntimeError(f"failed to emit LLVM bitcode via {compiler}: {stderr}") from exc
        return bc_path.read_bytes()


def compile_to_c_executable(
    src: str,
    output_path: Path | str,
    *,
    compiler: str = "cc",
    extra_args: Optional[List[str]] = None,
) -> Path:
    """Compile TinyLanguage to a native executable via the C backend."""
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        raise RuntimeError(f"compiler '{compiler}' not found on PATH (set --compiler or install clang/gcc)")
    c_source = compile_to_c_source(src)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        c_path = Path(tmpdir) / "tiny_program.c"
        c_path.write_text(c_source, encoding="utf-8")
        cmd = [compiler_path, str(c_path), "-o", str(output_path)]
        args = list(extra_args) if extra_args else []
        if "-lm" not in args:
            args.append("-lm")
        cmd.extend(args)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on external toolchain
            stderr = exc.stderr.strip() if exc.stderr else "unknown compiler error"
            raise RuntimeError(f"failed to compile C executable via {compiler}: {stderr}") from exc
    return output_path


def compile_to_executable(
    src: str,
    output_path: Path | str,
    *,
    compiler: str = "clang",
    extra_args: Optional[List[str]] = None,
    target_triple: Optional[str] = None,
    data_layout: Optional[str] = None,
    llvm_opt: bool = False,
    module_namespace: Optional[str] = None,
    module_path: Optional[Path] = None,
    module_resolver: Optional[LLVMModuleResolver] = None,
) -> Path:
    """Compile TinyLanguage to a native executable via LLVM IR and a system compiler."""
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        raise RuntimeError(f"compiler '{compiler}' not found on PATH (set --compiler or install clang)")
    llvm_ir = compile_to_llvm_ir(
        src,
        target_triple=target_triple,
        data_layout=data_layout,
        llvm_opt=llvm_opt,
        module_namespace=module_namespace,
        module_path=module_path,
        module_resolver=module_resolver,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        ll_path = Path(tmpdir) / "tiny_program.ll"
        ll_path.write_text(llvm_ir, encoding="utf-8")
        cmd = [compiler_path, str(ll_path), "-o", str(output_path)]
        if extra_args:
            cmd.extend(extra_args)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover - depends on external toolchain
            stderr = exc.stderr.strip() if exc.stderr else "unknown compiler error"
            raise RuntimeError(f"failed to compile executable via {compiler}: {stderr}") from exc
    return output_path


def run_with_python_backend(src: str) -> str:
    """Execute TinyLanguage code by generating and running Python source."""
    module = compile_to_python_ast(src)
    namespace: dict = {}
    exec(compile(module, "<tiny_python_backend>", "exec"), namespace, namespace)
    return namespace["tiny_main"]()


def run_with_native_backend(
    src: str,
    *,
    module_namespace: Optional[str] = None,
    module_path: Optional[Path] = None,
    module_resolver: Optional[NativeModuleResolver] = None,
) -> str:
    """Run code through the experimental native bytecode backend and VM."""
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator(
        allow_heap=True,
        allow_match=True,
        module_namespace=module_namespace,
        source=src,
    ).compile_program(stmts)
    resolver = module_resolver or NativeModuleResolver()
    vm = NativeVM(
        module_resolver=resolver,
        module_namespace=module_namespace,
        module_path=module_path,
        source=src,
    )
    return vm.run(program)


def _load_llvmlite_binding():
    if importlib.util.find_spec("llvmlite") is None:
        raise RuntimeError("llvmlite is not installed (install it to enable the LLVM JIT backend)")
    return importlib.import_module("llvmlite.binding")


def _register_llvm_symbols(llvm_binding) -> None:
    if sys.platform == "win32":
        libc = ctypes.CDLL("msvcrt")
    else:
        llvm_binding.load_library_permanently(None)
        libc = ctypes.CDLL(None)
    llvm_binding.add_symbol("printf", ctypes.cast(libc.printf, ctypes.c_void_p).value)
    llvm_binding.add_symbol("fflush", ctypes.cast(libc.fflush, ctypes.c_void_p).value)
    llvm_binding.add_symbol("calloc", ctypes.cast(libc.calloc, ctypes.c_void_p).value)
    llvm_binding.add_symbol("free", ctypes.cast(libc.free, ctypes.c_void_p).value)
    llvm_binding.add_symbol(
        "__py_import_module", ctypes.cast(_LLVM_PYTHON_INTEROP.import_module, ctypes.c_void_p).value
    )
    llvm_binding.add_symbol(
        "__py_call", ctypes.cast(_LLVM_PYTHON_INTEROP.call, ctypes.c_void_p).value
    )


class _LLVMPythonInterop:
    def __init__(self) -> None:
        self._namespaces: dict[str, set[str]] = {}
        self._buffers: list[ctypes.Array] = []
        self.import_module = ctypes.CFUNCTYPE(ctypes.c_longlong, ctypes.c_void_p, ctypes.c_longlong)(
            self._import_module
        )
        self.call = ctypes.CFUNCTYPE(
            ctypes.c_longlong,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_longlong,
            ctypes.c_longlong,
            ctypes.c_longlong,
        )(self._call)

    def _decode_str(self, ptr: int) -> str:
        if ptr == 0:
            return ""
        value = ctypes.cast(ptr, ctypes.c_char_p).value
        if value is None:
            return ""
        return value.decode("utf-8")

    def _read_heap_list(self, ptr: int) -> list[int]:
        if ptr == 0:
            return []
        data_ptr = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_longlong))
        size = data_ptr[-1]
        if size <= 0:
            return []
        return [int(data_ptr[i]) for i in range(size)]

    def _read_allowlist(self, ptr: int) -> set[str]:
        return {self._decode_str(value) for value in self._read_heap_list(ptr) if value != 0}

    def _decode_args(self, args_ptr: int, types_ptr: int) -> list[Any]:
        raw_args = self._read_heap_list(args_ptr)
        if not raw_args:
            return []
        tags = self._read_heap_list(types_ptr) if types_ptr != 0 else []
        if len(tags) != len(raw_args):
            tags = [0] * len(raw_args)
        decoded: list[Any] = []
        for value, tag in zip(raw_args, tags):
            if tag == 1:
                decoded.append(struct.unpack("d", struct.pack("q", value))[0])
            elif tag == 2:
                decoded.append(bool(value))
            elif tag == 3:
                decoded.append(self._decode_str(value))
            else:
                decoded.append(int(value))
        return decoded

    def _import_module(self, module_ptr: int, allow_ptr: int) -> int:
        try:
            module_name = self._decode_str(module_ptr)
            allowlist = self._read_allowlist(allow_ptr)
            if module_name:
                self._namespaces.setdefault(module_name, set()).update(allowlist)
            return 0
        except Exception:
            return 0

    def _call(self, module_ptr: int, attr_ptr: int, args_ptr: int, types_ptr: int, allow_ptr: int) -> int:
        try:
            module_name = self._decode_str(module_ptr)
            attr_name = self._decode_str(attr_ptr)
            allowlist = self._read_allowlist(allow_ptr)
            if not allowlist:
                allowlist = self._namespaces.get(module_name, set())
            if allowlist and attr_name not in allowlist:
                return 0
            module = importlib.import_module(module_name)
            func = getattr(module, attr_name)
            args = self._decode_args(args_ptr, types_ptr)
            result = func(*args)
            if isinstance(result, bool):
                return int(result)
            if isinstance(result, int):
                return int(result)
            if isinstance(result, float):
                return int(result)
            if isinstance(result, str):
                buf = ctypes.create_string_buffer(result.encode("utf-8"))
                self._buffers.append(buf)
                return ctypes.cast(buf, ctypes.c_void_p).value
            return 0
        except Exception:
            return 0


_LLVM_PYTHON_INTEROP = _LLVMPythonInterop()


def _create_llvm_engine(llvm_binding, *, target_triple: Optional[str] = None):
    try:
        llvm_binding.initialize()
    except RuntimeError as exc:
        if "deprecated" not in str(exc).lower():
            raise
    llvm_binding.initialize_native_target()
    llvm_binding.initialize_native_asmprinter()
    if target_triple:
        target = llvm_binding.Target.from_triple(target_triple)
    else:
        target = llvm_binding.Target.from_default_triple()
    target_machine = target.create_target_machine()
    backing_mod = llvm_binding.parse_assembly("")
    return llvm_binding.create_mcjit_compiler(backing_mod, target_machine)


def _format_llvm_debug_context(step: str, llvm_binding=None) -> str:
    details = [f"LLVM JIT step: {step}", f"platform={sys.platform}", f"python={sys.version.split()[0]}"]
    if llvm_binding is not None:
        try:
            details.append(f"llvmlite={llvm_binding.__version__}")
        except AttributeError:
            pass
        try:
            details.append(f"triple={llvm_binding.get_default_triple()}")
        except Exception:
            pass
    return " | ".join(details)


def _raise_llvm_jit_error(step: str, exc: Exception, llvm_binding=None) -> None:
    context = _format_llvm_debug_context(step, llvm_binding)
    raise RuntimeError(f"LLVM JIT failed during {step}: {exc} ({context})") from exc


def _optimize_llvm_module(llvm_binding, module) -> None:
    pass_manager = llvm_binding.create_module_pass_manager()
    pass_manager.add_promote_memory_to_register_pass()
    pass_manager.add_instruction_combining_pass()
    pass_manager.run(module)


def _optimize_llvm_ir(llvm_ir: str) -> str:
    llvm_binding = _load_llvmlite_binding()
    module = llvm_binding.parse_assembly(llvm_ir)
    module.verify()
    _optimize_llvm_module(llvm_binding, module)
    return str(module)


class _CaptureCStdout:
    def __enter__(self) -> "_CaptureCStdout":
        self._temp = tempfile.TemporaryFile(mode="w+b")
        if sys.platform == "win32":
            import ctypes.wintypes
            import msvcrt

            self._msvcrt = ctypes.CDLL("msvcrt")
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._msvcrt._dup.argtypes = [ctypes.c_int]
            self._msvcrt._dup.restype = ctypes.c_int
            self._msvcrt._dup2.argtypes = [ctypes.c_int, ctypes.c_int]
            self._msvcrt._dup2.restype = ctypes.c_int
            self._msvcrt._close.argtypes = [ctypes.c_int]
            self._msvcrt._close.restype = ctypes.c_int
            self._msvcrt._open_osfhandle.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self._msvcrt._open_osfhandle.restype = ctypes.c_int
            self._kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
            self._kernel32.DuplicateHandle.argtypes = [
                ctypes.wintypes.HANDLE,
                ctypes.wintypes.HANDLE,
                ctypes.wintypes.HANDLE,
                ctypes.POINTER(ctypes.wintypes.HANDLE),
                ctypes.wintypes.DWORD,
                ctypes.wintypes.BOOL,
                ctypes.wintypes.DWORD,
            ]
            self._kernel32.DuplicateHandle.restype = ctypes.wintypes.BOOL
            source_handle = msvcrt.get_osfhandle(self._temp.fileno())
            current_process = self._kernel32.GetCurrentProcess()
            duplicated_handle = ctypes.wintypes.HANDLE()
            if not self._kernel32.DuplicateHandle(
                current_process,
                ctypes.wintypes.HANDLE(source_handle),
                current_process,
                ctypes.byref(duplicated_handle),
                0,
                True,
                2,
            ):
                raise OSError(ctypes.get_last_error(), "DuplicateHandle failed")
            self._temp_fd = self._msvcrt._open_osfhandle(duplicated_handle.value, os.O_RDWR)
            if self._temp_fd == -1:
                raise OSError("failed to open duplicated stdout handle")
            self._original_fd = self._msvcrt._dup(1)
            self._python_fd = os.dup(1)
            self._msvcrt._dup2(self._temp_fd, 1)
            os.dup2(self._temp.fileno(), 1)
        else:
            self._original_fd = os.dup(1)
            os.dup2(self._temp.fileno(), 1)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if sys.platform == "win32":
            os.dup2(self._python_fd, 1)
            os.close(self._python_fd)
            self._msvcrt._dup2(self._original_fd, 1)
            self._msvcrt._close(self._original_fd)
            self._msvcrt._close(self._temp_fd)
        else:
            os.dup2(self._original_fd, 1)
            os.close(self._original_fd)
        self._temp.seek(0)
        data = self._temp.read()
        self._temp.close()
        encoding = sys.stdout.encoding or "utf-8"
        self.output = data.decode(encoding, errors="replace")


def _flush_c_stdout() -> None:
    if sys.platform == "win32":
        libc = ctypes.CDLL("msvcrt")
    else:
        libc = ctypes.CDLL(None)
    libc.fflush(None)


def _resolve_llvm_target_info(
    llvm_binding, *, target_triple: Optional[str] = None, data_layout: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    resolved_triple = target_triple
    resolved_layout = data_layout
    if resolved_triple is not None and resolved_layout is not None:
        return resolved_triple, resolved_layout
    try:
        base_triple = resolved_triple or llvm_binding.get_default_triple()
        target = llvm_binding.Target.from_triple(base_triple)
        target_machine = target.create_target_machine()
        if resolved_triple is None:
            resolved_triple = target_machine.triple
        if resolved_layout is None:
            resolved_layout = str(target_machine.target_data)
    except Exception:
        return resolved_triple, resolved_layout
    return resolved_triple, resolved_layout


def run_with_llvm_jit(
    src: str,
    *,
    target_triple: Optional[str] = None,
    data_layout: Optional[str] = None,
    llvm_opt: bool = False,
) -> str:
    """Execute TinyLanguage code via the LLVM IR JIT (requires llvmlite)."""
    try:
        stmts = _parse_and_lint(src)
    except Exception as exc:
        _raise_llvm_jit_error("parse", exc)
    try:
        program = NativeCodeGenerator(allow_heap=True, allow_match=False, source=src).compile_program(stmts)
    except Exception as exc:
        _raise_llvm_jit_error("native-codegen", exc)
    try:
        llvm_binding = _load_llvmlite_binding()
    except Exception as exc:
        _raise_llvm_jit_error("llvmlite-load", exc)
    try:
        resolved_triple, resolved_layout = _resolve_llvm_target_info(
            llvm_binding,
            target_triple=target_triple,
            data_layout=data_layout,
        )
    except Exception as exc:
        _raise_llvm_jit_error("target-info", exc, llvm_binding)
    try:
        llvm_ir = LLVMCodeGenerator(
            target_triple=resolved_triple,
            data_layout=resolved_layout,
            source=src,
        ).compile_program(program)
    except Exception as exc:
        _raise_llvm_jit_error("llvm-ir-codegen", exc)
    try:
        _register_llvm_symbols(llvm_binding)
    except Exception as exc:
        _raise_llvm_jit_error("register-symbols", exc, llvm_binding)
    try:
        engine = _create_llvm_engine(llvm_binding, target_triple=resolved_triple)
    except Exception as exc:
        _raise_llvm_jit_error("create-engine", exc, llvm_binding)
    try:
        module = llvm_binding.parse_assembly(llvm_ir)
        module.verify()
    except Exception as exc:
        _raise_llvm_jit_error("verify-module", exc, llvm_binding)
    if llvm_opt:
        try:
            _optimize_llvm_module(llvm_binding, module)
        except Exception as exc:
            _raise_llvm_jit_error("optimize-module", exc, llvm_binding)
    try:
        engine.add_module(module)
        engine.finalize_object()
        engine.run_static_constructors()
    except Exception as exc:
        _raise_llvm_jit_error("finalize", exc, llvm_binding)
    func_addr = engine.get_function_address("tiny_main")
    if not func_addr:
        raise RuntimeError(
            f"LLVM JIT failed to locate tiny_main ({_format_llvm_debug_context('locate-tiny_main', llvm_binding)})"
        )
    cfunc = ctypes.CFUNCTYPE(ctypes.c_int32)(func_addr)
    with _CaptureCStdout() as capture:
        cfunc()
        _flush_c_stdout()
    if capture.output:
        print(capture.output, end="")
    return ""


def run_with_python_bytecode_backend(src: str) -> str:
    """Execute native IR by emitting Python bytecode instructions."""
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator(allow_heap=True, allow_match=False, source=src).compile_program(stmts)
    return run_program_via_python_bytecode(program)


def _is_incomplete_source(src: str) -> bool:
    """Return True when the REPL buffer still has unclosed delimiters or strings."""
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
    """Wire tab completion and history persistence for the REPL when available."""
    if readline is None:
        return  # Skip configuration if readline support is unavailable
    readline.set_completer_delims(" \t\n")  # Treat whitespace as completion delimiters

    def completer(text: str, state: int) -> Optional[str]:
        completions = sorted(set(scope_provider()))  # Grab the latest symbol list
        matches = [word for word in completions if word.startswith(text)]
        return matches[state] if state < len(matches) else None  # Return nth match or None

    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")  # Enable tab completion binding
    try:
        readline.read_history_file(history_path)  # Load persisted history if available
    except FileNotFoundError:
        history_path.touch()  # Create an empty history file on first run
    readline.set_history_length(1000)  # Keep a generous but bounded history size


def _save_history(history_path: Path) -> None:
    """Persist REPL history to disk when readline support exists."""
    if readline is None:
        return  # Nothing to do without readline support
    try:
        readline.write_history_file(history_path)  # Persist the in-memory buffer
    except FileNotFoundError:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.touch()
        readline.write_history_file(history_path)


def _read_repl_command(read_fn) -> Optional[str]:
    """Read a single REPL submission, allowing multiline input when needed."""
    buffer: List[str] = []  # Accumulate multi-line input until braces balance
    while True:
        prompt = "tiny> " if not buffer else "...> "  # Primary or continuation prompt
        try:
            line = read_fn(prompt)  # Ask the configured read function for input
        except EOFError:
            return None if not buffer else "\n".join(buffer)  # Exit or return partial block
        buffer.append(line)
        src = "\n".join(buffer)
        if _is_incomplete_source(src):
            continue  # Keep reading if brackets/parens are unbalanced
        return src


def _resolve_read_fn():
    """Choose the appropriate input function depending on readline availability."""
    if isinstance(readline, _FallbackReadline):
        return readline.readline  # Use the fallback implementation when available
    return input  # Otherwise rely on the built-in input()


def _repl_highlighting_enabled() -> bool:
    """Return True when REPL syntax highlighting should be active."""

    if not PYGMENTS_AVAILABLE:
        return False  # Skip when pygments is not installed

    env_flag = os.environ.get("TINYL_REPL_HIGHLIGHT", "").strip().lower()
    if env_flag in {"0", "false", "off", "no"}:
        return False  # Opt-out when users request it explicitly

    return sys.stdout.isatty()  # Only highlight when writing to an interactive TTY


def _print_optional_dependency_instructions() -> None:
    """Print installation hints for optional LLVM-related dependencies."""
    lines = [
        "Optional dependencies:",
        "- LLVM JIT backend: pip install llvmlite",
        "- LLVM optimization passes (--llvm-opt): pip install llvmlite",
        "- Native executable emission: install clang (or set --compiler to a compatible tool)",
    ]
    print("\n".join(lines))


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for running files, snippets, REPL sessions, or codegen."""
    parser = argparse.ArgumentParser(description="Run a TinyLanguage program from a file")
    mode_group = parser.add_mutually_exclusive_group()  # Eval and REPL are exclusive options
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
    parser.add_argument(
        "--emit-python",
        dest="emit_python",
        metavar="FILE",
        help="Emit Python code generated from TinyLanguage and write it to FILE (use '-' for stdout)",
    )
    parser.add_argument(
        "--emit-llvm",
        dest="emit_llvm",
        metavar="FILE",
        help="Emit LLVM IR for the native backend subset and write it to FILE (use '-' for stdout)",
    )
    parser.add_argument(
        "--emit-exe",
        dest="emit_exe",
        metavar="FILE",
        help="Compile a native executable via LLVM IR and write it to FILE",
    )
    parser.add_argument(
        "--compiler",
        default=os.environ.get("TINYLANG_COMPILER", "clang"),
        help="System compiler to use with --emit-exe (default: clang, env: TINYLANG_COMPILER)",
    )
    parser.add_argument(
        "--llvm-target-triple",
        dest="llvm_target_triple",
        help="Override the LLVM target triple for --emit-llvm/--emit-exe/--llvm-jit",
    )
    parser.add_argument(
        "--llvm-data-layout",
        dest="llvm_data_layout",
        help="Override the LLVM data layout for --emit-llvm/--emit-exe/--llvm-jit",
    )
    parser.add_argument(
        "--llvm-opt",
        action="store_true",
        help="Run basic LLVM optimization passes (mem2reg, instcombine) on emitted IR",
    )
    backend_group = parser.add_mutually_exclusive_group()
    backend_group.add_argument(
        "--python-backend",
        action="store_true",
        help="Execute the program via the experimental Python codegen backend",
    )
    backend_group.add_argument(
        "--native-backend",
        action="store_true",
        help="Execute the program via the experimental native bytecode backend",
    )
    backend_group.add_argument(
        "--native-python-bytecode",
        action="store_true",
        help="Execute the program by compiling native IR to pure Python bytecode",
    )
    backend_group.add_argument(
        "--llvm-jit",
        action="store_true",
        help="Execute the program via the experimental LLVM JIT backend (requires llvmlite)",
    )
    parser.add_argument(
        "--copy-on-call",
        action=argparse.BooleanOptionalAction,
        default=_copy_on_call_default(),
        help="Deep-copy non-escaping mutable arguments before calls (env: TINYLANG_COPY_ON_CALL)",
    )
    args, remaining = parser.parse_known_args(argv)
    args.program_args = remaining
    if args.program_args and args.program_args[0] == "--":
        args.program_args = args.program_args[1:]

    if args.repl and (
        args.python_backend or args.native_backend or args.native_python_bytecode or args.llvm_jit
    ):
        parser.error("--native-backend/--python-backend cannot be combined with --repl")

    if args.format_file is not None:
        from formatter import format_source

        with open(args.format_file, "r", encoding="utf-8") as handle:
            print(format_source(handle.read()), end="")
        return 0

    if args.eval is not None:
        try:
            streamed = False
            if args.native_backend:
                output = run_with_native_backend(args.eval)
            elif args.native_python_bytecode:
                output = run_with_python_bytecode_backend(args.eval)
            elif args.python_backend:
                output = run_with_python_backend(args.eval)
            elif args.llvm_jit:
                output = run_with_llvm_jit(
                    args.eval,
                    target_triple=args.llvm_target_triple,
                    data_layout=args.llvm_data_layout,
                    llvm_opt=args.llvm_opt,
                )
                streamed = True
            else:
                runtime = Runtime(args.eval)
                runtime.copy_on_call = args.copy_on_call
                output = compile_and_run(
                    args.eval, runtime=runtime, stream_output=True, copy_on_call=args.copy_on_call
                )
                streamed = runtime.streamed_output

            if not streamed:
                print(output, end="")
            return 0
        except TinyLangError as err:
            print(_format_error_for_source(args.eval, err), file=sys.stderr)
            return 1
        except Exception as exc:  # pragma: no cover - unexpected errors
            print(str(exc), file=sys.stderr)
            return 1

    if args.repl:  # Interactive shell mode
        history_path = Path.home() / ".tiny_language_history"
        runtime = Runtime("")
        runtime.copy_on_call = args.copy_on_call
        env = Environment(parent=None, namespace=None, runtime=runtime)
        scope_provider = lambda: list(KEYWORDS | BUILTINS | set(env.all_names()))
        highlight_enabled = _repl_highlighting_enabled()
        _configure_readline(history_path, scope_provider)
        read_fn = _resolve_read_fn()
        try:
            while True:
                src = _read_repl_command(read_fn)
                if src is None:
                    print()
                    break
                if not src.strip():
                    continue  # Ignore blank submissions
                if src.strip().lower() == "s":
                    _print_optional_dependency_instructions()
                    continue
                if highlight_enabled:
                    highlighted = highlight_source(src)
                    if highlighted:
                        print(highlighted, end="" if highlighted.endswith("\n") else "\n")
                if readline is not None:
                    try:
                        readline.add_history(src)
                    except Exception:
                        pass  # History persistence failures should not crash the REPL
                try:
                    compile_and_run(
                        src,
                        env=env,
                        runtime=runtime,
                        stream_output=True,
                        copy_on_call=args.copy_on_call,
                    )
                except TinyLangError as err:
                    print(_format_error_for_source(src, err), file=sys.stderr)
                except Exception as exc:  # pragma: no cover - unexpected errors
                    print(str(exc), file=sys.stderr)
        finally:
            _save_history(history_path)  # Always attempt to save history on exit
        return 0

    if args.emit_python:
        if not args.file:
            parser.error("--emit-python requires a source file")
        source_text = Path(args.file).read_text(encoding="utf-8")
        generated = compile_to_python_source(source_text)
        if args.emit_python == "-":
            print(generated)
        else:
            Path(args.emit_python).write_text(generated, encoding="utf-8")
        return 0

    if args.emit_llvm:
        if not args.file:
            parser.error("--emit-llvm requires a source file")
        source_text = Path(args.file).read_text(encoding="utf-8")
        llvm_ir = compile_to_llvm_ir(
            source_text,
            target_triple=args.llvm_target_triple,
            data_layout=args.llvm_data_layout,
            llvm_opt=args.llvm_opt,
            module_path=Path(args.file),
        )
        if args.emit_llvm == "-":
            print(llvm_ir)
        else:
            Path(args.emit_llvm).write_text(llvm_ir, encoding="utf-8")
        return 0

    if args.emit_exe:
        if not args.file:
            parser.error("--emit-exe requires a source file")
        source_text = Path(args.file).read_text(encoding="utf-8")
        try:
            compile_to_executable(
                source_text,
                Path(args.emit_exe),
                compiler=args.compiler,
                target_triple=args.llvm_target_triple,
                data_layout=args.llvm_data_layout,
                llvm_opt=args.llvm_opt,
                module_path=Path(args.file),
            )
        except RuntimeError as err:
            print(str(err), file=sys.stderr)
            return 1
        return 0

    if not args.file:
        parser.error("the following arguments are required: file")  # Align with argparse behavior

    program_argv = [args.file] + list(args.program_args)
    streamed = False
    original_argv = sys.argv[:]
    sys.argv = program_argv
    try:
        if args.native_backend:
            output = run_with_native_backend(Path(args.file).read_text(encoding="utf-8"))
        elif args.python_backend:
            output = run_with_python_backend(Path(args.file).read_text(encoding="utf-8"))
        elif args.llvm_jit:
            output = run_with_llvm_jit(
                Path(args.file).read_text(encoding="utf-8"),
                target_triple=args.llvm_target_triple,
                data_layout=args.llvm_data_layout,
                llvm_opt=args.llvm_opt,
            )
            streamed = True
        else:
            output = run_file(args.file, stream_output=True, copy_on_call=args.copy_on_call)
            streamed = True
    finally:
        sys.argv = original_argv

    if not streamed:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "compile_and_run",
    "compile_to_c_executable",
    "compile_to_c_source",
    "compile_to_executable",
    "compile_to_llvm_ir",
    "compile_to_llvm_bitcode_via_c",
    "compile_to_llvm_ir_via_c",
    "compile_to_python_ast",
    "compile_to_python_source",
    "run_with_python_backend",
    "run_with_native_backend",
    "run_with_llvm_jit",
    "run_with_python_bytecode_backend",
    "run_file",
    "main",
    "ModuleResolver",
    "NativeModuleResolver",
    "LLVMModuleResolver",
]
