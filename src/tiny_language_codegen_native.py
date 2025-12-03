"""Experimental native code generator and bytecode VM for TinyLanguage.

This module translates a subset of the AST into a small stack-based
bytecode and executes it with a tiny VM. It is intentionally scoped to
cover the tutorial-style examples first (literals, arithmetic, control
flow, simple functions, and `print`). Unsupported constructs raise
``NotImplementedError`` so gaps remain visible.
"""

from typing import Any, Dict, List, Optional

from native_ir import FunctionIR, Instruction, Opcode, ProgramIR


class NativeCodeGenerator:
    """Convert TinyLanguage AST nodes into bytecode instructions."""

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

    def _compile_if(self, stmt: "If") -> List[NativeInstruction]:
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

    def _compile_while(self, stmt: "While") -> List[NativeInstruction]:
        instructions: List[NativeInstruction] = []
        loop_start = 0
        cond_instrs = self._compile_expr(stmt.cond)
        instructions.extend(cond_instrs)
        jump_out_index = len(instructions)
        instructions.append(Instruction(Opcode.JUMP_IF_FALSE, None))

        body_instrs: List[NativeInstruction] = []
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
        if isinstance(expr, Var):
            return [Instruction(Opcode.LOAD, expr.name)]
        if isinstance(expr, Bin):
            instructions = self._compile_expr(expr.a)
            instructions.extend(self._compile_expr(expr.b))
            instructions.append(Instruction(Opcode.BINARY, expr.op))
            return instructions
        if isinstance(expr, Call):
            instructions: List[Instruction] = []
            for arg in expr.args:
                instructions.extend(self._compile_expr(arg))
            instructions.append(Instruction(Opcode.CALL, (expr.name, len(expr.args))))
            return instructions
        raise NotImplementedError(f"native codegen does not yet support expression {type(expr).__name__}")


class _Frame:
    def __init__(self, instructions: List[NativeInstruction], locals_: Optional[Dict[str, Any]] = None) -> None:
        self.instructions = instructions
        self.locals = locals_ or {}
        self.ip = 0


class NativeVM:
    """Execute bytecode generated by ``NativeCodeGenerator``."""

    _binary_ops = {
        "+": lambda a, b: a + b,
        "-": lambda a, b: a - b,
        "*": lambda a, b: a * b,
        "/": lambda a, b: a / b,
        "%": lambda a, b: a % b,
        "^": lambda a, b: a**b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        "<": lambda a, b: a < b,
        ">": lambda a, b: a > b,
        "<=": lambda a, b: a <= b,
        ">=": lambda a, b: a >= b,
        "&&": lambda a, b: bool(a) and bool(b),
        "||": lambda a, b: bool(a) or bool(b),
        "and": lambda a, b: bool(a) and bool(b),
        "or": lambda a, b: bool(a) or bool(b),
    }

    def __init__(self) -> None:
        self.output: List[str] = []
        self.globals: Dict[str, Any] = {}
        self.program: Optional[ProgramIR] = None

    def run(self, program: ProgramIR) -> str:
        self.program = program
        self._execute(_Frame(program.entry, self.globals))
        return "".join(self.output)

    def _execute(self, frame: _Frame) -> Any:
        stack: List[Any] = []
        while frame.ip < len(frame.instructions):
            instr = frame.instructions[frame.ip]
            frame.ip += 1

            if instr.op == Opcode.PUSH_CONST:
                stack.append(instr.arg)
            elif instr.op == Opcode.LOAD:
                stack.append(self._load(frame.locals, instr.arg))
            elif instr.op == Opcode.STORE:
                value = stack.pop()
                frame.locals[instr.arg] = value
                if frame.locals is self.globals:
                    self.globals[instr.arg] = value
            elif instr.op == Opcode.BINARY:
                right = stack.pop()
                left = stack.pop()
                op_fn = self._binary_ops.get(instr.arg)
                if op_fn is None:
                    raise RuntimeError(f"unsupported operator {instr.arg}")
                stack.append(op_fn(left, right))
            elif instr.op == Opcode.PRINT:
                values = [stack.pop() for _ in range(int(instr.arg))][::-1]
                self.output.append(" ".join(self._format_value(v) for v in values) + "\n")
            elif instr.op == Opcode.JUMP:
                frame.ip = int(instr.arg)
            elif instr.op == Opcode.JUMP_IF_FALSE:
                cond = stack.pop()
                if not cond:
                    frame.ip = int(instr.arg)
            elif instr.op == Opcode.CALL:
                name, argc = instr.arg
                args = [stack.pop() for _ in range(argc)][::-1]
                stack.append(self._call(name, args))
            elif instr.op == Opcode.POP:
                stack.pop()
            elif instr.op == Opcode.RETURN:
                return stack.pop() if stack else None
            else:
                raise RuntimeError(f"unknown opcode {instr.op}")
        return None

    def _load(self, locals_: Dict[str, Any], name: str) -> Any:
        if name in locals_:
            return locals_[name]
        if name in self.globals:
            return self.globals[name]
        raise RuntimeError(f"unknown variable {name}")

    def _call(self, name: str, args: List[Any]) -> Any:
        if self.program is None:
            raise RuntimeError("VM has no program loaded")
        target = self.program.functions.get(name)
        if target is None:
            raise RuntimeError(f"unknown function {name}")
        if len(args) != len(target.params):
            raise RuntimeError(f"function {name} expects {len(target.params)} args, got {len(args)}")
        locals_ = dict(zip(target.params, args))
        return self._execute(_Frame(target.instructions, locals_))

    def _format_value(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
