
    # ----- Evaluation -----
    # AST evaluator that executes statements against the runtime environment.
    #
    # These helpers interpret TinyLanguage IR directly, handling control flow,
    # function calls, heap operations, and async primitives. They are stitched
    # into the original monolithic interpreter so other modules can share the
    # same execution semantics.

    def eval_block(self, stmts: List[IR], env: "Environment", namespace: Optional[str] = None) -> Any:
        for st in stmts:
            res = self.eval_stmt(st, env, namespace)
            if isinstance(res, ReturnSignal):
                return res
        return None

    def eval_stmt(self, s: IR, env: "Environment", namespace: Optional[str] = None) -> Any:
        self._maybe_pause(s, env, namespace)
        try:
            if isinstance(s, Let):
                env.define(s.name, self.eval_expr(s.expr, env), s.pos)
            elif isinstance(s, Assign):
                value = self.eval_expr(s.expr, env)
                if env.contains(s.name):
                    env.assign(s.name, value, s.pos)
                else:
                    env.define(s.name, value, s.pos)
            elif isinstance(s, FieldAssign):
                obj = self.eval_expr(s.obj, env)
                val = self.eval_expr(s.expr, env)
                self.field_set(obj, s.name, val)
            elif isinstance(s, Print):
                vals = [self.eval_expr(expr, env) for expr in s.exprs]
                text = " ".join(self.format_value(v) for v in vals)
                with self._lock:
                    self.output.append(f"{text}\n")
                    mirror_stdout = bool(getattr(self.debugger, "mirror_stdout", False))
                    trace_to_stdout = bool(getattr(self, "trace_to_stdout", False))
                    if self.stream_output or mirror_stdout or trace_to_stdout:
                        import sys

                        sys.stdout.write(f"{text}\n")
                        sys.stdout.flush()
                        self.streamed_output = True
            elif isinstance(s, Flush):
                self.flush_streams()
            elif isinstance(s, If):
                cond = self.eval_expr(s.cond, env)
                branch = s.then if self._is_truthy(cond) else s.els
                res = self.eval_block(branch, env, namespace)
                if isinstance(res, ReturnSignal):
                    return res
            elif isinstance(s, While):
                while self._is_truthy(self.eval_expr(s.cond, env)):
                    res = self.eval_block(s.body, env, namespace)
                    if isinstance(res, ReturnSignal):
                        return res
            elif isinstance(s, TryCatch):
                try:
                    res = self.eval_block(s.body, env, namespace)
                    if isinstance(res, ReturnSignal):
                        return res
                except TinyLangError as err:
                    if s.err_name:
                        env.define(s.err_name, self._error_value(self._ensure_error_has_stack(err)), s.pos)
                    res = self.eval_block(s.handler, env, namespace)
                    if isinstance(res, ReturnSignal):
                        return res
            elif isinstance(s, Namespace):
                qualified = self._qualify_name(s.name, namespace)
                child_env = Environment(parent=env, namespace=qualified, runtime=self)
                env.define(s.name, NamespaceRef(self, qualified), s.pos)
                self.namespace_envs[qualified] = child_env
                self.eval_block(s.body, child_env, qualified)
            elif isinstance(s, Import):
                binding = _import_binding_name(s.module, s.alias)
                ns_ref = self.module_resolver.import_module(
                    s.module,
                    self,
                    caller_namespace=namespace or env.namespace,
                    caller_path=self.current_module_path,
                    pos=s.pos,
                )
                env.define(binding, ns_ref, s.pos)
            elif isinstance(s, Fn):
                s.namespace = namespace
                fn_name = self._qualify_name(s.name, namespace)
                with self._lock:
                    self.functions[fn_name] = s
            elif isinstance(s, Return):
                return ReturnSignal(self.eval_expr(s.expr, env))
            elif isinstance(s, CallStmt):
                allowed = s.name in {"heap_set", "heap_get", "delete", "tag", "join"}
                if not allowed:
                    raise RuntimeError(
                        f"call with return value must be bound; bare call statements are not allowed (offending call: {s.name}())"
                    )
                self.eval_expr(Call(s.name, s.args, pos=s.pos), env)
            elif isinstance(s, OpDef):
                self.register_operator(s, env)
            elif isinstance(s, DestructAssign):
                val = self.eval_expr(s.expr, env)
                for nm in s.names:
                    extracted = val[str(nm)]
                    if env.contains(nm):
                        env.assign(nm, extracted, s.pos)
                    else:
                        env.define(nm, extracted, s.pos)
            elif isinstance(s, TypeDef):
                self.register_type(s.name, s.fields, s.variants)
            elif isinstance(s, ClassDef):
                self.register_class(s.name, s.fields, s.bases)
                for m in s.methods:
                    m.namespace = namespace
                    self.register_method(m)
            elif isinstance(s, MethodDef):
                s.namespace = namespace
                self.register_class(s.class_name, []) if s.class_name not in self.types else None
                self.register_method(s)
            else:
                raise RuntimeError(f"unknown statement {s}")
            return None
        except (ReturnSignal, TinyLangError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._error(str(exc), getattr(s, "pos", SourcePos.origin())) from exc

    def eval_expr(self, e: IR, env: "Environment") -> Any:
        try:
            if isinstance(e, Num):
                return float(e.txt) if "." in e.txt else int(e.txt)
            if isinstance(e, Str):
                return e.txt
            if isinstance(e, Bool):
                return e.value
            if isinstance(e, Null):
                return None
            if isinstance(e, Var):
                if e.name == "errorMessage":
                    return self.error_message
                if env.contains(e.name):
                    return env.get(e.name)
                # Allow tag identifiers such as `Arr` to be passed through as plain
                # strings when they look like type names, while still flagging
                # genuinely undefined variables used in expressions.
                if e.name and e.name[0].isupper():
                    return e.name
                raise self._error(
                    f"unknown variable {e.name}",
                    e.pos,
                    candidates=env.all_names(),
                )
            if isinstance(e, Call):
                if e.name == "__type_field_type":
                    return self.type_field_type(str(self.eval_expr(e.args[0], env)), str(self.eval_expr(e.args[1], env)))
                if e.name == "__new":
                    return self.__new(int(self.eval_expr(e.args[0], env)))
                if e.name == "new":
                    return self.__new(int(self.eval_expr(e.args[0], env)))
                if e.name == "heap_get":
                    return self.heap_get(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env), pos=e.pos)
                if e.name == "heap_set":
                    return self.heap_set(
                        self.eval_expr(e.args[0], env),
                        self.eval_expr(e.args[1], env),
                        self.eval_expr(e.args[2], env),
                        pos=e.pos,
                    )
                if e.name == "delete":
                    return self.delete(self.eval_expr(e.args[0], env), pos=e.pos)
                if e.name == "tag":
                    return self.tag(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env), pos=e.pos)
                if e.name == "join":
                    if not (1 <= len(e.args) <= 3):
                        raise RuntimeError("join expects between 1 and 3 arguments")
                    handle = self.eval_expr(e.args[0], env)
                    if len(e.args) == 1:
                        return self.join_handle(handle)
                    try:
                        timeout_ms = float(self.eval_expr(e.args[1], env))
                    except Exception:
                        raise RuntimeError("join timeout must be numeric")
                    cancel_on_timeout = False
                    if len(e.args) == 3:
                        cancel_on_timeout = bool(self.eval_expr(e.args[2], env))
                    return self.join_handle(
                        handle,
                        timeout_ms=timeout_ms,
                        cancel_on_timeout=cancel_on_timeout,
                        want_status=True,
                    )
                if e.name == "cancel":
                    if len(e.args) != 1:
                        raise RuntimeError("cancel expects 1 argument")
                    return self.cancel_handle(self.eval_expr(e.args[0], env))
                if e.name == "len":
                    if len(e.args) != 1:
                        raise RuntimeError("len expects 1 argument")
                    target = self.eval_expr(e.args[0], env)
                    try:
                        if isinstance(target, int) and target in self.heap:
                            return len(self.heap[target])
                        return len(target)  # type: ignore[arg-type]
                    except Exception:
                        raise RuntimeError("len expects a sized value")
                if e.name == "__nextafter":
                    return math.nextafter(self.eval_expr(e.args[0], env), self.eval_expr(e.args[1], env))
                if e.name == "power":
                    base = self.eval_expr(e.args[0], env)
                    exp = self.eval_expr(e.args[1], env)
                    number_res = self._number_power(base, exp)
                    if number_res is not None:
                        return number_res
                    res = math.pow(base, exp)
                    if isinstance(res, float) and res.is_integer():
                        res = int(res)
                    return res
                arg_values = [self.eval_expr(arg_expr, env) for arg_expr in e.args]
                invoked, native_res = self._invoke_native(e.name, arg_values)
                if invoked:
                    return native_res
                resolved_name, fn = self._resolve_function(e.name, env)
                if fn is not None:
                    if fn.is_async:
                        return self._start_task(fn, arg_values)
                    return self._invoke_function(fn, arg_values)
                raise RuntimeError(f"unknown function {e.name}")
            if isinstance(e, Spawn):
                resolved_name, fn = self._resolve_function(e.name, env)
                if fn is None:
                    raise RuntimeError(f"unknown function {e.name}")
                arg_values = [self.eval_expr(arg, env) for arg in e.args]
                return self._start_task(fn, arg_values)
            if isinstance(e, Await):
                handle = self.eval_expr(e.expr, env)
                return self.join_handle(handle)
            if isinstance(e, New):
                return self.__new(int(self.eval_expr(e.size, env)))
            if isinstance(e, NewLit):
                p = self.__new(len(e.items))
                for idx, item in enumerate(e.items):
                    self.heap_set(p, idx, self.eval_expr(item, env), pos=e.pos)
                return p
            if isinstance(e, Bin):
                if e.op == "and":
                    left = self.eval_expr(e.a, env)
                    if not self._is_truthy(left):
                        return False
                    return bool(self._is_truthy(self.eval_expr(e.b, env)))
                if e.op == "or":
                    left = self.eval_expr(e.a, env)
                    if self._is_truthy(left):
                        return True
                    return bool(self._is_truthy(self.eval_expr(e.b, env)))
                if e.op == "not":
                    return not self._is_truthy(self.eval_expr(e.b, env))
                return self.__binop(e.op, self.eval_expr(e.a, env), self.eval_expr(e.b, env))
            if isinstance(e, ObjLit):
                obj: Dict[str, Any] = {"__tag__": "Struct"}
                for k, v in e.fields:
                    obj[k] = self.eval_expr(v, env)
                return obj
            if isinstance(e, VariantCtor):
                init = {k: self.eval_expr(v, env) for k, v in e.fields}
                return self.instantiate_variant(e.variant, init, type_name=e.type_name, pos=e.pos)
            if isinstance(e, Match):
                val = self.eval_expr(e.expr, env)
                return self.eval_match(e, val, env)
            if isinstance(e, Field):
                obj = self.eval_expr(e.obj, env)
                return self.field_get(obj, e.name, pos=e.pos)
            if isinstance(e, MethodCall):
                obj = self.eval_expr(e.obj, env)
                args = [self.eval_expr(a, env) for a in e.args]
                return self.call_method(obj, e.name, args)
            if isinstance(e, ClassNew):
                init = {k: self.eval_expr(v, env) for k, v in e.init}
                self.register_class(e.name, []) if e.name not in self.types else None
                return self.instantiate_class(e.name, init)
            raise RuntimeError(f"unknown expr {e}")
        except TinyLangError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._error(str(exc), getattr(e, "pos", SourcePos.origin())) from exc


class Environment:
    def __init__(
        self, parent: Optional["Environment"], namespace: Optional[str] = None, runtime: Optional["Runtime"] = None
    ):
        self.parent = parent  # Outer lexical scope (if any)
        self.namespace = namespace  # Module/namespace name for namespacing lookups
        self.runtime = runtime or (parent.runtime if parent else None)
        self.values: Dict[str, Any] = {}  # Local symbol table
        self.types: Dict[str, str] = {}

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise RuntimeError(f"unknown variable {name}")

    def define(self, name: str, value: Any, pos: SourcePos) -> None:
        if self.runtime:
            self.types[name] = self.runtime._infer_type_name(value)
        else:
            self.types[name] = "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else type(value).__name__
        self.values[name] = value

    def assign(self, name: str, value: Any, pos: SourcePos) -> None:
        if name in self.values:
            if self.runtime:
                self.runtime._check_assignment_type(self, name, value, pos, local_only=True)
                self.types[name] = self.runtime._infer_type_name(value)
            else:
                self.types[name] = "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else type(value).__name__
            self.values[name] = value
        elif self.parent is not None:
            self.parent.assign(name, value, pos)
        else:
            self.define(name, value, pos)

    def contains(self, name: str) -> bool:
        if name in self.values:
            return True
        return self.parent.contains(name) if self.parent else False

    def type_of(self, name: str, *, local_only: bool = False) -> Optional[str]:
        if name in self.types:
            return self.types[name]
        if not local_only and self.parent is not None:
            return self.parent.type_of(name)
        return None

    def all_names(self) -> List[str]:
        names = list(self.values.keys())  # Start with current scope names
        if self.parent:
            names.extend(self.parent.all_names())  # Include ancestors
        return names


