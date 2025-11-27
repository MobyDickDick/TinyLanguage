# ----- Runtime -----


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        super().__init__()
        self.value = value


@dataclass
class BaseView:
    obj: Dict[str, Any]
    class_name: str


@dataclass
class NamespaceRef:
    runtime: "Runtime"
    name: str


def _import_binding_name(module: str, alias: Optional[str]) -> str:
    if alias:
        return alias
    stripped = module.lstrip(".") or module
    return stripped.split(".")[-1]


class ModuleResolver:
    def __init__(self, search_paths: Optional[List[Path]] = None):
        env_paths = os.environ.get("TINYPATH", "")
        configured_paths = [Path(p) for p in env_paths.split(os.pathsep) if p]
        default_roots = [Path.cwd(), Path(__file__).parent]
        self.search_paths: List[Path] = search_paths or configured_paths + default_roots
        self.cache: Dict[Path, NamespaceRef] = {}
        self._in_progress: List[Path] = []

    def _resolve_name(self, raw: str, caller_namespace: Optional[str], pos: Optional[SourcePos]) -> str:
        leading = len(raw) - len(raw.lstrip("."))
        if leading == 0:
            return raw
        if not caller_namespace:
            raise TinyLangError(
                format_error("", pos or SourcePos.origin(), "relative import outside a module", code="E008"),
                pos or SourcePos.origin(),
                code="E008",
            )
        base = caller_namespace.split(".")
        if leading > len(base):
            raise TinyLangError(
                format_error(
                    "",
                    pos or SourcePos.origin(),
                    "relative import traverses beyond module root",
                    code="E008",
                ),
                pos or SourcePos.origin(),
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
        runtime: "Runtime",
        *,
        caller_namespace: Optional[str],
        caller_path: Optional[Path],
        pos: Optional[SourcePos] = None,
    ) -> NamespaceRef:
        resolved_name = self._resolve_name(name, caller_namespace, pos)
        for candidate in self._candidate_paths(resolved_name, caller_path):
            resolved_path = candidate.resolve()
            if resolved_path in self.cache:
                return self.cache[resolved_path]
            if resolved_path.exists():
                if resolved_path in self._in_progress:
                    raise TinyLangError(
                        format_error(
                            "",
                            pos or SourcePos.origin(),
                            f"circular import involving {resolved_path}",
                            code="E008",
                        ),
                        pos or SourcePos.origin(),
                        code="E008",
                    )
                self._in_progress.append(resolved_path)
                try:
                    module_env = Environment(parent=None, namespace=resolved_name)
                    compile_and_run(
                        resolved_path.read_text(encoding="utf-8"),
                        env=module_env,
                        runtime=runtime,
                        module_namespace=resolved_name,
                        module_path=resolved_path,
                        module_resolver=self,
                    )
                    ns_ref = NamespaceRef(runtime, resolved_name)
                    self.cache[resolved_path] = ns_ref
                    return ns_ref
                finally:
                    self._in_progress.remove(resolved_path)
        raise TinyLangError(
            format_error(
                "", pos or SourcePos.origin(), f"module '{name}' not found on search path", code="E008"
            ),
            pos or SourcePos.origin(),
            code="E008",
        )


@dataclass
class SpawnHandle:
    thread: threading.Thread
    done: threading.Event
    cancelled: threading.Event
    result: Any = None
    error: Optional[BaseException] = None


@dataclass
class CancellationToken:
    cancelled: threading.Event = field(default_factory=threading.Event)
    reason: Optional[str] = None
    _linked: List[SpawnHandle] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def cancel(self, reason: Optional[str] = None) -> bool:
        with self._lock:
            already = self.cancelled.is_set()
            if already:
                return False
            self.reason = reason
            self.cancelled.set()
            for handle in list(self._linked):
                handle.cancelled.set()
            return True

    def link_handle(self, handle: SpawnHandle) -> bool:
        with self._lock:
            if handle in self._linked:
                return False
            if self.cancelled.is_set():
                handle.cancelled.set()
                return False
            self._linked.append(handle)
            return True


class Runtime:
    def __init__(self, source: str):
        self._lock = threading.RLock()
        self.heap: Dict[int, List[Any]] = {}
        self.ptr_tags: Dict[int, str] = {}
        self.ops: Dict[Tuple[str, Optional[str], Optional[str]], Any] = {}
        self.methods: Dict[Tuple[str, str], MethodDef] = {}
        self.types: Dict[str, Dict[str, Any]] = {}
        self.next_ptr = 1
        self.output: List[str] = []
        self.functions: Dict[str, Fn] = {}
        self.native_functions: Dict[str, Callable[..., Any]] = {}
        self.global_env: Optional["Environment"] = None
        self.error_messages: List[str] = []
        self.source = source
        self.source_map: Dict[Optional[str], str] = {None: source}
        self.namespace_envs: Dict[str, "Environment"] = {}
        self.module_resolver: ModuleResolver = ModuleResolver()
        self.current_module_path: Optional[Path] = None
        self.current_module_namespace: Optional[str] = None
        self.call_stack: List[StackFrame] = []

    @staticmethod
    def _qualify_name(name: str, namespace: Optional[str]) -> str:
        return f"{namespace}.{name}" if namespace else name

    def _source_for_namespace(self, namespace: Optional[str]) -> str:
        with self._lock:
            if namespace in self.source_map:
                return self.source_map[namespace]
        return self.source

    def _format_stacktrace(self, stack: Sequence[StackFrame]) -> str:
        if not stack:
            return ""
        lines = ["Stack trace:"]
        for frame in reversed(stack):
            lines.append(f"  at {frame.qualified_name} (line {frame.pos.line}, col {frame.pos.col})")
        return "\n".join(lines)

    def _record_error(
        self,
        msg: str,
        pos: Optional[SourcePos] = None,
        *,
        code: str = "E000",
        hint: Optional[str] = None,
        formatted: Optional[str] = None,
    ) -> None:
        if formatted is None:
            source = self._source_for_namespace(self.current_module_namespace if pos is not None else None)
            base = format_error(source, pos, msg, code=code, hint=hint) if pos is not None else msg
            stack_part = self._format_stacktrace(self.call_stack)
            formatted = f"{base}\n{stack_part}" if stack_part else base
        with self._lock:
            # Only keep the most recent runtime error so `errorMessage` reflects
            # the latest failure instead of accumulating older ones.
            self.error_messages = [formatted]

    def _error(
        self,
        msg: str,
        pos: SourcePos,
        *,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        candidates: Optional[List[str]] = None,
        ) -> TinyLangError:
        derived_code, derived_hint = _classify_error(msg, candidates)
        code = code or derived_code
        hint = hint or derived_hint
        source = self._source_for_namespace(self.current_module_namespace)
        formatted = format_error(source, pos, msg, code=code, hint=hint)
        stack = tuple(self.call_stack)
        if stack:
            formatted = f"{formatted}\n{self._format_stacktrace(stack)}"
        self._record_error(msg, pos, code=code, hint=hint, formatted=formatted)
        return TinyLangError(formatted, pos, code=code, hint=hint, stack=stack)

    def _ensure_error_has_stack(self, err: TinyLangError) -> TinyLangError:
        if err.stack:
            return err
        stack = tuple(self.call_stack)
        if not stack:
            return err
        err.stack = stack
        err.message = f"{err.message}\n{self._format_stacktrace(stack)}"
        return err

    @staticmethod
    def _error_value(err: TinyLangError) -> Dict[str, Any]:
        stack_strings = [
            f"{frame.qualified_name} (line {frame.pos.line}, col {frame.pos.col})" for frame in err.stack
        ]
        return {
            "__tag__": "Error",
            "code": err.code,
            "message": str(err),
            "hint": err.hint,
            "stack": stack_strings,
        }

    @property
    def error_message(self) -> Optional[str]:
        with self._lock:
            if not self.error_messages:
                return None
            return self.error_messages[-1]

    # heap helpers
    def __new(self, n: int) -> int:
        if n < 0:
            raise RuntimeError("alloc error: negative size")
        with self._lock:
            p = self.next_ptr
            self.next_ptr += 1
            self.heap[p] = [0 for _ in range(int(n))]
            return p

    def delete(self, p: Any, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        try:
            ip = int(p)
            with self._lock:
                self.heap.pop(ip, None)
                self.ptr_tags.pop(ip, None)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def heap_get(self, p: Any, i: Any, *, pos: Optional[SourcePos] = None) -> Any:
        try:
            ip = int(p)
            idx = int(i)
        except Exception:
            self._record_error("heap access error: pointer or index is not numeric", pos)
            return None

        with self._lock:
            try:
                arr = self.heap[ip]
            except KeyError:
                self._record_error(f"heap access error: unknown pointer {ip}", pos)
                return None

            try:
                return arr[idx]
            except Exception:
                self._record_error(
                    f"heap access error: index {idx} out of range for pointer {ip}", pos
                )
                return None

    def heap_set(self, p: Any, i: Any, v: Any, *, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        try:
            with self._lock:
                self.heap[int(p)][int(i)] = v
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            self._record_error(str(e), pos)
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def tag(self, p: Any, typ: Any, *, pos: Optional[SourcePos] = None) -> Dict[str, Any]:
        try:
            with self._lock:
                self.ptr_tags[int(p)] = str(typ)
            return {"__tag__": "Record", "e": {"__tag__": "Error", "code": 0, "msg": ""}}
        except Exception as e:  # noqa: BLE001
            self._record_error(str(e), pos)
            return {
                "__tag__": "Record",
                "e": {"__tag__": "Error", "code": 1, "msg": str(e)},
            }

    def __get_tag(self, v: Any) -> Optional[str]:
        if isinstance(v, dict) and "__tag__" in v:
            return v["__tag__"]
        if isinstance(v, BaseView):
            return v.class_name
        try:
            iv = int(v)
            with self._lock:
                if iv in self.ptr_tags:
                    return self.ptr_tags[iv]
        except Exception:
            pass
        return None

    def _value_type_name(self, value: Any) -> Optional[str]:
        tag = self.__get_tag(value)
        if tag:
            return tag
        if value is None:
            return "Null"
        if isinstance(value, bool):
            return "Bool"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "string"
        return type(value).__name__

    def _type_matches(self, expected: str, value: Any) -> bool:
        actual = self._value_type_name(value)
        if actual is None:
            return False
        expected_norm = expected.strip()
        actual_norm = actual.strip() if isinstance(actual, str) else str(actual)
        if expected_norm == actual_norm or expected_norm.lower() == actual_norm.lower():
            return True
        if expected_norm.lower() == "number" and actual_norm.lower() in {"number", "int", "float"}:
            return True
        if expected_norm.lower() == "string" and actual_norm.lower() == "string":
            return True
        if expected_norm.lower() in {"bool", "boolean"} and actual_norm.lower() in {"bool", "boolean"}:
            return True
        if expected_norm == "Null" and value is None:
            return True
        return False

    def _enforce_annotation(self, expected: str, value: Any, *, label: str, pos: SourcePos) -> None:
        if not self._type_matches(expected, value):
            actual = self._value_type_name(value) or type(value).__name__
            raise self._error(
                f"type mismatch for {label}: expected {expected} but got {actual}",
                pos,
                code="E009",
                hint="Adjust the type annotation or pass a compatible value to satisfy the hint.",
            )

    @staticmethod
    def _number_fields(val: Any) -> Optional[Dict[str, Any]]:
        if isinstance(val, dict) and val.get("__tag__") == "Number":
            return val.get("__fields__", {}).get("Number")
        return None

    @staticmethod
    def _make_number(value: Any, error: str) -> Dict[str, Any]:
        return {"__tag__": "Number", "__fields__": {"Number": {"value": value, "error": error}}}

    @staticmethod
    def _intervall_fields(val: Any) -> Optional[Dict[str, Any]]:
        if isinstance(val, dict) and val.get("__tag__") == "NumberIntervall":
            return val.get("__fields__", {}).get("NumberIntervall")
        return None

    @staticmethod
    def _make_intervall(lower: Any, upper: Any, error: str) -> Dict[str, Any]:
        return {
            "__tag__": "NumberIntervall",
            "__fields__": {"NumberIntervall": {"lower": lower, "upper": upper, "error": error}},
        }

    def _number_to_intervall(self, value: Any) -> Optional[Dict[str, Any]]:
        fields = self._number_fields(value)
        if fields is None:
            return None
        err = fields.get("error", "normal") or "normal"
        if err in {"plus_infinity", "minus_infinity", "any_number"}:
            return self._make_intervall(0, 0, err)
        lower = fields.get("value", 0)
        upper = fields.get("value", 0)
        return self._make_intervall(lower, upper, "normal")

    def _coerce_to_number(self, val: Any) -> Any:
        if val is None:
            return self._make_number(0, "normal")
        if self.__get_tag(val) == "Number":
            return val
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return self._make_number(val, "normal")
        return val

    def _coerce_to_intervall(self, val: Any) -> Any:
        if val is None:
            return self._make_intervall(0, 0, "normal")
        if self.__get_tag(val) == "NumberIntervall":
            return val
        from_number = self._number_to_intervall(val)
        if from_number is not None:
            return from_number
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return self._make_intervall(val, val, "normal")
        return val

    def _coerce_numeric_operands(
        self, op: str, a: Any, b: Any, ta: Optional[str], tb: Optional[str]
    ) -> Tuple[Any, Any]:
        arithmetic_ops = {"+", "-", "*", "/", "^"}
        if op not in arithmetic_ops:
            return a, b
        if ta == "NumberIntervall" or tb == "NumberIntervall":
            return self._coerce_to_intervall(a), self._coerce_to_intervall(b)
        if ta == "Number" or tb == "Number":
            return self._coerce_to_number(a), self._coerce_to_number(b)
        return a, b

    def _number_binop(self, op: str, a: Any, b: Any) -> Any:
        fields_a = self._number_fields(a)
        fields_b = self._number_fields(b)
        if fields_a is None or fields_b is None:
            return None

        val_a = fields_a.get("value", 0)
        val_b = fields_b.get("value", 0)
        err_a = fields_a.get("error", "normal") or "normal"
        err_b = fields_b.get("error", "normal") or "normal"

        def mk(err: str, value: Any = 0) -> Dict[str, Any]:
            return self._make_number(value, err)

        def overflow(v: float) -> Optional[str]:
            limit = 1e21
            if v > limit:
                return "plus_infinity"
            if v < -limit:
                return "minus_infinity"
            return None

        if op == "^":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a != "normal" or err_b != "normal":
                return mk("any_number")
            if not isinstance(val_b, (int, float)):
                return mk("any_number")
            if isinstance(val_b, float):
                if not val_b.is_integer():
                    return mk("any_number")
                val_b = int(val_b)
            try:
                res = val_a**val_b
            except Exception:
                return mk("any_number")
            ov = overflow(res)
            if ov:
                return mk(ov)
            rounded = False
            if isinstance(res, float):
                rounded = not res.is_integer()
                if not rounded:
                    res = int(res)
            return mk("rounded" if rounded else "normal", res)

        if op == "+":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a == "minus_infinity" and err_b == "normal" and val_b > 0:
                return mk("any_number")
            if err_b == "minus_infinity" and err_a == "normal" and val_a > 0:
                return mk("any_number")
            if err_a == "plus_infinity" or err_b == "plus_infinity":
                return mk("plus_infinity")
            if err_a == "minus_infinity" or err_b == "minus_infinity":
                return mk("minus_infinity")
            res = val_a + val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "-":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a == "plus_infinity" and err_b == "normal" and val_b > 0:
                return mk("any_number")
            if err_a == "plus_infinity" or err_b == "minus_infinity":
                return mk("plus_infinity")
            if err_a == "minus_infinity" or err_b == "plus_infinity":
                return mk("minus_infinity")
            res = val_a - val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "*":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_a in {"plus_infinity", "minus_infinity"} and err_b in {"plus_infinity", "minus_infinity"}:
                sign = 1
                if err_a == "minus_infinity":
                    sign *= -1
                if err_b == "minus_infinity":
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            if err_a in {"plus_infinity", "minus_infinity"}:
                if val_b == 0:
                    return mk("any_number")
                sign = -1 if err_a == "minus_infinity" else 1
                if val_b < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            if err_b in {"plus_infinity", "minus_infinity"}:
                if val_a == 0:
                    return mk("any_number")
                sign = -1 if err_b == "minus_infinity" else 1
                if val_a < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            res = val_a * val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            return mk("normal", res)

        if op == "/":
            if err_a == "any_number" or err_b == "any_number":
                return mk("any_number")
            if err_b in {"plus_infinity", "minus_infinity"} and err_a == "normal":
                return mk("normal", 0)
            if err_b == "normal" and val_b == 0:
                if err_a == "plus_infinity":
                    return mk("plus_infinity")
                if err_a == "minus_infinity":
                    return mk("minus_infinity")
                if val_a > 0:
                    return mk("plus_infinity")
                if val_a < 0:
                    return mk("minus_infinity")
                return mk("any_number")
            if err_a in {"plus_infinity", "minus_infinity"}:
                if err_b in {"plus_infinity", "minus_infinity"}:
                    return mk("any_number")
                sign = -1 if err_a == "minus_infinity" else 1
                if err_b == "normal" and val_b < 0:
                    sign *= -1
                return mk("plus_infinity" if sign > 0 else "minus_infinity")
            res = val_a / val_b
            ov = overflow(res)
            if ov:
                return mk(ov)
            rounded = False
            if isinstance(res, float):
                rounded = not res.is_integer()
                if not rounded:
                    res = int(res)
            return mk("rounded" if rounded else "normal", res)

        return None

    def _number_power(self, base: Any, exponent: Any) -> Any:
        fields_a = self._number_fields(base)
        fields_b = self._number_fields(exponent)
        if fields_a is None or fields_b is None:
            return None

        val_a = fields_a.get("value", 0)
        val_b = fields_b.get("value", 0)
        err_a = fields_a.get("error", "normal") or "normal"
        err_b = fields_b.get("error", "normal") or "normal"

        def mk(err: str, value: Any = 0) -> Dict[str, Any]:
            return self._make_number(value, err)

        def overflow(v: float) -> Optional[str]:
            limit = 1e21
            if v > limit:
                return "plus_infinity"
            if v < -limit:
                return "minus_infinity"
            return None

        if err_a == "any_number" or err_b == "any_number":
            return mk("any_number")
        if err_a != "normal" or err_b != "normal":
            return mk("any_number")
        try:
            res = val_a**val_b
        except Exception:
            return mk("any_number")
        ov = overflow(res)
        if ov:
            return mk(ov)
        rounded = False
        if isinstance(res, float):
            rounded = not res.is_integer()
            if not rounded:
                res = int(res)
        return mk("rounded" if rounded else "normal", res)

    def __binop(self, op: str, a: Any, b: Any) -> Any:
        if a is None:
            a = 0
        if b is None:
            b = 0
        ta = self.__get_tag(a)
        tb = self.__get_tag(b)
        a, b = self._coerce_numeric_operands(op, a, b, ta, tb)
        ta = self.__get_tag(a)
        tb = self.__get_tag(b)
        num_res = self._number_binop(op, a, b)
        if num_res is not None:
            return num_res
        key = (op, ta, tb)
        with self._lock:
            impl = self.ops.get(key)
        if impl:
            return impl(a, b)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b
        if op == "^":
            if isinstance(b, float):
                if not b.is_integer():
                    raise RuntimeError("exponent for ^ must be an integer")
                b = int(b)
            elif not isinstance(b, int):
                raise RuntimeError("exponent for ^ must be an integer")
            return a**b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        raise RuntimeError(f"unsupported op {op}")

    def field_get(self, obj: Any, key: str, *, pos: Optional[SourcePos] = None) -> Any:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        if isinstance(target_obj, NamespaceRef):
            env = self.namespace_envs.get(target_obj.name)
            if env and env.contains(key):
                return env.get(key)
            qualified = self._qualify_name(key, target_obj.name)
            with self._lock:
                if qualified in self.functions:
                    return NamespaceRef(self, qualified)
            self._record_error(f"unknown field {key}", pos)
            return None
        if isinstance(target_obj, dict) and "__fields__" in target_obj:
            try:
                fmap = self._resolve_field_storage(
                    target_obj, key, owner_hint, target_obj["__tag__"], allow_write=False
                )
                return fmap[key]
            except Exception as err:  # noqa: BLE001
                self._record_error(str(err), pos)
                return None
        try:
            return target_obj[str(key)]
        except Exception:
            self._record_error(f"unknown field {key}", pos)
            return None

    def field_set(self, obj: Any, key: str, val: Any) -> None:
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        owner_hint = obj.class_name if isinstance(obj, BaseView) else None
        if isinstance(target_obj, dict) and "__fields__" in target_obj:
            fmap = self._resolve_field_storage(target_obj, key, owner_hint, target_obj["__tag__"], allow_write=True)
            fmap[key] = val
            return
        target_obj[str(key)] = val

    def register_type(self, name: str, fields: List[Tuple[str, str]]) -> None:
        with self._lock:
            self.types[str(name)] = {"kind": "record", "fields": dict(fields)}

    def register_class(self, name: str, fields: List[Tuple[str, str]], bases: Optional[List[str]] = None) -> None:
        base_list = list(bases) if bases is not None else []
        with self._lock:
            existing = self.types.get(name)
            if existing:
                if existing.get("kind") != "class":
                    raise RuntimeError(f"type {name} already defined and is not a class")
                existing["fields"].update(dict(fields))
                if bases is not None:
                    existing["bases"] = base_list
                return
            self.types[str(name)] = {"kind": "class", "fields": dict(fields), "bases": base_list}

    def register_method(self, md: MethodDef) -> None:
        with self._lock:
            self.methods[(md.class_name, md.name)] = md

    def register_native(self, name: str, func: Callable[..., Any], namespace: Optional[str] = None) -> None:
        qualified = self._qualify_name(name, namespace)
        with self._lock:
            self.native_functions[qualified] = func

    def register_operator(self, opdef: OpDef, env: "Environment") -> None:
        def impl(a_val: Any, b_val: Any) -> Any:
            op_env = Environment(parent=env, namespace=env.namespace)
            op_env.values[opdef.a_name] = a_val
            op_env.values[opdef.b_name] = b_val
            res = self.eval_block(opdef.body, op_env, env.namespace)
            if isinstance(res, ReturnSignal):
                return res.value
            return res

        with self._lock:
            self.ops[(opdef.op, opdef.a_type, opdef.b_type)] = impl

    def class_mro(self, name: str) -> List[str]:
        with self._lock:
            info = self.types.get(name)
            if info is None or info.get("kind") != "class":
                raise RuntimeError(f"unknown class {name}")
            bases = list(info.get("bases", []))
        mro: List[str] = [name]
        for base in bases:
            with self._lock:
                if base not in self.types:
                    raise RuntimeError(f"unknown base class {base} for {name}")
            for ancestor in self.class_mro(base):
                if ancestor not in mro:
                    mro.append(ancestor)
        return mro

    @staticmethod
    def _split_field_name(fname: str) -> Tuple[Optional[str], str]:
        if "." in fname:
            owner, rest = fname.split(".", 1)
            return owner, rest
        return None, fname

    def instantiate_class(self, name: str, init: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            info = self.types.get(name)
            if info is None or info.get("kind") != "class":
                raise RuntimeError(f"unknown class {name}")
        mro = self.class_mro(name)
        obj: Dict[str, Any] = {"__tag__": name, "__fields__": {}}
        for cls in mro:
            with self._lock:
                finfo = self.types.get(cls)
                if finfo is None or finfo.get("kind") != "class":
                    raise RuntimeError(f"unknown class {cls}")
            obj["__fields__"][cls] = {fname: None for fname in finfo["fields"]}

        for raw_name, val in init.items():
            owner_hint, fname = self._split_field_name(raw_name)
            fmap = self._resolve_field_storage(obj, fname, owner_hint, name)
            fmap[fname] = val
        return obj

    def _resolve_function(self, name: str, env: "Environment") -> Tuple[Optional[str], Optional[Fn]]:
        with self._lock:
            fn = self.functions.get(name)
        if fn is not None:
            return name, fn
        if "." not in name and env.namespace:
            qualified = self._qualify_name(name, env.namespace)
            with self._lock:
                fn = self.functions.get(qualified)
            if fn is not None:
                return qualified, fn
        return None, None

    def _invoke_native(self, qualified_name: str, args: List[Any]) -> Tuple[bool, Any]:
        with self._lock:
            native = self.native_functions.get(qualified_name)
        if native is None:
            return False, None
        return True, native(*args)

    def _invoke_function(self, fn: Fn, args: List[Any]) -> Any:
        call_env = Environment(parent=self.global_env, namespace=fn.namespace)
        for param, arg in zip(fn.params, args):
            if param.type:
                self._enforce_annotation(param.type, arg, label=f"parameter {param.name} in function {fn.name}", pos=fn.pos)
            call_env.values[param.name] = arg
        frame = StackFrame(fn.name, fn.namespace, fn.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = fn.namespace or prev_namespace
        try:
            res = self.eval_block(fn.body, call_env, fn.namespace)
            if isinstance(res, ReturnSignal):
                value = res.value
                if fn.return_type:
                    self._enforce_annotation(fn.return_type, value, label=f"return value for function {fn.name}", pos=fn.pos)
                return value
            if fn.return_type:
                self._enforce_annotation(fn.return_type, res, label=f"return value for function {fn.name}", pos=fn.pos)
            return res
        except TinyLangError as err:
            raise self._ensure_error_has_stack(err) from err
        finally:
            self.call_stack.pop()
            self.current_module_namespace = prev_namespace

    def _run_spawn(self, fn: Fn, args: List[Any], handle: SpawnHandle) -> None:
        try:
            if handle.cancelled.is_set():
                handle.error = RuntimeError("spawn cancelled")
                return
            result = self._invoke_function(fn, args)
            if handle.cancelled.is_set():
                handle.error = RuntimeError("spawn cancelled")
            else:
                handle.result = result
        except Exception as exc:  # noqa: BLE001
            handle.error = exc
        finally:
            handle.done.set()

    def _join_status(self, handle: SpawnHandle, *, done: bool) -> Dict[str, Any]:
        return {
            "__tag__": "JoinStatus",
            "done": done,
            "cancelled": handle.cancelled.is_set(),
            "error": str(handle.error) if handle.error else None,
            "result": None if handle.error or not done or handle.cancelled.is_set() else handle.result,
        }

    def cancel_handle(self, handle: Any) -> bool:
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("cancel expects a spawn handle")
        already = handle.cancelled.is_set()
        handle.cancelled.set()
        return not already

    def make_cancellation_token(self) -> CancellationToken:
        return CancellationToken()

    def cancel_token(self, token: Any, reason: Optional[str] = None) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("cancel_token expects a cancellation token")
        return token.cancel(reason)

    def token_cancelled(self, token: Any) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("token_cancelled expects a cancellation token")
        return token.cancelled.is_set()

    def token_reason(self, token: Any) -> Optional[str]:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("token_reason expects a cancellation token")
        return token.reason

    def link_token(self, token: Any, handle: Any) -> bool:
        if not isinstance(token, CancellationToken):
            raise RuntimeError("link_token expects a cancellation token")
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("link_token expects a spawn handle")
        return token.link_handle(handle)

    def join_handle(
        self,
        handle: Any,
        *,
        timeout_ms: Optional[float] = None,
        cancel_on_timeout: bool = False,
        want_status: bool = False,
    ) -> Any:
        if not isinstance(handle, SpawnHandle):
            raise RuntimeError("join expects a spawn handle")

        timeout = None if timeout_ms is None else max(0.0, timeout_ms / 1000.0)
        finished = handle.done.wait(timeout)
        if not finished:
            if cancel_on_timeout:
                self.cancel_handle(handle)
            if want_status:
                return self._join_status(handle, done=False)
            return None

        handle.thread.join()
        if handle.cancelled.is_set():
            if want_status:
                return self._join_status(handle, done=True)
            raise handle.error or RuntimeError("join cancelled")
        if handle.error:
            if want_status:
                return self._join_status(handle, done=True)
            raise handle.error
        if want_status:
            return self._join_status(handle, done=True)
        return handle.result

    def _resolve_field_storage(
        self,
        obj: Dict[str, Any],
        fname: str,
        owner_hint: Optional[str],
        current_class: str,
        *,
        allow_write: bool = True,
    ) -> Dict[str, Any]:
        if "__fields__" not in obj:
            raise RuntimeError("field access on non-class value")

        def lookup_mro(start_class: str) -> List[str]:
            return self.class_mro(start_class)

        mro = lookup_mro(owner_hint or current_class)
        matches: List[Tuple[str, Dict[str, Any]]] = []

        for cls in mro:
            fmap = obj["__fields__"].get(cls, {})
            if fname in fmap:
                matches.append((cls, fmap))

        if owner_hint:
            for cls, fmap in matches:
                if cls == owner_hint:
                    return fmap
            raise RuntimeError(f"unknown field {fname} for base class {owner_hint}")

        if matches:
            primary_class = current_class
            for cls, fmap in matches:
                if cls == primary_class:
                    return fmap

        if len(matches) == 1:
            return matches[0][1]
        if len(matches) > 1:
            action = "assign" if allow_write else "access"
            raise RuntimeError(
                f"ambiguous field {fname} during {action}; please qualify with a base class name"
            )
        raise RuntimeError(f"unknown field {fname} for class {current_class}")

    def find_method(self, start_class: str, name: str) -> Optional[MethodDef]:
        for cls in self.class_mro(start_class):
            with self._lock:
                md = self.methods.get((cls, name))
            if md:
                return md
        return None

    def call_method(self, obj: Any, name: str, args: List[Any]) -> Any:
        if isinstance(obj, NamespaceRef):
            qualified_name = self._qualify_name(name, obj.name)
            invoked, native_res = self._invoke_native(qualified_name, args)
            if invoked:
                return native_res
            fn = self.functions.get(qualified_name)
            if fn is None:
                raise RuntimeError(f"unknown function {qualified_name}")
            return self._invoke_function(fn, args)
        target_obj = obj.obj if isinstance(obj, BaseView) else obj
        start_class = obj.class_name if isinstance(obj, BaseView) else self.__get_tag(target_obj)
        cname = self.__get_tag(target_obj)
        if start_class is None or cname is None:
            raise RuntimeError("method call on untagged value")
        md = self.find_method(start_class, name)
        if md is None:
            raise RuntimeError(f"no method {name} for class {start_class}")
        env = Environment(parent=None)
        self_value: Any = target_obj
        if md.class_name != cname:
            self_value = BaseView(target_obj, md.class_name)
        env.values[md.params[0].name] = self_value  # self
        for base in self.class_mro(cname)[1:]:
            env.values[base] = BaseView(target_obj, base)
        for param, arg in zip(md.params[1:], args):
            if param.type:
                self._enforce_annotation(param.type, arg, label=f"parameter {param.name} in method {md.class_name}.{md.name}", pos=md.pos)
            env.values[param.name] = arg
        frame = StackFrame(f"{md.class_name}.{md.name}", md.namespace, md.pos)
        self.call_stack.append(frame)
        prev_namespace = self.current_module_namespace
        self.current_module_namespace = md.namespace or prev_namespace
        try:
            res = self.eval_block(md.body, env)
            if isinstance(res, ReturnSignal):
                value = res.value
                if md.return_type:
                    self._enforce_annotation(md.return_type, value, label=f"return value for method {md.class_name}.{md.name}", pos=md.pos)
                return value
            if md.return_type:
                self._enforce_annotation(md.return_type, res, label=f"return value for method {md.class_name}.{md.name}", pos=md.pos)
            return res
        except TinyLangError as err:
            raise self._ensure_error_has_stack(err) from err
        finally:
            self.call_stack.pop()
            self.current_module_namespace = prev_namespace

    def type_field_type(self, tname: str, fname: str) -> Optional[str]:
        with self._lock:
            t = self.types.get(tname)
        if t is None:
            return None
        owner_hint, field_name = self._split_field_name(fname)
        if t.get("kind") == "class":
            targets: List[str] = []
            if owner_hint:
                targets.append(owner_hint)
            else:
                targets.append(tname)
                targets.extend(self.class_mro(tname)[1:])
            hits = []
            for cls in targets:
                info = self.types.get(cls)
                if info and field_name in info.get("fields", {}):
                    hits.append(info["fields"][field_name])
                    if owner_hint:
                        break
                    if cls == tname:
                        return info["fields"][field_name]
            if len(hits) == 1:
                return hits[0]
            return None
        return t["fields"].get(field_name)

    @staticmethod
    def format_value(val: Any) -> str:
        if isinstance(val, dict) and val.get("__tag__") == "Number":
            fields = val.get("__fields__", {}).get("Number", {})
            err = fields.get("error")
            if err in {"plus_infinity", "minus_infinity", "any_number"}:
                return str(err)
            if "value" in fields:
                value = fields.get("value")
                if err == "rounded":
                    return f"{value} (rounded)"
                return str(value)
        if isinstance(val, dict) and val.get("__tag__") == "NumberIntervall":
            fields = val.get("__fields__", {}).get("NumberIntervall", {})
            err = fields.get("error")
            if err in {"plus_infinity", "minus_infinity", "any_number"}:
                return str(err)
            if err == "upper_bound_is_plus_infinity":
                lower = fields.get("lower")
                return f"[{lower}, infinity]"
            if err == "lower_bound_is_minus_infinity":
                upper = fields.get("upper")
                return f"[-infinity, {upper}]"
            if err == "wrapped_interval":
                lower = fields.get("lower")
                upper = fields.get("upper")
                return f"[{lower}, {upper}]"
            if "lower" in fields and "upper" in fields:
                lower = fields.get("lower")
                upper = fields.get("upper")
                center = (lower + upper) / 2
                radius = (upper - lower) / 2

                def _format_float(val: float) -> str:
                    abs_val = abs(val)
                    if abs_val >= 1e-9:
                        rounded = round(val, 12)
                        if abs(rounded - val) <= abs_val * 1e-12:
                            val = rounded
                    return str(val)

                return f"{_format_float(center)} +/- {_format_float(radius)}"
        if isinstance(val, bool):
            return "true" if val else "false"
        if val is None:
            return "Null"
        return str(val)

    @staticmethod
    def _is_truthy(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if val is None:
            return False
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, str):
            return len(val) > 0
        try:
            return bool(val)
        except Exception:
            return True

    
