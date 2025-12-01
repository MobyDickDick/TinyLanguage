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
    "async",
    "await",
    "true",
    "false",
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
        if c in "+-*/><^!":
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
                stop = SourcePos(start_line, self.col - 1)
                return Token("STRING", "".join(buf), pos0, stop)
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
        span = SourceSpan(pos0, pos0)
        raise TinyLangError(
            format_error(self.s, span, "unterminated string literal"), pos0, span=span
        )


