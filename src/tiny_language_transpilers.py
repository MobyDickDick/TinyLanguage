"""Prototype transpilers between TinyLanguage IR and other languages.

The goal is to provide a minimal, semantics-preserving bridge that can
translate a constrained subset of imperative code to and from Python,
Julia, JavaScript, and C++. The current implementation focuses on a
shared intermediate representation (IR) that captures straight-line
assignments, function calls, and returns. Each language-specific
transpiler implements bidirectional conversion against that IR.

The prototypes intentionally keep the supported syntax small so that we
can iterate quickly while adding more constructs later. When a construct
is not supported, the transpilers raise ``ValueError`` with descriptive
messages so callers can fail fast and extend the IR as needed. The shared
IR already includes placeholders for common control-flow building blocks
so language frontends can grow into them gradually.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Set


# ----- Shared IR -----


@dataclass(eq=True)
class Expression:
    pass


@dataclass(eq=True)
class Name(Expression):
    identifier: str


@dataclass(eq=True)
class Literal(Expression):
    value: object


@dataclass(eq=True)
class BinaryOp(Expression):
    op: str
    left: Expression
    right: Expression


@dataclass(eq=True)
class Call(Expression):
    func: str
    args: List[Expression]


@dataclass(eq=True)
class Statement:
    pass


@dataclass(eq=True)
class Assign(Statement):
    target: str
    expr: Expression


@dataclass(eq=True)
class Return(Statement):
    expr: Expression


@dataclass(eq=True)
class ExprStmt(Statement):
    expr: Expression


@dataclass(eq=True)
class IfElse(Statement):
    condition: Expression
    then_body: List[Statement]
    else_body: List[Statement] = field(default_factory=list)


@dataclass(eq=True)
class While(Statement):
    condition: Expression
    body: List[Statement]


@dataclass(eq=True)
class FunctionIR:
    name: str
    params: List[str]
    body: List[Statement] = field(default_factory=list)
    docstring: str | None = None


@dataclass(eq=True)
class ProgramIR:
    functions: List[FunctionIR]
    body: List[Statement] = field(default_factory=list)
    docstring: str | None = None


# ----- Helpers -----


_OPERATOR_MAP = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.Gt: ">",
    ast.LtE: "<=",
    ast.GtE: ">=",
}


def _expr_from_ast(node: ast.AST) -> Expression:
    if isinstance(node, ast.Name):
        return Name(node.id)
    if isinstance(node, ast.Constant):
        return Literal(node.value)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _OPERATOR_MAP:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        return BinaryOp(_OPERATOR_MAP[op_type], _expr_from_ast(node.left), _expr_from_ast(node.right))
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
        op_type = type(node.ops[0])
        if op_type not in _OPERATOR_MAP:
            raise ValueError(f"Unsupported comparison: {op_type.__name__}")
        return BinaryOp(_OPERATOR_MAP[op_type], _expr_from_ast(node.left), _expr_from_ast(node.comparators[0]))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are supported")
        return Call(node.func.id, [_expr_from_ast(arg) for arg in node.args])
    raise ValueError(f"Unsupported expression node: {ast.dump(node)}")


def _expr_to_source(expr: Expression, render_literal) -> str:
    if isinstance(expr, Name):
        return expr.identifier
    if isinstance(expr, Literal):
        return render_literal(expr.value)
    if isinstance(expr, BinaryOp):
        return f"{_expr_to_source(expr.left, render_literal)} {expr.op} {_expr_to_source(expr.right, render_literal)}"
    if isinstance(expr, Call):
        args = ", ".join(_expr_to_source(arg, render_literal) for arg in expr.args)
        return f"{expr.func}({args})"
    raise ValueError(f"Unsupported expression for rendering: {expr}")

def _sanitize_for_python(expr_text: str) -> str:
    sanitized = expr_text
    sanitized = sanitized.replace("&&", " and ").replace("||", " or ")
    sanitized = re.sub(r"\btrue\b", "True", sanitized)
    sanitized = re.sub(r"\bfalse\b", "False", sanitized)
    sanitized = re.sub(r"\bnull\b", "None", sanitized)
    sanitized = re.sub(r"\bnullptr\b", "None", sanitized)
    sanitized = re.sub(r"\bnothing\b", "None", sanitized)
    return sanitized


def _parse_expression(expr_text: str) -> Expression:
    sanitized = _sanitize_for_python(expr_text.strip())
    node = ast.parse(sanitized, mode="eval").body
    return _expr_from_ast(node)


# ----- Base class -----


class LanguageTranspiler:
    indent: str = "    "

    def _render_literal(self, value: object) -> str:
        return repr(value)

    def _render_expr(self, expr: Expression) -> str:
        return _expr_to_source(expr, self._render_literal)

    def to_source(self, program: ProgramIR) -> str:
        raise NotImplementedError

    def from_source(self, code: str) -> ProgramIR:
        raise NotImplementedError

    def _lines(self, lines: Iterable[str]) -> str:
        return "\n".join(lines)


# ----- Python -----


class PythonTranspiler(LanguageTranspiler):
    indent = "    "

    def to_source(self, program: ProgramIR) -> str:
        chunks: List[str] = []
        for fn in program.functions:
            chunks.append(self._render_function(fn))
        if program.body:
            chunks.extend(self._render_statements(program.body, indent_level=0))
        return self._lines(chunks)

    def _render_function(self, fn: FunctionIR) -> str:
        header = f"def {fn.name}({', '.join(fn.params)}):"
        body_lines = self._render_statements(fn.body, indent_level=1) or [self.indent + "pass"]
        return "\n".join([header, *body_lines])

    def _render_statements(self, statements: Sequence[Statement], indent_level: int) -> List[str]:
        rendered: List[str] = []
        pad = self.indent * indent_level
        for stmt in statements:
            if isinstance(stmt, Assign):
                rendered.append(f"{pad}{stmt.target} = {self._render_expr(stmt.expr)}")
            elif isinstance(stmt, Return):
                rendered.append(f"{pad}return {self._render_expr(stmt.expr)}")
            elif isinstance(stmt, ExprStmt):
                rendered.append(f"{pad}{self._render_expr(stmt.expr)}")
            elif isinstance(stmt, IfElse):
                rendered.append(f"{pad}if {self._render_expr(stmt.condition)}:")
                then_body = self._render_statements(stmt.then_body, indent_level + 1)
                rendered.extend(then_body or [pad + self.indent + "pass"])
                if stmt.else_body:
                    rendered.append(f"{pad}else:")
                    else_body = self._render_statements(stmt.else_body, indent_level + 1)
                    rendered.extend(else_body or [pad + self.indent + "pass"])
            elif isinstance(stmt, While):
                rendered.append(f"{pad}while {self._render_expr(stmt.condition)}:")
                body = self._render_statements(stmt.body, indent_level + 1)
                rendered.extend(body or [pad + self.indent + "pass"])
            else:
                raise ValueError(f"Unsupported statement: {stmt}")
        return rendered

    def from_source(self, code: str) -> ProgramIR:
        module = ast.parse(code)
        module_docstring = ast.get_docstring(module)
        functions: List[FunctionIR] = []
        body: List[Statement] = []
        for node in module.body:
            if isinstance(node, ast.FunctionDef):
                functions.append(self._function_from_ast(node))
            else:
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                    # Skip module-level docstrings or bare constants.
                    continue
                body.append(self._stmt_from_ast(node))
        return ProgramIR(functions=functions, body=body, docstring=module_docstring)

    def _function_from_ast(self, node: ast.FunctionDef) -> FunctionIR:
        params = [arg.arg for arg in node.args.args]
        docstring = ast.get_docstring(node)
        stmts = [
            self._stmt_from_ast(stmt)
            for stmt in node.body
            if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Constant)
        ]
        return FunctionIR(name=node.name, params=params, body=stmts, docstring=docstring)

    def _stmt_from_ast(self, node: ast.AST) -> Statement:
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise ValueError("Only simple assignments are supported")
            return Assign(node.targets[0].id, _expr_from_ast(node.value))
        if isinstance(node, ast.Return):
            return Return(_expr_from_ast(node.value))
        if isinstance(node, ast.Expr):
            return ExprStmt(_expr_from_ast(node.value))
        if isinstance(node, ast.If):
            then_body = [self._stmt_from_ast(stmt) for stmt in node.body]
            else_body = [self._stmt_from_ast(stmt) for stmt in node.orelse]
            return IfElse(_expr_from_ast(node.test), then_body, else_body)
        if isinstance(node, ast.While):
            loop_body = [self._stmt_from_ast(stmt) for stmt in node.body]
            return While(_expr_from_ast(node.test), loop_body)
        raise ValueError(f"Unsupported statement node: {ast.dump(node)}")


# ----- Julia -----


class JuliaTranspiler(LanguageTranspiler):
    indent = "    "

    def _render_literal(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "nothing"
        if isinstance(value, str):
            return json.dumps(value)
        return repr(value)

    def to_source(self, program: ProgramIR) -> str:
        chunks: List[str] = []
        for fn in program.functions:
            header = f"function {fn.name}({', '.join(fn.params)})"
            body_lines = self._render_statements(fn.body, indent_level=1)
            chunks.append("\n".join([header, *body_lines, "end"]))
        if program.body:
            chunks.extend(self._render_statements(program.body, indent_level=0))
        return self._lines(chunks)

    def from_source(self, code: str) -> ProgramIR:
        lines = [line.strip() for line in code.splitlines() if line.strip()]
        functions: List[FunctionIR] = []
        body: List[Statement] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("function "):
                name, params_text = self._parse_signature(line)
                fn_body, i = self._parse_block(lines, i + 1)
                if i >= len(lines) or lines[i] != "end":
                    raise ValueError("Unterminated Julia function body")
                functions.append(FunctionIR(name=name, params=params_text, body=fn_body))
                i += 1
            else:
                block, i = self._parse_block(lines, i)
                body.extend(block)
        return ProgramIR(functions=functions, body=body)

    def _parse_signature(self, line: str) -> tuple[str, List[str]]:
        match = re.match(r"function\s+([A-Za-z_]\w*)\((.*)\)", line)
        if not match:
            raise ValueError(f"Invalid Julia function signature: {line}")
        name = match.group(1)
        params = [param.strip() for param in match.group(2).split(",") if param.strip()]
        return name, params

    def _parse_block(self, lines: List[str], i: int) -> tuple[List[Statement], int]:
        stmts: List[Statement] = []
        while i < len(lines):
            line = lines[i]
            if line == "end" or line == "else":
                return stmts, i
            if line.startswith("if "):
                condition = line[3:].strip()
                then_body, i = self._parse_block(lines, i + 1)
                else_body: List[Statement] = []
                if i < len(lines) and lines[i] == "else":
                    else_body, i = self._parse_block(lines, i + 1)
                if i >= len(lines) or lines[i] != "end":
                    raise ValueError("Unterminated Julia if/else block")
                stmts.append(IfElse(_parse_expression(condition), then_body, else_body))
                i += 1
                continue
            if line.startswith("while "):
                condition = line[6:].strip()
                loop_body, i = self._parse_block(lines, i + 1)
                if i >= len(lines) or lines[i] != "end":
                    raise ValueError("Unterminated Julia while block")
                stmts.append(While(_parse_expression(condition), loop_body))
                i += 1
                continue
            stmts.append(_parse_statement(line))
            i += 1
        return stmts, i

    def _render_statements(self, statements: Sequence[Statement], indent_level: int) -> List[str]:
        rendered: List[str] = []
        pad = self.indent * indent_level
        for stmt in statements:
            if isinstance(stmt, Assign):
                rendered.append(f"{pad}{stmt.target} = {self._render_expr(stmt.expr)}")
            elif isinstance(stmt, Return):
                rendered.append(f"{pad}return {self._render_expr(stmt.expr)}")
            elif isinstance(stmt, ExprStmt):
                rendered.append(f"{pad}{self._render_expr(stmt.expr)}")
            elif isinstance(stmt, IfElse):
                rendered.append(f"{pad}if {self._render_expr(stmt.condition)}")
                rendered.extend(self._render_statements(stmt.then_body, indent_level + 1) or [pad + self.indent + "nothing"])
                if stmt.else_body:
                    rendered.append(f"{pad}else")
                    rendered.extend(self._render_statements(stmt.else_body, indent_level + 1) or [pad + self.indent + "nothing"])
                rendered.append(f"{pad}end")
            elif isinstance(stmt, While):
                rendered.append(f"{pad}while {self._render_expr(stmt.condition)}")
                rendered.extend(self._render_statements(stmt.body, indent_level + 1) or [pad + self.indent + "nothing"])
                rendered.append(f"{pad}end")
            else:
                raise ValueError(f"Unsupported statement: {stmt}")
        return rendered


# ----- JavaScript -----


class JavaScriptTranspiler(LanguageTranspiler):
    indent = "  "

    def _render_literal(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, str):
            return json.dumps(value)
        return repr(value)

    def to_source(self, program: ProgramIR) -> str:
        chunks: List[str] = []
        for fn in program.functions:
            header = f"function {fn.name}({', '.join(fn.params)}) {{"
            body_lines = self._render_statements(fn.body, indent_level=1)
            chunks.append("\n".join([header, *body_lines, "}"]))
        if program.body:
            chunks.extend(self._render_statements(program.body, indent_level=0))
        return self._lines(chunks)

    def from_source(self, code: str) -> ProgramIR:
        lines = self._tokenize_lines(code)
        functions: List[FunctionIR] = []
        body: List[Statement] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("function "):
                name, params = self._parse_signature(line)
                body_start = self._block_start_index(lines, i, line)
                fn_body, i = self._parse_block(lines, body_start)
                if i >= len(lines) or lines[i] != "}":
                    raise ValueError("Unterminated JavaScript function body")
                functions.append(FunctionIR(name=name, params=params, body=fn_body))
                i += 1
            else:
                block, i = self._parse_block(lines, i)
                body.extend(block)
        return ProgramIR(functions=functions, body=body)

    def _parse_signature(self, line: str) -> tuple[str, List[str]]:
        match = re.match(r"function\s+([A-Za-z_]\w*)\((.*)\)\s*\{?", line)
        if not match:
            raise ValueError(f"Invalid JavaScript function signature: {line}")
        name = match.group(1)
        params = [param.strip() for param in match.group(2).split(",") if param.strip()]
        return name, params

    def _tokenize_lines(self, code: str) -> List[str]:
        tokens: List[str] = []
        for raw in code.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            pieces = re.split(r"([{}])", stripped)
            for piece in pieces:
                part = piece.strip()
                if not part:
                    continue
                tokens.append(part.rstrip(";"))
        return tokens

    def _parse_block(self, lines: List[str], i: int) -> tuple[List[Statement], int]:
        stmts: List[Statement] = []
        while i < len(lines):
            line = lines[i]
            if line == "}":
                return stmts, i
            if line == "else":
                return stmts, i
            if line.startswith("if"):
                condition = self._extract_condition(line, keyword="if")
                body_start = self._block_start_index(lines, i, line)
                then_body, i = self._parse_block(lines, body_start)
                if i >= len(lines) or lines[i] != "}":
                    raise ValueError("Unterminated JavaScript if block")
                i += 1
                else_body: List[Statement] = []
                if i < len(lines) and lines[i].startswith("else"):
                    else_start = self._block_start_index(lines, i, lines[i], keyword="else", expects_condition=False)
                    else_body, i = self._parse_block(lines, else_start)
                    if i >= len(lines) or lines[i] != "}":
                        raise ValueError("Unterminated JavaScript else block")
                    i += 1
                stmts.append(IfElse(_parse_expression(condition), then_body, else_body))
                continue
            if line.startswith("while"):
                condition = self._extract_condition(line, keyword="while")
                body_start = self._block_start_index(lines, i, line)
                loop_body, i = self._parse_block(lines, body_start)
                if i >= len(lines) or lines[i] != "}":
                    raise ValueError("Unterminated JavaScript while block")
                i += 1
                stmts.append(While(_parse_expression(condition), loop_body))
                continue
            stmts.append(_parse_statement(line))
            i += 1
        return stmts, i

    def _block_start_index(self, lines: List[str], i: int, line: str, keyword: str | None = None, expects_condition: bool = True) -> int:
        stripped = line.strip()
        if stripped.endswith("{"):
            return i + 1
        if i + 1 < len(lines) and lines[i + 1] == "{":
            return i + 2
        label = keyword or "block"
        raise ValueError(f"JavaScript {label} must open with '{{'")

    def _extract_condition(self, line: str, keyword: str) -> str:
        match = re.match(rf"{keyword}\s*\((.*)\)\s*\{{?", line)
        if not match:
            raise ValueError(f"Invalid JavaScript {keyword} syntax: {line}")
        return match.group(1)

    def _render_statements(self, statements: Sequence[Statement], indent_level: int) -> List[str]:
        rendered: List[str] = []
        pad = self.indent * indent_level
        for stmt in statements:
            if isinstance(stmt, Assign):
                rendered.append(f"{pad}{stmt.target} = {self._render_expr(stmt.expr)};")
            elif isinstance(stmt, Return):
                rendered.append(f"{pad}return {self._render_expr(stmt.expr)};")
            elif isinstance(stmt, ExprStmt):
                rendered.append(f"{pad}{self._render_expr(stmt.expr)};")
            elif isinstance(stmt, IfElse):
                rendered.append(f"{pad}if ({self._render_expr(stmt.condition)}) {{")
                rendered.extend(self._render_statements(stmt.then_body, indent_level + 1))
                rendered.append(f"{pad}}}")
                if stmt.else_body:
                    rendered.append(f"{pad}else {{")
                    rendered.extend(self._render_statements(stmt.else_body, indent_level + 1))
                    rendered.append(f"{pad}}}")
            elif isinstance(stmt, While):
                rendered.append(f"{pad}while ({self._render_expr(stmt.condition)}) {{")
                rendered.extend(self._render_statements(stmt.body, indent_level + 1))
                rendered.append(f"{pad}}}")
            else:
                raise ValueError(f"Unsupported statement: {stmt}")
        return rendered


# ----- C++ -----


class CppTranspiler(LanguageTranspiler):
    indent = "  "

    def _render_literal(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "nullptr"
        if isinstance(value, str):
            return json.dumps(value)
        return repr(value)

    def to_source(self, program: ProgramIR) -> str:
        chunks: List[str] = []
        for fn in program.functions:
            signature = f"auto {fn.name}({', '.join(f'auto {p}' for p in fn.params)}) {{"
            body_lines = self._render_statements(fn.body, indent_level=1)
            chunks.append("\n".join([signature, *body_lines, "}"]))
        if program.body:
            chunks.extend(self._render_statements(program.body, indent_level=0))
        return self._lines(chunks)

    def from_source(self, code: str) -> ProgramIR:
        lines = self._tokenize_lines(code)
        functions: List[FunctionIR] = []
        body: List[Statement] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("auto "):
                name, params = self._parse_signature(line)
                body_start = self._block_start_index(lines, i, line)
                fn_body, i = self._parse_block(lines, body_start)
                if i >= len(lines) or lines[i] != "}":
                    raise ValueError("Unterminated C++ function body")
                functions.append(FunctionIR(name=name, params=params, body=fn_body))
                i += 1
            else:
                block, i = self._parse_block(lines, i)
                body.extend(block)
        return ProgramIR(functions=functions, body=body)

    def _parse_signature(self, line: str) -> tuple[str, List[str]]:
        match = re.match(r"auto\s+([A-Za-z_]\w*)\((.*)\)\s*\{?", line)
        if not match:
            raise ValueError(f"Invalid C++ function signature: {line}")
        name = match.group(1)
        params = []
        params_raw = match.group(2).strip()
        if params_raw:
            for param in params_raw.split(','):
                cleaned = param.strip()
                cleaned = cleaned.replace("auto", "").strip()
                if cleaned:
                    params.append(cleaned)
        return name, params

    def _tokenize_lines(self, code: str) -> List[str]:
        tokens: List[str] = []
        for raw in code.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            pieces = re.split(r"([{}])", stripped)
            for piece in pieces:
                part = piece.strip()
                if not part:
                    continue
                tokens.append(part.rstrip(";"))
        return tokens

    def _parse_block(self, lines: List[str], i: int) -> tuple[List[Statement], int]:
        stmts: List[Statement] = []
        while i < len(lines):
            line = lines[i]
            if line == "}":
                return stmts, i
            if line == "else":
                return stmts, i
            if line.startswith("if"):
                condition = self._extract_condition(line, keyword="if")
                body_start = self._block_start_index(lines, i, line)
                then_body, i = self._parse_block(lines, body_start)
                if i >= len(lines) or lines[i] != "}":
                    raise ValueError("Unterminated C++ if block")
                i += 1
                else_body: List[Statement] = []
                if i < len(lines) and lines[i].startswith("else"):
                    else_start = self._block_start_index(lines, i, lines[i], keyword="else", expects_condition=False)
                    else_body, i = self._parse_block(lines, else_start)
                    if i >= len(lines) or lines[i] != "}":
                        raise ValueError("Unterminated C++ else block")
                    i += 1
                stmts.append(IfElse(_parse_expression(condition), then_body, else_body))
                continue
            if line.startswith("while"):
                condition = self._extract_condition(line, keyword="while")
                body_start = self._block_start_index(lines, i, line)
                loop_body, i = self._parse_block(lines, body_start)
                if i >= len(lines) or lines[i] != "}":
                    raise ValueError("Unterminated C++ while block")
                i += 1
                stmts.append(While(_parse_expression(condition), loop_body))
                continue
            stmts.append(_parse_statement(line))
            i += 1
        return stmts, i

    def _block_start_index(self, lines: List[str], i: int, line: str, keyword: str | None = None, expects_condition: bool = True) -> int:
        stripped = line.strip()
        if stripped.endswith("{"):
            return i + 1
        if i + 1 < len(lines) and lines[i + 1] == "{":
            return i + 2
        label = keyword or "block"
        raise ValueError(f"C++ {label} must open with '{{'")

    def _extract_condition(self, line: str, keyword: str) -> str:
        match = re.match(rf"{keyword}\s*\((.*)\)\s*\{{?", line)
        if not match:
            raise ValueError(f"Invalid C++ {keyword} syntax: {line}")
        return match.group(1)

    def _render_statements(self, statements: Sequence[Statement], indent_level: int) -> List[str]:
        rendered: List[str] = []
        pad = self.indent * indent_level
        for stmt in statements:
            if isinstance(stmt, Assign):
                rendered.append(f"{pad}{stmt.target} = {self._render_expr(stmt.expr)};")
            elif isinstance(stmt, Return):
                rendered.append(f"{pad}return {self._render_expr(stmt.expr)};")
            elif isinstance(stmt, ExprStmt):
                rendered.append(f"{pad}{self._render_expr(stmt.expr)};")
            elif isinstance(stmt, IfElse):
                rendered.append(f"{pad}if ({self._render_expr(stmt.condition)}) {{")
                rendered.extend(self._render_statements(stmt.then_body, indent_level + 1))
                rendered.append(f"{pad}}}")
                if stmt.else_body:
                    rendered.append(f"{pad}else {{")
                    rendered.extend(self._render_statements(stmt.else_body, indent_level + 1))
                    rendered.append(f"{pad}}}")
            elif isinstance(stmt, While):
                rendered.append(f"{pad}while ({self._render_expr(stmt.condition)}) {{")
                rendered.extend(self._render_statements(stmt.body, indent_level + 1))
                rendered.append(f"{pad}}}")
            else:
                raise ValueError(f"Unsupported statement: {stmt}")
        return rendered


# ----- TinyLanguage -----


class TinyLanguageTranspiler(LanguageTranspiler):
    """Render the shared IR into TinyLanguage syntax.

    This is intentionally minimal and only covers the constructs required for the
    Rosetta-style examples and tests.
    """

    indent = "    "

    def __init__(self) -> None:
        self._unused_counter = 0

    def _next_unused(self, defined: Set[str]) -> str:
        while True:
            self._unused_counter += 1
            name = f"ignored{self._unused_counter}"
            if name not in defined:
                return name

    def _render_literal(self, value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, str):
            return json.dumps(value)
        return repr(value)

    def to_source(self, program: ProgramIR) -> str:
        chunks: List[str] = []
        if program.docstring:
            chunks.extend(self._render_comment_block(program.docstring))
            chunks.append("")
        for index, fn in enumerate(program.functions):
            chunks.append(self._render_function(fn))
            if index < len(program.functions) - 1:
                chunks.append("")
        if program.body:
            if chunks and chunks[-1] != "":
                chunks.append("")
            chunks.extend(self._render_statements(program.body, indent_level=0, defined=set()))
        return self._lines(chunks)

    def _render_function(self, fn: FunctionIR) -> str:
        defined: Set[str] = set(fn.params)
        header = f"fn {fn.name}({', '.join(fn.params)}) {{"
        body_lines: List[str] = []
        if fn.docstring:
            body_lines.extend(self._render_comment_block(fn.docstring, indent_level=1))
        body_lines.extend(self._render_statements(fn.body, indent_level=1, defined=defined))
        if not body_lines:
            body_lines.append(self.indent + "// no-op")
        return "\n".join([header, *body_lines, "}"])

    def _render_comment_block(self, docstring: str, indent_level: int = 0) -> List[str]:
        pad = self.indent * indent_level
        lines = docstring.splitlines() or [""]
        rendered: List[str] = []
        for line in lines:
            if line.strip():
                rendered.append(f"{pad}// {line}")
            else:
                rendered.append(f"{pad}//")
        return rendered

    def _render_statements(self, statements: Sequence[Statement], indent_level: int, defined: Set[str]) -> List[str]:
        rendered: List[str] = []
        pad = self.indent * indent_level
        local_defined = set(defined)
        for stmt in statements:
            if isinstance(stmt, Assign):
                keyword = "def " if stmt.target not in local_defined else ""
                rendered.append(f"{pad}{keyword}{stmt.target} = {self._render_expr(stmt.expr)};")
                local_defined.add(stmt.target)
            elif isinstance(stmt, Return):
                rendered.append(f"{pad}return {self._render_expr(stmt.expr)};")
            elif isinstance(stmt, ExprStmt):
                expr_source = self._render_expr(stmt.expr)
                if isinstance(stmt.expr, Call):
                    unused_name = self._next_unused(local_defined)
                    if stmt.expr.func == "print":
                        rendered.append(f"{pad}{expr_source};")
                    else:
                        rendered.append(f"{pad}def {unused_name} = {expr_source};")
                        local_defined.add(unused_name)
                else:
                    rendered.append(f"{pad}{expr_source};")
            elif isinstance(stmt, IfElse):
                rendered.append(f"{pad}if ({self._render_expr(stmt.condition)}) {{")
                rendered.extend(
                    self._render_statements(stmt.then_body, indent_level + 1, defined=set(local_defined))
                )
                if stmt.else_body:
                    rendered.append(f"{pad}}} else {{")
                    rendered.extend(
                        self._render_statements(stmt.else_body, indent_level + 1, defined=set(local_defined))
                    )
                    rendered.append(f"{pad}}}")
                else:
                    rendered.append(f"{pad}}}")
            elif isinstance(stmt, While):
                rendered.append(f"{pad}while ({self._render_expr(stmt.condition)}) {{")
                rendered.extend(
                    self._render_statements(stmt.body, indent_level + 1, defined=set(local_defined))
                )
                rendered.append(f"{pad}}}")
            else:
                raise ValueError(f"Unsupported statement: {stmt}")
        return rendered

    def from_source(self, code: str) -> ProgramIR:  # pragma: no cover - parser not yet implemented
        raise NotImplementedError("Parsing TinyLanguage to the shared IR is not implemented yet.")


# ----- Generic parsing -----


def _parse_statement(line: str) -> Statement:
    line = line.strip()
    if line.endswith(";"):
        line = line[:-1]
    if line.startswith("return "):
        return Return(_parse_expression(line.replace("return ", "", 1)))
    if re.match(r"^(const |let |var |auto )", line):
        line = re.sub(r"^(const |let |var |auto )", "", line)
    if "=" in line:
        target, expr = line.split("=", 1)
        return Assign(target.strip(), _parse_expression(expr))
    return ExprStmt(_parse_expression(line))
