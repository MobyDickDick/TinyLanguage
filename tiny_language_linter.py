# ----- Linter -----


def _param_names(params: List[Param]) -> List[str]:
    return [p.name for p in params]


def uses_in_expr(e: IR, reads: Dict[str, int]) -> None:
    if isinstance(e, Var):
        reads[e.name] = reads.get(e.name, 0) + 1
    elif isinstance(e, Bin):
        uses_in_expr(e.a, reads)
        uses_in_expr(e.b, reads)
    elif isinstance(e, Call):
        for a in e.args:
            uses_in_expr(a, reads)
    elif isinstance(e, Spawn):
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


def lint_stmt_reads(s: IR, reads: Dict[str, int]) -> None:
    if isinstance(s, (Let, Assign)):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, FieldAssign):
        uses_in_expr(s.obj, reads)
        uses_in_expr(s.expr, reads)
    elif isinstance(s, Print):
        for expr in s.exprs:
            uses_in_expr(expr, reads)
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
    elif isinstance(s, TryCatch):
        for t in s.body:
            lint_stmt_reads(t, reads)
        handler_reads: Dict[str, int] = {}
        for t in s.handler:
            lint_stmt_reads(t, handler_reads)
        if s.err_name:
            # Mark the catch binding as referenced if it is consumed inside the handler
            if handler_reads.get(s.err_name, 0) == 0:
                handler_reads[s.err_name] = 0
        for name, count in handler_reads.items():
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, Return):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, OpDef):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp)
        miss = []
        if not s.a_name.startswith("_") and tmp.get(s.a_name, 0) == 0:
            miss.append(s.a_name)
        if not s.b_name.startswith("_") and tmp.get(s.b_name, 0) == 0:
            miss.append(s.b_name)
        if miss:
            raise RuntimeError(f"unused operator parameter(s) in op {s.op}: {', '.join(miss)}")
        for name, count in tmp.items():
            if name in {s.a_name, s.b_name}:
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, DestructAssign):
        uses_in_expr(s.expr, reads)
    elif isinstance(s, MethodDef):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp)
        param_names = _param_names(s.params)
        miss = [p for p in param_names if not p.startswith("_") and tmp.get(p, 0) == 0]
        if miss:
            raise RuntimeError(
                f"unused parameter(s) in method {s.class_name}.{s.name}: {', '.join(miss)}"
            )
        for name, count in tmp.items():
            if name in set(param_names):
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, Fn):
        tmp: Dict[str, int] = {}
        for t in s.body:
            lint_stmt_reads(t, tmp)
        param_names = _param_names(s.params)
        for name, count in tmp.items():
            if name in set(param_names):
                continue
            reads[name] = max(reads.get(name, 0), count)
    elif isinstance(s, ClassDef):
        for m in s.methods:
            lint_stmt_reads(m, reads)
    elif isinstance(s, Namespace):
        for t in s.body:
            lint_stmt_reads(t, reads)
    elif isinstance(s, CallStmt):
        for arg in s.args:
            uses_in_expr(arg, reads)


def lint_fn_params_used(fn: Fn, source: Optional[str] = None) -> None:
    reads: Dict[str, int] = {}
    for st in fn.body:
        lint_stmt_reads(st, reads)
    param_names = _param_names(fn.params)
    unused = [p for p in param_names if not p.startswith("_") and reads.get(p, 0) == 0]
    if unused:
        msg = f"unused parameter(s) in function {fn.name}: {', '.join(unused)}"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, fn.pos, msg, code="E002", hint="Remove the unused parameter or reference it."),
            fn.pos,
            code="E002",
            hint="Remove the unused parameter or reference it.",
        )
    lint_param_mutations_returned(fn.body, set(param_names), fn.name, is_method=False, source=source, pos=fn.pos)
    lint_destruct_call_outputs(fn.body, source)
    lint_return_signatures(fn.body, fn.name, is_method=False, source=source, pos=fn.pos)
    lint_return_exhaustiveness(
        fn.body, fn.name, expected_return=fn.return_type, is_method=False, source=source, pos=fn.pos
    )
    lint_locals_used(fn.body, source)


def lint_method_params_used(md: MethodDef, source: Optional[str] = None) -> None:
    reads: Dict[str, int] = {}
    for st in md.body:
        lint_stmt_reads(st, reads)
    param_names = _param_names(md.params)
    unused = [p for p in param_names if not p.startswith("_") and reads.get(p, 0) == 0]
    if unused:
        msg = f"unused parameter(s) in method {md.class_name}.{md.name}: {', '.join(unused)}"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, md.pos, msg, code="E002", hint="Remove the unused parameter or reference it."),
            md.pos,
            code="E002",
            hint="Remove the unused parameter or reference it.",
        )
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
        pos=md.pos,
    )
    lint_locals_used(md.body, source)


def lint_locals_used(stmts: List[IR], source: Optional[str] = None) -> None:
    defs: Dict[str, SourcePos] = {}
    uses: Dict[str, int] = {}

    def collect_defs(block: List[IR]) -> None:
        for idx, s in enumerate(block):
            if isinstance(s, Let):
                defs[s.name] = s.pos
            elif isinstance(s, Import):
                defs[_import_binding_name(s.module, s.alias)] = s.pos
            elif isinstance(s, DestructAssign):
                for nm in s.names:
                    defs[nm] = s.pos
            elif isinstance(s, TryCatch):
                collect_defs(s.body)
                if s.err_name:
                    defs[s.err_name] = s.pos
                collect_defs(s.handler)
            elif isinstance(s, If):
                collect_defs(s.then)
                collect_defs(s.els)
            elif isinstance(s, While):
                collect_defs(s.body)
            elif isinstance(s, Namespace):
                collect_defs(s.body)

    collect_defs(stmts)
    for s in stmts:
        lint_stmt_reads(s, uses)
    unused = [n for n in defs if not n.startswith("_") and uses.get(n, 0) == 0]
    if unused:
        pos = defs[unused[0]]
        msg = f"unused local binding(s): {', '.join(unused)}"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, pos, msg, code="E002", hint="Remove the unused binding or reference it."),
            pos,
            code="E002",
            hint="Remove the unused binding or reference it.",
        )


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


def lint_bare_call_results(
    stmts: List[IR], signatures: Dict[str, Optional[str]], source: Optional[str] = None
) -> None:
    disallowed: set[str] = {name for name, ret in signatures.items() if ret not in {None, "Null"}}

    def visit(block: List[IR]) -> None:
        for st in block:
            if isinstance(st, CallStmt):
                if st.name in disallowed:
                    hint = "Assign the return value or explicitly acknowledge it with `_ = ...;`."
                    msg = f"call to {st.name} returns a value that is ignored"
                    if source is None:
                        raise RuntimeError(msg)
                    raise TinyLangError(
                        format_error(source, st.pos, msg, code="E011", hint=hint),
                        st.pos,
                        code="E011",
                        hint=hint,
                    )
            if isinstance(st, If):
                visit(st.then)
                visit(st.els)
            elif isinstance(st, While):
                visit(st.body)
            elif isinstance(st, TryCatch):
                visit(st.body)
                visit(st.handler)
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
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, first_misordered.pos, msg, code="E012", hint=hint),
            first_misordered.pos,
            code="E012",
            hint=hint,
        )

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
        if isinstance(st, TryCatch):
            if _block_guarantees_return(st.body) and _block_guarantees_return(st.handler):
                return True
        elif isinstance(st, While):
            continue
        elif isinstance(st, (Fn, MethodDef, ClassDef, Namespace)):
            continue
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
                    if source is None:
                        raise RuntimeError(msg)
                    raise TinyLangError(format_error(source, st.pos, msg, code="E007", hint=hint), st.pos, code="E007", hint=hint)
            elif isinstance(st, If):
                visit(st.then)
                visit(st.els)
            elif isinstance(st, While):
                visit(st.body)
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
    pos: SourcePos,
) -> None:
    if expected_return is None:
        return
    if _is_optional_annotation(expected_return):
        return
    if _block_guarantees_return(stmts):
        return
    kind = "method" if is_method else "function"
    msg = f"not all paths in {kind} {fn_name} return a value for annotated type {expected_return}"
    if source is None:
        raise RuntimeError(msg)
    raise TinyLangError(
        format_error(
            source,
            pos,
            msg,
            code="E010",
            hint="Add return statements for every branch or provide a default return to satisfy the annotation.",
        ),
        pos,
        code="E010",
        hint="Add return statements for every branch or provide a default return to satisfy the annotation.",
    )


def lint_no_consecutive_definitions(stmts: List[IR]) -> None:
    prev: Optional[str] = None

    def check_block(block: List[IR]) -> None:
        nonlocal prev
        prev = None
        for st in block:
            if isinstance(st, (If, While)):
                lint_no_consecutive_definitions(st.then if isinstance(st, If) else st.body)
                if isinstance(st, If):
                    lint_no_consecutive_definitions(st.els)
                prev = None
                continue
            if isinstance(st, Fn):
                lint_no_consecutive_definitions(st.body)
                prev = None
                continue
            if isinstance(st, MethodDef):
                lint_no_consecutive_definitions(st.body)
                prev = None
                continue
            if isinstance(st, ClassDef):
                for m in st.methods:
                    lint_no_consecutive_definitions(m.body)
                prev = None
                continue
            if isinstance(st, Namespace):
                lint_no_consecutive_definitions(st.body)
                prev = None
                continue
            if isinstance(st, TryCatch):
                lint_no_consecutive_definitions(st.body)
                lint_no_consecutive_definitions(st.handler)
                prev = None
                continue

            current: Optional[str] = None
            if isinstance(st, Let):
                current = st.name

            if current is not None and prev == current:
                raise RuntimeError(f"variable {current} defined twice in a row")

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


def check_destruct_call_expr(expr: IR, names: set[str], *, source: Optional[str], pos: SourcePos) -> None:
    if isinstance(expr, Call):
        skip = {"heap_set", "heap_get", "delete", "tag", "__new", "new"}
        if expr.name in skip:
            return
        missing = sorted({arg.name for arg in expr.args if isinstance(arg, Var) and arg.name not in names})
        if missing:
            msg = f"destructuring call to {expr.name} must include output for argument(s): {', '.join(missing)}"
            if source:
                raise TinyLangError(
                    format_error(
                        source,
                        pos,
                        msg,
                        code="E006",
                        hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
                    ),
                    pos,
                    code="E006",
                    hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
                )
            raise RuntimeError(msg)
    elif isinstance(expr, MethodCall):
        missing = sorted({arg.name for arg in expr.args if isinstance(arg, Var) and arg.name not in names})
        if missing:
            msg = f"destructuring method call to {expr.name} must include output for argument(s): {', '.join(missing)}"
            if source:
                raise TinyLangError(
                    format_error(
                        source,
                        pos,
                        msg,
                        code="E006",
                        hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
                    ),
                    pos,
                    code="E006",
                    hint="Add the missing binding(s) to the destructuring pattern so each referenced argument is captured.",
                )
            raise RuntimeError(msg)


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
        elif isinstance(st, While):
            for body_stmt in st.body:
                visit(body_stmt)

    for st in stmts:
        visit(st)

    missing = sorted(mutated - returned)
    if missing:
        kind = "method" if is_method else "function"
        msg = f"mutated parameter(s) in {kind} {fn_name} must be returned: {', '.join(missing)}"
        if source is None:
            raise RuntimeError(msg)
        raise TinyLangError(
            format_error(source, pos, msg, code="E001", hint="Return the mutated parameters so callers receive the updates."),
            pos,
            code="E001",
            hint="Return the mutated parameters so callers receive the updates.",
        )


