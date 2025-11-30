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
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


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


@dataclass(eq=True)
class ProgramIR:
    functions: List[FunctionIR]
    body: List[Statement] = field(default_factory=list)


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


def _expr_to_python(expr: Expression) -> str:
    if isinstance(expr, Name):
        return expr.identifier
    if isinstance(expr, Literal):
        return repr(expr.value)
    if isinstance(expr, BinaryOp):
        return f"{_expr_to_python(expr.left)} {expr.op} {_expr_to_python(expr.right)}"
    if isinstance(expr, Call):
        args = ", ".join(_expr_to_python(arg) for arg in expr.args)
        return f"{expr.func}({args})"
    raise ValueError(f"Unsupported expression for Python rendering: {expr}")


def _sanitize_for_python(expr_text: str) -> str:
    sanitized = expr_text
    sanitized = sanitized.replace("&&", " and ").replace("||", " or ")
    sanitized = re.sub(r"\btrue\b", "True", sanitized)
    sanitized = re.sub(r"\bfalse\b", "False", sanitized)
    sanitized = re.sub(r"\bnothing\b", "None", sanitized)
    return sanitized


def _parse_expression(expr_text: str) -> Expression:
    sanitized = _sanitize_for_python(expr_text.strip())
    node = ast.parse(sanitized, mode="eval").body
    return _expr_from_ast(node)


def _indent_lines(lines: Iterable[str], indent: str) -> List[str]:
    return [f"{indent}{line}" for line in lines]


def _render_block(statements: Sequence[Statement], render_expr, line_suffix: str = "") -> List[str]:
    rendered: List[str] = []
    for stmt in statements:
        if isinstance(stmt, Assign):
            rendered.append(f"{stmt.target} = {render_expr(stmt.expr)}{line_suffix}")
        elif isinstance(stmt, Return):
            rendered.append(f"return {render_expr(stmt.expr)}{line_suffix}")
        elif isinstance(stmt, ExprStmt):
            rendered.append(f"{render_expr(stmt.expr)}{line_suffix}")
        elif isinstance(stmt, IfElse):
            raise ValueError("If/else rendering requires language-specific handling (not yet implemented).")
        elif isinstance(stmt, While):
            raise ValueError("While-loop rendering requires language-specific handling (not yet implemented).")
        else:
            raise ValueError(f"Unsupported statement: {stmt}")
    return rendered


# ----- Base class -----


class LanguageTranspiler:
    indent: str = "    "

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
            chunks.extend(_render_block(program.body, _expr_to_python))
        return self._lines(chunks)

    def _render_function(self, fn: FunctionIR) -> str:
        header = f"def {fn.name}({', '.join(fn.params)}):"
        body_lines = _render_block(fn.body, _expr_to_python)
        indented = [self.indent + line for line in body_lines or ["pass"]]
        return "\n".join([header, *indented])

    def from_source(self, code: str) -> ProgramIR:
        module = ast.parse(code)
        functions: List[FunctionIR] = []
        body: List[Statement] = []
        for node in module.body:
            if isinstance(node, ast.FunctionDef):
                functions.append(self._function_from_ast(node))
            else:
                body.append(self._stmt_from_ast(node))
        return ProgramIR(functions=functions, body=body)

    def _function_from_ast(self, node: ast.FunctionDef) -> FunctionIR:
        params = [arg.arg for arg in node.args.args]
        stmts = [self._stmt_from_ast(stmt) for stmt in node.body if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Constant)]
        return FunctionIR(name=node.name, params=params, body=stmts)

    def _stmt_from_ast(self, node: ast.AST) -> Statement:
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise ValueError("Only simple assignments are supported")
            return Assign(node.targets[0].id, _expr_from_ast(node.value))
        if isinstance(node, ast.Return):
            return Return(_expr_from_ast(node.value))
        if isinstance(node, ast.Expr):
            return ExprStmt(_expr_from_ast(node.value))
        raise ValueError(f"Unsupported statement node: {ast.dump(node)}")


# ----- Julia -----


class JuliaTranspiler(LanguageTranspiler):
    indent = "    "

    def to_source(self, program: ProgramIR) -> str:
        chunks: List[str] = []
        for fn in program.functions:
            header = f"function {fn.name}({', '.join(fn.params)})"
            body_lines = _render_block(fn.body, _expr_to_python)
            indented = [self.indent + line for line in body_lines]
            chunks.append("\n".join([header, *indented, "end"]))
        if program.body:
            chunks.extend(_render_block(program.body, _expr_to_python))
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
                i += 1
                fn_body: List[str] = []
                while i < len(lines) and lines[i] != "end":
                    fn_body.append(lines[i])
                    i += 1
                functions.append(FunctionIR(name=name, params=params_text, body=self._parse_statements(fn_body)))
            else:
                body.extend(self._parse_statements([line]))
            i += 1
        return ProgramIR(functions=functions, body=body)

    def _parse_signature(self, line: str) -> tuple[str, List[str]]:
        match = re.match(r"function\s+([A-Za-z_]\w*)\((.*)\)", line)
        if not match:
            raise ValueError(f"Invalid Julia function signature: {line}")
        name = match.group(1)
        params = [param.strip() for param in match.group(2).split(",") if param.strip()]
        return name, params

    def _parse_statements(self, lines: List[str]) -> List[Statement]:
        stmts: List[Statement] = []
        for line in lines:
            stmts.append(_parse_statement(line))
        return stmts


# ----- JavaScript -----


class JavaScriptTranspiler(LanguageTranspiler):
    indent = "  "

    def to_source(self, program: ProgramIR) -> str:
        chunks: List[str] = []
        for fn in program.functions:
            header = f"function {fn.name}({', '.join(fn.params)}) {{"
            body_lines = _render_block(fn.body, _expr_to_python, line_suffix=";")
            indented = [self.indent + line for line in body_lines]
            chunks.append("\n".join([header, *indented, "}"]))
        if program.body:
            chunks.extend(_render_block(program.body, _expr_to_python, line_suffix=";"))
        return self._lines(chunks)

    def from_source(self, code: str) -> ProgramIR:
        lines = [line.strip().rstrip(";") for line in code.splitlines() if line.strip()]
        functions: List[FunctionIR] = []
        body: List[Statement] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("function "):
                name, params = self._parse_signature(line)
                i += 1
                fn_body: List[str] = []
                while i < len(lines) and lines[i] != "}":
                    fn_body.append(lines[i])
                    i += 1
                functions.append(FunctionIR(name=name, params=params, body=[_parse_statement(l) for l in fn_body]))
            else:
                body.append(_parse_statement(line))
            i += 1
        return ProgramIR(functions=functions, body=body)

    def _parse_signature(self, line: str) -> tuple[str, List[str]]:
        match = re.match(r"function\s+([A-Za-z_]\w*)\((.*)\)\s*\{?", line)
        if not match:
            raise ValueError(f"Invalid JavaScript function signature: {line}")
        name = match.group(1)
        params = [param.strip() for param in match.group(2).split(",") if param.strip()]
        return name, params


# ----- C++ -----


class CppTranspiler(LanguageTranspiler):
    indent = "  "

    def to_source(self, program: ProgramIR) -> str:
        chunks: List[str] = []
        for fn in program.functions:
            signature = f"auto {fn.name}({', '.join(f'auto {p}' for p in fn.params)}) {{"
            body_lines = _render_block(fn.body, _expr_to_python, line_suffix=";")
            indented = [self.indent + line for line in body_lines]
            chunks.append("\n".join([signature, *indented, "}"]))
        if program.body:
            chunks.extend(_render_block(program.body, _expr_to_python, line_suffix=";"))
        return self._lines(chunks)

    def from_source(self, code: str) -> ProgramIR:
        lines = [line.strip().rstrip(";") for line in code.splitlines() if line.strip()]
        functions: List[FunctionIR] = []
        body: List[Statement] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("auto "):
                name, params = self._parse_signature(line)
                i += 1
                fn_body: List[str] = []
                while i < len(lines) and lines[i] != "}":
                    fn_body.append(lines[i])
                    i += 1
                functions.append(FunctionIR(name=name, params=params, body=[_parse_statement(l) for l in fn_body]))
            else:
                body.append(_parse_statement(line))
            i += 1
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
