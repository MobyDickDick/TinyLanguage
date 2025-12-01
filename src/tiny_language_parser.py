# ----- Parser -----


class Parser:
    def __init__(self, lx: Lexer, source: str):
        self.lx = lx
        self.source = source
        self.tok = lx.next_token()
        self._allow_variant_ctor = True

    def _error(self, message: str, pos: SourcePos, span: Optional[SourceSpan] = None) -> TinyLangError:
        code, hint = _classify_error(message)
        effective_pos = span.start if span else pos
        rendered = format_error(self.source, span or pos, message, code=code, hint=hint)
        return TinyLangError(rendered, effective_pos, code=code, hint=hint, span=span)

    @staticmethod
    def _tok_span(tok: Token) -> SourceSpan:
        return SourceSpan(tok.start, tok.stop)

    def _eat(self, kind: str, text: Optional[str] = None) -> Token:
        if self.tok.kind != kind or (text is not None and self.tok.text != text):
            raise self._error(f"expected {kind}{' '+text if text else ''}", self.tok.pos, self._tok_span(self.tok))
        t = self.tok
        self.tok = self.lx.next_token()
        return t

    def _eat_name_or_kw(self) -> Token:
        if self.tok.kind in {"NAME", "KW"}:
            t = self.tok
            self.tok = self.lx.next_token()
            return t
        raise self._error("expected NAME", self.tok.pos, self._tok_span(self.tok))

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
            kw = self._eat("KW", "define")
            name_tok = self._eat("NAME")
            self._eat("SYM", "=")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return Let(name_tok.text, expr, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "print":
            kw = self._eat("KW", "print")
            self._eat("SYM", "(")
            exprs: List[IR] = []
            if not (self.tok.kind == "SYM" and self.tok.text == ")"):
                exprs.append(self.parse_expr())
                while self._accept("SYM", ","):
                    exprs.append(self.parse_expr())
            self._eat("SYM", ")")
            self._eat("SYM", ";")
            return Print(exprs, pos=kw.pos)
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
            return If(cond, then, els, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "while":
            kw = self._eat("KW", "while")
            self._eat("SYM", "(")
            cond = self.parse_expr()
            self._eat("SYM", ")")
            body = self.parse_block()
            return While(cond, body, pos=kw.pos)
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
            return TryCatch(body, err_name, handler, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "import":
            kw = self._eat("KW", "import")
            module = self.parse_module_path()
            alias: Optional[str] = None
            if self.tok.kind == "KW" and self.tok.text == "as":
                self._eat("KW", "as")
                alias = self._eat("NAME").text
            self._eat("SYM", ";")
            return Import(module, alias, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "namespace":
            kw = self._eat("KW", "namespace")
            name = self.parse_qualified_name()
            body = self.parse_block()
            return Namespace(name, body, pos=kw.pos)
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
            return Fn(
                name_tok.text,
                params,
                body,
                return_type=return_type,
                is_async=is_async,
                pos=fn_kw.pos,
            )
        if self.tok.kind == "KW" and self.tok.text == "return":
            kw = self._eat("KW", "return")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return Return(expr, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "type":
            kw = self._eat("KW", "type")
            name_tok = self._eat("NAME")
            self._eat("SYM", "{")
            variants: List[TypeVariant] = []
            # Distinguish between legacy product types (field list) and
            # sum types (variant list) by peeking for an early ':'.
            if self.tok.kind == "NAME":
                first_name_tok = self._eat("NAME")
                if self._accept("SYM", ":"):
                    first_type = self._eat_name_or_kw().text
                    self._eat("SYM", ";")
                    fields: List[Tuple[str, str]] = [(first_name_tok.text, first_type)]
                    while not self._accept("SYM", "}"):
                        fname = self._eat("NAME").text
                        self._eat("SYM", ":")
                        ftype = self._eat_name_or_kw().text
                        self._eat("SYM", ";")
                        fields.append((fname, ftype))
                    return TypeDef(name_tok.text, fields=fields, pos=kw.pos)
                # otherwise treat it as a variant name and fall through
                variants.append(TypeVariant(first_name_tok.text, self.parse_variant_fields()))
                self._eat("SYM", ";")
            while not self._accept("SYM", "}"):
                vname = self._eat("NAME").text
                vfields = self.parse_variant_fields()
                self._eat("SYM", ";")
                variants.append(TypeVariant(vname, vfields))
            return TypeDef(name_tok.text, variants=variants, pos=kw.pos)
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
                    methods.append(
                        MethodDef(
                            cname_tok.text,
                            mname_tok.text,
                            params,
                            body,
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
            return ClassDef(cname_tok.text, fields, methods, bases, pos=kw.pos)
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
            return OpDef(op_tok.text, a_name, a_type, b_name, b_type, body, pos=kw.pos)
        # destructuring or assignment/field assignment
        if self.tok.kind == "SYM" and self.tok.text == "{":
            names, start_pos = self.parse_destruct_names()
            self._eat("SYM", "=")
            expr = self.parse_expr()
            self._eat("SYM", ";")
            return DestructAssign(names, expr, pos=start_pos)
        if self.tok.kind == "NAME":
            # look ahead for field assignment or normal assignment/call
            name_tok = self.tok
            self._eat("NAME")
            if self._accept("SYM", "."):
                field_name = self._eat_name_or_kw().text
                if self._accept("SYM", "="):
                    expr = self.parse_expr()
                    self._eat("SYM", ";")
                    return FieldAssign(Var(name_tok.text, pos=name_tok.pos), field_name, expr, pos=name_tok.pos)
                # method call statement
                args = self.parse_arg_list()
                self._eat("SYM", ";")
                return CallStmt(f"{name_tok.text}.{field_name}", args, pos=name_tok.pos)
            if self._accept("SYM", "="):
                expr = self.parse_expr()
                self._eat("SYM", ";")
                return Assign(name_tok.text, expr, pos=name_tok.pos)
            # call statement on identifier
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                self._eat("SYM", ";")
                return CallStmt(name_tok.text, args, pos=name_tok.pos)
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

    def parse_destruct_names(self) -> Tuple[List[str], SourcePos]:
        start_pos = self._eat("SYM", "{").pos
        names = [self._eat("NAME").text]
        while self._accept("SYM", ","):
            names.append(self._eat("NAME").text)
        self._eat("SYM", "}")
        return names, start_pos

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
            left = Bin("or", left, right, pos=op_tok.pos)
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
            left = Bin("and", left, right, pos=op_tok.pos)
        return left

    def parse_compare(self) -> IR:
        left = self.parse_term()
        while self.tok.kind == "OP" and self.tok.text in (">", ">=", "<", "<=", "==", "!="):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_term()
            left = Bin(op, left, right, pos=op_tok.pos)
        return left

    def parse_term(self) -> IR:
        left = self.parse_factor()
        while self.tok.kind == "OP" and self.tok.text in ("+", "-"):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_factor()
            left = Bin(op, left, right, pos=op_tok.pos)
        return left

    def parse_factor(self) -> IR:
        left = self.parse_power()
        while self.tok.kind == "OP" and self.tok.text in ("*", "/"):
            op = self.tok.text
            op_tok = self._eat("OP")
            right = self.parse_power()
            left = Bin(op, left, right, pos=op_tok.pos)
        return left

    def parse_power(self) -> IR:
        left = self.parse_unary()
        if self.tok.kind == "OP" and self.tok.text == "^":
            op_tok = self._eat("OP")
            right = self.parse_power()
            return Bin("^", left, right, pos=op_tok.pos)
        return left

    def parse_unary(self) -> IR:
        if self.tok.kind == "OP" and self.tok.text == "-":
            op_tok = self._eat("OP")
            return Bin("-", Num("0", pos=op_tok.pos), self.parse_unary(), pos=op_tok.pos)
        if (self.tok.kind == "KW" and self.tok.text == "not") or (
            self.tok.kind == "OP" and self.tok.text == "!"
        ):
            op_tok = self.tok
            self._eat(self.tok.kind)
            return Bin("not", Num("0", pos=op_tok.pos), self.parse_unary(), pos=op_tok.pos)
        return self.parse_postfix()

    def parse_postfix(self) -> IR:
        expr = self.parse_primary()
        while True:
            if self.tok.kind == "SYM" and self.tok.text == ".":
                dot_tok = self._eat("SYM", ".")
                name_tok = self._eat_name_or_kw()
                if self.tok.kind == "SYM" and self.tok.text == "(":
                    args = self.parse_arg_list()
                    expr = MethodCall(expr, name_tok.text, args, pos=dot_tok.pos)
                else:
                    expr = Field(expr, name_tok.text, pos=dot_tok.pos)
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
            self._eat("SYM", ":")
            body = self.parse_expr()
            self._eat("SYM", ";")
            cases.append(MatchCase(pattern, body, pos=pattern.pos))
        return Match(target, cases, pos=kw.pos)

    def parse_pattern(self) -> Pattern:
        if self.tok.kind == "NAME" and self.tok.text == "_":
            tok = self._eat("NAME")
            return WildcardPattern(name=None, pos=tok.pos)
        if self.tok.kind != "NAME":
            raise self._error("expected pattern", self.tok.pos, self._tok_span(self.tok))
        vname_tok = self._eat("NAME")
        bindings: Dict[str, Optional[str]] = {}
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
        return VariantPattern(vname_tok.text, bindings, pos=vname_tok.pos)

    def parse_primary(self) -> IR:
        if self._accept("SYM", "("):
            inner = self.parse_expr()
            self._eat("SYM", ")")
            return inner
        if self.tok.kind == "KW" and self.tok.text == "await":
            kw = self._eat("KW", "await")
            expr = self.parse_expr()
            return Await(expr, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "match":
            return self.parse_match()
        if self.tok.kind == "NUMBER":
            t = self._eat("NUMBER")
            return Num(t.text, pos=t.pos)
        if self.tok.kind == "STRING":
            t = self._eat("STRING")
            return Str(t.text, pos=t.pos)
        if self.tok.kind == "KW" and self.tok.text in {"true", "false"}:
            kw = self.tok
            val = kw.text == "true"
            self._eat("KW")
            return Bool(val, pos=kw.pos)
        if self.tok.kind == "KW" and self.tok.text == "Null":
            kw = self._eat("KW")
            return Null(pos=kw.pos)
        if self.tok.kind in {"NAME", "KW"}:
            name_tok = self._eat(self.tok.kind)
            name = name_tok.text
            if name == "spawn":
                target = self._eat_name_or_kw().text
                args = self.parse_arg_list()
                return Spawn(target, args, pos=name_tok.pos)
            if name == "new" and self.tok.kind == "SYM" and self.tok.text == "[":
                start_tok = self._eat("SYM", "[")
                items: List[IR] = []
                if not (self.tok.kind == "SYM" and self.tok.text == "]"):
                    items.append(self.parse_expr())
                    while self._accept("SYM", ","):
                        items.append(self.parse_expr())
                self._eat("SYM", "]")
                return NewLit(items, pos=start_tok.pos)
            if self.tok.kind == "SYM" and self.tok.text == "(":
                args = self.parse_arg_list()
                return Call(name, args, pos=name_tok.pos)
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
                return ClassNew(cname, init, pos=name_tok.pos)
            if self._allow_variant_ctor and self.tok.kind == "SYM" and self.tok.text == "{":
                fields = self.parse_variant_init_fields()
                return VariantCtor(name, fields, pos=name_tok.pos)
            return Var(name, pos=name_tok.pos)
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
            return ObjLit(fields, pos=start_tok.pos)
        raise self._error(f"unexpected token {self.tok.kind}", self.tok.pos, self._tok_span(self.tok))

    def parse_field_name(self) -> str:
        name = self._eat("NAME").text
        if self._accept("SYM", "."):
            sub = self._eat("NAME").text
            return f"{name}.{sub}"
        return name

    def parse_variant_fields(self) -> List[Tuple[str, str]]:
        fields: List[Tuple[str, str]] = []
        if self._accept("SYM", "{"):
            while not self._accept("SYM", "}"):
                fname = self._eat("NAME").text
                self._eat("SYM", ":")
                ftype = self._eat_name_or_kw().text
                fields.append((fname, ftype))
                if self._accept("SYM", "}"):
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

    def parse_module_path(self) -> str:
        prefix = ""
        while self._accept("SYM", "."):
            prefix += "."
        if self.tok.kind != "NAME":
            raise self._error("expected NAME", self.tok.pos, self._tok_span(self.tok))
        parts = [self._eat("NAME").text]
        while self._accept("SYM", "."):
            parts.append(self._eat("NAME").text)
        return prefix + ".".join(parts)

    def parse_qualified_name(self) -> str:
        parts = [self._eat("NAME").text]
        while self._accept("SYM", "."):
            parts.append(self._eat("NAME").text)
        return ".".join(parts)


