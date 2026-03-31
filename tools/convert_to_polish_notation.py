"""Simple helper to rewrite arithmetic expressions into prefix (Polish) notation.

Scope intentionally limited to avoid unsafe mass rewrites:
- handles binary +, -, *, /, %, **
- handles unary + and -
- preserves non-expression parts as-is
"""

from __future__ import annotations

import ast
from pathlib import Path

BIN_OPS = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Mod: "%",
    ast.Pow: "**",
}

UNARY_OPS = {
    ast.UAdd: "+",
    ast.USub: "-",
}


def _expr_to_polish(node: ast.AST) -> str:
    if isinstance(node, ast.BinOp):
        op = BIN_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return f"({op} {_expr_to_polish(node.left)} {_expr_to_polish(node.right)})"
    if isinstance(node, ast.UnaryOp):
        op = UNARY_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return f"({op} {_expr_to_polish(node.operand)})"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def convert_expression(expr: str) -> str:
    parsed = ast.parse(expr, mode="eval")
    return _expr_to_polish(parsed.body)


def main() -> int:
    src = Path("imageCompositeConverterFs/mainFiles")
    if not src.exists():
        print(f"skip: {src} does not exist")
        return 0

    converted = 0
    for path in src.rglob("*.expr"):
        expr = path.read_text(encoding="utf-8").strip()
        if not expr:
            continue
        path.write_text(convert_expression(expr) + "\n", encoding="utf-8")
        converted += 1

    print(f"converted {converted} expression file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
