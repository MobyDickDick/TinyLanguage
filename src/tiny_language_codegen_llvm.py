"""Lightweight LLVM IR prototype for TinyLanguage.

The goal of this prototype is to expose a minimal code path that can translate
the native stack-based IR into a textual LLVM module. It intentionally supports
only the constructs needed for the tutorial-style examples (numeric literals,
assignments, arithmetic, and `print`) and will raise ``NotImplementedError`` for
everything else. The output is meant for inspection or piping into external
tools like ``llc`` rather than for production-grade code generation.
"""

from dataclasses import dataclass
from typing import Dict, List

from native_ir import Instruction, Opcode, ProgramIR


@dataclass
class _StackValue:
    """Keep track of a value's type and SSA name for LLVM emission."""

    name: str
    ty: str


class LLVMCodeGenerator:
    """Translate ``ProgramIR`` instructions into textual LLVM IR."""

    def __init__(self) -> None:
        self._tmp_index = 0
        self._stack: List[_StackValue] = []
        self._allocas: Dict[str, str] = {}
        self._var_types: Dict[str, str] = {}
        self._prologue: List[str] = []
        self._body: List[str] = []

    def compile_program(self, program: ProgramIR) -> str:
        """Return LLVM IR for the given native ``ProgramIR``.

        Only straight-line code in the entry block is supported for now. Control
        flow, user-defined functions, and complex types remain out of scope for
        this prototype so gaps stay visible during experimentation.
        """

        if program.functions:
            raise NotImplementedError("LLVM prototype only handles top-level code without functions")

        self._tmp_index = 0
        self._stack.clear()
        self._allocas.clear()
        self._var_types.clear()
        self._prologue.clear()
        self._body.clear()

        for instr in program.entry:
            self._emit_instruction(instr)

        lines: List[str] = []
        lines.extend(self._header())
        lines.append("define i32 @tiny_main() {")
        lines.append("entry:")
        lines.extend(self._prologue)
        lines.extend(self._body)
        lines.append("  ret i32 0")
        lines.append("}")

        return "\n".join(lines)

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
        elif instr.op in {Opcode.JUMP, Opcode.JUMP_IF_FALSE, Opcode.CALL}:
            raise NotImplementedError(f"LLVM prototype does not yet support {instr.op.value}")
        elif instr.op == Opcode.RETURN:
            # The surrounding function emits a single final return, so intermediate
            # returns are ignored for now.
            return
        else:
            raise NotImplementedError(f"unhandled opcode {instr.op}")

    def _push_const(self, value: object) -> None:
        if isinstance(value, bool):
            self._stack.append(_StackValue(name="1" if value else "0", ty="i1"))
        elif isinstance(value, int):
            self._stack.append(_StackValue(name=str(value), ty="i64"))
        elif isinstance(value, float):
            self._stack.append(_StackValue(name=f"{value:.6e}", ty="double"))
        else:
            raise NotImplementedError(f"constants of type {type(value).__name__} are not supported in LLVM prototype")

    def _load_var(self, name: str) -> None:
        ty = self._var_types.get(name)
        if ty is None:
            raise NotImplementedError(f"unknown variable {name} in LLVM prototype")
        dest = self._next_tmp()
        self._body.append(f"  {dest} = load {ty}, {ty}* %{self._allocas[name]}")
        self._stack.append(_StackValue(name=dest, ty=ty))

    def _store_var(self, name: str) -> None:
        if not self._stack:
            raise RuntimeError("store requested with empty stack")
        value = self._stack.pop()
        if name not in self._allocas:
            self._allocas[name] = name
            self._var_types[name] = value.ty
            self._prologue.append(f"  %{name} = alloca {value.ty}")
        self._body.append(f"  store {value.ty} {value.name}, {value.ty}* %{self._allocas[name]}")

    def _binary_op(self, op: str) -> None:
        right = self._stack.pop()
        left = self._stack.pop()
        if left.ty != right.ty:
            raise NotImplementedError("mixed-type arithmetic is not yet supported in LLVM prototype")

        if op in {"+", "-", "*", "/", "%"}:
            self._emit_arithmetic_op(op, left, right)
            return
        if op in {"==", "!=", "<", ">", "<=", ">="}:
            self._emit_comparison(op, left, right)
            return
        raise NotImplementedError(f"operator {op} not supported in LLVM prototype")

    def _emit_arithmetic_op(self, op: str, left: _StackValue, right: _StackValue) -> None:
        ty = left.ty
        dest = self._next_tmp()
        if ty == "double":
            instr = {"+": "fadd", "-": "fsub", "*": "fmul", "/": "fdiv"}.get(op)
            if op == "%":
                instr = None  # double modulo not supported for now
        else:
            instr = {"+": "add", "-": "sub", "*": "mul", "/": "sdiv", "%": "srem"}.get(op)
        if instr is None:
            raise NotImplementedError(f"operator {op} not supported for type {ty} in LLVM prototype")
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
                raise NotImplementedError(f"comparison {op} not supported for type {ty} in LLVM prototype")
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
                raise NotImplementedError(f"comparison {op} not supported for type {ty} in LLVM prototype")
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

    # ----- Helpers -----

    def _next_tmp(self) -> str:
        self._tmp_index += 1
        return f"%t{self._tmp_index}"

    def _format_for_type(self, ty: str) -> tuple[str, int]:
        if ty == "double":
            return ".fmt_double", 4
        if ty in {"i64", "i1"}:
            return ".fmt_i64", 4
        raise NotImplementedError(f"printing values of type {ty} not supported in LLVM prototype")

    def _header(self) -> List[str]:
        return [
            "@.fmt_i64 = private unnamed_addr constant [4 x i8] c\"%ld\\0A\\00\"",
            "@.fmt_double = private unnamed_addr constant [4 x i8] c\"%f\\0A\\00\"",
            "declare i32 @printf(i8*, ...)",
        ]
