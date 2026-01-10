"""Parser that turns TinyLanguage tokens into AST nodes.

The parser consumes tokens from ``Lexer`` and builds the lightweight IR objects
defined in ``tiny_language_ast.py``. Error spans are attached eagerly so later
stages (linter, runtime) can surface precise diagnostics without re-parsing the
source text.
"""

# ----- Parser -----


class Parser:
    def __init__(self, lx: Lexer, source: str):
        self.lx = lx
        self.source = source
        self.tok = lx.next_token()
        self._last_tok = Token("<start>", "", SourcePos.origin(), SourcePos.origin())
        self._allow_variant_ctor = True

    @staticmethod
    def _attach_span(node: IR, start: SourcePos, stop: SourcePos) -> IR:
        node.span = SourceSpan(start, stop)
        try:
            current_pos = node.pos  # type: ignore[attr-defined]
        except Exception:
            current_pos = None
        if current_pos is None or current_pos == SourcePos.origin():
            node.pos = start
        return node

    @staticmethod
    def _node_start(node: IR) -> SourcePos:
        span = getattr(node, "span", None)
        return span.start if span is not None else getattr(node, "pos")

    @staticmethod
    def _node_stop(node: IR) -> SourcePos:
        span = getattr(node, "span", None)
        return span.stop if span is not None else getattr(node, "pos")

    @classmethod
    def _span_cover(cls, a: IR, b: IR) -> SourceSpan:
        start = cls._node_start(a)
        stop = cls._node_stop(b)
        return SourceSpan(start, stop)

    def _error(self, message: str, pos: SourcePos, span: Optional[SourceSpan] = None) -> TinyLangError:
        code, hint = _classify_error(message)
        effective_pos = span.start if span else pos
        rendered = format_error(self.source, span or pos, message, code=code, hint=hint)
        return TinyLangError(rendered, effective_pos, code=code, hint=hint, span=span)

    @staticmethod
    def _tok_span(tok: Token) -> SourceSpan:
        return SourceSpan(tok.start, tok.stop)

    @staticmethod
    def _token_description(tok: Token) -> str:
        if tok.kind == "EOF":
            return "EOF"
        if tok.text:
            return f"{tok.kind} {tok.text}"
        return tok.kind

    def _eat(self, kind: str, text: Optional[str] = None) -> Token:
        if self.tok.kind != kind or (text is not None and self.tok.text != text):
            expected = f"{kind}{' '+text if text else ''}"
            got = self._token_description(self.tok)
            raise self._error(f"expected {expected}, got {got}", self.tok.pos, self._tok_span(self.tok))
        t = self.tok
        self.tok = self.lx.next_token()
        self._last_tok = t
        return t

    def _eat_name_or_kw(self) -> Token:
        if self.tok.kind in {"NAME", "KW"}:
            t = self.tok
            self.tok = self.lx.next_token()
            self._last_tok = t
            return t
        got = self._token_description(self.tok)
        raise self._error(f"expected NAME, got {got}", self.tok.pos, self._tok_span(self.tok))

    def _accept(self, kind: str, text: Optional[str] = None) -> bool:
        if self.tok.kind == kind and (text is None or self.tok.text == text):
            t = self.tok
            self.tok = self.lx.next_token()
            self._last_tok = t
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
        if self.tok.kind == "KW" and self.tok.text == "def":
            kw = self._eat("KW", "def")
            name_tok = self._eat("NAME")
            self._eat("SYM", "=")
            expr = self.parse_expr()
            semi = self._eat("SYM", ";")
            name_span = self._tok_span(name_tok)
            return self._attach_span(
                Let(name_tok.text, expr, pos=kw.pos, name_span=name_span), kw.start, semi.stop
            )
        if self.tok.kind == "KW" and self.tok.text == "print":
            kw = self._eat("KW", "print")
            self._eat("SYM", "(")
            exprs: List[IR] = []
            if not (self.tok.kind == "SYM" and self.tok.text == ")"):
                exprs.append(self.parse_expr())
                while self._accept("SYM", ","):
                    exprs.append(self.parse_expr())
            self._eat("SYM", ")")
            semi = self._eat("SYM", ";")
            return self._attach_span(Print(exprs, pos=kw.pos), kw.start, semi.stop)
        if self.tok.kind == "KW" and self.tok.text == "flush":
            kw = self._eat("KW", "flush")
            self._eat("SYM", "(")
            self._eat("SYM", ")")
            semi = self._eat("SYM", ";")
            return self._attach_span(Flush(pos=kw.pos), kw.start, semi.stop)
        if self.tok.kind == "KW" and self.tok.text == "if":
            kw = self._eat("KW", "if")
            self._eat("SYM", "(")
            cond = self.parse_expr()
            self._eat("SYM", ")")
            then = self.parse_block()
            els: List[IR] = []
            if self.tok.kind == "KW" and self.tok.text == "else":
                self._eat("KW", "else")
                els = self.parse_block()
            return self._attach_span(If(cond, then, els, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "while":
            kw = self._eat("KW", "while")
            self._eat("SYM", "(")
            cond = self.parse_expr()
            self._eat("SYM", ")")
            body = self.parse_block()
            return self._attach_span(While(cond, body, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "switch":
            kw = self._eat("KW", "switch")
            self._eat("SYM", "(")
            target = self.parse_expr()
            self._eat("SYM", ")")
            self._eat("SYM", "{")
            cases: List[SwitchCase] = []
            has_default = False
            while not self._accept("SYM", "}"):
                if self.tok.kind == "KW" and self.tok.text == "case":
                    case_kw = self._eat("KW", "case")
                    value = self.parse_expr()
                    self._eat("SYM", ":")
                    body = self.parse_block()
                    cases.append(
                        self._attach_span(
                            SwitchCase(value, body, pos=case_kw.pos),
                            case_kw.start,
                            self._last_tok.stop,
                        )
                    )
                    continue
                if self.tok.kind == "KW" and self.tok.text == "default":
                    default_kw = self._eat("KW", "default")
                    if has_default:
                        raise self._error("duplicate default case", default_kw.pos, self._tok_span(default_kw))
                    has_default = True
                    self._eat("SYM", ":")
                    body = self.parse_block()
                    cases.append(
                        self._attach_span(
                            SwitchCase(None, body, pos=default_kw.pos),
                            default_kw.start,
                            self._last_tok.stop,
                        )
                    )
                    continue
                raise self._error("expected case or default", self.tok.pos, self._tok_span(self.tok))
            return self._attach_span(Switch(target, cases, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "try":
            kw = self._eat("KW", "try")
            body = self.parse_block()
            self._eat("KW", "catch")
            err_name = None
            if self._accept("SYM", "("):
                err_name = self._eat("NAME").text
                self._eat("SYM", ")")
            else:
                err_name = self._eat("NAME").text
            handler = self.parse_block()
            return self._attach_span(TryCatch(body, err_name, handler, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "task":
            kw = self._eat("KW", "task")
            body = self.parse_block()
            return self._attach_span(TaskBlock(body, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "import":
            kw = self._eat("KW", "import")
            module, module_span = self.parse_module_path()
            alias: Optional[str] = None
            binding_span = module_span
            if self.tok.kind == "KW" and self.tok.text == "as":
                self._eat("KW", "as")
                alias_tok = self._eat("NAME")
                alias = alias_tok.text
                binding_span = self._tok_span(alias_tok)
            semi = self._eat("SYM", ";")
            return self._attach_span(
                Import(
                    module,
                    alias,
                    pos=kw.pos,
                    module_span=module_span,
                    binding_span=binding_span,
                ),
                kw.start,
                semi.stop,
            )
        if self.tok.kind == "KW" and self.tok.text == "namespace":
            kw = self._eat("KW", "namespace")
            name = self.parse_qualified_name()
            body = self.parse_block()
            return self._attach_span(Namespace(name, body, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text in {"fn", "async"}:
            is_async = False
            if self.tok.text == "async":
                self._eat("KW", "async")
                is_async = True
                fn_kw = self._eat("KW", "fn")
            else:
                fn_kw = self._eat("KW", "fn")
            name_tok = self._eat("NAME")
            params = self.parse_param_list()
            return_type = None
            if self._accept("OP", "-"):
                self._eat("OP", ">")
                return_type = self.parse_type_annotation()
            body = self.parse_block()
            return_params = self._collect_return_param_usage(body, {p.name for p in params})
            return self._attach_span(
                Fn(
                    name_tok.text,
                    params,
                    body,
                    return_param_names=return_params,
                    return_type=return_type,
                    is_async=is_async,
                    pos=fn_kw.pos,
                ),
                fn_kw.start,
                self._last_tok.stop,
            )
        if self.tok.kind == "KW" and self.tok.text == "return":
            kw = self._eat("KW", "return")
            expr = self.parse_expr()
            semi = self._eat("SYM", ";")
            return self._attach_span(Return(expr, pos=kw.pos), kw.start, semi.stop)
        if self.tok.kind == "KW" and self.tok.text == "type":
            kw = self._eat("KW", "type")
            name_tok = self._eat("NAME")

            def _parse_product_fields() -> Tuple[List[Tuple[str, str]], Token]:
                self._eat("SYM", "{")
                fields: List[Tuple[str, str]] = []
                semi = self._last_tok
                while not self._accept("SYM", "}"):
                    fname = self._eat("NAME").text
                    self._eat("SYM", ":")
                    ftype = self._eat_name_or_kw().text
                    semi = self._eat("SYM", ";")
                    fields.append((fname, ftype))
                return fields, semi

            def _parse_sum_variants() -> Tuple[List[TypeVariant], Token, Optional[List[Tuple[str, str]]]]:
                self._eat("SYM", "{")
                variants: List[TypeVariant] = []
                semi = self._last_tok
                # Distinguish between legacy product types (field list) and
                # sum types (variant list) by peeking for an early ':'.
                if self.tok.kind == "NAME":
                    first_name_tok = self._eat("NAME")
                    if self._accept("SYM", ":"):
                        first_type = self._eat_name_or_kw().text
                        semi = self._eat("SYM", ";")
                        fields: List[Tuple[str, str]] = [(first_name_tok.text, first_type)]
                        while not self._accept("SYM", "}"):
                            fname = self._eat("NAME").text
                            self._eat("SYM", ":")
                            ftype = self._eat_name_or_kw().text
                            semi = self._eat("SYM", ";")
                            fields.append((fname, ftype))
                        return [], semi, fields
                    # otherwise treat it as a variant name and fall through
                    variants.append(TypeVariant(first_name_tok.text, self.parse_variant_fields()))
                    semi = self._eat("SYM", ";")
                while not self._accept("SYM", "}"):
                    vname = self._eat("NAME").text
                    vfields = self.parse_variant_fields()
                    semi = self._eat("SYM", ";")
                    variants.append(TypeVariant(vname, vfields))
                return variants, semi, None

            if self._accept("SYM", "="):
                kind_tok = self._eat_name_or_kw()
                kind = kind_tok.text
                if kind == "product":
                    fields, semi = _parse_product_fields()
                    return self._attach_span(TypeDef(name_tok.text, fields=fields, pos=kw.pos), kw.start, semi.stop)
                if kind == "sum":
                    variants, semi, legacy_fields = _parse_sum_variants()
                    if legacy_fields is not None:
                        return self._attach_span(TypeDef(name_tok.text, fields=legacy_fields, pos=kw.pos), kw.start, semi.stop)
                    return self._attach_span(TypeDef(name_tok.text, variants=variants, pos=kw.pos), kw.start, self._last_tok.stop)
                raise self._error(f"unknown type kind {kind!r}", kind_tok.pos, self._tok_span(kind_tok))

            # Backwards-compatible parsing without an explicit '=' keyword.
            variants = []
            parsed_variants, semi, legacy_fields = _parse_sum_variants()
            if legacy_fields is not None:
                return self._attach_span(TypeDef(name_tok.text, fields=legacy_fields, pos=kw.pos), kw.start, semi.stop)
            return self._attach_span(TypeDef(name_tok.text, variants=parsed_variants, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "class":
            kw = self._eat("KW", "class")
            cname_tok = self._eat("NAME")
            bases: List[str] = []
            if self._accept("SYM", ":"):
                bases.append(self._eat("NAME").text)
                while self._accept("SYM", ","):
                    bases.append(self._eat("NAME").text)
            self._eat("SYM", "{")
            fields: List[Tuple[str, str]] = []
            methods: List[MethodDef] = []
            while not (self.tok.kind == "SYM" and self.tok.text == "}"):
                if self.tok.kind == "KW" and self.tok.text in {"fn", "async"}:
                    is_async = False
                    if self.tok.text == "async":
                        self._eat("KW", "async")
                        is_async = True
                        fn_kw = self._eat("KW", "fn")
                    else:
                        fn_kw = self._eat("KW", "fn")
                    mname_tok = self._eat_name_or_kw()
                    params = self.parse_param_list()
                    return_type = None
                    if self._accept("OP", "-"):
                        self._eat("OP", ">")
                        return_type = self.parse_type_annotation()
                    body = self.parse_block()
                    return_params = self._collect_return_param_usage(body, {p.name for p in params})
                    methods.append(
                        MethodDef(
                            cname_tok.text,
                            mname_tok.text,
                            params,
                            body,
                            return_param_names=return_params,
                            return_type=return_type,
                            namespace=cname_tok.text,
                            is_async=is_async,
                            pos=fn_kw.pos,
                        )
                    )
                else:
                    fname = self._eat("NAME").text
                    self._eat("SYM", ":")
                    ftype = self._eat("NAME").text
                    self._eat("SYM", ";")
                    fields.append((fname, ftype))
            self._eat("SYM", "}")
            return self._attach_span(ClassDef(cname_tok.text, fields, methods, bases, pos=kw.pos), kw.start, self._last_tok.stop)
        if self.tok.kind == "KW" and self.tok.text == "operator":
            kw = self._eat("KW", "operator")
            op_tok = self._eat("OP")
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
            return self._attach_span(
                OpDef(op_tok.text, a_name, a_type, b_name, b_type, body, pos=kw.pos), kw.start, self._last_tok.stop
            )
        # destructuring or assignment/field assignment
        if self.tok.kind == "SYM" and self.tok.text == "{":
            names, start_pos, name_spans = self.parse_destruct_names()
            self._eat("SYM", "=")
            expr = self.parse_expr()
            semi = self._eat("SYM", ";")
            return self._attach_span(
                DestructAssign(names, expr, pos=start_pos, name_spans=name_spans), start_pos, semi.stop
            )
        if self.tok.kind == "NAME":
            # look ahead for field assignment or normal assignment/call
            name_tok = self.tok
            self._eat("NAME")
            if self._accept("SYM", "."):
                field_name = self._eat_name_or_kw().text
                if self._accept("SYM", "="):
                    expr = self.parse_expr()
                    semi = self._eat("SYM", ";")
                    return self._attach_span(
                        FieldAssign(Var(name_tok.text, pos=name_tok.pos), field_name, expr, pos=name_tok.pos),
                        name_tok.start,
                        semi.stop,
                    )
                # method call statement
                args = self.parse_arg_list()
                semi = self._eat("SYM", ";")
                return self._attach_span(
                    CallStmt(f"{name_tok.text}.{field_name}", args, pos=name_tok.pos), name_tok.start, semi.stop
                )
            if self._accept("SYM", "="):
                expr = self.parse_expr()
                semi = self._eat("SYM", ";")
                name_span = self._tok_span(name_tok)
                return self._attach_span(
                    Assign(name_tok.text, expr, pos=name_tok.pos, name_span=name_span), name_tok.start, semi.stop
                )
            # call statement on identifier
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                semi = self._eat("SYM", ";")
                return self._attach_span(CallStmt(name_tok.text, args, pos=name_tok.pos), name_tok.start, semi.stop)
            raise self._error("unexpected token after name", name_tok.pos, self._tok_span(name_tok))
        raise self._error(f"unexpected token {self.tok.kind}", self.tok.pos, self._tok_span(self.tok))

    def parse_param(self) -> Param:
        name_tok = self._eat("NAME")
        annotation = None
        if self._accept("SYM", ":"):
            annotation = self.parse_type_annotation()
        return Param(name_tok.text, annotation)

    def parse_param_list(self) -> List[Param]:
        self._eat("SYM", "(")
        params: List[Param] = []
        if not (self.tok.kind == "SYM" and self.tok.text == ")"):
            params.append(self.parse_param())
            while self._accept("SYM", ","):
                params.append(self.parse_param())
        self._eat("SYM", ")")
        return params

    def _collect_return_param_usage(self, stmts: List[IR], param_names: Set[str]) -> Set[str]:
        used: Set[str] = set()

        def visit_expr(expr: IR) -> None:
            if isinstance(expr, Var):
                if expr.name in param_names:
                    used.add(expr.name)
                return
            if isinstance(expr, Field):
                visit_expr(expr.obj)
                return
            if isinstance(expr, MethodCall):
                visit_expr(expr.obj)
                for arg in expr.args:
                    visit_expr(arg)
                return
            if isinstance(expr, Call):
                if expr.name in param_names:
                    used.add(expr.name)
                for arg in expr.args:
                    visit_expr(arg)
                return
            if isinstance(expr, Spawn):
                for arg in expr.args:
                    visit_expr(arg)
                return
            if isinstance(expr, Await):
                visit_expr(expr.expr)
                return
            if isinstance(expr, Bin):
                visit_expr(expr.a)
                visit_expr(expr.b)
                return
            if isinstance(expr, ObjLit):
                for _, val in expr.fields:
                    visit_expr(val)
                return
            if isinstance(expr, VariantCtor):
                for _, val in expr.fields:
                    visit_expr(val)
                return
            if isinstance(expr, ClassNew):
                for _, val in expr.init:
                    visit_expr(val)
                return
            if isinstance(expr, NewLit):
                for val in expr.items:
                    visit_expr(val)
                return
            if isinstance(expr, Match):
                visit_expr(expr.expr)
                for case in expr.cases:
                    visit_expr(case.body)
                return

        def visit_stmt(stmt: IR) -> None:
            if isinstance(stmt, Return):
                visit_expr(stmt.expr)
            elif isinstance(stmt, If):
                for child in stmt.then:
                    visit_stmt(child)
                for child in stmt.els:
                    visit_stmt(child)
            elif isinstance(stmt, While):
                for child in stmt.body:
                    visit_stmt(child)
            elif isinstance(stmt, Switch):
                visit_expr(stmt.expr)
                for case in stmt.cases:
                    if case.value is not None:
                        visit_expr(case.value)
                    for child in case.body:
                        visit_stmt(child)
            elif isinstance(stmt, TryCatch):
                for child in stmt.body:
                    visit_stmt(child)
                for child in stmt.handler:
                    visit_stmt(child)
            elif isinstance(stmt, TaskBlock):
                for child in stmt.body:
                    visit_stmt(child)
            elif isinstance(stmt, Namespace):
                for child in stmt.body:
                    visit_stmt(child)
            elif isinstance(stmt, Fn) or isinstance(stmt, MethodDef):
                return

        for st in stmts:
            visit_stmt(st)
        return used

    def parse_type_annotation(self) -> str:
        name = self._eat_name_or_kw().text
        if self._accept("SYM", "?"):
            return f"{name}?"
        return name

    def parse_arg_list(self) -> List[IR]:
        self._eat("SYM", "(")
        args: List[IR] = []
        if not (self.tok.kind == "SYM" and self.tok.text == ")"):
            args.append(self.parse_expr())
            while self._accept("SYM", ","):
                args.append(self.parse_expr())
        self._eat("SYM", ")")
        return args

    def parse_destruct_names(self) -> Tuple[List[str], SourcePos, List[SourceSpan]]:
        start_tok = self._eat("SYM", "{")
        names: List[str] = []
        spans: List[SourceSpan] = []
        first = self._eat("NAME")
        names.append(first.text)
        spans.append(self._tok_span(first))
        while self._accept("SYM", ","):
            name_tok = self._eat("NAME")
            names.append(name_tok.text)
            spans.append(self._tok_span(name_tok))
        self._eat("SYM", "}")
        return names, start_tok.pos, spans

    # expression parsing with precedence
    def parse_expr(self) -> IR:
        return self.parse_logic_or()

    def parse_logic_or(self) -> IR:
        left = self.parse_logic_and()
        while (
            (self.tok.kind == "KW" and self.tok.text == "or")
            or (self.tok.kind == "OP" and self.tok.text == "||")
        ):
            op_tok = self.tok
            self._eat(self.tok.kind)
            right = self.parse_logic_and()
            left = self._attach_span(Bin("or", left, right, pos=op_tok.pos), self._span_cover(left, right).start, self._span_cover(left, right).stop)
        return left

    def parse_logic_and(self) -> IR:
        left = self.parse_compare()
        while (
            (self.tok.kind == "KW" and self.tok.text == "and")
            or (self.tok.kind == "OP" and self.tok.text == "&&")
        ):
            op_tok = self.tok
            self._eat(self.tok.kind)
            right = self.parse_compare()
            span = self._span_cover(left, right)
            left = self._attach_span(Bin("and", left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_compare(self) -> IR:
        left = self.parse_term()
        while self.tok.kind == "OP" and self.tok.text in (">", ">=", "<", "<=", "==", "!="):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_term()
            span = self._span_cover(left, right)
            left = self._attach_span(Bin(op, left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_term(self) -> IR:
        left = self.parse_factor()
        while self.tok.kind == "OP" and self.tok.text in ("+", "-"):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_factor()
            span = self._span_cover(left, right)
            left = self._attach_span(Bin(op, left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_factor(self) -> IR:
        left = self.parse_power()
        while self.tok.kind == "OP" and self.tok.text in ("*", "/", "%"):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_power()
            span = self._span_cover(left, right)
            left = self._attach_span(Bin(op, left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_power(self) -> IR:
        left = self.parse_unary()
        if self.tok.kind == "OP" and self.tok.text == "^":
            op_tok = self._eat("OP")
            right = self.parse_power()
            span = self._span_cover(left, right)
            return self._attach_span(Bin("^", left, right, pos=op_tok.pos), span.start, span.stop)
        return left

    def parse_unary(self) -> IR:
        if self.tok.kind == "OP" and self.tok.text == "-":
            op_tok = self._eat("OP")
            rhs = self.parse_unary()
            span = self._span_cover(Num("0", pos=op_tok.pos), rhs)
            return self._attach_span(Bin("-", Num("0", pos=op_tok.pos), rhs, pos=op_tok.pos), span.start, span.stop)
        if (self.tok.kind == "KW" and self.tok.text == "not") or (
            self.tok.kind == "OP" and self.tok.text == "!"
        ):
            op_tok = self.tok
            self._eat(self.tok.kind)
            rhs = self.parse_unary()
            span = self._span_cover(Num("0", pos=op_tok.pos), rhs)
            return self._attach_span(Bin("not", Num("0", pos=op_tok.pos), rhs, pos=op_tok.pos), span.start, span.stop)
        return self.parse_postfix()

    def parse_postfix(self) -> IR:
        expr = self.parse_primary()
        while True:
            if self.tok.kind == "SYM" and self.tok.text == ".":
                dot_tok = self._eat("SYM", ".")
                name_tok = self._eat_name_or_kw()
                if self.tok.kind == "SYM" and self.tok.text == "(":
                    args = self.parse_arg_list()
                    expr = self._attach_span(
                        MethodCall(expr, name_tok.text, args, pos=dot_tok.pos),
                        self._node_start(expr),
                        self._last_tok.stop,
                    )
                else:
                    expr = self._attach_span(
                        Field(expr, name_tok.text, pos=dot_tok.pos),
                        self._node_start(expr),
                        name_tok.stop,
                    )
                continue
            break
        return expr

    def parse_match(self) -> Match:
        kw = self._eat("KW", "match")
        prev_allow = self._allow_variant_ctor
        self._allow_variant_ctor = False
        try:
            target = self.parse_expr()
        finally:
            self._allow_variant_ctor = prev_allow
        self._eat("SYM", "{")
        cases: List[MatchCase] = []
        while not self._accept("SYM", "}"):
            if not (self.tok.kind == "KW" and self.tok.text == "case"):
                raise self._error("expected case", self.tok.pos, self._tok_span(self.tok))
            self._eat("KW", "case")
            pattern = self.parse_pattern()
            if self._accept("SYM", ":"):
                pass
            elif self._accept("SYM", "="):
                if not self._accept("OP", ">"):
                    raise self._error("expected '=>'", self.tok.pos, self._tok_span(self.tok))
            else:
                raise self._error("expected ':' or '=>'", self.tok.pos, self._tok_span(self.tok))
            body = self.parse_expr()
            semi = self._eat("SYM", ";")
            cases.append(self._attach_span(MatchCase(pattern, body, pos=pattern.pos), pattern.pos, semi.stop))
        return self._attach_span(Match(target, cases, pos=kw.pos), kw.start, self._last_tok.stop)

    def parse_pattern(self) -> Pattern:
        if self.tok.kind == "NAME" and self.tok.text == "_":
            tok = self._eat("NAME")
            return self._attach_span(WildcardPattern(name=None, pos=tok.pos), tok.start, tok.stop)
        if self.tok.kind != "NAME":
            raise self._error("expected pattern", self.tok.pos, self._tok_span(self.tok))
        vname_tok = self._eat("NAME")
        bindings: Dict[str, Optional[str]] = {}
        positional: Optional[List[Optional[str]]] = None
        if self._accept("SYM", "{"):
            while not self._accept("SYM", "}"):
                fname = self._eat("NAME").text
                bind_name: Optional[str] = fname
                if self._accept("SYM", ":"):
                    bind_tok = self._eat_name_or_kw()
                    bind_name = None if bind_tok.text == "_" else bind_tok.text
                bindings[fname] = bind_name
                if self._accept("SYM", "}"):
                    break
                if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                    raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
        elif self._accept("SYM", "("):
            positional = []
            while not self._accept("SYM", ")"):
                bind_tok = self._eat_name_or_kw()
                positional.append(None if bind_tok.text == "_" else bind_tok.text)
                if self._accept("SYM", ")"):
                    break
                if not (self._accept("SYM", ",") or self._accept("SYM", ";")):
                    raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
        return self._attach_span(
            VariantPattern(vname_tok.text, bindings, positional_bindings=positional, pos=vname_tok.pos),
            vname_tok.start,
            self._last_tok.stop,
        )

    def parse_primary(self) -> IR:
        if self._accept("SYM", "("):
            inner = self.parse_expr()
            self._eat("SYM", ")")
            return inner
        if self.tok.kind == "KW" and self.tok.text == "await":
            kw = self._eat("KW", "await")
            expr = self.parse_expr()
            end = self._node_stop(expr)
            return self._attach_span(Await(expr, pos=kw.pos), kw.start, end)
        if self.tok.kind == "KW" and self.tok.text == "match":
            return self.parse_match()
        if self.tok.kind == "NUMBER":
            t = self._eat("NUMBER")
            return self._attach_span(Num(t.text, pos=t.pos), t.start, t.stop)
        if self.tok.kind == "STRING":
            t = self._eat("STRING")
            return self._attach_span(Str(t.text, pos=t.pos), t.start, t.stop)
        if self.tok.kind == "KW" and self.tok.text in {"true", "false"}:
            kw = self.tok
            val = kw.text == "true"
            self._eat("KW")
            return self._attach_span(Bool(val, pos=kw.pos), kw.start, kw.stop)
        if self.tok.kind == "KW" and self.tok.text == "Null":
            kw = self._eat("KW")
            return self._attach_span(Null(pos=kw.pos), kw.start, kw.stop)
        if self.tok.kind in {"NAME", "KW"}:
            name_tok = self._eat(self.tok.kind)
            name = name_tok.text
            if name == "spawn":
                target = self._eat_name_or_kw().text
                args = self.parse_arg_list()
                return self._attach_span(Spawn(target, args, pos=name_tok.pos), name_tok.start, self._last_tok.stop)
            if name == "new" and self.tok.kind == "SYM" and self.tok.text == "[":
                start_tok = self._eat("SYM", "[")
                items: List[IR] = []
                if not (self.tok.kind == "SYM" and self.tok.text == "]"):
                    items.append(self.parse_expr())
                    while self._accept("SYM", ","):
                        items.append(self.parse_expr())
                self._eat("SYM", "]")
                return self._attach_span(NewLit(items, pos=start_tok.pos), start_tok.start, self._last_tok.stop)
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                return self._attach_span(Call(name, args, pos=name_tok.pos), name_tok.start, self._last_tok.stop)
            if name == "new" and self.tok.kind == "NAME":
                cname = self._eat("NAME").text
                start_tok = self._eat("SYM", "{")
                init: List[Tuple[str, IR]] = []
                while not self._accept("SYM", "}"):
                    fname = self.parse_field_name()
                    self._eat("SYM", ":")
                    fexpr = self.parse_expr()
                    init.append((fname, fexpr))
                    if self._accept("SYM", "}"):
                        break
                    if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                        raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
                return self._attach_span(ClassNew(cname, init, pos=name_tok.pos), name_tok.start, self._last_tok.stop)
            if self._allow_variant_ctor and self.tok.kind == "SYM" and self.tok.text == "{":
                fields = self.parse_variant_init_fields()
                return self._attach_span(VariantCtor(name, fields, pos=name_tok.pos), name_tok.start, self._last_tok.stop)
            return self._attach_span(Var(name, pos=name_tok.pos), name_tok.start, name_tok.stop)
        if self.tok.kind == "SYM" and self.tok.text == "{":
            start_tok = self._eat("SYM", "{")
            fields: List[Tuple[str, IR]] = []
            while not self._accept("SYM", "}"):
                fname = self.parse_field_name()
                self._eat("SYM", ":")
                fexpr = self.parse_expr()
                fields.append((fname, fexpr))
                if self._accept("SYM", "}"):
                    break
                if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                    raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
            return self._attach_span(ObjLit(fields, pos=start_tok.pos), start_tok.start, self._last_tok.stop)
        raise self._error(f"unexpected token {self.tok.kind}", self.tok.pos, self._tok_span(self.tok))

    def parse_field_name(self) -> str:
        name = self._eat("NAME").text
        if self._accept("SYM", "."):
            sub = self._eat("NAME").text
            return f"{name}.{sub}"
        return name

    def parse_variant_fields(self) -> List[Tuple[str, str]]:
        fields: List[Tuple[str, str]] = []
        if self._accept("SYM", "{") or self._accept("SYM", "("):
            closing = "}" if self._last_tok.text == "{" else ")"
            while not self._accept("SYM", closing):
                fname = self._eat("NAME").text
                self._eat("SYM", ":")
                ftype = self._eat_name_or_kw().text
                fields.append((fname, ftype))
                if self._accept("SYM", closing):
                    break
                if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                    raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
        return fields

    def parse_variant_init_fields(self) -> List[Tuple[str, IR]]:
        start_tok = self._eat("SYM", "{")
        fields: List[Tuple[str, IR]] = []
        while not self._accept("SYM", "}"):
            fname = self._eat("NAME").text
            self._eat("SYM", ":")
            fexpr = self.parse_expr()
            fields.append((fname, fexpr))
            if self._accept("SYM", "}"):
                break
            if not (self._accept("SYM", ";") or self._accept("SYM", ",")):
                raise self._error("expected field separator", self.tok.pos, self._tok_span(self.tok))
        return fields

    def parse_module_path(self) -> Tuple[str, SourceSpan]:
        prefix = ""
        start_tok: Optional[Token] = None
        while self._accept("SYM", "."):
            start_tok = start_tok or self._last_tok
            prefix += "."
        if self.tok.kind != "NAME":
            raise self._error("expected NAME", self.tok.pos, self._tok_span(self.tok))
        first_tok = self._eat("NAME")
        parts = [first_tok.text]
        last_tok = first_tok
        while self._accept("SYM", "."):
            last_tok = self._eat("NAME")
            parts.append(last_tok.text)
        start = (start_tok or first_tok).start
        span = SourceSpan(start, last_tok.stop)
        return prefix + ".".join(parts), span

    def parse_qualified_name(self) -> str:
        parts = [self._eat("NAME").text]
        while self._accept("SYM", "."):
            parts.append(self._eat("NAME").text)
        return ".".join(parts)
