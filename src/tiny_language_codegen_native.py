"""Experimental native code generator and bytecode VM for TinyLanguage.

This module translates a subset of the AST into a small stack-based
bytecode and executes it with a tiny VM. It is intentionally scoped to
cover the tutorial-style examples first (literals, arithmetic, control
flow, simple functions, and `print`). Unsupported constructs raise
``NotImplementedError`` so gaps remain visible.
"""

from typing import Dict, List

from native_ir import ClassIR, FunctionIR, Instruction, Opcode, OperatorOverloadIR, ProgramIR


class NativeCodeGenerator:
    """Convert TinyLanguage AST nodes into bytecode instructions."""

    def __init__(self, *, allow_heap: bool = False) -> None:
        self._allow_heap = allow_heap
        self._tmp_index = 0

    def compile_program(self, stmts: List["IR"]) -> ProgramIR:
        functions: Dict[str, FunctionIR] = {}
        entry_instructions: List[Instruction] = []
        classes: Dict[str, ClassIR] = {}
        operator_overloads: List[OperatorOverloadIR] = []

        for stmt in stmts:
            if isinstance(stmt, Fn):
                functions[stmt.name] = self._compile_function(stmt)
            elif isinstance(stmt, OpDef):
                overload_name = self._operator_name(stmt)
                functions[overload_name] = self._compile_operator(stmt, overload_name)
                operator_overloads.append(
                    OperatorOverloadIR(
                        op=stmt.op, a_type=stmt.a_type, b_type=stmt.b_type, func_name=overload_name
                    )
                )
            elif isinstance(stmt, ClassDef):
                self._register_class(stmt, classes)
                for method in stmt.methods:
                    functions[self._method_name(method.class_name, method.name)] = self._compile_method(method)
            elif isinstance(stmt, MethodDef):
                self._register_method_class(stmt, classes)
                functions[self._method_name(stmt.class_name, stmt.name)] = self._compile_method(stmt)
            else:
                raw = self._compile_stmt(stmt)
                entry_instructions.extend(self._shift_labels(raw, len(entry_instructions)))

        entry_instructions.append(Instruction(Opcode.RETURN))
        return ProgramIR(
            entry=entry_instructions,
            functions=functions,
            classes=classes,
            operator_overloads=operator_overloads,
        )

    def _compile_function(self, fn: "Fn") -> FunctionIR:
        body_instrs: List[Instruction] = []
        for stmt in fn.body:
            raw = self._compile_stmt(stmt)
            body_instrs.extend(self._shift_labels(raw, len(body_instrs)))
        body_instrs.append(Instruction(Opcode.RETURN))
        return FunctionIR(name=fn.name, params=[param.name for param in fn.params], instructions=body_instrs)

    def _compile_method(self, md: "MethodDef") -> FunctionIR:
        body_instrs: List[Instruction] = []
        for stmt in md.body:
            raw = self._compile_stmt(stmt)
            body_instrs.extend(self._shift_labels(raw, len(body_instrs)))
        body_instrs.append(Instruction(Opcode.RETURN))
        return FunctionIR(
            name=self._method_name(md.class_name, md.name),
            params=[param.name for param in md.params],
            instructions=body_instrs,
        )

    def _compile_operator(self, opdef: "OpDef", name: str) -> FunctionIR:
        body_instrs: List[Instruction] = []
        for stmt in opdef.body:
            raw = self._compile_stmt(stmt)
            body_instrs.extend(self._shift_labels(raw, len(body_instrs)))
        body_instrs.append(Instruction(Opcode.RETURN))
        return FunctionIR(name=name, params=[opdef.a_name, opdef.b_name], instructions=body_instrs)

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
            if "." in stmt.name:
                obj_name, method_name = stmt.name.split(".", 1)
                expr = MethodCall(Var(obj_name, pos=stmt.pos), method_name, stmt.args, pos=stmt.pos)
            else:
                expr = Call(stmt.name, stmt.args, pos=stmt.pos)
            instructions = self._compile_expr(expr)
            instructions.append(Instruction(Opcode.POP))
            return instructions
        if isinstance(stmt, FieldAssign):
            instructions = self._compile_expr(stmt.obj)
            instructions.append(Instruction(Opcode.PUSH_CONST, stmt.name))
            instructions.extend(self._compile_expr(stmt.expr))
            instructions.append(Instruction(Opcode.CALL, ("__field_set", 3)))
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
        if isinstance(expr, Field):
            instructions = self._compile_expr(expr.obj)
            instructions.append(Instruction(Opcode.PUSH_CONST, expr.name))
            instructions.append(Instruction(Opcode.CALL, ("__field_get", 2)))
            return instructions
        if isinstance(expr, MethodCall):
            instructions = self._compile_expr(expr.obj)
            instructions.append(Instruction(Opcode.PUSH_CONST, expr.name))
            for arg in expr.args:
                instructions.extend(self._compile_expr(arg))
            instructions.append(Instruction(Opcode.CALL, ("__method_call", 2 + len(expr.args))))
            return instructions
        if isinstance(expr, ClassNew):
            instructions: List[Instruction] = [Instruction(Opcode.PUSH_CONST, expr.name)]
            for name, value in expr.init:
                instructions.append(Instruction(Opcode.PUSH_CONST, name))
                instructions.extend(self._compile_expr(value))
            instructions.append(Instruction(Opcode.CALL, ("__class_new", 1 + 2 * len(expr.init))))
            return instructions
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

    @staticmethod
    def _method_name(class_name: str, method_name: str) -> str:
        return f"{class_name}.{method_name}"

    @staticmethod
    def _operator_name(opdef: "OpDef") -> str:
        return f"__op_{opdef.op}_{opdef.a_type}_{opdef.b_type}"

    def _register_class(self, stmt: "ClassDef", classes: Dict[str, ClassIR]) -> None:
        if stmt.name in classes:
            existing = classes[stmt.name]
            for fname, _ in stmt.fields:
                if fname not in existing.fields:
                    existing.fields.append(fname)
            if stmt.bases:
                existing.bases = list(stmt.bases)
            return
        classes[stmt.name] = ClassIR(
            name=stmt.name,
            fields=[fname for fname, _ in stmt.fields],
            bases=list(stmt.bases),
        )

    def _register_method_class(self, stmt: "MethodDef", classes: Dict[str, ClassIR]) -> None:
        if stmt.class_name not in classes:
            classes[stmt.class_name] = ClassIR(name=stmt.class_name, fields=[])
