"""Lightweight LLVM IR prototype for TinyLanguage.

The goal of this prototype is to expose a minimal code path that can translate
the native stack-based IR into a textual LLVM module. It intentionally supports
the constructs needed for the tutorial-style examples (numeric literals,
assignments, arithmetic, comparisons, simple control flow, and `print`) and
will raise ``NotImplementedError`` for everything else. The output is meant for
inspection or piping into external tools like ``llc`` rather than for
production-grade code generation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from native_ir import FunctionIR, Instruction, Opcode, OperatorOverloadIR, ProgramIR


@dataclass
class _StackValue:
    """Keep track of a value's type and SSA name for LLVM emission."""

    name: str
    ty: str
    source: Optional[str] = None
    literal: Optional[int] = None
    literal_str: Optional[str] = None
    class_name: Optional[str] = None
    variant_name: Optional[str] = None


@dataclass(frozen=True)
class _ResolvedFunctionSignature:
    param_types: Dict[str, str]
    return_type: str


@dataclass
class _FunctionSignature:
    param_types: Dict[str, Optional[str]]
    return_type: Optional[str]


@dataclass
class _TypeValue:
    ty: Optional[str]
    source: Optional[str] = None
    literal: Optional[int] = None
    literal_str: Optional[str] = None
    class_name: Optional[str] = None
    variant_name: Optional[str] = None


class LLVMCodeGenerator:
    """Translate ``ProgramIR`` instructions into textual LLVM IR."""

    def __init__(self, *, target_triple: Optional[str] = None, data_layout: Optional[str] = None) -> None:
        self._tmp_index = 0
        self._label_index = 0
        self._stack: List[_StackValue] = []
        self._allocas: Dict[str, str] = {}
        self._var_types: Dict[str, str] = {}
        self._var_literals: Dict[str, int] = {}
        self._var_classes: Dict[str, str] = {}
        self._var_variants: Dict[str, str] = {}
        self._prologue: List[str] = []
        self._body: List[str] = []
        self._string_constants: Dict[str, Tuple[str, int]] = {}
        self._string_defs: List[str] = []
        self._function_signatures: Dict[str, _ResolvedFunctionSignature] = {}
        self._current_return_type: Optional[str] = None
        self._current_instruction: Optional[Instruction] = None
        self._heap_cell_types: Dict[Tuple[str, int], str] = {}
        self._class_layouts: Dict[str, List[Tuple[str, str]]] = {}
        self._class_mros: Dict[str, List[str]] = {}
        self._class_ids: Dict[str, int] = {}
        self._class_methods: Dict[str, Dict[str, str]] = {}
        self._class_field_types: Dict[Tuple[str, int], str] = {}
        self._variant_fields: Dict[str, List[str]] = {}
        self._variant_field_types: Dict[Tuple[str, str], str] = {}
        self._variant_to_type: Dict[str, str] = {}
        self._target_triple = target_triple
        self._data_layout = data_layout
        self._operator_overloads: Dict[Tuple[str, str, str], str] = {}

    def _format_opcode(self, op: Opcode) -> str:
        return op.value if isinstance(op, Opcode) else str(op)

    def _supported_opcodes(self) -> str:
        return ", ".join(self._format_opcode(op) for op in Opcode)

    def _instruction_context(self, instr: Optional[Instruction] = None) -> str:
        if instr is None:
            return ""
        op_name = self._format_opcode(instr.op)
        if instr.arg is None:
            return f" (instruction: {op_name})"
        return f" (instruction: {op_name} {instr.arg!r})"

    def _lowering_error(self, reason: str, instr: Optional[Instruction] = None) -> None:
        context = self._instruction_context(instr or self._current_instruction)
        raise NotImplementedError(f"LLVM prototype missing lowering: {reason}{context}")

    def _unsupported_opcode(self, instr: Instruction) -> None:
        op_name = self._format_opcode(instr.op)
        self._lowering_error(
            f"opcode {op_name} not supported. Supported opcodes: {self._supported_opcodes()}.",
            instr,
        )

    def compile_program(self, program: ProgramIR) -> str:
        """Return LLVM IR for the given native ``ProgramIR``.

        The LLVM prototype supports top-level code plus simple user-defined
        functions and calls over the numeric subset. Complex types remain out of
        scope so gaps stay visible during experimentation.
        """

        self._register_type_metadata(program)
        self._register_class_metadata(program)
        self._operator_overloads = self._register_operator_overloads(program.operator_overloads)
        self._class_field_types.clear()
        self._function_signatures = self._infer_signatures(program)
        self._string_constants.clear()
        self._string_defs.clear()

        function_blocks: List[List[str]] = []
        for func in program.functions.values():
            function_blocks.append(self._compile_function(func, self._function_signatures[func.name]))
        entry_block = self._compile_entry(program.entry)

        lines: List[str] = []
        lines.extend(self._header())
        lines.extend(self._string_defs)
        for block in function_blocks:
            lines.extend(block)
        lines.extend(entry_block)
        return "\n".join(lines)

    def _compile_entry(self, instructions: List[Instruction]) -> List[str]:
        self._tmp_index = 0
        self._label_index = 0
        self._stack.clear()
        self._allocas.clear()
        self._var_types.clear()
        self._var_literals.clear()
        self._var_classes.clear()
        self._var_variants.clear()
        self._prologue.clear()
        self._body.clear()
        self._current_return_type = None
        self._heap_cell_types.clear()

        block_starts = self._collect_block_starts(instructions)
        label_map = self._label_map(block_starts)
        self._emit_blocks(instructions, block_starts, label_map, allow_return=False, exit_label="exit")

        lines: List[str] = []
        lines.append("define i32 @tiny_main() {")
        lines.append("entry:")
        lines.extend(self._prologue)
        lines.append(f"  br label %{label_map[0]}")
        lines.extend(self._body)
        lines.append("exit:")
        lines.append("  ret i32 0")
        lines.append("}")
        return lines

    def _compile_function(self, func: FunctionIR, signature: _ResolvedFunctionSignature) -> List[str]:
        self._tmp_index = 0
        self._label_index = 0
        self._stack.clear()
        self._allocas.clear()
        self._var_types.clear()
        self._var_literals.clear()
        self._var_classes.clear()
        self._var_variants.clear()
        self._prologue.clear()
        self._body.clear()
        self._current_return_type = signature.return_type
        self._heap_cell_types.clear()

        params: List[Tuple[str, str]] = [(name, signature.param_types[name]) for name in func.params]
        for name, ty in params:
            addr_name = f"{name}.addr"
            arg_name = f"{name}.arg"
            self._allocas[name] = addr_name
            self._var_types[name] = ty
            self._prologue.append(f"  %{addr_name} = alloca {ty}")
            self._prologue.append(f"  store {ty} %{arg_name}, {ty}* %{addr_name}")
        if "." in func.name and func.params:
            self._var_classes[func.params[0]] = func.name.split(".", 1)[0]

        block_starts = self._collect_block_starts(func.instructions)
        label_map = self._label_map(block_starts)
        self._emit_blocks(func.instructions, block_starts, label_map, allow_return=True, exit_label="exit")

        param_sig = ", ".join(f"{ty} %{name}.arg" for name, ty in params)
        lines: List[str] = []
        lines.append(f"define {signature.return_type} @{func.name}({param_sig}) {{")
        lines.append("entry:")
        lines.extend(self._prologue)
        lines.append(f"  br label %{label_map[0]}")
        lines.extend(self._body)
        lines.append("exit:")
        lines.append(f"  ret {signature.return_type} {self._zero_value(signature.return_type)}")
        lines.append("}")
        return lines

    def _zero_value(self, ty: str) -> str:
        if ty == "double":
            return "0.0"
        if ty == "i1":
            return "0"
        if ty == "i64":
            return "0"
        raise NotImplementedError(f"zero literal not supported for type {ty}")

    def _collect_block_starts(self, instructions: List[Instruction]) -> List[int]:
        starts = {0}
        for idx, instr in enumerate(instructions):
            if instr.op == Opcode.JUMP:
                if instr.arg is not None:
                    target = int(instr.arg)
                    if target != len(instructions):
                        starts.add(target)
            elif instr.op == Opcode.JUMP_IF_FALSE:
                if instr.arg is not None:
                    target = int(instr.arg)
                    if target != len(instructions):
                        starts.add(target)
                if idx + 1 < len(instructions):
                    starts.add(idx + 1)
        return sorted(starts)

    def _label_map(self, block_starts: List[int]) -> Dict[int, str]:
        return {start: f"block{start}" for start in block_starts}

    def _emit_blocks(
        self,
        instructions: List[Instruction],
        block_starts: List[int],
        label_map: Dict[int, str],
        allow_return: bool,
        exit_label: str,
    ) -> None:
        for index, start in enumerate(block_starts):
            if self._stack:
                raise NotImplementedError("LLVM prototype cannot carry stack values across basic blocks")
            self._body.append(f"{label_map[start]}:")
            end = block_starts[index + 1] if index + 1 < len(block_starts) else len(instructions)
            terminated = self._emit_block_body(instructions, start, end, label_map, allow_return, exit_label)
            if not terminated:
                if self._stack:
                    raise NotImplementedError("LLVM prototype cannot carry stack values across basic blocks")
                next_label = (
                    label_map[block_starts[index + 1]] if index + 1 < len(block_starts) else exit_label
                )
                self._body.append(f"  br label %{next_label}")

    def _emit_block_body(
        self,
        instructions: List[Instruction],
        start: int,
        end: int,
        label_map: Dict[int, str],
        allow_return: bool,
        exit_label: str,
    ) -> bool:
        self._stack.clear()
        for idx in range(start, end):
            instr = instructions[idx]
            self._current_instruction = instr
            if instr.op == Opcode.JUMP:
                if self._stack:
                    self._lowering_error("cannot carry stack values across basic blocks", instr)
                target = int(instr.arg)
                target_label = "exit" if target == len(instructions) else label_map[target]
                self._body.append(f"  br label %{target_label}")
                return True
            if instr.op == Opcode.JUMP_IF_FALSE:
                cond_name = self._pop_condition()
                if self._stack:
                    self._lowering_error("cannot carry stack values across basic blocks", instr)
                target = int(instr.arg)
                target_label = exit_label if target == len(instructions) else label_map[target]
                fallthrough = idx + 1
                fallthrough_label = exit_label if fallthrough == len(instructions) else label_map[fallthrough]
                self._body.append(f"  br i1 {cond_name}, label %{fallthrough_label}, label %{target_label}")
                return True
            if instr.op == Opcode.RETURN:
                if not allow_return:
                    continue
                if not self._stack:
                    self._lowering_error("return requires a value", instr)
                value = self._stack.pop()
                self._body.append(f"  ret {value.ty} {value.name}")
                return True
            self._emit_instruction(instr)
        return False

    # ----- Instruction handlers -----

    def _emit_instruction(self, instr: Instruction) -> None:
        if instr.op == Opcode.PUSH_CONST:
            self._push_const(instr.arg)
        elif instr.op == Opcode.LOAD:
            self._load_var(instr.arg)
        elif instr.op == Opcode.STORE:
            self._store_var(instr.arg)
        elif instr.op == Opcode.BINARY:
            self._binary_op(instr.arg)
        elif instr.op == Opcode.PRINT:
            self._print_values(int(instr.arg))
        elif instr.op == Opcode.POP:
            self._pop_value()
        elif instr.op == Opcode.FLUSH:
            self._flush_output()
        elif instr.op == Opcode.CALL:
            self._call_function(instr.arg)
        elif instr.op == Opcode.RETURN:
            # The surrounding function emits a single final return, so intermediate
            # returns are ignored for now.
            return
        else:
            self._unsupported_opcode(instr)

    def _push_const(self, value: object) -> None:
        if value is None:
            self._stack.append(_StackValue(name="null", ty="i8*"))
        elif isinstance(value, bool):
            self._stack.append(_StackValue(name="1" if value else "0", ty="i1"))
        elif isinstance(value, int):
            self._stack.append(_StackValue(name=str(value), ty="i64", literal=value))
        elif isinstance(value, float):
            self._stack.append(_StackValue(name=f"{value:.6e}", ty="double"))
        elif isinstance(value, str):
            name, length = self._string_constant(value)
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = getelementptr inbounds [{length} x i8], [{length} x i8]* @{name}, i32 0, i32 0"
            )
            self._stack.append(_StackValue(name=dest, ty="i8*", literal_str=value))
        else:
            self._lowering_error(
                f"constants of type {type(value).__name__} are not supported",
            )

    def _load_var(self, name: str) -> None:
        if name in {"Map", "Set", "Deque"}:
            self._stack.append(_StackValue(name=name, ty="i64", class_name=name))
            return
        ty = self._var_types.get(name)
        if ty is None:
            self._lowering_error(f"unknown variable {name}")
        dest = self._next_tmp()
        self._body.append(f"  {dest} = load {ty}, {ty}* %{self._allocas[name]}")
        literal = self._var_literals.get(name)
        class_name = self._var_classes.get(name)
        variant_name = self._var_variants.get(name)
        self._stack.append(
            _StackValue(
                name=dest,
                ty=ty,
                source=name,
                literal=literal,
                class_name=class_name,
                variant_name=variant_name,
            )
        )

    def _store_var(self, name: str) -> None:
        if not self._stack:
            raise RuntimeError("store requested with empty stack")
        value = self._stack.pop()
        if name not in self._allocas:
            self._allocas[name] = name
            self._var_types[name] = value.ty
            self._prologue.append(f"  %{name} = alloca {value.ty}")
        if value.ty == "i64" and value.literal is not None:
            self._var_literals[name] = value.literal
        else:
            self._var_literals.pop(name, None)
        if value.class_name:
            self._var_classes[name] = value.class_name
        else:
            self._var_classes.pop(name, None)
        if value.variant_name:
            self._var_variants[name] = value.variant_name
        else:
            self._var_variants.pop(name, None)
        if value.source and value.source != name:
            for (ptr_name, idx), cell_ty in list(self._heap_cell_types.items()):
                if ptr_name == value.source:
                    self._heap_cell_types[(name, idx)] = cell_ty
        self._body.append(f"  store {value.ty} {value.name}, {value.ty}* %{self._allocas[name]}")

    def _binary_op(self, op: str) -> None:
        right = self._stack.pop()
        left = self._stack.pop()
        if left.ty != right.ty:
            self._lowering_error(
                f"mixed-type arithmetic not supported ({left.ty} vs {right.ty})"
            )

        overload_name = self._operator_overloads.get((op, left.ty, right.ty))
        if overload_name is not None:
            signature = self._function_signatures.get(overload_name)
            if signature is None:
                self._lowering_error(f"unknown operator overload {overload_name}")
            if len(signature.param_types) != 2:
                self._lowering_error(
                    f"operator overload {overload_name} expects 2 args, got {len(signature.param_types)}"
                )
            rendered_args: List[str] = []
            for (param_name, param_type), arg in zip(signature.param_types.items(), (left, right)):
                if arg.ty != param_type:
                    self._lowering_error(
                        f"argument for {overload_name}.{param_name} expected {param_type}, got {arg.ty}"
                    )
                rendered_args.append(f"{param_type} {arg.name}")
            dest = self._next_tmp()
            args_text = ", ".join(rendered_args)
            self._body.append(f"  {dest} = call {signature.return_type} @{overload_name}({args_text})")
            self._stack.append(_StackValue(name=dest, ty=signature.return_type))
            return

        if op in {"+", "-", "*", "/", "%"}:
            self._emit_arithmetic_op(op, left, right)
            return
        if op in {"==", "!=", "<", ">", "<=", ">="}:
            self._emit_comparison(op, left, right)
            return
        self._lowering_error(f"operator {op} not supported")

    def _emit_arithmetic_op(self, op: str, left: _StackValue, right: _StackValue) -> None:
        ty = left.ty
        dest = self._next_tmp()
        if ty == "double":
            instr = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv", "%": "frem"}.get(op)
        else:
            instr = {"+": "add", "-": "sub", "*": "mul", "/": "sdiv", "%": "srem"}.get(op)
        if instr is None:
            self._lowering_error(f"operator {op} not supported for type {ty}")
        self._body.append(f"  {dest} = {instr} {ty} {left.name}, {right.name}")
        self._stack.append(_StackValue(name=dest, ty=ty))

    def _emit_comparison(self, op: str, left: _StackValue, right: _StackValue) -> None:
        ty = left.ty
        dest = self._next_tmp()
        if ty == "double":
            predicate = {
                "==": "oeq",
                "!=": "one",
                "<": "olt",
                ">": "ogt",
                "<=": "ole",
                ">=": "oge",
            }.get(op)
            if predicate is None:
                self._lowering_error(f"comparison {op} not supported for type {ty}")
            self._body.append(f"  {dest} = fcmp {predicate} {ty} {left.name}, {right.name}")
        elif ty == "i8*":
            predicate = {"==": "eq", "!=": "ne"}.get(op)
            if predicate is None:
                self._lowering_error(f"comparison {op} not supported for type {ty}")
            self._body.append(f"  {dest} = icmp {predicate} {ty} {left.name}, {right.name}")
        else:
            predicate = {
                "==": "eq",
                "!=": "ne",
                "<": "slt",
                ">": "sgt",
                "<=": "sle",
                ">=": "sge",
            }.get(op)
            if predicate is None:
                self._lowering_error(f"comparison {op} not supported for type {ty}")
            self._body.append(f"  {dest} = icmp {predicate} {ty} {left.name}, {right.name}")
        self._stack.append(_StackValue(name=dest, ty="i1"))

    def _print_values(self, count: int) -> None:
        if count <= 0:
            return
        values = [self._stack.pop() for _ in range(count)][::-1]
        for value in values:
            fmt, fmt_len = self._format_for_type(value.ty)
            fmt_ptr = self._next_tmp()
            self._body.append(
                f"  {fmt_ptr} = getelementptr inbounds [{fmt_len} x i8], [{fmt_len} x i8]* @{fmt}, i32 0, i32 0"
            )
            if value.ty == "i1":
                widened = self._next_tmp()
                self._body.append(f"  {widened} = zext i1 {value.name} to i64")
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i64 {widened})")
            elif value.ty == "i8*":
                is_null = self._next_tmp()
                null_label = self._next_label("print.null")
                value_label = self._next_label("print.str")
                done_label = self._next_label("print.done")
                self._body.append(f"  {is_null} = icmp eq i8* {value.name}, null")
                self._body.append(f"  br i1 {is_null}, label %{null_label}, label %{value_label}")
                self._body.append(f"{null_label}:")
                null_name, null_len = self._string_constant("Null")
                null_ptr = self._next_tmp()
                self._body.append(
                    f"  {null_ptr} = getelementptr inbounds [{null_len} x i8], [{null_len} x i8]* @{null_name}, i32 0, i32 0"
                )
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i8* {null_ptr})")
                self._body.append(f"  br label %{done_label}")
                self._body.append(f"{value_label}:")
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, i8* {value.name})")
                self._body.append(f"  br label %{done_label}")
                self._body.append(f"{done_label}:")
            else:
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, {value.ty} {value.name})")

    def _pop_value(self) -> None:
        if not self._stack:
            raise RuntimeError("cannot POP from an empty LLVM prototype stack")
        self._stack.pop()

    def _flush_output(self) -> None:
        self._body.append("  call i32 @fflush(i8* null)")

    def _value_payload(self, value: _StackValue) -> str:
        if value.ty == "i64":
            return value.name
        dest = self._next_tmp()
        if value.ty == "i1":
            self._body.append(f"  {dest} = zext i1 {value.name} to i64")
            return dest
        if value.ty == "double":
            self._body.append(f"  {dest} = bitcast double {value.name} to i64")
            return dest
        if value.ty == "i8*":
            self._body.append(f"  {dest} = ptrtoint i8* {value.name} to i64")
            return dest
        self._lowering_error(f"cannot lower payload for type {value.ty}")
        return dest

    def _payload_to_value(self, payload: str, target_ty: str) -> _StackValue:
        if target_ty == "i64":
            return _StackValue(name=payload, ty="i64")
        dest = self._next_tmp()
        if target_ty == "i1":
            self._body.append(f"  {dest} = trunc i64 {payload} to i1")
            return _StackValue(name=dest, ty="i1")
        if target_ty == "double":
            self._body.append(f"  {dest} = bitcast i64 {payload} to double")
            return _StackValue(name=dest, ty="double")
        if target_ty == "i8*":
            self._body.append(f"  {dest} = inttoptr i64 {payload} to i8*")
            return _StackValue(name=dest, ty="i8*")
        self._lowering_error(f"cannot unbox payload for type {target_ty}")
        return _StackValue(name=payload, ty=target_ty)

    def _call_function(self, call_spec: Tuple[str, int]) -> None:
        name, argc = call_spec
        args = [self._stack.pop() for _ in range(argc)][::-1]
        if name.startswith("Map."):
            self._emit_map_call(name, args)
            return
        if name.startswith("Set."):
            self._emit_set_call(name, args)
            return
        if name.startswith("Deque."):
            self._emit_deque_call(name, args)
            return
        if name == "__variant_assume":
            if len(args) != 2:
                self._lowering_error("__variant_assume expects 2 args")
            variant_name = self._literal_string(args[1], context="__variant_assume")
            value = args[0]
            self._stack.append(
                _StackValue(
                    name=value.name,
                    ty=value.ty,
                    source=value.source,
                    literal=value.literal,
                    literal_str=value.literal_str,
                    class_name=value.class_name,
                    variant_name=variant_name,
                )
            )
            return
        if name == "__variant_new":
            self._emit_variant_new(args)
            return
        if name == "__variant_tag":
            self._emit_variant_tag(args)
            return
        if name == "__variant_get":
            self._emit_variant_get(args)
            return
        if name == "__match_error":
            self._emit_match_error(args)
            return
        if name == "__class_new":
            self._emit_class_new(args)
            return
        if name == "__field_get":
            self._emit_field_get(args)
            return
        if name == "__field_set":
            self._emit_field_set(args)
            return
        if name == "__method_call":
            self._emit_method_call(args)
            return
        resolved_name = name
        if name == "heap_set":
            resolved_name = self._resolve_heap_set_name(args)
        elif name == "heap_get":
            resolved_name = self._resolve_heap_get_name(args)

        signature = self._function_signatures.get(resolved_name)
        if signature is None:
            signature = self._builtin_signature(resolved_name)
        if signature is None:
            self._lowering_error(f"unknown function {resolved_name}")
        if argc != len(signature.param_types):
            self._lowering_error(
                f"function {resolved_name} expects {len(signature.param_types)} args, got {argc}"
            )
        rendered_args: List[str] = []
        for (param_name, param_type), arg in zip(signature.param_types.items(), args):
            if arg.ty != param_type:
                self._lowering_error(
                    f"argument for {resolved_name}.{param_name} expected {param_type}, got {arg.ty}"
                )
            rendered_args.append(f"{param_type} {arg.name}")
        dest = self._next_tmp()
        args_text = ", ".join(rendered_args)
        self._body.append(f"  {dest} = call {signature.return_type} @{resolved_name}({args_text})")
        self._stack.append(_StackValue(name=dest, ty=signature.return_type))
        if name == "heap_set":
            self._record_heap_cell_type(args)

    def _emit_map_call(self, name: str, args: List[_StackValue]) -> None:
        method = name.split(".", 1)[1]
        if method == "new":
            if args:
                self._lowering_error("Map.new expects 0 args")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_new()")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "len":
            if len(args) != 1:
                self._lowering_error("Map.len expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_len(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "set":
            if len(args) != 3:
                self._lowering_error("Map.set expects 3 args")
            key_payload = self._value_payload(args[1])
            value_payload = self._value_payload(args[2])
            self._body.append(
                f"  call i64 @__map_set(i64 {args[0].name}, i64 {key_payload}, i64 {value_payload})"
            )
            self._stack.append(args[2])
            return
        if method == "get":
            if len(args) not in {2, 3}:
                self._lowering_error("Map.get expects 2 or 3 args")
            key_payload = self._value_payload(args[1])
            default_ty = args[2].ty if len(args) == 3 else "i64"
            default_payload = self._value_payload(args[2]) if len(args) == 3 else "0"
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i64 @__map_get(i64 {args[0].name}, i64 {key_payload}, i64 {default_payload})"
            )
            self._stack.append(self._payload_to_value(dest, default_ty))
            return
        if method == "has":
            if len(args) != 2:
                self._lowering_error("Map.has expects 2 args")
            key_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i1 @__map_has(i64 {args[0].name}, i64 {key_payload})")
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "delete":
            if len(args) != 2:
                self._lowering_error("Map.delete expects 2 args")
            key_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i1 @__map_delete(i64 {args[0].name}, i64 {key_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "keys":
            if len(args) != 1:
                self._lowering_error("Map.keys expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_keys(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "values":
            if len(args) != 1:
                self._lowering_error("Map.values expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_values(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "entries":
            if len(args) != 1:
                self._lowering_error("Map.entries expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_entries(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "from_entries":
            if len(args) != 1:
                self._lowering_error("Map.from_entries expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__map_from_entries(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        self._lowering_error(f"unknown Map method {method}")

    def _emit_set_call(self, name: str, args: List[_StackValue]) -> None:
        method = name.split(".", 1)[1]
        if method == "new":
            if args:
                self._lowering_error("Set.new expects 0 args")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__set_new()")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "from_list":
            if len(args) != 1:
                self._lowering_error("Set.from_list expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__set_from_list(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "len":
            if len(args) != 1:
                self._lowering_error("Set.len expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__set_len(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "add":
            if len(args) != 2:
                self._lowering_error("Set.add expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i1 @__set_add(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "delete":
            if len(args) != 2:
                self._lowering_error("Set.delete expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i1 @__set_delete(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "has":
            if len(args) != 2:
                self._lowering_error("Set.has expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i1 @__set_has(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i1"))
            return
        if method == "to_list":
            if len(args) != 1:
                self._lowering_error("Set.to_list expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__set_to_list(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        self._lowering_error(f"unknown Set method {method}")

    def _emit_deque_call(self, name: str, args: List[_StackValue]) -> None:
        method = name.split(".", 1)[1]
        if method == "new":
            if len(args) > 1:
                self._lowering_error("Deque.new expects 0 or 1 args")
            dest = self._next_tmp()
            if args:
                self._body.append(f"  {dest} = call i64 @__deque_from_list(i64 {args[0].name})")
            else:
                self._body.append(f"  {dest} = call i64 @__deque_new()")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "len":
            if len(args) != 1:
                self._lowering_error("Deque.len expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_len(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "push_left":
            if len(args) != 2:
                self._lowering_error("Deque.push_left expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i64 @__deque_push_left(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "push_right":
            if len(args) != 2:
                self._lowering_error("Deque.push_right expects 2 args")
            value_payload = self._value_payload(args[1])
            dest = self._next_tmp()
            self._body.append(
                f"  {dest} = call i64 @__deque_push_right(i64 {args[0].name}, i64 {value_payload})"
            )
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "pop_left":
            if len(args) != 1:
                self._lowering_error("Deque.pop_left expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_pop_left(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "pop_right":
            if len(args) != 1:
                self._lowering_error("Deque.pop_right expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_pop_right(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "peek_left":
            if len(args) != 1:
                self._lowering_error("Deque.peek_left expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_peek_left(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "peek_right":
            if len(args) != 1:
                self._lowering_error("Deque.peek_right expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_peek_right(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        if method == "to_list":
            if len(args) != 1:
                self._lowering_error("Deque.to_list expects 1 arg")
            dest = self._next_tmp()
            self._body.append(f"  {dest} = call i64 @__deque_to_list(i64 {args[0].name})")
            self._stack.append(_StackValue(name=dest, ty="i64"))
            return
        self._lowering_error(f"unknown Deque method {method}")

    def _emit_class_new(self, args: List[_StackValue]) -> None:
        if not args:
            self._lowering_error("__class_new expects at least 1 arg")
        class_name = self._literal_string(args[0], context="__class_new")
        layout = self._class_layouts.get(class_name)
        if layout is None:
            self._lowering_error(f"unknown class {class_name}")
        if (len(args) - 1) % 2 != 0:
            self._lowering_error("__class_new expects field name/value pairs")
        size = len(layout) + 1
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i64 @__new(i64 {size})")
        ptr = _StackValue(name=dest, ty="i64", source=dest, class_name=class_name)
        class_id = self._class_ids[class_name]
        self._emit_heap_set(ptr, 0, self._const_i64(class_id))
        for index in range(1, len(args), 2):
            field_name = self._literal_string(args[index], context="__class_new")
            value = args[index + 1]
            field_index = self._class_field_index(class_name, field_name)
            self._emit_heap_set(ptr, field_index, value)
            self._class_field_types[(class_name, field_index)] = value.ty
        self._stack.append(_StackValue(name=dest, ty="i64", source=dest, class_name=class_name))

    def _emit_field_get(self, args: List[_StackValue]) -> None:
        if len(args) != 2:
            self._lowering_error("__field_get expects 2 args")
        obj, field_name = args
        class_name = obj.class_name
        if class_name is None:
            self._lowering_error("field access on unknown class value")
        field_literal = self._literal_string(field_name, context="__field_get")
        field_index = self._class_field_index(class_name, field_literal)
        resolved_name = self._resolve_class_heap_get_name(class_name, field_index)
        dest = self._next_tmp()
        arg_text = f"i64 {obj.name}, i64 {field_index}"
        self._body.append(f"  {dest} = call {self._heap_get_return_type(resolved_name)} @{resolved_name}({arg_text})")
        self._stack.append(
            _StackValue(name=dest, ty=self._heap_get_return_type(resolved_name))
        )

    def _emit_field_set(self, args: List[_StackValue]) -> None:
        if len(args) != 3:
            self._lowering_error("__field_set expects 3 args")
        obj, field_name, value = args
        class_name = obj.class_name
        if class_name is None:
            self._lowering_error("field access on unknown class value")
        field_literal = self._literal_string(field_name, context="__field_set")
        field_index = self._class_field_index(class_name, field_literal)
        self._emit_heap_set(obj, field_index, value)
        self._class_field_types[(class_name, field_index)] = value.ty
        self._stack.append(value)

    def _emit_method_call(self, args: List[_StackValue]) -> None:
        if len(args) < 2:
            self._lowering_error("__method_call expects at least 2 args")
        obj, method_name, *rest = args
        class_name = obj.class_name
        if class_name in {"Map", "Set", "Deque"}:
            method_literal = self._literal_string(method_name, context="__method_call")
            if class_name == "Map":
                self._emit_map_call(f"Map.{method_literal}", rest)
            elif class_name == "Set":
                self._emit_set_call(f"Set.{method_literal}", rest)
            else:
                self._emit_deque_call(f"Deque.{method_literal}", rest)
            return
        if class_name is None:
            self._lowering_error("method call on unknown class value")
        method_literal = self._literal_string(method_name, context="__method_call")
        target_name = self._resolve_method_target(class_name, method_literal)
        signature = self._function_signatures.get(target_name)
        if signature is None:
            self._lowering_error(f"unknown function {target_name}")
        call_args = [obj] + list(rest)
        if len(call_args) != len(signature.param_types):
            self._lowering_error(
                f"function {target_name} expects {len(signature.param_types)} args, got {len(call_args)}"
            )
        rendered_args: List[str] = []
        for (param_name, param_type), arg in zip(signature.param_types.items(), call_args):
            if arg.ty != param_type:
                self._lowering_error(
                    f"argument for {target_name}.{param_name} expected {param_type}, got {arg.ty}"
                )
            rendered_args.append(f"{param_type} {arg.name}")
        dest = self._next_tmp()
        args_text = ", ".join(rendered_args)
        self._body.append(f"  {dest} = call {signature.return_type} @{target_name}({args_text})")
        self._stack.append(_StackValue(name=dest, ty=signature.return_type))

    def _emit_variant_new(self, args: List[_StackValue]) -> None:
        if len(args) < 2:
            self._lowering_error("__variant_new expects at least 2 args (variant, type_name)")
        variant_name = self._literal_string(args[0], context="__variant_new")
        type_name = args[1].literal_str
        if type_name is None:
            type_name = self._variant_to_type.get(variant_name)
        fields = self._variant_fields.get(variant_name)
        if fields is None:
            self._lowering_error(f"unknown variant {variant_name}")
        if (len(args) - 2) % 2 != 0:
            self._lowering_error("__variant_new expects field name/value pairs")
        provided_fields = {}
        for index in range(2, len(args), 2):
            field_name = self._literal_string(args[index], context="__variant_new")
            provided_fields[field_name] = args[index + 1]
        missing = sorted(set(fields) - set(provided_fields.keys()))
        extra = sorted(set(provided_fields.keys()) - set(fields))
        if missing:
            self._lowering_error(f"missing field(s) for variant {variant_name}: {', '.join(missing)}")
        if extra:
            self._lowering_error(f"unknown field(s) for variant {variant_name}: {', '.join(extra)}")
        size = len(fields) + 1
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i64 @__new(i64 {size})")
        ptr = _StackValue(name=dest, ty="i64", source=dest, variant_name=variant_name)
        self._emit_heap_set(ptr, 0, _StackValue(name=args[0].name, ty="i8*", literal_str=variant_name))
        for idx, field_name in enumerate(fields, start=1):
            value = provided_fields[field_name]
            self._emit_heap_set(ptr, idx, value)
        if type_name is not None:
            self._variant_to_type.setdefault(variant_name, type_name)
        self._stack.append(_StackValue(name=dest, ty="i64", variant_name=variant_name))

    def _emit_variant_tag(self, args: List[_StackValue]) -> None:
        if len(args) != 1:
            self._lowering_error("__variant_tag expects 1 arg")
        value = args[0]
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call i8* @heap_get_str(i64 {value.name}, i64 0)")
        self._stack.append(_StackValue(name=dest, ty="i8*", literal_str=value.variant_name))

    def _emit_variant_get(self, args: List[_StackValue]) -> None:
        if len(args) != 2:
            self._lowering_error("__variant_get expects 2 args")
        value, field_name_value = args
        field_name = self._literal_string(field_name_value, context="__variant_get")
        variant_name = self._resolve_variant_name(value)
        if variant_name is None:
            self._lowering_error("variant access on unknown tagged value")
        field_index = self._variant_field_index(variant_name, field_name)
        field_type = self._variant_field_type(variant_name, field_name)
        resolved_name = self._resolve_variant_heap_get_name(field_type)
        dest = self._next_tmp()
        self._body.append(f"  {dest} = call {field_type} @{resolved_name}(i64 {value.name}, i64 {field_index})")
        self._stack.append(_StackValue(name=dest, ty=field_type))

    def _emit_match_error(self, args: List[_StackValue]) -> None:
        if len(args) != 1:
            self._lowering_error("__match_error expects 1 arg")
        arg = args[0]
        self._body.append(f"  call void @__match_error(i64 {arg.name})")

    # ----- Helpers -----

    def _pop_condition(self) -> str:
        if not self._stack:
            raise RuntimeError("branch requested with empty stack")
        cond = self._stack.pop()
        if cond.ty == "i1":
            return cond.name
        if cond.ty == "i64":
            dest = self._next_tmp()
            self._body.append(f"  {dest} = icmp ne i64 {cond.name}, 0")
            return dest
        if cond.ty == "double":
            dest = self._next_tmp()
            self._body.append(f"  {dest} = fcmp one double {cond.name}, 0.0")
            return dest
        self._lowering_error(f"conditional branches for type {cond.ty} not supported")

    def _resolve_variant_name(self, value: _StackValue) -> Optional[str]:
        if value.variant_name:
            return value.variant_name
        if value.source:
            return self._var_variants.get(value.source)
        return None

    def _literal_string(self, value: _StackValue, *, context: str) -> str:
        if value.literal_str is None:
            self._lowering_error(f"{context} expects a string literal")
        return value.literal_str

    def _const_i64(self, value: int) -> _StackValue:
        return _StackValue(name=str(value), ty="i64", literal=value)

    def _emit_heap_set(self, ptr: _StackValue, idx: int, value: _StackValue) -> None:
        idx_value = self._const_i64(idx)
        args = [ptr, idx_value, value]
        resolved_name = self._resolve_heap_set_name(args)
        signature = self._builtin_signature(resolved_name)
        if signature is None:
            self._lowering_error(f"unknown function {resolved_name}")
        rendered_args: List[str] = []
        for (param_name, param_type), arg in zip(signature.param_types.items(), args):
            if arg.ty != param_type:
                self._lowering_error(
                    f"argument for {resolved_name}.{param_name} expected {param_type}, got {arg.ty}"
                )
            rendered_args.append(f"{param_type} {arg.name}")
        dest = self._next_tmp()
        args_text = ", ".join(rendered_args)
        self._body.append(f"  {dest} = call {signature.return_type} @{resolved_name}({args_text})")
        self._record_heap_cell_type(args)

    def _resolve_class_heap_get_name(self, class_name: str, field_index: int) -> str:
        cell_type = self._class_field_types.get((class_name, field_index))
        if cell_type == "i8*":
            return "heap_get_str"
        if cell_type == "double":
            return "heap_get_double"
        if cell_type == "i1":
            return "heap_get_bool"
        return "heap_get"

    def _heap_get_return_type(self, name: str) -> str:
        if name == "heap_get_str":
            return "i8*"
        if name == "heap_get_double":
            return "double"
        if name == "heap_get_bool":
            return "i1"
        return "i64"

    def _resolve_variant_heap_get_name(self, field_type: str) -> str:
        if field_type == "i8*":
            return "heap_get_str"
        if field_type == "double":
            return "heap_get_double"
        if field_type == "i1":
            return "heap_get_bool"
        return "heap_get"

    def _variant_field_index(self, variant_name: str, field_name: str) -> int:
        fields = self._variant_fields.get(variant_name)
        if fields is None:
            self._lowering_error(f"unknown variant {variant_name}")
        if field_name not in fields:
            self._lowering_error(f"field {field_name} missing for variant {variant_name}")
        return fields.index(field_name) + 1

    def _variant_field_type(self, variant_name: str, field_name: str) -> str:
        return self._variant_field_types.get((variant_name, field_name), "i64")

    def _split_field_name(self, field_name: str) -> Tuple[Optional[str], str]:
        if "." in field_name:
            owner, rest = field_name.split(".", 1)
            return owner, rest
        return None, field_name

    def _class_field_index(self, class_name: str, field_name: str) -> int:
        layout = self._class_layouts.get(class_name)
        if layout is None:
            self._lowering_error(f"unknown class {class_name}")
        owner_hint, raw_name = self._split_field_name(field_name)
        matches = [
            (idx, owner)
            for idx, (owner, fname) in enumerate(layout)
            if fname == raw_name
        ]
        if owner_hint:
            for idx, owner in matches:
                if owner == owner_hint:
                    return idx + 1
            self._lowering_error(f"unknown field {raw_name} for base class {owner_hint}")
        if matches:
            for idx, owner in matches:
                if owner == class_name:
                    return idx + 1
            if len(matches) == 1:
                return matches[0][0] + 1
            self._lowering_error(f"ambiguous field {raw_name} on class {class_name}")
        self._lowering_error(f"unknown field {raw_name} for class {class_name}")
        raise RuntimeError("unreachable")

    def _resolve_method_target(self, class_name: str, method_name: str) -> str:
        mro = self._class_mros.get(class_name)
        if mro is None:
            self._lowering_error(f"unknown class {class_name}")
        for cls in mro:
            methods = self._class_methods.get(cls, {})
            target = methods.get(method_name)
            if target is not None:
                return target
        self._lowering_error(f"no method {method_name} for class {class_name}")
        raise RuntimeError("unreachable")

    def _next_tmp(self) -> str:
        self._tmp_index += 1
        return f"%t{self._tmp_index}"

    def _next_label(self, prefix: str) -> str:
        self._label_index += 1
        return f"{prefix}.{self._label_index}"

    def _format_for_type(self, ty: str) -> tuple[str, int]:
        if ty == "double":
            return ".fmt_double", 5
        if ty in {"i64", "i1"}:
            return ".fmt_i64", 5
        if ty == "i8*":
            return ".fmt_str", 4
        self._lowering_error(f"printing values of type {ty} not supported")

    def _header(self) -> List[str]:
        lines: List[str] = []
        if self._data_layout:
            lines.append(f'target datalayout = "{self._data_layout}"')
        if self._target_triple:
            lines.append(f'target triple = "{self._target_triple}"')
        lines.extend(
            [
            "@.fmt_i64 = private unnamed_addr constant [5 x i8] c\"%ld\\0A\\00\"",
            "@.fmt_double = private unnamed_addr constant [5 x i8] c\"%lf\\0A\\00\"",
            "@.fmt_str = private unnamed_addr constant [4 x i8] c\"%s\\0A\\00\"",
            "@.heap_bounds_err = private unnamed_addr constant [54 x i8] c\"heap access error: index %ld out of range (size %ld)\\0A\\00\"",
            "@.match_error_fmt = private unnamed_addr constant [33 x i8] c\"non-exhaustive match for tag %s\\0A\\00\"",
            "@.deque_empty_err = private unnamed_addr constant [16 x i8] c\"deque is empty\\0A\\00\"",
            "declare i32 @printf(i8*, ...)",
            "declare i32 @fflush(i8*)",
            "declare i8* @calloc(i64, i64)",
            "declare void @free(i8*)",
            "declare void @exit(i32)",
            ]
        )
        lines.extend(self._runtime_helpers())
        return lines

    def _runtime_helpers(self) -> List[str]:
        return [
            "define i64 @__new(i64 %size) {",
            "entry:",
            "  %alloc_size = add i64 %size, 1",
            "  %ptr = call i8* @calloc(i64 %alloc_size, i64 8)",
            "  %base = bitcast i8* %ptr to i64*",
            "  store i64 %size, i64* %base",
            "  %data = getelementptr i64, i64* %base, i64 1",
            "  %int = ptrtoint i64* %data to i64",
            "  ret i64 %int",
            "}",
            "define i64 @new(i64 %size) {",
            "entry:",
            "  %ptr = call i64 @__new(i64 %size)",
            "  ret i64 %ptr",
            "}",
            "define i64 @__heap_bounds_error(i64 %idx, i64 %size) {",
            "entry:",
            "  %fmt = getelementptr [54 x i8], [54 x i8]* @.heap_bounds_err, i64 0, i64 0",
            "  %_printed = call i32 (i8*, ...) @printf(i8* %fmt, i64 %idx, i64 %size)",
            "  %_flushed = call i32 @fflush(i8* null)",
            "  call void @exit(i32 1)",
            "  ret i64 0",
            "}",
            "define i64 @heap_get(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %data = inttoptr i64 %ptr to i64*",
            "  %base = getelementptr i64, i64* %data, i64 -1",
            "  %size = load i64, i64* %base",
            "  %neg = icmp slt i64 %idx, 0",
            "  %oob = icmp sge i64 %idx, %size",
            "  %bad = or i1 %neg, %oob",
            "  br i1 %bad, label %err, label %ok",
            "err:",
            "  %_ignored = call i64 @__heap_bounds_error(i64 %idx, i64 %size)",
            "  ret i64 0",
            "ok:",
            "  %offset = getelementptr i64, i64* %data, i64 %idx",
            "  %value = load i64, i64* %offset",
            "  ret i64 %value",
            "}",
            "define i64 @heap_set(i64 %ptr, i64 %idx, i64 %value) {",
            "entry:",
            "  %data = inttoptr i64 %ptr to i64*",
            "  %base = getelementptr i64, i64* %data, i64 -1",
            "  %size = load i64, i64* %base",
            "  %neg = icmp slt i64 %idx, 0",
            "  %oob = icmp sge i64 %idx, %size",
            "  %bad = or i1 %neg, %oob",
            "  br i1 %bad, label %err, label %ok",
            "err:",
            "  %_ignored = call i64 @__heap_bounds_error(i64 %idx, i64 %size)",
            "  ret i64 0",
            "ok:",
            "  %offset = getelementptr i64, i64* %data, i64 %idx",
            "  store i64 %value, i64* %offset",
            "  ret i64 0",
            "}",
            "define i8* @heap_get_str(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %raw = call i64 @heap_get(i64 %ptr, i64 %idx)",
            "  %cast = inttoptr i64 %raw to i8*",
            "  ret i8* %cast",
            "}",
            "define double @heap_get_double(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %raw = call i64 @heap_get(i64 %ptr, i64 %idx)",
            "  %cast = bitcast i64 %raw to double",
            "  ret double %cast",
            "}",
            "define i1 @heap_get_bool(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %raw = call i64 @heap_get(i64 %ptr, i64 %idx)",
            "  %cast = trunc i64 %raw to i1",
            "  ret i1 %cast",
            "}",
            "define i64 @heap_set_str(i64 %ptr, i64 %idx, i8* %value) {",
            "entry:",
            "  %cast = ptrtoint i8* %value to i64",
            "  %_ignored = call i64 @heap_set(i64 %ptr, i64 %idx, i64 %cast)",
            "  ret i64 0",
            "}",
            "define i64 @heap_set_double(i64 %ptr, i64 %idx, double %value) {",
            "entry:",
            "  %cast = bitcast double %value to i64",
            "  %_ignored = call i64 @heap_set(i64 %ptr, i64 %idx, i64 %cast)",
            "  ret i64 0",
            "}",
            "define i64 @heap_set_bool(i64 %ptr, i64 %idx, i1 %value) {",
            "entry:",
            "  %cast = zext i1 %value to i64",
            "  %_ignored = call i64 @heap_set(i64 %ptr, i64 %idx, i64 %cast)",
            "  ret i64 0",
            "}",
            "define i64 @heap_len(i64 %ptr) {",
            "entry:",
            "  %data = inttoptr i64 %ptr to i64*",
            "  %base = getelementptr i64, i64* %data, i64 -1",
            "  %size = load i64, i64* %base",
            "  ret i64 %size",
            "}",
            "define i64 @delete(i64 %ptr) {",
            "entry:",
            "  %data = inttoptr i64 %ptr to i64*",
            "  %base = getelementptr i64, i64* %data, i64 -1",
            "  %raw = bitcast i64* %base to i8*",
            "  call void @free(i8* %raw)",
            "  ret i64 0",
            "}",
            "define void @__match_error(i64 %ptr) {",
            "entry:",
            "  %tag = call i8* @heap_get_str(i64 %ptr, i64 0)",
            "  %fmt = getelementptr [33 x i8], [33 x i8]* @.match_error_fmt, i64 0, i64 0",
            "  %_printed = call i32 (i8*, ...) @printf(i8* %fmt, i8* %tag)",
            "  %_flushed = call i32 @fflush(i8* null)",
            "  call void @exit(i32 1)",
            "  ret void",
            "}",
            "define void @__deque_empty_error() {",
            "entry:",
            "  %fmt = getelementptr [16 x i8], [16 x i8]* @.deque_empty_err, i64 0, i64 0",
            "  %_printed = call i32 (i8*, ...) @printf(i8* %fmt)",
            "  %_flushed = call i32 @fflush(i8* null)",
            "  call void @exit(i32 1)",
            "  ret void",
            "}",
            "define i64 @__map_new() {",
            "entry:",
            "  %map = call i64 @__new(i64 2)",
            "  %entries = call i64 @__new(i64 0)",
            "  %_ignored0 = call i64 @heap_set(i64 %map, i64 0, i64 0)",
            "  %_ignored1 = call i64 @heap_set(i64 %map, i64 1, i64 %entries)",
            "  ret i64 %map",
            "}",
            "define i64 @__map_len(i64 %map) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  ret i64 %len",
            "}",
            "define i64 @__map_find(i64 %entries, i64 %len, i64 %key) {",
            "entry:",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %next_loop]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %not_found, label %check",
            "check:",
            "  %idx = mul i64 %i, 2",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %idx)",
            "  %eq = icmp eq i64 %cur, %key",
            "  br i1 %eq, label %found, label %next_loop",
            "next_loop:",
            "  %next = add i64 %i, 1",
            "  br label %loop",
            "found:",
            "  ret i64 %i",
            "not_found:",
            "  ret i64 -1",
            "}",
            "define i64 @__map_get(i64 %map, i64 %key, i64 %default) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %idx = call i64 @__map_find(i64 %entries, i64 %len, i64 %key)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %ok, label %missing",
            "ok:",
            "  %pos = mul i64 %idx, 2",
            "  %val_idx = add i64 %pos, 1",
            "  %val = call i64 @heap_get(i64 %entries, i64 %val_idx)",
            "  ret i64 %val",
            "missing:",
            "  ret i64 %default",
            "}",
            "define i1 @__map_has(i64 %map, i64 %key) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %idx = call i64 @__map_find(i64 %entries, i64 %len, i64 %key)",
            "  %found = icmp sge i64 %idx, 0",
            "  ret i1 %found",
            "}",
            "define i1 @__map_delete(i64 %map, i64 %key) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %idx = call i64 @__map_find(i64 %entries, i64 %len, i64 %key)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %do_delete, label %not_found",
            "do_delete:",
            "  %new_len = sub i64 %len, 1",
            "  %new_size = mul i64 %new_len, 2",
            "  %new_entries = call i64 @__new(i64 %new_size)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %do_delete], [%next, %copy_next]",
            "  %write = phi i64 [0, %do_delete], [%write_next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %check",
            "check:",
            "  %skip = icmp eq i64 %i, %idx",
            "  br i1 %skip, label %skip_entry, label %copy_entry",
            "skip_entry:",
            "  %next = add i64 %i, 1",
            "  %write_next = add i64 %write, 0",
            "  br label %copy_next",
            "copy_entry:",
            "  %src_pos = mul i64 %i, 2",
            "  %src_val = add i64 %src_pos, 1",
            "  %key_val = call i64 @heap_get(i64 %entries, i64 %src_pos)",
            "  %val_val = call i64 @heap_get(i64 %entries, i64 %src_val)",
            "  %dst_pos = mul i64 %write, 2",
            "  %dst_val = add i64 %dst_pos, 1",
            "  %_k = call i64 @heap_set(i64 %new_entries, i64 %dst_pos, i64 %key_val)",
            "  %_v = call i64 @heap_set(i64 %new_entries, i64 %dst_val, i64 %val_val)",
            "  %next = add i64 %i, 1",
            "  %write_next = add i64 %write, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %map, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %map, i64 1, i64 %new_entries)",
            "  ret i1 1",
            "not_found:",
            "  ret i1 0",
            "}",
            "define i64 @__map_set(i64 %map, i64 %key, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %idx = call i64 @__map_find(i64 %entries, i64 %len, i64 %key)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %update, label %extend",
            "update:",
            "  %pos = mul i64 %idx, 2",
            "  %val_idx = add i64 %pos, 1",
            "  %_u = call i64 @heap_set(i64 %entries, i64 %val_idx, i64 %value)",
            "  ret i64 %value",
            "extend:",
            "  %new_len = add i64 %len, 1",
            "  %new_size = mul i64 %new_len, 2",
            "  %new_entries = call i64 @__new(i64 %new_size)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %extend], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %src_pos = mul i64 %i, 2",
            "  %src_val = add i64 %src_pos, 1",
            "  %key_val = call i64 @heap_get(i64 %entries, i64 %src_pos)",
            "  %val_val = call i64 @heap_get(i64 %entries, i64 %src_val)",
            "  %_k = call i64 @heap_set(i64 %new_entries, i64 %src_pos, i64 %key_val)",
            "  %_v = call i64 @heap_set(i64 %new_entries, i64 %src_val, i64 %val_val)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %key_pos = mul i64 %len, 2",
            "  %val_pos = add i64 %key_pos, 1",
            "  %_nk = call i64 @heap_set(i64 %new_entries, i64 %key_pos, i64 %key)",
            "  %_nv = call i64 @heap_set(i64 %new_entries, i64 %val_pos, i64 %value)",
            "  %_l = call i64 @heap_set(i64 %map, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %map, i64 1, i64 %new_entries)",
            "  ret i64 %value",
            "}",
            "define i64 @__map_keys(i64 %map) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %keys = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %src = mul i64 %i, 2",
            "  %key_val = call i64 @heap_get(i64 %entries, i64 %src)",
            "  %_k = call i64 @heap_set(i64 %keys, i64 %i, i64 %key_val)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %keys",
            "}",
            "define i64 @__map_values(i64 %map) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %values = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %src = mul i64 %i, 2",
            "  %val_idx = add i64 %src, 1",
            "  %val = call i64 @heap_get(i64 %entries, i64 %val_idx)",
            "  %_v = call i64 @heap_set(i64 %values, i64 %i, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %values",
            "}",
            "define i64 @__map_entries(i64 %map) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %map, i64 0)",
            "  %entries = call i64 @heap_get(i64 %map, i64 1)",
            "  %out = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %src = mul i64 %i, 2",
            "  %val_idx = add i64 %src, 1",
            "  %key_val = call i64 @heap_get(i64 %entries, i64 %src)",
            "  %val = call i64 @heap_get(i64 %entries, i64 %val_idx)",
            "  %pair = call i64 @__new(i64 2)",
            "  %_k = call i64 @heap_set(i64 %pair, i64 0, i64 %key_val)",
            "  %_v = call i64 @heap_set(i64 %pair, i64 1, i64 %val)",
            "  %_o = call i64 @heap_set(i64 %out, i64 %i, i64 %pair)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %out",
            "}",
            "define i64 @__map_from_entries(i64 %entries_list) {",
            "entry:",
            "  %map = call i64 @__map_new()",
            "  %len = call i64 @heap_len(i64 %entries_list)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %pair = call i64 @heap_get(i64 %entries_list, i64 %i)",
            "  %key_val = call i64 @heap_get(i64 %pair, i64 0)",
            "  %val_val = call i64 @heap_get(i64 %pair, i64 1)",
            "  %_ignored = call i64 @__map_set(i64 %map, i64 %key_val, i64 %val_val)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %map",
            "}",
            "define i64 @__set_new() {",
            "entry:",
            "  %set = call i64 @__new(i64 2)",
            "  %entries = call i64 @__new(i64 0)",
            "  %_ignored0 = call i64 @heap_set(i64 %set, i64 0, i64 0)",
            "  %_ignored1 = call i64 @heap_set(i64 %set, i64 1, i64 %entries)",
            "  ret i64 %set",
            "}",
            "define i64 @__set_len(i64 %set) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  ret i64 %len",
            "}",
            "define i64 @__set_find(i64 %entries, i64 %len, i64 %value) {",
            "entry:",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %next_loop]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %not_found, label %check",
            "check:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %eq = icmp eq i64 %cur, %value",
            "  br i1 %eq, label %found, label %next_loop",
            "next_loop:",
            "  %next = add i64 %i, 1",
            "  br label %loop",
            "found:",
            "  ret i64 %i",
            "not_found:",
            "  ret i64 -1",
            "}",
            "define i1 @__set_has(i64 %set, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  %entries = call i64 @heap_get(i64 %set, i64 1)",
            "  %idx = call i64 @__set_find(i64 %entries, i64 %len, i64 %value)",
            "  %found = icmp sge i64 %idx, 0",
            "  ret i1 %found",
            "}",
            "define i1 @__set_add(i64 %set, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  %entries = call i64 @heap_get(i64 %set, i64 1)",
            "  %idx = call i64 @__set_find(i64 %entries, i64 %len, i64 %value)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %already, label %extend",
            "already:",
            "  ret i1 0",
            "extend:",
            "  %new_len = add i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %extend], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_n = call i64 @heap_set(i64 %new_entries, i64 %len, i64 %value)",
            "  %_l = call i64 @heap_set(i64 %set, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %set, i64 1, i64 %new_entries)",
            "  ret i1 1",
            "}",
            "define i1 @__set_delete(i64 %set, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  %entries = call i64 @heap_get(i64 %set, i64 1)",
            "  %idx = call i64 @__set_find(i64 %entries, i64 %len, i64 %value)",
            "  %found = icmp sge i64 %idx, 0",
            "  br i1 %found, label %do_delete, label %not_found",
            "do_delete:",
            "  %new_len = sub i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %do_delete], [%next, %copy_next]",
            "  %write = phi i64 [0, %do_delete], [%write_next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %check",
            "check:",
            "  %skip = icmp eq i64 %i, %idx",
            "  br i1 %skip, label %skip_entry, label %copy_entry",
            "skip_entry:",
            "  %next = add i64 %i, 1",
            "  %write_next = add i64 %write, 0",
            "  br label %copy_next",
            "copy_entry:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %write, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  %write_next = add i64 %write, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %set, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %set, i64 1, i64 %new_entries)",
            "  ret i1 1",
            "not_found:",
            "  ret i1 0",
            "}",
            "define i64 @__set_to_list(i64 %set) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %set, i64 0)",
            "  %entries = call i64 @heap_get(i64 %set, i64 1)",
            "  %out = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %out, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %out",
            "}",
            "define i64 @__set_from_list(i64 %list) {",
            "entry:",
            "  %set = call i64 @__set_new()",
            "  %len = call i64 @heap_len(i64 %list)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %val = call i64 @heap_get(i64 %list, i64 %i)",
            "  %_ignored = call i1 @__set_add(i64 %set, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %set",
            "}",
            "define i64 @__deque_new() {",
            "entry:",
            "  %deque = call i64 @__new(i64 2)",
            "  %entries = call i64 @__new(i64 0)",
            "  %_ignored0 = call i64 @heap_set(i64 %deque, i64 0, i64 0)",
            "  %_ignored1 = call i64 @heap_set(i64 %deque, i64 1, i64 %entries)",
            "  ret i64 %deque",
            "}",
            "define i64 @__deque_from_list(i64 %list) {",
            "entry:",
            "  %deque = call i64 @__new(i64 2)",
            "  %len = call i64 @heap_len(i64 %list)",
            "  %entries = call i64 @__new(i64 %len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %entry], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %val = call i64 @heap_get(i64 %list, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %entries, i64 %i, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %entries)",
            "  ret i64 %deque",
            "}",
            "define i64 @__deque_len(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  ret i64 %len",
            "}",
            "define i64 @__deque_push_left(i64 %deque, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %new_len = add i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  %_v = call i64 @heap_set(i64 %new_entries, i64 0, i64 %value)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %entry], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %val = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %dst = add i64 %i, 1",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %dst, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %new_entries)",
            "  ret i64 %new_len",
            "}",
            "define i64 @__deque_push_right(i64 %deque, i64 %value) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %new_len = add i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %entry], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %val = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %i, i64 %val)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_v = call i64 @heap_set(i64 %new_entries, i64 %len, i64 %value)",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %new_entries)",
            "  ret i64 %new_len",
            "}",
            "define i64 @__deque_pop_left(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %empty = icmp eq i64 %len, 0",
            "  br i1 %empty, label %err, label %ok",
            "err:",
            "  call void @__deque_empty_error()",
            "  ret i64 0",
            "ok:",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %val = call i64 @heap_get(i64 %entries, i64 0)",
            "  %new_len = sub i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %ok], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %new_len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %src = add i64 %i, 1",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %src)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %new_entries)",
            "  ret i64 %val",
            "}",
            "define i64 @__deque_pop_right(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %empty = icmp eq i64 %len, 0",
            "  br i1 %empty, label %err, label %ok",
            "err:",
            "  call void @__deque_empty_error()",
            "  ret i64 0",
            "ok:",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %last = sub i64 %len, 1",
            "  %val = call i64 @heap_get(i64 %entries, i64 %last)",
            "  %new_len = sub i64 %len, 1",
            "  %new_entries = call i64 @__new(i64 %new_len)",
            "  br label %copy",
            "copy:",
            "  %i = phi i64 [0, %ok], [%next, %copy_next]",
            "  %done = icmp sge i64 %i, %new_len",
            "  br i1 %done, label %copied, label %copy_body",
            "copy_body:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %new_entries, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %copy_next",
            "copy_next:",
            "  br label %copy",
            "copied:",
            "  %_l = call i64 @heap_set(i64 %deque, i64 0, i64 %new_len)",
            "  %_e = call i64 @heap_set(i64 %deque, i64 1, i64 %new_entries)",
            "  ret i64 %val",
            "}",
            "define i64 @__deque_peek_left(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %empty = icmp eq i64 %len, 0",
            "  br i1 %empty, label %err, label %ok",
            "err:",
            "  call void @__deque_empty_error()",
            "  ret i64 0",
            "ok:",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %val = call i64 @heap_get(i64 %entries, i64 0)",
            "  ret i64 %val",
            "}",
            "define i64 @__deque_peek_right(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %empty = icmp eq i64 %len, 0",
            "  br i1 %empty, label %err, label %ok",
            "err:",
            "  call void @__deque_empty_error()",
            "  ret i64 0",
            "ok:",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %last = sub i64 %len, 1",
            "  %val = call i64 @heap_get(i64 %entries, i64 %last)",
            "  ret i64 %val",
            "}",
            "define i64 @__deque_to_list(i64 %deque) {",
            "entry:",
            "  %len = call i64 @heap_get(i64 %deque, i64 0)",
            "  %entries = call i64 @heap_get(i64 %deque, i64 1)",
            "  %out = call i64 @__new(i64 %len)",
            "  br label %loop",
            "loop:",
            "  %i = phi i64 [0, %entry], [%next, %loop_next]",
            "  %done = icmp sge i64 %i, %len",
            "  br i1 %done, label %done_block, label %body",
            "body:",
            "  %cur = call i64 @heap_get(i64 %entries, i64 %i)",
            "  %_c = call i64 @heap_set(i64 %out, i64 %i, i64 %cur)",
            "  %next = add i64 %i, 1",
            "  br label %loop_next",
            "loop_next:",
            "  br label %loop",
            "done_block:",
            "  ret i64 %out",
            "}",
        ]

    def _register_type_metadata(self, program: ProgramIR) -> None:
        self._variant_fields.clear()
        self._variant_field_types.clear()
        self._variant_to_type.clear()

        for type_name, type_def in program.types.items():
            if type_def.variants:
                for variant_name, fields in type_def.variants.items():
                    self._variant_to_type[variant_name] = type_name
                    self._variant_fields[variant_name] = [fname for fname, _ in fields]
                    for fname, ftype in fields:
                        llvm_type = self._llvm_type_from_annotation(ftype) or "i64"
                        self._variant_field_types[(variant_name, fname)] = llvm_type
            elif type_def.fields is not None:
                variant_name = type_def.name
                self._variant_to_type[variant_name] = type_name
                self._variant_fields[variant_name] = [fname for fname, _ in type_def.fields]
                for fname, ftype in type_def.fields:
                    llvm_type = self._llvm_type_from_annotation(ftype) or "i64"
                    self._variant_field_types[(variant_name, fname)] = llvm_type

    def _register_class_metadata(self, program: ProgramIR) -> None:
        self._class_layouts.clear()
        self._class_mros.clear()
        self._class_ids.clear()
        self._class_methods.clear()

        for func_name in program.functions:
            if "." not in func_name:
                continue
            class_name, method_name = func_name.split(".", 1)
            self._class_methods.setdefault(class_name, {})[method_name] = func_name

        def build_mro(name: str) -> List[str]:
            cached = self._class_mros.get(name)
            if cached is not None:
                return cached
            class_def = program.classes.get(name)
            if class_def is None:
                self._class_mros[name] = [name]
                return [name]
            mro: List[str] = [name]
            for base in class_def.bases:
                if base not in program.classes:
                    self._lowering_error(f"unknown base class {base} for {name}")
                for ancestor in build_mro(base):
                    if ancestor not in mro:
                        mro.append(ancestor)
            self._class_mros[name] = mro
            return mro

        for class_name in program.classes:
            build_mro(class_name)

        for class_name, mro in self._class_mros.items():
            layout: List[Tuple[str, str]] = []
            for cls in mro:
                class_def = program.classes.get(cls)
                if class_def is None:
                    continue
                for field in class_def.fields:
                    layout.append((cls, field))
            self._class_layouts[class_name] = layout

        for idx, class_name in enumerate(sorted(program.classes.keys()), start=1):
            self._class_ids[class_name] = idx

    def _infer_signatures(self, program: ProgramIR) -> Dict[str, _ResolvedFunctionSignature]:
        signatures: Dict[str, _FunctionSignature] = {}
        for func in program.functions.values():
            signatures[func.name] = _FunctionSignature(
                param_types={name: None for name in func.params},
                return_type=None,
            )
        for overload in program.operator_overloads:
            func = program.functions.get(overload.func_name)
            if func is None or len(func.params) != 2:
                continue
            signature = signatures.get(overload.func_name)
            if signature is None:
                continue
            a_ty = self._llvm_type_from_annotation(overload.a_type)
            b_ty = self._llvm_type_from_annotation(overload.b_type)
            if a_ty and signature.param_types.get(func.params[0]) is None:
                signature.param_types[func.params[0]] = a_ty
            if b_ty and signature.param_types.get(func.params[1]) is None:
                signature.param_types[func.params[1]] = b_ty
        if not signatures:
            return {}

        for _ in range(len(signatures) + 1):
            changed = False
            for func in program.functions.values():
                if self._infer_function_signature(func, signatures):
                    changed = True
            if not changed:
                break

        resolved: Dict[str, _ResolvedFunctionSignature] = {}
        for name, signature in signatures.items():
            param_types = {param: ty or "i64" for param, ty in signature.param_types.items()}
            return_type = signature.return_type or "i64"
            resolved[name] = _ResolvedFunctionSignature(param_types=param_types, return_type=return_type)
        return resolved

    def _infer_function_signature(
        self, func: FunctionIR, signatures: Dict[str, _FunctionSignature]
    ) -> bool:
        changed = False
        stack: List[_TypeValue] = []
        locals_types: Dict[str, Optional[str]] = {}
        locals_literals: Dict[str, int] = {}
        locals_classes: Dict[str, str] = {}
        locals_variants: Dict[str, str] = {}
        heap_cell_types: Dict[Tuple[str, int], str] = {}
        signature = signatures[func.name]
        if "." in func.name and func.params:
            locals_classes[func.params[0]] = func.name.split(".", 1)[0]

        def set_param_type(param_name: str, ty: str) -> None:
            nonlocal changed
            existing = signature.param_types.get(param_name)
            if existing is None:
                signature.param_types[param_name] = ty
                changed = True
            elif existing != ty:
                raise NotImplementedError(
                    f"mixed-type parameter {param_name} in LLVM prototype: {existing} vs {ty}"
                )

        def set_return_type(ty: str) -> None:
            nonlocal changed
            if signature.return_type is None:
                signature.return_type = ty
                changed = True
            elif signature.return_type != ty:
                raise NotImplementedError(
                    f"mixed-type return in LLVM prototype: {signature.return_type} vs {ty}"
                )

        def resolve_variant_name(value: _TypeValue) -> Optional[str]:
            if value.variant_name:
                return value.variant_name
            if value.source:
                return locals_variants.get(value.source)
            return None

        for instr in func.instructions:
            if instr.op == Opcode.PUSH_CONST:
                if instr.arg is None:
                    stack.append(_TypeValue("i8*"))
                elif isinstance(instr.arg, bool):
                    stack.append(_TypeValue("i1"))
                elif isinstance(instr.arg, int):
                    stack.append(_TypeValue("i64", literal=instr.arg))
                elif isinstance(instr.arg, float):
                    stack.append(_TypeValue("double"))
                elif isinstance(instr.arg, str):
                    stack.append(_TypeValue("i8*", literal_str=instr.arg))
                else:
                    raise NotImplementedError(
                        f"constants of type {type(instr.arg).__name__} are not supported in LLVM prototype"
                    )
            elif instr.op == Opcode.LOAD:
                name = instr.arg
                if name in locals_types:
                    literal = locals_literals.get(name)
                    stack.append(
                        _TypeValue(
                            locals_types[name],
                            source=name,
                            literal=literal,
                            class_name=locals_classes.get(name),
                            variant_name=locals_variants.get(name),
                        )
                    )
                elif name in signature.param_types:
                    stack.append(
                        _TypeValue(
                            signature.param_types[name],
                            source=name,
                            class_name=locals_classes.get(name),
                            variant_name=locals_variants.get(name),
                        )
                    )
                else:
                    raise NotImplementedError(f"unknown variable {name} in LLVM prototype")
            elif instr.op == Opcode.STORE:
                value = stack.pop()
                ty = value.ty
                if ty is None and value.source and value.source in signature.param_types:
                    ty = signature.param_types[value.source]
                locals_types[instr.arg] = ty
                if ty == "i64" and value.literal is not None:
                    locals_literals[instr.arg] = value.literal
                else:
                    locals_literals.pop(instr.arg, None)
                if value.class_name:
                    locals_classes[instr.arg] = value.class_name
                else:
                    locals_classes.pop(instr.arg, None)
                if value.variant_name:
                    locals_variants[instr.arg] = value.variant_name
                else:
                    locals_variants.pop(instr.arg, None)
                if value.source and value.source != instr.arg:
                    for (ptr_name, idx), cell_ty in list(heap_cell_types.items()):
                        if ptr_name == value.source:
                            heap_cell_types[(instr.arg, idx)] = cell_ty
            elif instr.op == Opcode.BINARY:
                right = stack.pop()
                left = stack.pop()
                left_ty = left.ty
                right_ty = right.ty
                if left_ty and right_ty and left_ty != right_ty:
                    raise NotImplementedError("mixed-type arithmetic is not yet supported in LLVM prototype")
                known_ty = left_ty or right_ty
                if left_ty is None and left.source and known_ty:
                    set_param_type(left.source, known_ty)
                    left_ty = known_ty
                if right_ty is None and right.source and known_ty:
                    set_param_type(right.source, known_ty)
                    right_ty = known_ty
                op = instr.arg
                overload_name = None
                if known_ty is not None:
                    overload_name = self._operator_overloads.get((op, known_ty, known_ty))
                if overload_name is not None:
                    overload_sig = signatures.get(overload_name)
                    if overload_sig is None:
                        raise NotImplementedError(f"unknown operator overload {overload_name}")
                    stack.append(_TypeValue(overload_sig.return_type))
                    continue
                if op in {"+", "-", "*", "/", "%"}:
                    stack.append(_TypeValue(known_ty))
                elif op in {"==", "!=", "<", ">", "<=", ">="}:
                    stack.append(_TypeValue("i1"))
                else:
                    raise NotImplementedError(f"operator {op} not supported in LLVM prototype")
            elif instr.op == Opcode.PRINT:
                for _ in range(int(instr.arg)):
                    stack.pop()
            elif instr.op == Opcode.FLUSH:
                continue
            elif instr.op == Opcode.POP:
                stack.pop()
            elif instr.op == Opcode.JUMP:
                stack.clear()
            elif instr.op == Opcode.JUMP_IF_FALSE:
                if stack:
                    stack.pop()
                stack.clear()
            elif instr.op == Opcode.CALL:
                name, argc = instr.arg
                args = [stack.pop() for _ in range(argc)][::-1]
                if name == "__variant_assume":
                    if len(args) != 2:
                        raise NotImplementedError("__variant_assume expects 2 args")
                    variant_name = args[1].literal_str
                    if variant_name is None:
                        raise NotImplementedError("__variant_assume expects a string literal variant name")
                    value = args[0]
                    stack.append(
                        _TypeValue(
                            value.ty,
                            source=value.source,
                            literal=value.literal,
                            literal_str=value.literal_str,
                            class_name=value.class_name,
                            variant_name=variant_name,
                        )
                    )
                    continue
                if name == "__variant_new":
                    if len(args) < 2:
                        raise NotImplementedError("__variant_new expects at least 2 args")
                    variant_name = args[0].literal_str
                    if variant_name is None:
                        raise NotImplementedError("__variant_new expects a string literal variant name")
                    stack.append(_TypeValue("i64", variant_name=variant_name))
                    continue
                if name == "__variant_tag":
                    if len(args) != 1:
                        raise NotImplementedError("__variant_tag expects 1 arg")
                    stack.append(_TypeValue("i8*", literal_str=args[0].variant_name))
                    continue
                if name == "__variant_get":
                    if len(args) != 2:
                        raise NotImplementedError("__variant_get expects 2 args")
                    field_name = args[1].literal_str
                    if field_name is None:
                        raise NotImplementedError("__variant_get expects a string literal field name")
                    variant_name = resolve_variant_name(args[0])
                    if variant_name is None:
                        field_type = None
                        for (candidate_variant, candidate_field), ty in self._variant_field_types.items():
                            if candidate_field == field_name:
                                if field_type is None:
                                    field_type = ty
                                elif field_type != ty:
                                    raise NotImplementedError(
                                        f"ambiguous field {field_name} across variants in LLVM prototype"
                                    )
                        stack.append(_TypeValue(field_type or "i64"))
                    else:
                        field_type = self._variant_field_types.get((variant_name, field_name), "i64")
                        stack.append(_TypeValue(field_type))
                    continue
                if name == "__match_error":
                    if len(args) != 1:
                        raise NotImplementedError("__match_error expects 1 arg")
                    continue
                if name == "__class_new":
                    if not args:
                        raise NotImplementedError("__class_new expects at least 1 arg")
                    class_name_value = args[0].literal_str
                    if class_name_value is None:
                        raise NotImplementedError("__class_new expects a string literal class name")
                    if (len(args) - 1) % 2 != 0:
                        raise NotImplementedError("__class_new expects field name/value pairs")
                    for index in range(1, len(args), 2):
                        field_name = args[index].literal_str
                        if field_name is None:
                            raise NotImplementedError("__class_new expects string literal field names")
                        value = args[index + 1]
                        if value.ty is not None:
                            field_index = self._class_field_index(class_name_value, field_name)
                            existing = self._class_field_types.get((class_name_value, field_index))
                            if existing is None:
                                self._class_field_types[(class_name_value, field_index)] = value.ty
                                changed = True
                            elif existing != value.ty:
                                raise NotImplementedError(
                                    f"mixed-type field {class_name_value}.{field_name} in LLVM prototype"
                                )
                    stack.append(_TypeValue("i64", class_name=class_name_value))
                    continue
                if name == "__field_get":
                    if len(args) != 2:
                        raise NotImplementedError("__field_get expects 2 args")
                    obj, field_name = args
                    class_name_value = obj.class_name
                    field_literal = field_name.literal_str
                    if class_name_value is None or field_literal is None:
                        raise NotImplementedError("__field_get expects class value and field name literal")
                    field_index = self._class_field_index(class_name_value, field_literal)
                    field_type = self._class_field_types.get((class_name_value, field_index), "i64")
                    stack.append(_TypeValue(field_type))
                    continue
                if name == "__field_set":
                    if len(args) != 3:
                        raise NotImplementedError("__field_set expects 3 args")
                    obj, field_name, value = args
                    class_name_value = obj.class_name
                    field_literal = field_name.literal_str
                    if class_name_value is None or field_literal is None:
                        raise NotImplementedError("__field_set expects class value and field name literal")
                    field_index = self._class_field_index(class_name_value, field_literal)
                    if value.ty is not None:
                        existing = self._class_field_types.get((class_name_value, field_index))
                        if existing is None:
                            self._class_field_types[(class_name_value, field_index)] = value.ty
                            changed = True
                        elif existing != value.ty:
                            raise NotImplementedError(
                                f"mixed-type field {class_name_value}.{field_literal} in LLVM prototype"
                            )
                    stack.append(value)
                    continue
                if name == "__method_call":
                    if len(args) < 2:
                        raise NotImplementedError("__method_call expects at least 2 args")
                    obj, method_name, *rest = args
                    class_name_value = obj.class_name
                    method_literal = method_name.literal_str
                    if class_name_value is None or method_literal is None:
                        raise NotImplementedError("__method_call expects class value and method name literal")
                    if class_name_value in {"Map", "Set", "Deque"}:
                        call_name = f"{class_name_value}.{method_literal}"
                        args = rest
                        name = call_name
                        if name.startswith("Map."):
                            method = name.split(".", 1)[1]
                            if method == "set" and len(args) >= 3:
                                stack.append(_TypeValue(args[2].ty))
                            elif method == "get" and len(args) == 3:
                                stack.append(_TypeValue(args[2].ty))
                            elif method in {"has", "delete"}:
                                stack.append(_TypeValue("i1"))
                            elif method in {"len"}:
                                stack.append(_TypeValue("i64"))
                            elif method in {"new", "keys", "values", "entries", "from_entries"}:
                                stack.append(_TypeValue("i64"))
                            else:
                                stack.append(_TypeValue("i64"))
                            continue
                        if name.startswith("Set."):
                            method = name.split(".", 1)[1]
                            if method in {"add", "delete", "has"}:
                                stack.append(_TypeValue("i1"))
                            elif method in {"new", "from_list", "to_list"}:
                                stack.append(_TypeValue("i64"))
                            else:
                                stack.append(_TypeValue("i64"))
                            continue
                        if name.startswith("Deque."):
                            stack.append(_TypeValue("i64"))
                            continue
                    target_name = self._resolve_method_target(class_name_value, method_literal)
                    callee = signatures.get(target_name)
                    if callee is None:
                        raise NotImplementedError(f"unknown function {target_name}")
                    method_args = [obj] + list(rest)
                    for param_name, arg in zip(callee.param_types.keys(), method_args):
                        expected = callee.param_types[param_name]
                        if expected is None and arg.ty:
                            callee.param_types[param_name] = arg.ty
                            changed = True
                        if arg.ty is None and arg.source and expected:
                            set_param_type(arg.source, expected)
                        if expected and arg.ty and expected != arg.ty:
                            raise NotImplementedError(
                                f"argument type mismatch for {target_name}.{param_name}: {expected} vs {arg.ty}"
                            )
                    stack.append(_TypeValue(callee.return_type))
                    continue
                if name.startswith("Map."):
                    method = name.split(".", 1)[1]
                    if method == "set" and len(args) >= 3:
                        stack.append(_TypeValue(args[2].ty))
                    elif method == "get" and len(args) == 3:
                        stack.append(_TypeValue(args[2].ty))
                    elif method in {"has", "delete"}:
                        stack.append(_TypeValue("i1"))
                    elif method in {"len"}:
                        stack.append(_TypeValue("i64"))
                    elif method in {"new", "keys", "values", "entries", "from_entries"}:
                        stack.append(_TypeValue("i64"))
                    else:
                        stack.append(_TypeValue("i64"))
                    continue
                if name.startswith("Set."):
                    method = name.split(".", 1)[1]
                    if method in {"add", "delete", "has"}:
                        stack.append(_TypeValue("i1"))
                    elif method in {"new", "from_list", "to_list"}:
                        stack.append(_TypeValue("i64"))
                    else:
                        stack.append(_TypeValue("i64"))
                    continue
                if name.startswith("Deque."):
                    method = name.split(".", 1)[1]
                    if method in {"new", "from_list", "to_list", "len", "push_left", "push_right"}:
                        stack.append(_TypeValue("i64"))
                    elif method in {"pop_left", "pop_right", "peek_left", "peek_right"}:
                        stack.append(_TypeValue("i64"))
                    else:
                        stack.append(_TypeValue("i64"))
                    continue
                if name == "heap_set":
                    self._record_heap_cell_type_inference(args, heap_cell_types)
                    stack.append(_TypeValue("i64"))
                    continue
                if name == "heap_get":
                    known = self._heap_cell_type_from_inference(args, heap_cell_types)
                    stack.append(_TypeValue(known or "i64"))
                    continue
                callee = signatures.get(name)
                if callee is None:
                    builtin = self._builtin_signature(name)
                    if builtin is None:
                        raise NotImplementedError(f"unknown function {name} in LLVM prototype")
                    for param_ty, arg in zip(builtin.param_types.values(), args):
                        if param_ty and arg.ty and param_ty != arg.ty:
                            raise NotImplementedError(
                                f"argument type mismatch for {name}: {param_ty} vs {arg.ty}"
                            )
                    stack.append(_TypeValue(builtin.return_type))
                    continue
                for param_name, arg in zip(callee.param_types.keys(), args):
                    expected = callee.param_types[param_name]
                    if expected is None and arg.ty:
                        callee.param_types[param_name] = arg.ty
                        changed = True
                    if arg.ty is None and arg.source and expected:
                        set_param_type(arg.source, expected)
                    if expected and arg.ty and expected != arg.ty:
                        raise NotImplementedError(
                            f"argument type mismatch for {name}.{param_name}: {expected} vs {arg.ty}"
                        )
                stack.append(_TypeValue(callee.return_type))
            elif instr.op == Opcode.RETURN:
                if stack:
                    value = stack.pop()
                    if value.ty is None and value.source and signature.return_type:
                        set_param_type(value.source, signature.return_type)
                        value = _TypeValue(signature.return_type)
                    if value.ty:
                        set_return_type(value.ty)
                stack.clear()
            else:
                self._unsupported_opcode(instr)

        return changed

    def _builtin_signature(self, name: str) -> Optional[_ResolvedFunctionSignature]:
        if name in {"__new", "new"}:
            return _ResolvedFunctionSignature(param_types={"size": "i64"}, return_type="i64")
        if name == "heap_get":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64", "idx": "i64"}, return_type="i64")
        if name == "heap_get_str":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64", "idx": "i64"}, return_type="i8*")
        if name == "heap_get_double":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64", "idx": "i64"}, return_type="double")
        if name == "heap_get_bool":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64", "idx": "i64"}, return_type="i1")
        if name == "heap_set":
            return _ResolvedFunctionSignature(
                param_types={"ptr": "i64", "idx": "i64", "value": "i64"}, return_type="i64"
            )
        if name == "heap_set_str":
            return _ResolvedFunctionSignature(
                param_types={"ptr": "i64", "idx": "i64", "value": "i8*"}, return_type="i64"
            )
        if name == "heap_set_double":
            return _ResolvedFunctionSignature(
                param_types={"ptr": "i64", "idx": "i64", "value": "double"}, return_type="i64"
            )
        if name == "heap_set_bool":
            return _ResolvedFunctionSignature(
                param_types={"ptr": "i64", "idx": "i64", "value": "i1"}, return_type="i64"
            )
        if name == "delete":
            return _ResolvedFunctionSignature(param_types={"ptr": "i64"}, return_type="i64")
        return None

    def _register_operator_overloads(
        self, overloads: List[OperatorOverloadIR]
    ) -> Dict[Tuple[str, str, str], str]:
        registered: Dict[Tuple[str, str, str], str] = {}
        for overload in overloads:
            a_ty = self._llvm_type_from_annotation(overload.a_type)
            b_ty = self._llvm_type_from_annotation(overload.b_type)
            if a_ty is None or b_ty is None:
                continue
            registered[(overload.op, a_ty, b_ty)] = overload.func_name
        return registered

    def _llvm_type_from_annotation(self, name: str) -> Optional[str]:
        normalized = name.lower()
        if normalized in {"number", "int", "integer"}:
            return "i64"
        if normalized in {"float", "double"}:
            return "double"
        if normalized in {"bool", "boolean"}:
            return "i1"
        if normalized in {"string", "str"}:
            return "i8*"
        if normalized == "null":
            return "i8*"
        return None

    def _resolve_heap_set_name(self, args: List[_StackValue]) -> str:
        if len(args) != 3:
            return "heap_set"
        value = args[2]
        if value.ty == "i8*":
            return "heap_set_str"
        if value.ty == "double":
            return "heap_set_double"
        if value.ty == "i1":
            return "heap_set_bool"
        return "heap_set"

    def _resolve_heap_get_name(self, args: List[_StackValue]) -> str:
        if len(args) != 2:
            return "heap_get"
        ptr = args[0]
        idx = args[1]
        key = self._heap_cell_key(ptr, idx)
        if key is None:
            return "heap_get"
        cell_type = self._heap_cell_types.get(key)
        if cell_type == "i8*":
            return "heap_get_str"
        if cell_type == "double":
            return "heap_get_double"
        if cell_type == "i1":
            return "heap_get_bool"
        return "heap_get"

    def _heap_cell_key(self, ptr: _StackValue, idx: _StackValue) -> Optional[Tuple[str, int]]:
        if ptr.source is None:
            return None
        if idx.ty != "i64" or idx.literal is None:
            return None
        return (ptr.source, idx.literal)

    def _record_heap_cell_type(self, args: List[_StackValue]) -> None:
        if len(args) != 3:
            return
        ptr, idx, value = args
        key = self._heap_cell_key(ptr, idx)
        if key is None:
            return
        self._heap_cell_types[key] = value.ty

    def _record_heap_cell_type_inference(
        self, args: List[_TypeValue], heap_cell_types: Dict[Tuple[str, int], str]
    ) -> None:
        if len(args) != 3:
            return
        ptr, idx, value = args
        if ptr.source is None or idx.literal is None:
            return
        if idx.ty != "i64" or value.ty is None:
            return
        heap_cell_types[(ptr.source, idx.literal)] = value.ty

    def _heap_cell_type_from_inference(
        self, args: List[_TypeValue], heap_cell_types: Dict[Tuple[str, int], str]
    ) -> Optional[str]:
        if len(args) != 2:
            return None
        ptr, idx = args
        if ptr.source is None or idx.literal is None or idx.ty != "i64":
            return None
        return heap_cell_types.get((ptr.source, idx.literal))

    def _string_constant(self, value: str) -> Tuple[str, int]:
        cached = self._string_constants.get(value)
        if cached:
            return cached
        encoded = value.encode("utf-8")
        escaped = "".join(self._escape_byte(byte) for byte in encoded)
        length = len(encoded) + 1
        name = f".str{len(self._string_constants)}"
        self._string_constants[value] = (name, length)
        self._string_defs.append(
            f"@{name} = private unnamed_addr constant [{length} x i8] c\"{escaped}\\00\""
        )
        return name, length

    def _escape_byte(self, value: int) -> str:
        if value in {0x5C, 0x22}:
            return f"\\{value:02X}"
        if 0x20 <= value <= 0x7E:
            return chr(value)
        return f"\\{value:02X}"
