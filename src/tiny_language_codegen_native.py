"""Experimental native code generator and bytecode VM for TinyLanguage.

This module translates a subset of the AST into a small stack-based
bytecode and executes it with a tiny VM. It is intentionally scoped to
cover the tutorial-style examples first (literals, arithmetic, control
flow, simple functions, and `print`). Unsupported constructs raise
``NotImplementedError`` so gaps remain visible.
"""

from typing import Dict, List

from native_ir import FunctionIR, Instruction, Opcode, ProgramIR


class NativeCodeGenerator:
    """Convert TinyLanguage AST nodes into bytecode instructions."""

    def __init__(self, *, allow_heap: bool = False) -> None:
        self._allow_heap = allow_heap
        self._tmp_index = 0

    def compile_program(self, stmts: List["IR"]) -> ProgramIR:
        functions: Dict[str, FunctionIR] = {}
        entry_instructions: List[Instruction] = []

        for stmt in stmts:
            if isinstance(stmt, Fn):
                functions[stmt.name] = self._compile_function(stmt)
            else:
                raw = self._compile_stmt(stmt)
                entry_instructions.extend(self._shift_labels(raw, len(entry_instructions)))

        entry_instructions.append(Instruction(Opcode.RETURN))
        return ProgramIR(entry=entry_instructions, functions=functions)

    def _compile_function(self, fn: "Fn") -> FunctionIR:
        body_instrs: List[Instruction] = []
        for stmt in fn.body:
            raw = self._compile_stmt(stmt)
            body_instrs.extend(self._shift_labels(raw, len(body_instrs)))
        body_instrs.append(Instruction(Opcode.RETURN))
        return FunctionIR(name=fn.name, params=[param.name for param in fn.params], instructions=body_instrs)

    def _shift_labels(self, instructions: List[Instruction], offset: int) -> List[Instruction]:
        shifted: List[Instruction] = []
        for instr in instructions:
            if instr.op in {Opcode.JUMP, Opcode.JUMP_IF_FALSE} and instr.arg is not None:
                shifted.append(Instruction(instr.op, instr.arg + offset))
            else:
                shifted.append(instr)
        return shifted

    def _compile_stmt(self, stmt: "IR") -> List[Instruction]:
        if isinstance(stmt, Let):
            return self._compile_binding(stmt.name, stmt.expr)
        if isinstance(stmt, Assign):
            return self._compile_binding(stmt.name, stmt.expr)
        if isinstance(stmt, Print):
            instructions: List[Instruction] = []
            for expr in stmt.exprs:
                instructions.extend(self._compile_expr(expr))
            instructions.append(Instruction(Opcode.PRINT, len(stmt.exprs)))
            return instructions
        if isinstance(stmt, Flush):
            return [Instruction(Opcode.FLUSH)]
        if isinstance(stmt, If):
            return self._compile_if(stmt)
        if isinstance(stmt, While):
            return self._compile_while(stmt)
        if isinstance(stmt, Return):
            instructions = self._compile_expr(stmt.expr)
            instructions.append(Instruction(Opcode.RETURN))
            return instructions
        if isinstance(stmt, CallStmt):
            instructions = self._compile_expr(Call(stmt.name, stmt.args, pos=stmt.pos))
            instructions.append(Instruction(Opcode.POP))
            return instructions
        raise NotImplementedError(f"native codegen does not yet support {type(stmt).__name__}")

    def _compile_if(self, stmt: "If") -> List[Instruction]:
        instructions = self._compile_expr(stmt.cond)
        jump_false_index = len(instructions)
        instructions.append(Instruction(Opcode.JUMP_IF_FALSE, None))

        then_block = []
        for inner in stmt.then:
            nested = self._compile_stmt(inner)
            then_block.extend(self._shift_labels(nested, len(instructions) + len(then_block)))
        then_block.append(Instruction(Opcode.JUMP, None))

        else_block = []
        for inner in stmt.els:
            nested = self._compile_stmt(inner)
            else_block.extend(self._shift_labels(nested, len(instructions) + len(then_block) + len(else_block)))

        else_start = len(instructions) + len(then_block)
        instructions[jump_false_index] = Instruction(Opcode.JUMP_IF_FALSE, else_start)

        end_of_then = len(instructions) + len(then_block) + len(else_block)
        then_block[-1] = Instruction(Opcode.JUMP, end_of_then)

        instructions.extend(then_block)
        instructions.extend(else_block)
        return instructions

    def _compile_while(self, stmt: "While") -> List[Instruction]:
        instructions: List[Instruction] = []
        loop_start = 0
        cond_instrs = self._compile_expr(stmt.cond)
        instructions.extend(cond_instrs)
        jump_out_index = len(instructions)
        instructions.append(Instruction(Opcode.JUMP_IF_FALSE, None))

        body_instrs: List[Instruction] = []
        for inner in stmt.body:
            nested = self._compile_stmt(inner)
            body_instrs.extend(self._shift_labels(nested, len(instructions) + len(body_instrs)))
        body_instrs.append(Instruction(Opcode.JUMP, loop_start))

        loop_exit = len(instructions) + len(body_instrs)
        instructions[jump_out_index] = Instruction(Opcode.JUMP_IF_FALSE, loop_exit)

        instructions.extend(body_instrs)
        return instructions

    def _compile_binding(self, name: str, expr: "IR") -> List[Instruction]:
        instructions = self._compile_expr(expr)
        instructions.append(Instruction(Opcode.STORE, name))
        return instructions

    def _compile_expr(self, expr: "IR") -> List[Instruction]:
        if isinstance(expr, Num):
            value = float(expr.txt) if "." in expr.txt else int(expr.txt)
            return [Instruction(Opcode.PUSH_CONST, value)]
        if isinstance(expr, Str):
            return [Instruction(Opcode.PUSH_CONST, expr.txt)]
        if isinstance(expr, Bool):
            return [Instruction(Opcode.PUSH_CONST, expr.value)]
        if isinstance(expr, Null):
            return [Instruction(Opcode.PUSH_CONST, None)]
        if isinstance(expr, New):
            if not self._allow_heap:
                raise NotImplementedError("native codegen does not yet support heap allocations")
            instructions = self._compile_expr(expr.size)
            instructions.append(Instruction(Opcode.CALL, ("__new", 1)))
            return instructions
        if isinstance(expr, NewLit):
            if not self._allow_heap:
                raise NotImplementedError("native codegen does not yet support heap allocations")
            temp_name = self._next_tmp()
            instructions: List[Instruction] = [
                Instruction(Opcode.PUSH_CONST, len(expr.items)),
                Instruction(Opcode.CALL, ("__new", 1)),
                Instruction(Opcode.STORE, temp_name),
            ]
            for idx, item in enumerate(expr.items):
                instructions.append(Instruction(Opcode.LOAD, temp_name))
                instructions.append(Instruction(Opcode.PUSH_CONST, idx))
                instructions.extend(self._compile_expr(item))
                instructions.append(Instruction(Opcode.CALL, ("heap_set", 3)))
                instructions.append(Instruction(Opcode.POP))
            instructions.append(Instruction(Opcode.LOAD, temp_name))
            return instructions
        if isinstance(expr, Var):
            return [Instruction(Opcode.LOAD, expr.name)]
        if isinstance(expr, Bin):
            instructions = self._compile_expr(expr.a)
            instructions.extend(self._compile_expr(expr.b))
            instructions.append(Instruction(Opcode.BINARY, expr.op))
            return instructions
        if isinstance(expr, Call):
            if expr.name in {"__new", "new", "heap_get", "heap_set", "delete"} and not self._allow_heap:
                raise NotImplementedError("native codegen does not yet support heap allocations")
            instructions: List[Instruction] = []
            for arg in expr.args:
                instructions.extend(self._compile_expr(arg))
            instructions.append(Instruction(Opcode.CALL, (expr.name, len(expr.args))))
            return instructions
        raise NotImplementedError(f"native codegen does not yet support expression {type(expr).__name__}")

    def _next_tmp(self) -> str:
        self._tmp_index += 1
        return f"__tmp_heap_{self._tmp_index}"
