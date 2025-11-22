from __future__ import annotations

import argparse

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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
}


@dataclass
class Token:
    kind: str
    text: str
    pos: int


class Lexer:
    def __init__(self, source: str):
        self.s = source
        self.i = 0
        self.n = len(source)

    def _peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    def _advance(self, n: int = 1) -> None:
        self.i += n

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
            return Token("EOF", "", self.i)
        c = self.s[self.i]
        pos = self.i

        if c == '"':
            return self._read_string()
        if c.isalpha() or c == "_":
            j = self.i + 1
            while j < self.n and (self.s[j].isalnum() or self.s[j] == "_"):
                j += 1
            txt = self.s[self.i:j]
            self.i = j
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
                elif cj.isdigit():
                    j += 1
                else:
                    break
            txt = self.s[self.i:j]
            self.i = j
            return Token("NUMBER", txt, pos)
        if c in (">", "<", "="):
            if self.i + 1 < self.n and self.s[self.i + 1] == "=":
                self.i += 2
                return Token("OP", c + "=", pos)
        if c in "+-*/><":
            self._advance()
            return Token("OP", c, pos)
        if c in "(){}[];,=:.":
            self._advance()
            return Token("SYM", c, pos)
        raise SyntaxError(f"Lexing error at position {pos} (char='{c}')")

    def _read_string(self) -> Token:
        pos0 = self.i
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
                    raise SyntaxError(f"unterminated escape in string at {pos0}")
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
        raise SyntaxError(f"unterminated string literal starting at {pos0}")


# ----- AST Nodes -----


class IR:
    pass


@dataclass
class Let(IR):
    name: str
    expr: IR


@dataclass
class Assign(IR):
    name: str
    expr: IR


@dataclass
class FieldAssign(IR):
    obj: IR
    name: str
    expr: IR


@dataclass
class Print(IR):
    expr: IR


@dataclass
class If(IR):
    cond: IR
    then: List[IR]
    els: List[IR]


@dataclass
class While(IR):
    cond: IR
    body: List[IR]


@dataclass
class Fn(IR):
    name: str
    params: List[str]
    body: List[IR]


@dataclass
class MethodDef(IR):
    class_name: str
    name: str
    params: List[str]
    body: List[IR]


@dataclass
class Return(IR):
    expr: IR


@dataclass
class CallStmt(IR):
    name: str
    args: List[IR]


@dataclass
class OpDef(IR):
    op: str
    a_name: str
    a_type: str
    b_name: str
    b_type: str
    body: List[IR]


@dataclass
class DestructAssign(IR):
    names: List[str]
    expr: IR


@dataclass
class TypeDef(IR):
    name: str
    fields: List[Tuple[str, str]]


@dataclass
class ClassDef(IR):
    name: str
    fields: List[Tuple[str, str]]
    methods: List["MethodDef"]
    bases: List[str]


# Expressions
@dataclass
class Num(IR):
    txt: str


@dataclass
class Str(IR):
    txt: str


@dataclass
class Var(IR):
    name: str


@dataclass
class Call(IR):
    name: str
    args: List[IR]


@dataclass
class New(IR):
    size: IR


@dataclass
class NewLit(IR):
    items: List[IR]


@dataclass
class Bin(IR):
    op: str
    a: IR
    b: IR


@dataclass
class ObjLit(IR):
    fields: List[Tuple[str, IR]]


@dataclass
class Field(IR):
    obj: IR
    name: str


@dataclass
class MethodCall(IR):
    obj: IR
    name: str
    args: List[IR]


@dataclass
class ClassNew(IR):
    name: str
    init: List[Tuple[str, IR]]


# ----- Parser -----


class Parser:
    def __init__(self, lx: Lexer):
        self.lx = lx
        self.tok = lx.next_token()

    def _eat(self, kind: str, text: Optional[str] = None) -> Token:
        if self.tok.kind != kind or (text is not None and self.tok.text != text):
            raise SyntaxError(f"expected {kind}{' '+text if text else ''} at {self.tok.pos}")
        t = self.tok
        self.tok = self.lx.next_token()
        return t

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
            self._eat("KW", "define")
            name = self._eat("NAME").text
            self._eat("SYM", "=")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return Let(name, expr)
        if self.tok.kind == "KW" and self.tok.text == "print":
            self._eat("KW", "print")
            self._eat("SYM", "(")
            expr = self.parse_expr()
            self._eat("SYM", ")")
            self._eat("SYM", ";")
            return Print(expr)
        if self.tok.kind == "KW" and self.tok.text == "if":
            self._eat("KW", "if")
            self._eat("SYM", "(")
            cond = self.parse_expr()
            self._eat("SYM", ")")
            then = self.parse_block()
            els: List[IR] = []
            if self.tok.kind == "KW" and self.tok.text == "else":
                self._eat("KW", "else")
                els = self.parse_block()
            return If(cond, then, els)
        if self.tok.kind == "KW" and self.tok.text == "while":
            self._eat("KW", "while")
            self._eat("SYM", "(")
            cond = self.parse_expr()
            self._eat("SYM", ")")
            body = self.parse_block()
            return While(cond, body)
        if self.tok.kind == "KW" and self.tok.text == "fn":
            self._eat("KW", "fn")
            name = self._eat("NAME").text
            params = self.parse_param_list()
            body = self.parse_block()
            return Fn(name, params, body)
        if self.tok.kind == "KW" and self.tok.text == "return":
            self._eat("KW", "return")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return Return(expr)
        if self.tok.kind == "KW" and self.tok.text == "type":
            self._eat("KW", "type")
            name = self._eat("NAME").text
            self._eat("SYM", "{")
            fields: List[Tuple[str, str]] = []
            while not self._accept("SYM", "}"):
                fname = self._eat("NAME").text
                self._eat("SYM", ":")
                ftype = self._eat("NAME").text
                self._eat("SYM", ";")
                fields.append((fname, ftype))
            return TypeDef(name, fields)
        if self.tok.kind == "KW" and self.tok.text == "class":
            self._eat("KW", "class")
            cname = self._eat("NAME").text
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
                    mname = self._eat("NAME").text
                    params = self.parse_param_list()
                    body = self.parse_block()
                    methods.append(MethodDef(cname, mname, params, body))
                else:
                    fname = self._eat("NAME").text
                    self._eat("SYM", ":")
                    ftype = self._eat("NAME").text
                    self._eat("SYM", ";")
                    fields.append((fname, ftype))
            self._eat("SYM", "}")
            return ClassDef(cname, fields, methods, bases)
        if self.tok.kind == "KW" and self.tok.text == "operator":
            self._eat("KW", "operator")
            op = self._eat("OP").text
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
            return OpDef(op, a_name, a_type, b_name, b_type, body)
        # destructuring or assignment/field assignment
        if self.tok.kind == "SYM" and self.tok.text == "{":
            names = self.parse_destruct_names()
            self._eat("SYM", "=")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return DestructAssign(names, expr)
        if self.tok.kind == "NAME":
            # look ahead for field assignment or normal assignment/call
            name_tok = self.tok
            self._eat("NAME")
            if self._accept("SYM", "."):
                field_name = self._eat("NAME").text
                if self._accept("SYM", "="):
                    expr = self.parse_expr()
                    self._eat("SYM", ";")
                    return FieldAssign(Var(name_tok.text), field_name, expr)
                # method call statement
                args = self.parse_arg_list()
                self._eat("SYM", ";")
                return CallStmt(f"{name_tok.text}.{field_name}", args)
            if self._accept("SYM", "="):
                expr = self.parse_expr()
                self._eat("SYM", ";")
                return Assign(name_tok.text, expr)
            # call statement on identifier
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                self._eat("SYM", ";")
                return CallStmt(name_tok.text, args)
            raise SyntaxError(f"unexpected token after name at {name_tok.pos}")
        raise SyntaxError(f"unexpected token {self.tok.kind} at {self.tok.pos}")

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

    def parse_destruct_names(self) -> List[str]:
        self._eat("SYM", "{")
        names = [self._eat("NAME").text]
        while self._accept("SYM", ","):
            names.append(self._eat("NAME").text)
        self._eat("SYM", "}")
        return names

    # expression parsing with precedence
    def parse_expr(self) -> IR:
        return self.parse_compare()

    def parse_compare(self) -> IR:
        left = self.parse_term()
        while self.tok.kind == "OP" and self.tok.text in (">", ">=", "<", "<=", "=="):
            op = self.tok.text
            self._eat("OP")
            right = self.parse_term()
            left = Bin(op, left, right)
        return left

    def parse_term(self) -> IR:
        left = self.parse_factor()
        while self.tok.kind == "OP" and self.tok.text in ("+", "-"):
            op = self.tok.text
            self._eat("OP")
            right = self.parse_factor()
            left = Bin(op, left, right)
        return left

    def parse_factor(self) -> IR:
        left = self.parse_unary()
        while self.tok.kind == "OP" and self.tok.text in ("*", "/"):
            op = self.tok.text
            self._eat("OP")
            right = self.parse_unary()
            left = Bin(op, left, right)
        return left

    def parse_unary(self) -> IR:
        if self.tok.kind == "OP" and self.tok.text == "-":
            self._eat("OP")
            return Bin("-", Num("0"), self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self) -> IR:
        expr = self.parse_primary()
        while True:
            if self._accept("SYM", "."):
                name = self._eat("NAME").text
                if self.tok.kind == "SYM" and self.tok.text == "(":
                    args = self.parse_arg_list()
                    expr = MethodCall(expr, name, args)
                else:
                    expr = Field(expr, name)
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
            return Num(t.text)
        if self.tok.kind == "STRING":
            t = self._eat("STRING")
            return Str(t.text)
        if self.tok.kind in {"NAME", "KW"}:
            name = self._eat(self.tok.kind).text
            if name == "new" and self.tok.kind == "SYM" and self.tok.text == "[":
                self._eat("SYM", "[")
                items: List[IR] = []
                if not (self.tok.kind == "SYM" and self.tok.text == "]"):
                    items.append(self.parse_expr())
                    while self._accept("SYM", ","):
                        items.append(self.parse_expr())
                self._eat("SYM", "]")
                return NewLit(items)
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                return Call(name, args)
            if name == "new" and self.tok.kind == "NAME":
                cname = self._eat("NAME").text
                self._eat("SYM", "{")
                init: List[Tuple[str, IR]] = []
                while not self._accept("SYM", "}"):
                    fname = self.parse_field_name()
                    self._eat("SYM", ":")
                    fexpr = self.parse_expr()
                    init.append((fname, fexpr))
                    if self._accept("SYM", "}"):
                        break
                    if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                        raise SyntaxError(f"expected field separator at {self.tok.pos}")
                return ClassNew(cname, init)
            return Var(name)
        if self._accept("SYM", "{"):
            fields: List[Tuple[str, IR]] = []
            while not self._accept("SYM", "}"):
                fname = self.parse_field_name()
                self._eat("SYM", ":")
                fexpr = self.parse_expr()
                fields.append((fname, fexpr))
                if self._accept("SYM", "}"):
                    break
                if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                    raise SyntaxError(f"expected field separator at {self.tok.pos}")
            return ObjLit(fields)
        raise SyntaxError(f"unexpected token {self.tok.kind} at {self.tok.pos}")

    def parse_field_name(self) -> str:
        name = self._eat("NAME").text
        if self._accept("SYM", "."):
            sub = self._eat("NAME").text
            return f"{name}.{sub}"
        return name


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
        uses_in_expr(s.expr, reads)
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
    elif isinstance(s, ClassDef):
        for m in s.methods:
            lint_stmt_reads(m, reads)


def lint_fn_params_used(fn: Fn) -> None:
    reads: Dict[str, int] = {}
    for st in fn.body:
        lint_stmt_reads(st, reads)
    unused = [p for p in fn.params if reads.get(p, 0) == 0]
    if unused:
        raise RuntimeError(f"unused parameter(s) in function {fn.name}: {', '.join(unused)}")
    lint_param_mutations_returned(fn.body, set(fn.params), fn.name, is_method=False)
    lint_destruct_call_outputs(fn.body)
    lint_locals_used(fn.body)


def lint_method_params_used(md: MethodDef) -> None:
    reads: Dict[str, int] = {}
    for st in md.body:
        lint_stmt_reads(st, reads)
    unused = [p for p in md.params if reads.get(p, 0) == 0]
    if unused:
        raise RuntimeError(
            f"unused parameter(s) in method {md.class_name}.{md.name}: {', '.join(unused)}"
        )
    lint_param_mutations_returned(md.body, set(md.params), f"{md.class_name}.{md.name}", is_method=True)
    lint_destruct_call_outputs(md.body)
    lint_locals_used(md.body)


def lint_locals_used(stmts: List[IR]) -> None:
    defs: Dict[str, int] = {}
    uses: Dict[str, int] = {}

    def collect_defs(block: List[IR]) -> None:
        for idx, s in enumerate(block):
            if isinstance(s, Let):
                defs[s.name] = idx
            elif isinstance(s, DestructAssign):
                for nm in s.names:
                    defs[nm] = idx
            elif isinstance(s, If):
                collect_defs(s.then)
                collect_defs(s.els)
            elif isinstance(s, While):
                collect_defs(s.body)

    collect_defs(stmts)
    for s in stmts:
        lint_stmt_reads(s, uses)
    unused = [n for n in defs if uses.get(n, 0) == 0]
    if unused:
        raise RuntimeError(f"unused local binding(s): {', '.join(unused)}")


def lint_destruct_call_outputs(stmts: List[IR]) -> None:
    for st in stmts:
        lint_destruct_call_outputs_stmt(st)


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
    stmts: List[IR], params: set[str], fn_name: str, *, is_method: bool
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
        raise RuntimeError(
            f"mutated parameter(s) in {kind} {fn_name} must be returned: {', '.join(missing)}"
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


class Runtime:
    def __init__(self):
        self.heap: Dict[int, List[Any]] = {}
        self.ptr_tags: Dict[int, str] = {}
        self.ops: Dict[Tuple[str, Optional[str], Optional[str]], Any] = {}
        self.methods: Dict[Tuple[str, str], MethodDef] = {}
        self.types: Dict[str, Dict[str, Any]] = {}
        self.next_ptr = 1
        self.output: List[str] = []
        self.functions: Dict[str, Fn] = {}
        self.error_messages: List[str] = []

    def _record_error(self, msg: str) -> None:
        self.error_messages.append(msg)

    @property
    def error_message(self) -> Optional[str]:
        if not self.error_messages:
            return None
        return "; ".join(self.error_messages)

    # heap helpers
    def __new(self, n: int) -> int:
        if n < 0:
            raise RuntimeError("alloc error: negative size")
        p = self.next_ptr
        self.next_ptr += 1
        self.heap[p] = [0 for _ in range(int(n))]
        return p

    def delete(self, p: Any) -> Dict[str, Any]:
        try:
            ip = int(p)
            self.heap.pop(ip, None)
            self.ptr_tags.pop(ip, None)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def heap_get(self, p: Any, i: Any) -> Any:
        try:
            ip = int(p)
            idx = int(i)
        except Exception:
            self._record_error("heap access error: pointer or index is not numeric")
            return None

        try:
            arr = self.heap[ip]
        except KeyError:
            self._record_error(f"heap access error: unknown pointer {ip}")
            return None

        try:
            return arr[idx]
        except Exception:
            self._record_error(f"heap access error: index {idx} out of range for pointer {ip}")
            return None

    def heap_set(self, p: Any, i: Any, v: Any) -> Dict[str, Any]:
        try:
            self.heap[int(p)][int(i)] = v
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def tag(self, p: Any, typ: Any) -> Dict[str, Any]:
        try:
            self.ptr_tags[int(p)] = str(typ)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def __get_tag(self, v: Any) -> Optional[str]:
        if isinstance(v, dict) and "__tag__" in v:
            return v["__tag__"]
        try:
            iv = int(v)
            if iv in self.ptr_tags:
                return self.ptr_tags[iv]
        except Exception:
            pass
        return None

    def __binop(self, op: str, a: Any, b: Any) -> Any:
        ta = self.__get_tag(a)
        tb = self.__get_tag(b)
        key = (op, ta, tb)
        if key in self.ops:
            return self.ops[key](a, b)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b
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
        raise RuntimeError(f"unsupported op {op}")

    def field_get(self, obj: Any, key: str) -> Any:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        if isinstance(target_obj, dict) and "__fields__" in target_obj:
            try:
                fmap = self._resolve_field_storage(
                    target_obj, key, owner_hint, target_obj["__tag__"], allow_write=False
                )
                return fmap[key]
            except Exception as err:  # noqa: BLE001
                self._record_error(str(err))
                return None
        try:
            return target_obj[str(key)]
        except Exception:
            self._record_error(f"unknown field {key}")
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
        self.types[str(name)] = {"kind": "record", "fields": dict(fields)}

    def register_class(self, name: str, fields: List[Tuple[str, str]], bases: Optional[List[str]] = None) -> None:
        base_list = list(bases) if bases is not None else []
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
        self.methods[(md.class_name, md.name)] = md

    def register_operator(self, opdef: OpDef, env: "Environment") -> None:
        def impl(a_val: Any, b_val: Any) -> Any:
            op_env = Environment(parent=env)
            op_env.values[opdef.a_name] = a_val
            op_env.values[opdef.b_name] = b_val
            return self.eval_block(opdef.body, op_env)

        self.ops[(opdef.op, opdef.a_type, opdef.b_type)] = impl

    def class_mro(self, name: str) -> List[str]:
        info = self.types.get(name)
        if info is None or info.get("kind") != "class":
            raise RuntimeError(f"unknown class {name}")
        mro: List[str] = [name]
        for base in info.get("bases", []):
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
        info = self.types.get(name)
        if info is None or info.get("kind") != "class":
            raise RuntimeError(f"unknown class {name}")
        mro = self.class_mro(name)
        obj: Dict[str, Any] = {"__tag__": name, "__fields__": {}}
        for cls in mro:
            finfo = self.types.get(cls)
            if finfo is None or finfo.get("kind") != "class":
                raise RuntimeError(f"unknown class {cls}")
            obj["__fields__"][cls] = {fname: None for fname in finfo["fields"]}

        for raw_name, val in init.items():
            owner_hint, fname = self._split_field_name(raw_name)
            fmap = self._resolve_field_storage(obj, fname, owner_hint, name)
            fmap[fname] = val
        return obj

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
            md = self.methods.get((cls, name))
            if md:
                return md
        return None

    def call_method(self, obj: Any, name: str, args: List[Any]) -> Any:
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
        return self.eval_block(md.body, env)

    def type_field_type(self, tname: str, fname: str) -> Optional[str]:
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
        if isinstance(val, bool):
            return "true" if val else "false"
        return str(val)

    # ----- Evaluation -----
    def eval_block(self, stmts: List[IR], env: "Environment") -> Any:
        for st in stmts:
            res = self.eval_stmt(st, env)
            if isinstance(res, ReturnSignal):
                return res.value
        return None

    def eval_stmt(self, s: IR, env: "Environment") -> Any:
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
            val = self.eval_expr(s.expr, env)
            self.output.append(f"{self.format_value(val)}\n")
        elif isinstance(s, If):
            cond = self.eval_expr(s.cond, env)
            branch = s.then if cond else s.els
            res = self.eval_block(branch, env)
            if isinstance(res, ReturnSignal):
                return res
        elif isinstance(s, While):
            while self.eval_expr(s.cond, env):
                res = self.eval_block(s.body, env)
                if isinstance(res, ReturnSignal):
                    return res
        elif isinstance(s, Fn):
            self.functions[s.name] = s
        elif isinstance(s, Return):
            return ReturnSignal(self.eval_expr(s.expr, env))
        elif isinstance(s, CallStmt):
            allowed = s.name in {"heap_set", "heap_get", "delete", "tag"}
            if not allowed:
                raise RuntimeError(
                    f"call with return value must be bound; bare call statements are not allowed (offending call: {s.name}())"
                )
            self.eval_expr(Call(s.name, s.args), env)
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

    def eval_expr(self, e: IR, env: "Environment") -> Any:
        if isinstance(e, Num):
            return float(e.txt) if "." in e.txt else int(e.txt)
        if isinstance(e, Str):
            return e.txt
        if isinstance(e, Var):
            if e.name == "errorMessage":
                return self.error_message
            try:
                return env.get(e.name)
            except RuntimeError:
                return e.name
        if isinstance(e, Call):
            if e.name == "__type_field_type":
                return self.type_field_type(str(self.eval_expr(e.args[0], env)), str(self.eval_expr(e.args[1], env)))
            if e.name == "__new":
                return self.__new(int(self.eval_expr(e.args[0], env)))
            if e.name == "new":
                return self.__new(int(self.eval_expr(e.args[0], env)))
            if e.name == "heap_get":
                return self.heap_get(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env))
            if e.name == "heap_set":
                return self.heap_set(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env), self.eval_expr(e.args[2], env))
            if e.name == "delete":
                return self.delete(self.eval_expr(e.args[0], env))
            if e.name == "tag":
                return self.tag(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env))
            if e.name in self.functions:
                fn = self.functions[e.name]
                call_env = Environment(parent=None)
                for pname, arg_expr in zip(fn.params, e.args):
                    call_env.values[pname] = self.eval_expr(arg_expr, env)
                res = self.eval_block(fn.body, call_env)
                return res
            raise RuntimeError(f"unknown function {e.name}")
        if isinstance(e, New):
            return self.__new(int(self.eval_expr(e.size, env)))
        if isinstance(e, NewLit):
            p = self.__new(len(e.items))
            for idx, item in enumerate(e.items):
                self.heap_set(p, idx, self.eval_expr(item, env))
            return p
        if isinstance(e, Bin):
            return self.__binop(e.op, self.eval_expr(e.a, env), self.eval_expr(e.b, env))
        if isinstance(e, ObjLit):
            obj: Dict[str, Any] = {"__tag__": "Struct"}
            for k, v in e.fields:
                obj[k] = self.eval_expr(v, env)
            return obj
        if isinstance(e, Field):
            obj = self.eval_expr(e.obj, env)
            return self.field_get(obj, e.name)
        if isinstance(e, MethodCall):
            obj = self.eval_expr(e.obj, env)
            args = [self.eval_expr(a, env) for a in e.args]
            return self.call_method(obj, e.name, args)
        if isinstance(e, ClassNew):
            init = {k: self.eval_expr(v, env) for k, v in e.init}
            self.register_class(e.name, []) if e.name not in self.types else None
            return self.instantiate_class(e.name, init)
        raise RuntimeError(f"unknown expr {e}")


class Environment:
    def __init__(self, parent: Optional["Environment"]):
        self.parent = parent
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


# ----- Public API -----


def compile_and_run(src: str) -> str:
    parser = Parser(Lexer(src))
    stmts = parser.parse()
    runtime = Runtime()

    # lint functions + top level locals
    lint_destruct_call_outputs(stmts)
    lint_locals_used(stmts)
    for st in stmts:
        if isinstance(st, Fn):
            lint_fn_params_used(st)
        if isinstance(st, MethodDef):
            lint_method_params_used(st)
        if isinstance(st, ClassDef):
            for m in st.methods:
                lint_method_params_used(m)

    env = Environment(parent=None)
    for st in stmts:
        runtime.eval_stmt(st, env)
    return "".join(runtime.output)


def run_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return compile_and_run(f.read())


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a TinyLanguage program from a file")
    parser.add_argument("file", help="Path to the TinyLanguage source file to execute")
    args = parser.parse_args(argv)

    output = run_file(args.file)
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["compile_and_run", "run_file", "main"]
