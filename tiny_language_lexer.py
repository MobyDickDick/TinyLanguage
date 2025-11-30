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


