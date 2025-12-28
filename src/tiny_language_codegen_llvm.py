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

from native_ir import FunctionIR, Instruction, Opcode, ProgramIR


@dataclass
class _StackValue:
    """Keep track of a value's type and SSA name for LLVM emission."""

    name: str
    ty: str
    source: Optional[str] = None
    literal: Optional[int] = None


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


class LLVMCodeGenerator:
    """Translate ``ProgramIR`` instructions into textual LLVM IR."""

    def __init__(self, *, target_triple: Optional[str] = None, data_layout: Optional[str] = None) -> None:
        self._tmp_index = 0
        self._stack: List[_StackValue] = []
        self._allocas: Dict[str, str] = {}
        self._var_types: Dict[str, str] = {}
        self._var_literals: Dict[str, int] = {}
        self._prologue: List[str] = []
        self._body: List[str] = []
        self._string_constants: Dict[str, Tuple[str, int]] = {}
        self._string_defs: List[str] = []
        self._function_signatures: Dict[str, _ResolvedFunctionSignature] = {}
        self._current_return_type: Optional[str] = None
        self._current_instruction: Optional[Instruction] = None
        self._heap_cell_types: Dict[Tuple[str, int], str] = {}
        self._target_triple = target_triple
        self._data_layout = data_layout

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
        self._stack.clear()
        self._allocas.clear()
        self._var_types.clear()
        self._var_literals.clear()
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
        self._stack.clear()
        self._allocas.clear()
        self._var_types.clear()
        self._var_literals.clear()
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
        if isinstance(value, bool):
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
            self._stack.append(_StackValue(name=dest, ty="i8*"))
        else:
            self._lowering_error(
                f"constants of type {type(value).__name__} are not supported",
            )

    def _load_var(self, name: str) -> None:
        ty = self._var_types.get(name)
        if ty is None:
            self._lowering_error(f"unknown variable {name}")
        dest = self._next_tmp()
        self._body.append(f"  {dest} = load {ty}, {ty}* %{self._allocas[name]}")
        literal = self._var_literals.get(name)
        self._stack.append(_StackValue(name=dest, ty=ty, source=name, literal=literal))

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
        self._body.append(f"  store {value.ty} {value.name}, {value.ty}* %{self._allocas[name]}")

    def _binary_op(self, op: str) -> None:
        right = self._stack.pop()
        left = self._stack.pop()
        if left.ty != right.ty:
            self._lowering_error(
                f"mixed-type arithmetic not supported ({left.ty} vs {right.ty})"
            )

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
            else:
                self._body.append(f"  call i32 (i8*, ...) @printf(i8* {fmt_ptr}, {value.ty} {value.name})")

    def _pop_value(self) -> None:
        if not self._stack:
            raise RuntimeError("cannot POP from an empty LLVM prototype stack")
        self._stack.pop()

    def _flush_output(self) -> None:
        self._body.append("  call i32 @fflush(i8* null)")

    def _call_function(self, call_spec: Tuple[str, int]) -> None:
        name, argc = call_spec
        args = [self._stack.pop() for _ in range(argc)][::-1]
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

    def _next_tmp(self) -> str:
        self._tmp_index += 1
        return f"%t{self._tmp_index}"

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
            "declare i32 @printf(i8*, ...)",
            "declare i32 @fflush(i8*)",
            "declare i8* @calloc(i64, i64)",
            "declare void @free(i8*)",
            ]
        )
        lines.extend(self._runtime_helpers())
        return lines

    def _runtime_helpers(self) -> List[str]:
        return [
            "define i64 @__new(i64 %size) {",
            "entry:",
            "  %ptr = call i8* @calloc(i64 %size, i64 8)",
            "  %int = ptrtoint i8* %ptr to i64",
            "  ret i64 %int",
            "}",
            "define i64 @new(i64 %size) {",
            "entry:",
            "  %ptr = call i64 @__new(i64 %size)",
            "  ret i64 %ptr",
            "}",
            "define i64 @heap_get(i64 %ptr, i64 %idx) {",
            "entry:",
            "  %base = inttoptr i64 %ptr to i64*",
            "  %offset = getelementptr i64, i64* %base, i64 %idx",
            "  %value = load i64, i64* %offset",
            "  ret i64 %value",
            "}",
            "define i64 @heap_set(i64 %ptr, i64 %idx, i64 %value) {",
            "entry:",
            "  %base = inttoptr i64 %ptr to i64*",
            "  %offset = getelementptr i64, i64* %base, i64 %idx",
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
            "define i64 @delete(i64 %ptr) {",
            "entry:",
            "  %base = inttoptr i64 %ptr to i8*",
            "  call void @free(i8* %base)",
            "  ret i64 0",
            "}",
        ]

    def _infer_signatures(self, program: ProgramIR) -> Dict[str, _ResolvedFunctionSignature]:
        signatures: Dict[str, _FunctionSignature] = {}
        for func in program.functions.values():
            signatures[func.name] = _FunctionSignature(
                param_types={name: None for name in func.params},
                return_type=None,
            )
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
        heap_cell_types: Dict[Tuple[str, int], str] = {}
        signature = signatures[func.name]

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

        for instr in func.instructions:
            if instr.op == Opcode.PUSH_CONST:
                if isinstance(instr.arg, bool):
                    stack.append(_TypeValue("i1"))
                elif isinstance(instr.arg, int):
                    stack.append(_TypeValue("i64", literal=instr.arg))
                elif isinstance(instr.arg, float):
                    stack.append(_TypeValue("double"))
                elif isinstance(instr.arg, str):
                    stack.append(_TypeValue("i8*"))
                else:
                    raise NotImplementedError(
                        f"constants of type {type(instr.arg).__name__} are not supported in LLVM prototype"
                    )
            elif instr.op == Opcode.LOAD:
                name = instr.arg
                if name in locals_types:
                    literal = locals_literals.get(name)
                    stack.append(_TypeValue(locals_types[name], source=name, literal=literal))
                elif name in signature.param_types:
                    stack.append(_TypeValue(signature.param_types[name], source=name))
                else:
                    raise NotImplementedError(f"unknown variable {name} in LLVM prototype")
            elif instr.op == Opcode.STORE:
                value = stack.pop()
                ty = value.ty
                if ty is None and value.source:
                    ty = signature.param_types[value.source]
                locals_types[instr.arg] = ty
                if ty == "i64" and value.literal is not None:
                    locals_literals[instr.arg] = value.literal
                else:
                    locals_literals.pop(instr.arg, None)
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
