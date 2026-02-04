"""Static checks for TinyLanguage programs prior to execution.

The linter enforces style and safety rules such as unused bindings, consistent
import ordering, and exhaustiveness expectations. It runs immediately after
parsing so later stages can assume the IR has already been validated for common
footguns.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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


def _import_binding_name(module: str, alias: Optional[str]) -> str:
    if alias:
        return alias
    stripped = module.lstrip(".") or module
    return stripped.split(".")[-1]


def _lint_error(
    source: Optional[str],
    node: Any,
    message: str,
    *,
    code: str = "E000",
    hint: Optional[str] = None,
    suggestions: Optional[List[str]] = None,
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
    return TinyLangError(rendered, pos, code=code, hint=hint, suggestions=tuple(suggestions or ()), span=span)


@dataclass
class _HeapLifetime:
    may_live: bool = False
    may_freed: bool = False


def _clone_heap_states(states: Dict[str, _HeapLifetime]) -> Dict[str, _HeapLifetime]:
    return {name: _HeapLifetime(state.may_live, state.may_freed) for name, state in states.items()}


def _merge_heap_states(
    left: Dict[str, _HeapLifetime],
    right: Dict[str, _HeapLifetime],
) -> Dict[str, _HeapLifetime]:
    merged: Dict[str, _HeapLifetime] = {}
    for name in set(left) | set(right):
        left_state = left.get(name)
        right_state = right.get(name)
        merged[name] = _HeapLifetime(
            may_live=bool((left_state and left_state.may_live) or (right_state and right_state.may_live)),
            may_freed=bool((left_state and left_state.may_freed) or (right_state and right_state.may_freed)),
        )
    return merged


def _clone_heap_sizes(sizes: Dict[str, Optional[int]]) -> Dict[str, Optional[int]]:
    return dict(sizes)


def _merge_heap_sizes(
    left: Dict[str, Optional[int]],
    right: Dict[str, Optional[int]],
) -> Dict[str, Optional[int]]:
    merged: Dict[str, Optional[int]] = {}
    for name in set(left) | set(right):
        left_size = left.get(name)
        right_size = right.get(name)
        if left_size is None or right_size is None:
            merged[name] = None
        elif left_size == right_size:
            merged[name] = left_size
        else:
            merged[name] = None
    return merged


_INT_LITERAL = re.compile(r"^-?\d+$")


def _int_literal(expr: IR) -> Optional[int]:
    if not isinstance(expr, Num):
        return None
    txt = expr.txt.replace("_", "")
    if not _INT_LITERAL.match(txt):
        return None
    try:
        return int(txt, 10)
    except ValueError:
        return None


def _heap_allocation_size(expr: IR) -> Optional[int]:
    if isinstance(expr, NewLit):
        return len(expr.items)
    if isinstance(expr, New):
        size = _int_literal(expr.size)
        if size is None or size < 0:
            return None
        return size
    if isinstance(expr, Call) and expr.name in {"new", "__new"} and expr.args:
        size = _int_literal(expr.args[0])
        if size is None or size < 0:
            return None
        return size
    return None


def _is_heap_allocation_expr(expr: IR) -> bool:
    if isinstance(expr, (New, NewLit)):
        return True
    if isinstance(expr, Call) and expr.name in {"new", "__new"}:
        return True
    return False


def _heap_pointer_name(expr: IR) -> Optional[str]:
    if isinstance(expr, Var):
        return expr.name
    return None


def _lint_heap_expr(expr: IR, states: Dict[str, _HeapLifetime], source: Optional[str]) -> None:
    if isinstance(expr, Bin):
        _lint_heap_expr(expr.a, states, source)
        _lint_heap_expr(expr.b, states, source)
        return
    if isinstance(expr, Call):
        for arg in expr.args:
            _lint_heap_expr(arg, states, source)
        if expr.name in {"heap_get", "heap_set"} and expr.args:
            ptr_name = _heap_pointer_name(expr.args[0])
            if ptr_name:
                state = states.get(ptr_name)
                if state and state.may_freed:
                    raise _lint_error(
                        source,
                        expr,
                        f"use-after-free: pointer {ptr_name} may have been deleted before {expr.name}",
                        code="E017",
                        hint="Avoid accessing heap pointers after delete or reallocate them first.",
                    )
        if expr.name == "delete" and expr.args:
            ptr_name = _heap_pointer_name(expr.args[0])
            if ptr_name:
                state = states.get(ptr_name)
                if state and state.may_freed:
                    raise _lint_error(
                        source,
                        expr,
                        f"use-after-free: pointer {ptr_name} may have already been deleted",
                        code="E017",
                        hint="Ensure each heap pointer is deleted at most once.",
                    )
                states[ptr_name] = _HeapLifetime(may_live=False, may_freed=True)
        return
    if isinstance(expr, Spawn):
        for arg in expr.args:
            _lint_heap_expr(arg, states, source)
        return
    if isinstance(expr, Await):
        _lint_heap_expr(expr.expr, states, source)
        return
    if isinstance(expr, New):
        _lint_heap_expr(expr.size, states, source)
        return
    if isinstance(expr, NewLit):
        for item in expr.items:
            _lint_heap_expr(item, states, source)
        return
    if isinstance(expr, Field):
        _lint_heap_expr(expr.obj, states, source)
        return
    if isinstance(expr, MethodCall):
        _lint_heap_expr(expr.obj, states, source)
        for arg in expr.args:
            _lint_heap_expr(arg, states, source)
        return
    if isinstance(expr, ClassNew):
        for _, value in expr.init:
            _lint_heap_expr(value, states, source)
        return
    if isinstance(expr, ObjLit):
        for _, value in expr.fields:
            _lint_heap_expr(value, states, source)
        return
    if isinstance(expr, Match):
        _lint_heap_expr(expr.expr, states, source)
        for case in expr.cases:
            _lint_heap_expr(case.body, states, source)
        return
    if isinstance(expr, VariantCtor):
        for _, value in expr.fields:
            _lint_heap_expr(value, states, source)
        return


def _lint_heap_bounds_call(
    name: str,
    args: List[IR],
    sizes: Dict[str, Optional[int]],
    source: Optional[str],
    node: Any,
) -> None:
    if name not in {"heap_get", "heap_set"} or len(args) < 2:
        return
    ptr_name = _heap_pointer_name(args[0])
    if not ptr_name:
        return
    if ptr_name not in sizes:
        return
    idx = _int_literal(args[1])
    if idx is None:
        return
    if idx < 0:
        raise _lint_error(
            source,
            node,
            f"heap index {idx} is negative for pointer {ptr_name}",
            code="E020",
            hint="Heap indices must be zero or positive.",
        )
    size = sizes.get(ptr_name)
    if size is None:
        return
    if idx >= size:
        raise _lint_error(
            source,
            node,
            f"heap index {idx} is out of bounds for {ptr_name} (size {size})",
            code="E020",
            hint="Ensure heap indices stay within the allocated size.",
        )


def _lint_heap_bounds_expr(expr: IR, sizes: Dict[str, Optional[int]], source: Optional[str]) -> None:
    if isinstance(expr, Bin):
        _lint_heap_bounds_expr(expr.a, sizes, source)
        _lint_heap_bounds_expr(expr.b, sizes, source)
        return
    if isinstance(expr, Call):
        for arg in expr.args:
            _lint_heap_bounds_expr(arg, sizes, source)
        _lint_heap_bounds_call(expr.name, expr.args, sizes, source, expr)
        return
    if isinstance(expr, Spawn):
        for arg in expr.args:
            _lint_heap_bounds_expr(arg, sizes, source)
        return
    if isinstance(expr, Await):
        _lint_heap_bounds_expr(expr.expr, sizes, source)
        return
    if isinstance(expr, New):
        _lint_heap_bounds_expr(expr.size, sizes, source)
        return
    if isinstance(expr, NewLit):
        for item in expr.items:
            _lint_heap_bounds_expr(item, sizes, source)
        return
    if isinstance(expr, Field):
        _lint_heap_bounds_expr(expr.obj, sizes, source)
        return
    if isinstance(expr, MethodCall):
        _lint_heap_bounds_expr(expr.obj, sizes, source)
        for arg in expr.args:
            _lint_heap_bounds_expr(arg, sizes, source)
        return
    if isinstance(expr, ClassNew):
        for _, value in expr.init:
            _lint_heap_bounds_expr(value, sizes, source)
        return
    if isinstance(expr, ObjLit):
        for _, value in expr.fields:
            _lint_heap_bounds_expr(value, sizes, source)
        return
    if isinstance(expr, Match):
        _lint_heap_bounds_expr(expr.expr, sizes, source)
        for case in expr.cases:
            _lint_heap_bounds_expr(case.body, sizes, source)
        return
    if isinstance(expr, VariantCtor):
        for _, value in expr.fields:
            _lint_heap_bounds_expr(value, sizes, source)
        return


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
    lint_inferred_return_types(
        fn.body,
        fn.name,
        params=fn.params,
        return_annotation=fn.return_type,
        is_method=False,
        source=source,
    )
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
    lint_inferred_return_types(
        md.body,
        f"{md.class_name}.{md.name}",
        params=md.params,
        return_annotation=md.return_type,
        is_method=True,
        source=source,
    )
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
                    _mark_used(new_state, st.name)
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
    if isinstance(expr, ClassNew):
        return expr.name
    return None




def _normalize_inferred_type(type_name: str) -> str:
    parsed = _parse_type_expression(type_name)
    if not parsed:
        normalized = type_name.strip()
        if normalized.lower() in {"int", "float"}:
            return "number"
        return type_name

    def normalize(node: _ParsedType) -> _ParsedType:
        name = node.name
        if name.strip().lower() in {"int", "float"}:
            name = "number"
        return _ParsedType(name=name, args=[normalize(arg) for arg in node.args], optional=node.optional)

    return _render_type_expression(normalize(parsed))


@dataclass
class _ParsedType:
    name: str
    args: List["_ParsedType"]
    optional: bool = False


def _parse_type_expression(type_name: str) -> Optional[_ParsedType]:
    text = type_name.strip()
    if not text:
        return None
    idx = 0

    def skip_ws() -> None:
        nonlocal idx
        while idx < len(text) and text[idx].isspace():
            idx += 1

    def parse_expr() -> Optional[_ParsedType]:
        nonlocal idx
        skip_ws()
        start = idx
        while idx < len(text) and (text[idx].isalnum() or text[idx] in "._"):
            idx += 1
        if start == idx:
            return None
        name = text[start:idx]
        skip_ws()
        args: List[_ParsedType] = []
        if idx < len(text) and text[idx] == "[":
            idx += 1
            skip_ws()
            if idx < len(text) and text[idx] == "]":
                idx += 1
            else:
                while True:
                    arg = parse_expr()
                    if arg is None:
                        return None
                    args.append(arg)
                    skip_ws()
                    if idx < len(text) and text[idx] == ",":
                        idx += 1
                        continue
                    if idx < len(text) and text[idx] == "]":
                        idx += 1
                        break
                    return None
        skip_ws()
        optional = False
        if idx < len(text) and text[idx] == "?":
            optional = True
            idx += 1
        skip_ws()
        return _ParsedType(name=name, args=args, optional=optional)

    parsed = parse_expr()
    skip_ws()
    if parsed is None or idx != len(text):
        return None
    return parsed


def _render_type_expression(expr: _ParsedType) -> str:
    rendered = expr.name
    if expr.args:
        rendered = f"{rendered}[{', '.join(_render_type_expression(arg) for arg in expr.args)}]"
    if expr.optional:
        rendered = f"{rendered}?"
    return rendered


def _type_name_matches(expected: str, actual: str) -> bool:
    if expected.lower() == actual.lower():
        return True
    if expected.lower() == "number" and actual.lower() in {"number", "int", "float"}:
        return True
    if expected.lower() == "string" and actual.lower() == "string":
        return True
    if expected.lower() in {"bool", "boolean"} and actual.lower() in {"bool", "boolean"}:
        return True
    return False


def _types_match(expected: str, actual: str) -> bool:
    expected_norm = expected.strip()
    actual_norm = actual.strip()
    expected_expr = _parse_type_expression(expected_norm)
    actual_expr = _parse_type_expression(actual_norm)
    if expected_norm.lower() == "pointer" and actual_expr:
        if actual_expr.name.lower() == "list":
            return True
    if expected_expr and expected_expr.name.lower() == "any":
        return True
    if expected_expr and expected_expr.optional:
        if actual_norm.lower() == "null":
            return True
        expected_expr = _ParsedType(name=expected_expr.name, args=expected_expr.args, optional=False)
    if expected_expr and expected_expr.name.lower() == "list" and actual_norm.lower() == "pointer":
        return True
    if expected_expr and actual_expr:
        if actual_expr.optional and not expected_expr.optional:
            return False
        if expected_expr.args:
            if expected_expr.name.lower() in {"list", "set", "deque", "map"}:
                if not _type_name_matches(expected_expr.name, actual_expr.name):
                    return False
                if not actual_expr.args:
                    return False
                if expected_expr.name.lower() == "map" and len(expected_expr.args) != 2:
                    return False
                if len(expected_expr.args) != len(actual_expr.args):
                    return False
                return all(
                    _types_match(_render_type_expression(exp), _render_type_expression(act))
                    for exp, act in zip(expected_expr.args, actual_expr.args)
                )
        if not _type_name_matches(expected_expr.name, actual_expr.name):
            return False
        return True
    if expected_norm.lower() == "any":
        return True
    optional = expected_norm.endswith("?")
    base_expected = expected_norm[:-1].strip() if optional else expected_norm
    if optional and actual_norm.lower() == "null":
        return True
    if _type_name_matches(base_expected, actual_norm):
        return True
    if optional and actual_norm.lower() != "null":
        return _types_match(base_expected, actual_norm)
    return False


@dataclass
class _ClassInfo:
    fields: Dict[str, str]
    bases: List[str]


@dataclass
class _FunctionSignature:
    params: List[Param]
    return_type: Optional[str]


@dataclass
class _TypeInfo:
    fields: Dict[str, str]
    variants: Dict[str, List[Tuple[str, str]]]


@dataclass
class _AnnotationIndex:
    functions: Dict[str, _FunctionSignature]
    classes: Dict[str, _ClassInfo]
    methods: Dict[Tuple[str, str], _FunctionSignature]
    types: Dict[str, _TypeInfo]


@dataclass
class _ModuleSummary:
    name: str
    functions: Dict[str, _FunctionSignature]


def _qualify_name(name: str, prefix: str) -> str:
    return f"{prefix}.{name}" if prefix else name


def _qualify_reference(name: str, prefix: str) -> str:
    if not prefix or "." in name:
        return name
    return f"{prefix}.{name}"


def _collect_annotation_index(stmts: List[IR], prefix: str = "") -> _AnnotationIndex:
    functions: Dict[str, _FunctionSignature] = {}
    classes: Dict[str, _ClassInfo] = {}
    methods: Dict[Tuple[str, str], _FunctionSignature] = {}
    types: Dict[str, _TypeInfo] = {}
    for st in stmts:
        if isinstance(st, Fn):
            functions[_qualify_name(st.name, prefix)] = _FunctionSignature(list(st.params), st.return_type)
        elif isinstance(st, TypeDef):
            type_name = _qualify_name(st.name, prefix)
            fields = dict(st.fields) if st.fields else {}
            variants: Dict[str, List[Tuple[str, str]]] = {}
            if st.variants:
                for variant in st.variants:
                    variants[variant.name] = list(variant.fields)
            types[type_name] = _TypeInfo(fields=fields, variants=variants)
        elif isinstance(st, ClassDef):
            class_name = _qualify_name(st.name, prefix)
            bases = [_qualify_reference(base, prefix) for base in st.bases]
            classes[class_name] = _ClassInfo(fields=dict(st.fields), bases=bases)
            for method in st.methods:
                methods[(class_name, method.name)] = _FunctionSignature(list(method.params), method.return_type)
        elif isinstance(st, Namespace):
            nested_prefix = _qualify_name(st.name, prefix)
            nested = _collect_annotation_index(st.body, prefix=nested_prefix)
            functions.update(nested.functions)
            classes.update(nested.classes)
            methods.update(nested.methods)
            types.update(nested.types)
    return _AnnotationIndex(functions=functions, classes=classes, methods=methods, types=types)


def _module_has_annotations(stmts: List[IR]) -> bool:
    for st in stmts:
        if isinstance(st, Fn):
            if st.return_type or any(param.type for param in st.params):
                return True
        elif isinstance(st, MethodDef):
            if st.return_type or any(param.type for param in st.params):
                return True
        elif isinstance(st, TypeDef):
            if st.fields or st.variants:
                return True
        elif isinstance(st, ClassDef):
            if st.fields:
                return True
            if any(method.return_type or any(param.type for param in method.params) for method in st.methods):
                return True
        elif isinstance(st, Namespace):
            if _module_has_annotations(st.body):
                return True
    return False


def _signature_has_annotations(signature: _FunctionSignature) -> bool:
    return bool(signature.return_type or any(param.type for param in signature.params))


def _implicit_any_warning(
    *,
    kind: str,
    name: str,
    params: List[Param],
    return_type: Optional[str],
    source: Optional[str],
    node: Any,
) -> Optional[TinyLangError]:
    missing_params = [param.name for param in params if not param.type]
    missing_return = return_type is None
    if not missing_params and not missing_return:
        return None
    details = []
    if missing_params:
        details.append(f"unannotated parameter(s): {', '.join(missing_params)}")
    if missing_return:
        details.append("missing return type annotation")
    message = f"Implicit `any` in typed module ({kind} {name}): " + "; ".join(details) + "."
    hint = "Add explicit type annotations or use `any` to document dynamic intent."
    return _lint_error(source, node, message, code="W010", hint=hint)


def lint_implicit_any_usage(stmts: List[IR], source: Optional[str] = None) -> List[TinyLangError]:
    if not _module_has_annotations(stmts):
        return []
    warnings: List[TinyLangError] = []

    def visit(nodes: List[IR], prefix: str = "") -> None:
        for st in nodes:
            if isinstance(st, Fn):
                qualified = _qualify_name(st.name, prefix)
                warning = _implicit_any_warning(
                    kind="function",
                    name=qualified,
                    params=st.params,
                    return_type=st.return_type,
                    source=source,
                    node=st,
                )
                if warning is not None:
                    warnings.append(warning)
            elif isinstance(st, ClassDef):
                class_name = _qualify_name(st.name, prefix)
                for method in st.methods:
                    method_name = f"{class_name}.{method.name}"
                    warning = _implicit_any_warning(
                        kind="method",
                        name=method_name,
                        params=method.params,
                        return_type=method.return_type,
                        source=source,
                        node=method,
                    )
                    if warning is not None:
                        warnings.append(warning)
            elif isinstance(st, Namespace):
                nested_prefix = _qualify_name(st.name, prefix)
                visit(st.body, prefix=nested_prefix)

    visit(stmts)
    return warnings


def _format_summary_params(params: List[Param]) -> str:
    rendered = []
    for param in params:
        param_type = param.type or "any"
        rendered.append(f"{param.name}: {param_type}")
    return ", ".join(rendered)


def _format_type_expression(info: _TypeInfo) -> str:
    if info.variants:
        parts = []
        for variant_name, fields in sorted(info.variants.items()):
            if fields:
                field_parts = [f"{name}: {type_name}" for name, type_name in sorted(fields)]
                parts.append(f"{variant_name}({', '.join(field_parts)})")
            else:
                parts.append(variant_name)
        return " | ".join(parts)
    if info.fields:
        field_parts = [f"{name}: {type_name}" for name, type_name in sorted(info.fields.items())]
        return "{ " + ", ".join(field_parts) + " }"
    return "{}"


def build_module_summary(stmts: List[IR], module_name: str) -> Optional[str]:
    if not module_name or not _module_has_annotations(stmts):
        return None
    index = _collect_annotation_index(stmts)
    lines = [f"module: {module_name}", "", "exports:"]

    exported_functions = []
    for name, signature in sorted(index.functions.items()):
        if not _signature_has_annotations(signature):
            continue
        params = _format_summary_params(signature.params)
        return_type = signature.return_type or "any"
        exported_functions.append(f"  fn {name}({params}) -> {return_type}")
    lines.extend(exported_functions)

    lines.extend(["", "types:"])
    for name, info in sorted(index.types.items()):
        type_expr = _format_type_expression(info)
        lines.append(f"  type {name} = {type_expr}")

    lines.extend(["", "classes:"])
    methods_by_class: Dict[str, List[Tuple[str, _FunctionSignature]]] = {}
    for (class_name, method_name), signature in index.methods.items():
        methods_by_class.setdefault(class_name, []).append((method_name, signature))
    for name, info in sorted(index.classes.items()):
        class_methods = [
            (method_name, signature)
            for method_name, signature in sorted(methods_by_class.get(name, []))
            if _signature_has_annotations(signature)
        ]
        if not info.fields and not class_methods:
            continue
        lines.append(f"  class {name}")
        for field_name, field_type in sorted(info.fields.items()):
            lines.append(f"    field {field_name}: {field_type}")
        for method_name, signature in class_methods:
            params = _format_summary_params(signature.params)
            return_type = signature.return_type or "any"
            lines.append(f"    method {method_name}({params}) -> {return_type}")

    return "\n".join(lines).rstrip() + "\n"


def _base_type_name(type_name: Optional[str]) -> Optional[str]:
    if not type_name:
        return None
    normalized = type_name.strip()
    if normalized.endswith("?"):
        return normalized[:-1].strip()
    return normalized


def _build_variant_type_index(types: Dict[str, _TypeInfo]) -> Dict[str, Optional[str]]:
    variant_index: Dict[str, Optional[str]] = {}
    for type_name, info in types.items():
        if info.variants:
            for variant_name in info.variants:
                existing = variant_index.get(variant_name)
                if existing is None:
                    variant_index[variant_name] = type_name
                elif existing != type_name:
                    variant_index[variant_name] = None
        else:
            existing = variant_index.get(type_name)
            if existing is None:
                variant_index[type_name] = type_name
            elif existing != type_name:
                variant_index[type_name] = None
    return variant_index


def _resolve_method_return(
    classes: Dict[str, _ClassInfo],
    methods: Dict[Tuple[str, str], _FunctionSignature],
    class_name: str,
    method_name: str,
) -> Optional[str]:
    seen: Set[str] = set()
    queue = [class_name]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        signature = methods.get((current, method_name))
        if signature is not None:
            return signature.return_type
        info = classes.get(current)
        if info:
            queue.extend(info.bases)
    return None


def _infer_list_literal_type(
    items: List[IR],
    env: Dict[str, str],
    *,
    functions: Dict[str, _FunctionSignature],
    classes: Dict[str, _ClassInfo],
    methods: Dict[Tuple[str, str], _FunctionSignature],
    variant_types: Dict[str, Optional[str]],
) -> str:
    if not items:
        return "List[any]"
    candidate: Optional[str] = None
    for item in items:
        inferred = _infer_typed_expr_type(
            item,
            env,
            functions=functions,
            classes=classes,
            methods=methods,
            variant_types=variant_types,
        )
        if inferred is None:
            return "List[any]"
        normalized = _normalize_inferred_type(inferred)
        if normalized.lower() == "any":
            return "List[any]"
        if candidate is None:
            candidate = normalized
            continue
        if not (_types_match(candidate, normalized) and _types_match(normalized, candidate)):
            return "List[any]"
    if candidate is None:
        return "List[any]"
    return f"List[{candidate}]"


def _infer_typed_expr_type(
    expr: IR,
    env: Dict[str, str],
    *,
    functions: Dict[str, _FunctionSignature],
    classes: Dict[str, _ClassInfo],
    methods: Dict[Tuple[str, str], _FunctionSignature],
    variant_types: Dict[str, Optional[str]],
) -> Optional[str]:
    if isinstance(expr, (Num, Str, Bool, Null, Var, ClassNew)):
        return _infer_expr_type(expr, env)
    if isinstance(expr, New):
        return "Pointer"
    if isinstance(expr, NewLit):
        return _infer_list_literal_type(
            expr.items,
            env,
            functions=functions,
            classes=classes,
            methods=methods,
            variant_types=variant_types,
        )
    if isinstance(expr, ObjLit):
        return "Struct"
    if isinstance(expr, VariantCtor):
        if expr.type_name:
            return expr.type_name
        return variant_types.get(expr.variant)
    if isinstance(expr, Call):
        signature = functions.get(expr.name)
        if signature and signature.return_type:
            return signature.return_type
        return None
    if isinstance(expr, MethodCall):
        obj_type = _infer_typed_expr_type(
            expr.obj,
            env,
            functions=functions,
            classes=classes,
            methods=methods,
            variant_types=variant_types,
        )
        base_type = _base_type_name(obj_type)
        if base_type:
            return _resolve_method_return(classes, methods, base_type, expr.name)
        return None
    if isinstance(expr, Field):
        obj_type = _infer_typed_expr_type(
            expr.obj,
            env,
            functions=functions,
            classes=classes,
            methods=methods,
            variant_types=variant_types,
        )
        base_type = _base_type_name(obj_type)
        if base_type:
            return _resolve_field_type(classes, base_type, expr.name)
        return None
    return None


def _null_guarded_binding(cond: IR) -> Optional[Tuple[str, bool]]:
    if not isinstance(cond, Bin) or cond.op not in {"==", "!="}:
        return None
    left_var = cond.a.name if isinstance(cond.a, Var) else None
    right_var = cond.b.name if isinstance(cond.b, Var) else None
    if isinstance(cond.a, Null) and right_var:
        return right_var, cond.op == "=="
    if isinstance(cond.b, Null) and left_var:
        return left_var, cond.op == "=="
    return None


def _narrow_env_for_condition(
    cond: IR,
    env: Dict[str, str],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    guard = _null_guarded_binding(cond)
    if not guard:
        return dict(env), dict(env)
    name, is_equal = guard
    current = env.get(name)
    if not _is_optional_annotation(current):
        return dict(env), dict(env)
    base = _base_type_name(current) or current
    then_env = dict(env)
    else_env = dict(env)
    if is_equal:
        then_env[name] = "Null"
        else_env[name] = base
    else:
        then_env[name] = base
        else_env[name] = "Null"
    return then_env, else_env


def _variant_info_for_pattern(
    pattern: VariantPattern,
    *,
    match_type: Optional[str],
    types: Dict[str, _TypeInfo],
    variant_types: Dict[str, Optional[str]],
) -> Tuple[Optional[str], Optional[List[Tuple[str, str]]]]:
    if match_type:
        base = _base_type_name(match_type) or match_type
        info = types.get(base)
        if info and pattern.variant in info.variants:
            return base, info.variants[pattern.variant]
    type_name = variant_types.get(pattern.variant)
    if type_name:
        info = types.get(type_name)
        if info and pattern.variant in info.variants:
            return type_name, info.variants[pattern.variant]
    return None, None


def _pattern_bindings(
    pattern: Pattern,
    *,
    match_type: Optional[str],
    types: Dict[str, _TypeInfo],
    variant_types: Dict[str, Optional[str]],
) -> Tuple[Dict[str, str], Optional[str]]:
    bindings: Dict[str, str] = {}
    if isinstance(pattern, WildcardPattern):
        if pattern.name and match_type:
            bindings[pattern.name] = _normalize_inferred_type(match_type)
        return bindings, match_type
    if isinstance(pattern, VariantPattern):
        type_name, fields = _variant_info_for_pattern(
            pattern,
            match_type=match_type,
            types=types,
            variant_types=variant_types,
        )
        if fields:
            field_map = dict(fields)
            for field_name, binding_name in pattern.bindings.items():
                if not binding_name:
                    continue
                field_type = field_map.get(field_name)
                if field_type:
                    bindings[binding_name] = field_type
            if pattern.positional_bindings:
                for (field_name, field_type), binding_name in zip(fields, pattern.positional_bindings):
                    if binding_name:
                        bindings[binding_name] = field_type
        return bindings, type_name or match_type
    return bindings, match_type


def _resolve_field_type(
    classes: Dict[str, _ClassInfo],
    class_name: str,
    field_name: str,
    *,
    owner_hint: Optional[str] = None,
) -> Optional[str]:
    if owner_hint:
        info = classes.get(owner_hint)
        if info is None and "." not in owner_hint and "." in class_name:
            prefix = class_name.rsplit(".", 1)[0]
            info = classes.get(f"{prefix}.{owner_hint}")
        if info:
            return info.fields.get(field_name)
        return None
    seen: Set[str] = set()
    queue = [class_name]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        info = classes.get(current)
        if not info:
            continue
        if field_name in info.fields:
            return info.fields[field_name]
        queue.extend(info.bases)
    return None


def _resolve_method_params(
    classes: Dict[str, _ClassInfo],
    methods: Dict[Tuple[str, str], List[Param]],
    class_name: str,
    method_name: str,
) -> Optional[List[Param]]:
    seen: Set[str] = set()
    queue = [class_name]
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        params = methods.get((current, method_name))
        if params is not None:
            return params
        info = classes.get(current)
        if info:
            queue.extend(info.bases)
    return None


def _split_summary_params(params_text: str) -> List[Param]:
    normalized = params_text.strip()
    if not normalized:
        return []
    parts: List[str] = []
    buffer: List[str] = []
    depth = 0
    for ch in params_text:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth = max(depth - 1, 0)
        if ch == "," and depth == 0:
            parts.append("".join(buffer).strip())
            buffer = []
            continue
        buffer.append(ch)
    if buffer:
        parts.append("".join(buffer).strip())
    params: List[Param] = []
    for entry in parts:
        if not entry:
            continue
        if ":" in entry:
            name, type_name = entry.split(":", 1)
            params.append(Param(name.strip(), type_name.strip() or None))
        else:
            params.append(Param(entry.strip(), None))
    return params


def _parse_module_summary(summary_text: str) -> Optional[_ModuleSummary]:
    lines = [line.rstrip() for line in summary_text.splitlines()]
    if not lines or not lines[0].startswith("module: "):
        return None
    module_name = lines[0].split("module: ", 1)[1].strip()
    if not module_name:
        return None
    section: Optional[str] = None
    functions: Dict[str, _FunctionSignature] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "exports:":
            section = "exports"
            continue
        if stripped.endswith(":"):
            section = stripped[:-1]
            continue
        if section != "exports":
            continue
        if not stripped.startswith("fn "):
            continue
        header = stripped[len("fn ") :]
        if "(" not in header or ")" not in header:
            continue
        name_part, rest = header.split("(", 1)
        params_part, rest = rest.split(")", 1)
        return_type = None
        rest = rest.strip()
        if rest.startswith("->"):
            return_type = rest[2:].strip() or None
        params = _split_summary_params(params_part)
        functions[name_part.strip()] = _FunctionSignature(params=params, return_type=return_type)
    return _ModuleSummary(name=module_name, functions=functions)


def _iter_imports(stmts: List[IR]) -> List[Import]:
    imports: List[Import] = []
    for st in stmts:
        if isinstance(st, Import):
            imports.append(st)
        elif isinstance(st, Namespace):
            imports.extend(_iter_imports(st.body))
    return imports


def _resolve_import_name(raw: str, caller_namespace: Optional[str]) -> Optional[str]:
    leading = len(raw) - len(raw.lstrip("."))
    if leading == 0:
        return raw
    if not caller_namespace:
        return None
    base = caller_namespace.split(".")
    if leading > len(base):
        return None
    trimmed = base[: len(base) - leading]
    remainder = raw.lstrip(".")
    if remainder:
        trimmed.append(remainder)
    return ".".join(part for part in trimmed if part)


def _summary_paths_for_module(
    module_name: str,
    caller_path: Optional[Path],
    search_paths: List[Path],
    stdlib_root: Path,
) -> List[Path]:
    roots: List[Path] = []
    if module_name.startswith("stdlib."):
        rel_path = Path(*module_name.split(".")[1:])
        if stdlib_root.exists():
            roots.append(stdlib_root)
    else:
        rel_path = Path(*module_name.split("."))
        if caller_path:
            roots.append(caller_path.parent)
        roots.extend(search_paths)
    return [(root / rel_path).with_suffix(".tiny.summary") for root in roots]


def _load_import_summaries(
    stmts: List[IR],
    module_name: Optional[str],
    module_path: Optional[Path],
) -> Dict[str, _ModuleSummary]:
    env_paths = os.environ.get("TINYPATH", "")
    configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
    default_roots = [Path.cwd(), Path(__file__).parent]
    search_paths = configured_paths + default_roots
    stdlib_root = Path(__file__).resolve().parents[1] / "stdlib"
    summaries: Dict[str, _ModuleSummary] = {}
    for st in _iter_imports(stmts):
        resolved = _resolve_import_name(st.module, module_name)
        if not resolved:
            continue
        binding = _import_binding_name(st.module, st.alias)
        if binding in summaries:
            continue
        for summary_path in _summary_paths_for_module(resolved, module_path, search_paths, stdlib_root):
            if not summary_path.is_file():
                continue
            summary = _parse_module_summary(summary_path.read_text(encoding="utf-8"))
            if summary:
                summaries[binding] = summary
            break
    return summaries


def lint_call_validation(
    stmts: List[IR],
    source: Optional[str] = None,
    *,
    module_name: Optional[str] = None,
    module_path: Optional[Path] = None,
) -> None:
    index = _collect_annotation_index(stmts)
    function_params = {name: sig.params for name, sig in index.functions.items()}
    classes = index.classes
    methods = {key: sig.params for key, sig in index.methods.items()}
    variant_types = _build_variant_type_index(index.types)
    module_summaries = _load_import_summaries(stmts, module_name, module_path)

    def validate_call_params(
        *,
        label: str,
        params: List[Param],
        args: List[IR],
        call_site: IR,
        env: Dict[str, str],
    ) -> None:
        if len(args) != len(params):
            msg = f"argument count mismatch for {label}: expected {len(params)} but got {len(args)}"
            raise _lint_error(
                source,
                call_site,
                msg,
                code="E009",
                hint="Adjust the call to pass the expected number of arguments.",
            )
        for param, arg in zip(params, args):
            if not param.type:
                continue
            inferred = _infer_typed_expr_type(
                arg,
                env,
                functions=index.functions,
                classes=index.classes,
                methods=index.methods,
                variant_types=variant_types,
            )
            if inferred and not _types_match(param.type, inferred):
                msg = f"type mismatch for parameter {param.name} in {label}: expected {param.type} but got {inferred}"
                suggestion = (
                    f"If the call site is correct, consider updating the annotation for {param.name} to "
                    f"'{_normalize_inferred_type(inferred)}'."
                )
                raise _lint_error(
                    source,
                    arg,
                    msg,
                    code="E009",
                    hint="Adjust the type annotation (use '?' to allow Null) or pass a compatible value to satisfy the hint.",
                    suggestions=[suggestion],
                )

    def check_expr(expr: IR, env: Dict[str, str]) -> None:
        if isinstance(expr, Bin):
            check_expr(expr.a, env)
            check_expr(expr.b, env)
            return
        if isinstance(expr, Call):
            for arg in expr.args:
                check_expr(arg, env)
            params = function_params.get(expr.name)
            if params:
                validate_call_params(
                    label=f"function {expr.name}",
                    params=list(params),
                    args=expr.args,
                    call_site=expr,
                    env=env,
                )
            return
        if isinstance(expr, MethodCall):
            check_expr(expr.obj, env)
            for arg in expr.args:
                check_expr(arg, env)
            if isinstance(expr.obj, Var):
                summary = module_summaries.get(expr.obj.name)
                if summary:
                    signature = summary.functions.get(expr.name)
                    if signature:
                        validate_call_params(
                            label=f"function {summary.name}.{expr.name}",
                            params=list(signature.params),
                            args=expr.args,
                            call_site=expr,
                            env=env,
                        )
                    return
            obj_type = _infer_typed_expr_type(
                expr.obj,
                env,
                functions=index.functions,
                classes=index.classes,
                methods=index.methods,
                variant_types=variant_types,
            )
            if obj_type:
                base_type = _base_type_name(obj_type) or obj_type
                params = _resolve_method_params(classes, methods, base_type, expr.name)
                if params:
                    expected_params = params[1:]
                    validate_call_params(
                        label=f"method {base_type}.{expr.name}",
                        params=expected_params,
                        args=expr.args,
                        call_site=expr,
                        env=env,
                    )
            return
        if isinstance(expr, Spawn):
            for arg in expr.args:
                check_expr(arg, env)
            params = function_params.get(expr.name)
            if params:
                validate_call_params(
                    label=f"spawned function {expr.name}",
                    params=list(params),
                    args=expr.args,
                    call_site=expr,
                    env=env,
                )
            return
        if isinstance(expr, ClassNew):
            for _, value in expr.init:
                check_expr(value, env)
            return
        if isinstance(expr, Field):
            check_expr(expr.obj, env)
            return
        if isinstance(expr, Await):
            check_expr(expr.expr, env)
            return
        if isinstance(expr, New):
            check_expr(expr.size, env)
            return
        if isinstance(expr, NewLit):
            for item in expr.items:
                check_expr(item, env)
            return
        if isinstance(expr, ObjLit):
            for _, value in expr.fields:
                check_expr(value, env)
            return
        if isinstance(expr, Match):
            check_expr(expr.expr, env)
            match_type = _infer_typed_expr_type(
                expr.expr,
                env,
                functions=index.functions,
                classes=index.classes,
                methods=index.methods,
                variant_types=variant_types,
            )
            for case in expr.cases:
                case_bindings, narrowed_type = _pattern_bindings(
                    case.pattern,
                    match_type=match_type,
                    types=index.types,
                    variant_types=variant_types,
                )
                case_env = dict(env)
                case_env.update(case_bindings)
                if narrowed_type and isinstance(expr.expr, Var):
                    case_env[expr.expr.name] = _normalize_inferred_type(narrowed_type)
                check_expr(case.body, case_env)
            return
        if isinstance(expr, VariantCtor):
            for _, value in expr.fields:
                check_expr(value, env)
            return

    def check_block(block: List[IR], local_env: Dict[str, str]) -> None:
        for st in block:
            if isinstance(st, Let):
                check_expr(st.expr, local_env)
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    local_env[st.name] = _normalize_inferred_type(inferred)
            elif isinstance(st, Assign):
                check_expr(st.expr, local_env)
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    local_env[st.name] = local_env.get(st.name, _normalize_inferred_type(inferred))
            elif isinstance(st, DestructAssign):
                check_expr(st.expr, local_env)
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    for nm in st.names:
                        local_env[nm] = _normalize_inferred_type(inferred)
            elif isinstance(st, FieldAssign):
                check_expr(st.obj, local_env)
                check_expr(st.expr, local_env)
            elif isinstance(st, Print):
                for expr in st.exprs:
                    check_expr(expr, local_env)
            elif isinstance(st, CallStmt):
                check_expr(Call(st.name, st.args, st.pos), local_env)
            elif isinstance(st, Return):
                check_expr(st.expr, local_env)
            elif isinstance(st, If):
                check_expr(st.cond, local_env)
                then_env, else_env = _narrow_env_for_condition(st.cond, local_env)
                check_block(list(st.then), dict(then_env))
                check_block(list(st.els), dict(else_env))
            elif isinstance(st, While):
                check_expr(st.cond, local_env)
                check_block(list(st.body), dict(local_env))
            elif isinstance(st, Switch):
                check_expr(st.expr, local_env)
                for case in st.cases:
                    if case.value is not None:
                        check_expr(case.value, local_env)
                    check_block(list(case.body), dict(local_env))
            elif isinstance(st, TryCatch):
                check_block(list(st.body), dict(local_env))
                handler_env = dict(local_env)
                if st.err_name:
                    handler_env[st.err_name] = "Error"
                check_block(list(st.handler), handler_env)
            elif isinstance(st, TaskBlock):
                check_block(list(st.body), dict(local_env))
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

    check_block(stmts, {})


def lint_annotation_enforcement(stmts: List[IR], source: Optional[str] = None) -> None:
    index = _collect_annotation_index(stmts)
    classes = index.classes
    variant_types = _build_variant_type_index(index.types)

    def check_expr(expr: IR, env: Dict[str, str]) -> None:
        if isinstance(expr, Bin):
            check_expr(expr.a, env)
            check_expr(expr.b, env)
            return
        if isinstance(expr, ClassNew):
            for field_name, value in expr.init:
                check_expr(value, env)
                owner_hint = None
                field_key = field_name
                if "." in field_name:
                    owner_hint, field_key = field_name.split(".", 1)
                expected = _resolve_field_type(classes, expr.name, field_key, owner_hint=owner_hint)
                if expected:
                    inferred = _infer_typed_expr_type(
                        value,
                        env,
                        functions=index.functions,
                        classes=index.classes,
                        methods=index.methods,
                        variant_types=variant_types,
                    )
                    if inferred and not _types_match(expected, inferred):
                        msg = (
                            f"type mismatch for field {field_name} in class {expr.name}: "
                            f"expected {expected} but got {inferred}"
                        )
                        suggestion = (
                            f"Consider updating the field annotation for {field_name} to "
                            f"'{_normalize_inferred_type(inferred)}' if this value is correct."
                        )
                        raise _lint_error(
                            source,
                            value,
                            msg,
                            code="E009",
                            hint="Adjust the type annotation (use '?' to allow Null) or assign a compatible value.",
                            suggestions=[suggestion],
                        )
            return
        if isinstance(expr, Field):
            check_expr(expr.obj, env)
            return
        if isinstance(expr, Await):
            check_expr(expr.expr, env)
            return
        if isinstance(expr, New):
            check_expr(expr.size, env)
            return
        if isinstance(expr, NewLit):
            for item in expr.items:
                check_expr(item, env)
            return
        if isinstance(expr, ObjLit):
            for _, value in expr.fields:
                check_expr(value, env)
            return
        if isinstance(expr, Match):
            check_expr(expr.expr, env)
            match_type = _infer_typed_expr_type(
                expr.expr,
                env,
                functions=index.functions,
                classes=index.classes,
                methods=index.methods,
                variant_types=variant_types,
            )
            for case in expr.cases:
                case_bindings, narrowed_type = _pattern_bindings(
                    case.pattern,
                    match_type=match_type,
                    types=index.types,
                    variant_types=variant_types,
                )
                case_env = dict(env)
                case_env.update(case_bindings)
                if narrowed_type and isinstance(expr.expr, Var):
                    case_env[expr.expr.name] = _normalize_inferred_type(narrowed_type)
                check_expr(case.body, case_env)
            return
        if isinstance(expr, VariantCtor):
            for _, value in expr.fields:
                check_expr(value, env)
            return

    def check_block(
        block: List[IR],
        local_env: Dict[str, str],
        *,
        return_annotation: Optional[str] = None,
        return_label: Optional[str] = None,
    ) -> None:
        for st in block:
            if isinstance(st, Let):
                check_expr(st.expr, local_env)
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    local_env[st.name] = _normalize_inferred_type(inferred)
            elif isinstance(st, Assign):
                check_expr(st.expr, local_env)
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    local_env[st.name] = local_env.get(st.name, _normalize_inferred_type(inferred))
            elif isinstance(st, DestructAssign):
                check_expr(st.expr, local_env)
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    for nm in st.names:
                        local_env[nm] = _normalize_inferred_type(inferred)
            elif isinstance(st, FieldAssign):
                check_expr(st.obj, local_env)
                check_expr(st.expr, local_env)
                obj_type = _infer_typed_expr_type(
                    st.obj,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if obj_type:
                    base_type = _base_type_name(obj_type) or obj_type
                    expected = _resolve_field_type(classes, base_type, st.name)
                    inferred = _infer_typed_expr_type(
                        st.expr,
                        local_env,
                        functions=index.functions,
                        classes=index.classes,
                        methods=index.methods,
                        variant_types=variant_types,
                    )
                    if expected and inferred and not _types_match(expected, inferred):
                        msg = (
                            f"type mismatch for field {st.name} in class {obj_type}: "
                            f"expected {expected} but got {inferred}"
                        )
                        suggestion = (
                            f"Consider updating the field annotation for {st.name} to "
                            f"'{_normalize_inferred_type(inferred)}' if this value is correct."
                        )
                        raise _lint_error(
                            source,
                            st,
                            msg,
                            code="E009",
                            hint="Adjust the type annotation (use '?' to allow Null) or assign a compatible value.",
                            suggestions=[suggestion],
                        )
            elif isinstance(st, Print):
                for expr in st.exprs:
                    check_expr(expr, local_env)
            elif isinstance(st, CallStmt):
                check_expr(Call(st.name, st.args, st.pos), local_env)
            elif isinstance(st, Return):
                check_expr(st.expr, local_env)
            elif isinstance(st, If):
                check_expr(st.cond, local_env)
                then_env, else_env = _narrow_env_for_condition(st.cond, local_env)
                check_block(list(st.then), dict(then_env), return_annotation=return_annotation, return_label=return_label)
                check_block(list(st.els), dict(else_env), return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, While):
                check_expr(st.cond, local_env)
                check_block(list(st.body), dict(local_env), return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, Switch):
                check_expr(st.expr, local_env)
                for case in st.cases:
                    if case.value is not None:
                        check_expr(case.value, local_env)
                    check_block(list(case.body), dict(local_env), return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, TryCatch):
                check_block(list(st.body), dict(local_env), return_annotation=return_annotation, return_label=return_label)
                handler_env = dict(local_env)
                if st.err_name:
                    handler_env[st.err_name] = "Error"
                check_block(list(st.handler), handler_env, return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, TaskBlock):
                check_block(list(st.body), dict(local_env), return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, Namespace):
                check_block(list(st.body), {}, return_annotation=None, return_label=None)
            elif isinstance(st, Fn):
                fn_env = {p.name: p.type for p in st.params if p.type}
                label = f"return value for function {st.name}"
                check_block(list(st.body), fn_env, return_annotation=st.return_type, return_label=label)
            elif isinstance(st, MethodDef):
                method_env = {p.name: p.type for p in st.params if p.type}
                label = f"return value for method {st.class_name}.{st.name}"
                check_block(list(st.body), method_env, return_annotation=st.return_type, return_label=label)
            elif isinstance(st, ClassDef):
                for method in st.methods:
                    method_env = {p.name: p.type for p in method.params if p.type}
                    label = f"return value for method {method.class_name}.{method.name}"
                    check_block(list(method.body), method_env, return_annotation=method.return_type, return_label=label)

    check_block(stmts, {})


def lint_return_validation(stmts: List[IR], source: Optional[str] = None) -> None:
    """Ensure annotated return types match inferred return expression types."""
    index = _collect_annotation_index(stmts)
    variant_types = _build_variant_type_index(index.types)

    def check_block(
        block: List[IR],
        local_env: Dict[str, str],
        *,
        return_annotation: Optional[str] = None,
        return_label: Optional[str] = None,
    ) -> None:
        for st in block:
            if isinstance(st, Let):
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    local_env[st.name] = _normalize_inferred_type(inferred)
            elif isinstance(st, Assign):
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    local_env[st.name] = local_env.get(st.name, _normalize_inferred_type(inferred))
            elif isinstance(st, DestructAssign):
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    for nm in st.names:
                        local_env[nm] = _normalize_inferred_type(inferred)
            elif isinstance(st, Return):
                if return_annotation:
                    inferred = _infer_typed_expr_type(
                        st.expr,
                        local_env,
                        functions=index.functions,
                        classes=index.classes,
                        methods=index.methods,
                        variant_types=variant_types,
                    )
                    if inferred and not _types_match(return_annotation, inferred):
                        msg = (
                            f"type mismatch for {return_label}: expected {return_annotation} but got {inferred}"
                        )
                        suggestion = (
                            f"Consider updating the return annotation to '{_normalize_inferred_type(inferred)}' "
                            "if the returned value is correct."
                        )
                        raise _lint_error(
                            source,
                            st,
                            msg,
                            code="E009",
                            hint="Adjust the type annotation (use '?' to allow Null) or return a compatible value.",
                            suggestions=[suggestion],
                        )
            elif isinstance(st, If):
                then_env, else_env = _narrow_env_for_condition(st.cond, local_env)
                check_block(list(st.then), dict(then_env), return_annotation=return_annotation, return_label=return_label)
                check_block(list(st.els), dict(else_env), return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, While):
                check_block(list(st.body), dict(local_env), return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, Switch):
                for case in st.cases:
                    check_block(list(case.body), dict(local_env), return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, TryCatch):
                check_block(list(st.body), dict(local_env), return_annotation=return_annotation, return_label=return_label)
                handler_env = dict(local_env)
                if st.err_name:
                    handler_env[st.err_name] = "Error"
                check_block(list(st.handler), handler_env, return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, TaskBlock):
                check_block(list(st.body), dict(local_env), return_annotation=return_annotation, return_label=return_label)
            elif isinstance(st, Namespace):
                check_block(list(st.body), {}, return_annotation=None, return_label=None)
            elif isinstance(st, Fn):
                fn_env = {p.name: p.type for p in st.params if p.type}
                label = f"return value for function {st.name}"
                check_block(list(st.body), fn_env, return_annotation=st.return_type, return_label=label)
            elif isinstance(st, MethodDef):
                method_env = {p.name: p.type for p in st.params if p.type}
                label = f"return value for method {st.class_name}.{st.name}"
                check_block(list(st.body), method_env, return_annotation=st.return_type, return_label=label)
            elif isinstance(st, ClassDef):
                for method in st.methods:
                    method_env = {p.name: p.type for p in method.params if p.type}
                    label = f"return value for method {method.class_name}.{method.name}"
                    check_block(list(method.body), method_env, return_annotation=method.return_type, return_label=label)

    check_block(stmts, {})


def lint_assignment_types(stmts: List[IR], source: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> None:
    env = dict(env or {})
    index = _collect_annotation_index(stmts)
    variant_types = _build_variant_type_index(index.types)

    def check_block(block: List[IR], local_env: Dict[str, str]) -> Dict[str, str]:
        for st in block:
            if isinstance(st, Let):
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    local_env[st.name] = _normalize_inferred_type(inferred)
            elif isinstance(st, Assign):
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
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
                    local_env[st.name] = expected or _normalize_inferred_type(inferred)
            elif isinstance(st, DestructAssign):
                inferred = _infer_typed_expr_type(
                    st.expr,
                    local_env,
                    functions=index.functions,
                    classes=index.classes,
                    methods=index.methods,
                    variant_types=variant_types,
                )
                if inferred:
                    for nm in st.names:
                        local_env[nm] = _normalize_inferred_type(inferred)
            elif isinstance(st, If):
                then_branch, else_branch = _narrow_env_for_condition(st.cond, local_env)
                then_env = check_block(list(st.then), dict(then_branch))
                else_env = check_block(list(st.els), dict(else_branch))
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
                    inferred = _infer_typed_expr_type(
                        arg,
                        local_env,
                        functions=index.functions,
                        classes=index.classes,
                        methods=index.methods,
                        variant_types=variant_types,
                    )
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
        "Regex.",
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
                raise _lint_error(source, st, msg, code="E001", hint=hint)
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
        if isinstance(st.cond, Bool):
            if st.cond.value:
                return _block_guarantees_return(st.then)
            return _block_guarantees_return(st.els)
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


def lint_inferred_return_types(
    stmts: List[IR],
    fn_name: str,
    *,
    params: List[Param],
    return_annotation: Optional[str],
    is_method: bool,
    source: Optional[str],
) -> None:
    if return_annotation is not None:
        return
    expected: Optional[str] = None
    hint = "Add an explicit return type annotation or keep return values consistent to avoid implicit type changes."

    def record_return(st: Return, local_env: Dict[str, str]) -> None:
        nonlocal expected
        inferred = _infer_expr_type(st.expr, local_env)
        if inferred is None:
            return
        if expected is None:
            expected = inferred
            return
        if not _types_match(expected, inferred):
            kind = "method" if is_method else "function"
            msg = f"inferred return type for {kind} {fn_name} changed: expected {expected} but got {inferred}"
            raise _lint_error(source, st, msg, code="E014", hint=hint)

    def check_block(block: List[IR], local_env: Dict[str, str]) -> None:
        for st in block:
            if isinstance(st, Let):
                inferred = _infer_expr_type(st.expr, local_env)
                if inferred:
                    local_env[st.name] = inferred
            elif isinstance(st, Assign):
                inferred = _infer_expr_type(st.expr, local_env)
                if inferred:
                    local_env[st.name] = inferred
            elif isinstance(st, DestructAssign):
                inferred = _infer_expr_type(st.expr, local_env)
                if inferred:
                    for nm in st.names:
                        local_env[nm] = inferred
            elif isinstance(st, Return):
                record_return(st, local_env)
            elif isinstance(st, If):
                check_block(list(st.then), dict(local_env))
                check_block(list(st.els), dict(local_env))
            elif isinstance(st, While):
                check_block(list(st.body), dict(local_env))
            elif isinstance(st, Switch):
                for case in st.cases:
                    check_block(list(case.body), dict(local_env))
            elif isinstance(st, TryCatch):
                check_block(list(st.body), dict(local_env))
                handler_env = dict(local_env)
                if st.err_name:
                    handler_env[st.err_name] = "Error"
                check_block(list(st.handler), handler_env)
            elif isinstance(st, TaskBlock):
                check_block(list(st.body), dict(local_env))
            elif isinstance(st, Namespace):
                continue
            elif isinstance(st, (Fn, MethodDef, ClassDef)):
                continue

    env = {p.name: p.type for p in params if p.type}
    check_block(stmts, env)


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
                if isinstance(st.cond, Bool):
                    if st.cond.value:
                        visit_block(st.then)
                    else:
                        visit_block(st.els)
                else:
                    visit_block(st.then)
                    visit_block(st.els)
            elif isinstance(st, While):
                if not (isinstance(st.cond, Bool) and not st.cond.value):
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


def lint_heap_lifetimes(stmts: List[IR], source: Optional[str] = None) -> None:
    """Lint for heap pointer use-after-free, ownership, aliasing, and bounds issues."""

    def visit_block(
        block: List[IR],
        states: Dict[str, _HeapLifetime],
        sizes: Dict[str, Optional[int]],
    ) -> None:
        for st in block:
            if isinstance(st, (Let, Assign)):
                _lint_heap_expr(st.expr, states, source)
                _lint_heap_bounds_expr(st.expr, sizes, source)
                alias = _heap_pointer_name(st.expr)
                if alias and alias in sizes and alias != st.name:
                    raise _lint_error(
                        source,
                        st,
                        f"heap pointer ownership violation: {st.name} now aliases {alias}",
                        code="E019",
                        hint="Heap pointers use a single-owner model; copy data or allocate a new buffer instead.",
                    )
                if _is_heap_allocation_expr(st.expr):
                    existing = states.get(st.name)
                    if existing and existing.may_live:
                        raise _lint_error(
                            source,
                            st,
                            f"heap pointer {st.name} is overwritten without delete",
                            code="E018",
                            hint="Delete the previous heap allocation before rebinding this variable.",
                        )
                    states[st.name] = _HeapLifetime(may_live=True, may_freed=False)
                    sizes[st.name] = _heap_allocation_size(st.expr)
                else:
                    existing = states.get(st.name)
                    if existing and existing.may_live:
                        raise _lint_error(
                            source,
                            st,
                            f"heap pointer {st.name} is dropped without delete",
                            code="E018",
                            hint="Delete the heap allocation before assigning a non-pointer value.",
                        )
                    if existing:
                        states.pop(st.name, None)
                    sizes.pop(st.name, None)
            elif isinstance(st, FieldAssign):
                _lint_heap_expr(st.obj, states, source)
                _lint_heap_expr(st.expr, states, source)
                _lint_heap_bounds_expr(st.obj, sizes, source)
                _lint_heap_bounds_expr(st.expr, sizes, source)
            elif isinstance(st, Print):
                for expr in st.exprs:
                    _lint_heap_expr(expr, states, source)
                    _lint_heap_bounds_expr(expr, sizes, source)
            elif isinstance(st, CallStmt):
                for arg in st.args:
                    _lint_heap_expr(arg, states, source)
                    _lint_heap_bounds_expr(arg, sizes, source)
                if st.name in {"heap_get", "heap_set"} and st.args:
                    ptr_name = _heap_pointer_name(st.args[0])
                    if ptr_name:
                        state = states.get(ptr_name)
                        if state and state.may_freed:
                            raise _lint_error(
                                source,
                                st,
                                f"use-after-free: pointer {ptr_name} may have been deleted before {st.name}",
                                code="E017",
                                hint="Avoid accessing heap pointers after delete or reallocate them first.",
                            )
                _lint_heap_bounds_call(st.name, st.args, sizes, source, st)
                if st.name == "delete" and st.args:
                    ptr_name = _heap_pointer_name(st.args[0])
                    if ptr_name:
                        state = states.get(ptr_name)
                        if state and state.may_freed:
                            raise _lint_error(
                                source,
                                st,
                                f"use-after-free: pointer {ptr_name} may have already been deleted",
                                code="E017",
                                hint="Ensure each heap pointer is deleted at most once.",
                            )
                        states[ptr_name] = _HeapLifetime(may_live=False, may_freed=True)
                        sizes.pop(ptr_name, None)
            elif isinstance(st, If):
                _lint_heap_expr(st.cond, states, source)
                _lint_heap_bounds_expr(st.cond, sizes, source)
                then_states = _clone_heap_states(states)
                els_states = _clone_heap_states(states)
                then_sizes = _clone_heap_sizes(sizes)
                els_sizes = _clone_heap_sizes(sizes)
                visit_block(st.then, then_states, then_sizes)
                visit_block(st.els, els_states, els_sizes)
                merged = _merge_heap_states(then_states, els_states)
                merged_sizes = _merge_heap_sizes(then_sizes, els_sizes)
                states.clear()
                states.update(merged)
                sizes.clear()
                sizes.update(merged_sizes)
            elif isinstance(st, While):
                _lint_heap_expr(st.cond, states, source)
                _lint_heap_bounds_expr(st.cond, sizes, source)
                body_states = _clone_heap_states(states)
                body_sizes = _clone_heap_sizes(sizes)
                visit_block(st.body, body_states, body_sizes)
                merged = _merge_heap_states(states, body_states)
                merged_sizes = _merge_heap_sizes(sizes, body_sizes)
                states.clear()
                states.update(merged)
                sizes.clear()
                sizes.update(merged_sizes)
            elif isinstance(st, Switch):
                _lint_heap_expr(st.expr, states, source)
                _lint_heap_bounds_expr(st.expr, sizes, source)
                case_states: List[Dict[str, _HeapLifetime]] = []
                case_sizes: List[Dict[str, Optional[int]]] = []
                for case in st.cases:
                    if case.value is not None:
                        _lint_heap_expr(case.value, states, source)
                        _lint_heap_bounds_expr(case.value, sizes, source)
                    branch_states = _clone_heap_states(states)
                    branch_sizes = _clone_heap_sizes(sizes)
                    visit_block(case.body, branch_states, branch_sizes)
                    case_states.append(branch_states)
                    case_sizes.append(branch_sizes)
                if case_states:
                    merged = case_states[0]
                    for branch_states in case_states[1:]:
                        merged = _merge_heap_states(merged, branch_states)
                    states.clear()
                    states.update(merged)
                if case_sizes:
                    merged_sizes = case_sizes[0]
                    for branch_sizes in case_sizes[1:]:
                        merged_sizes = _merge_heap_sizes(merged_sizes, branch_sizes)
                    sizes.clear()
                    sizes.update(merged_sizes)
            elif isinstance(st, TryCatch):
                body_states = _clone_heap_states(states)
                handler_states = _clone_heap_states(states)
                body_sizes = _clone_heap_sizes(sizes)
                handler_sizes = _clone_heap_sizes(sizes)
                visit_block(st.body, body_states, body_sizes)
                visit_block(st.handler, handler_states, handler_sizes)
                merged = _merge_heap_states(body_states, handler_states)
                merged_sizes = _merge_heap_sizes(body_sizes, handler_sizes)
                states.clear()
                states.update(merged)
                sizes.clear()
                sizes.update(merged_sizes)
            elif isinstance(st, TaskBlock):
                visit_block(st.body, states, sizes)
            elif isinstance(st, Return):
                _lint_heap_expr(st.expr, states, source)
                _lint_heap_bounds_expr(st.expr, sizes, source)
            elif isinstance(st, DestructAssign):
                _lint_heap_expr(st.expr, states, source)
                _lint_heap_bounds_expr(st.expr, sizes, source)
            elif isinstance(st, Namespace):
                visit_block(st.body, {}, {})
            elif isinstance(st, Fn):
                visit_block(st.body, {}, {})
            elif isinstance(st, MethodDef):
                visit_block(st.body, {}, {})
            elif isinstance(st, ClassDef):
                for method in st.methods:
                    visit_block(method.body, {}, {})

    visit_block(stmts, {}, {})


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
