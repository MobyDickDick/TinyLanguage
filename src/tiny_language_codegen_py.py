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
