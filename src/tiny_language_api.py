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
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

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
        lint_assignment_types,
        lint_bare_call_results,
        lint_destruct_call_outputs,
        lint_fn_params_used,
        lint_import_style,
        lint_locals_used,
        lint_method_params_used,
        lint_no_consecutive_definitions,
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
    lint_no_consecutive_definitions(stmts)
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
        location = pos if pos is not None else pos_for_error
        leading = len(raw) - len(raw.lstrip("."))
        if leading == 0:
            return raw
        if not caller_namespace:
            raise TinyLangError(
                format_error("", location or SourcePos.origin(), "relative import outside a module", code="E008"),
                pos_for_error or SourcePos.origin(),
                code="E008",
            )
        base = caller_namespace.split(".")
        if leading > len(base):
            raise TinyLangError(
                format_error(
                    "",
                    location or SourcePos.origin(),
                    "relative import traverses beyond module root",
                    code="E008",
                ),
                pos_for_error or SourcePos.origin(),
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
        vm: NativeVM,
        *,
        caller_namespace: Optional[str],
        caller_path: Optional[Path],
        pos: Optional[Any] = None,
    ) -> NativeNamespaceRef:
        resolved_name = self._resolve_name(name, caller_namespace, pos)
        pos_for_error = pos.start if isinstance(pos, SourceSpan) else pos
        location = pos if pos is not None else pos_for_error
        for candidate in self._candidate_paths(resolved_name, caller_path):
            resolved_path = candidate.resolve()
            cached = self.cache.get(resolved_path)
            if cached is not None:
                return cached
            if resolved_path.exists():
                if resolved_path in self._in_progress:
                    raise TinyLangError(
                        format_error(
                            "",
                            location or SourcePos.origin(),
                            f"circular import involving {resolved_path}",
                            code="E008",
                        ),
                        pos_for_error or SourcePos.origin(),
                        code="E008",
                    )
                self._in_progress.append(resolved_path)
                try:
                    module_env: dict[str, Any] = {}
                    stmts = _parse_and_lint(resolved_path.read_text(encoding="utf-8"))
                    program = NativeCodeGenerator(allow_heap=True, module_namespace=resolved_name).compile_program(
                        stmts
                    )
                    vm.load_module(resolved_name, program, module_env, resolved_path)
                    ns_ref = NativeNamespaceRef(resolved_name)
                    self.cache[resolved_path] = ns_ref
                    return ns_ref
                finally:
                    self._in_progress.remove(resolved_path)
        raise TinyLangError(
            format_error("", pos or SourcePos.origin(), f"module '{name}' not found on search path", code="E008"),
            pos or SourcePos.origin(),
            code="E008",
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


def compile_to_llvm_ir(
    src: str,
    *,
    target_triple: Optional[str] = None,
    data_layout: Optional[str] = None,
    llvm_opt: bool = False,
) -> str:
    """Emit textual LLVM IR for the subset supported by the native backend."""
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator(allow_heap=True).compile_program(stmts)
    llvm_ir = LLVMCodeGenerator(target_triple=target_triple, data_layout=data_layout).compile_program(program)
    if llvm_opt:
        llvm_ir = _optimize_llvm_ir(llvm_ir)
    return llvm_ir


def compile_to_c_source(src: str) -> str:
    """Emit C source for the subset supported by the native backend."""
    stmts = _parse_and_lint(src)
    program = NativeCodeGenerator().compile_program(stmts)
    return CCodeGenerator().compile_program(program)


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
    program = NativeCodeGenerator(allow_heap=True, module_namespace=module_namespace).compile_program(stmts)
    resolver = module_resolver or NativeModuleResolver()
    vm = NativeVM(module_resolver=resolver, module_namespace=module_namespace, module_path=module_path)
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
        program = NativeCodeGenerator(allow_heap=True).compile_program(stmts)
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
    program = NativeCodeGenerator(allow_heap=True).compile_program(stmts)
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
]
