"""Experimental native code generator and bytecode VM for TinyLanguage.

This module translates a subset of the AST into a small stack-based
bytecode and executes it with a tiny VM. It is intentionally scoped to
cover the tutorial-style examples first (literals, arithmetic, control
flow, simple functions, and `print`). Unsupported constructs raise
``NotImplementedError`` so gaps remain visible.
"""

from typing import Dict, List

from native_ir import ClassIR, FunctionIR, Instruction, Opcode, OperatorOverloadIR, ProgramIR, TypeIR


class NativeCodeGenerator:
    """Convert TinyLanguage AST nodes into bytecode instructions."""

    def __init__(
        self,
        *,
        allow_heap: bool = False,
        allow_match: bool = False,
        module_namespace: str | None = None,
    ) -> None:
        self._allow_heap = allow_heap
        self._allow_match = allow_match
        self._module_namespace = module_namespace
        self._tmp_index = 0
        self._variant_fields: Dict[str, List[str]] = {}
        self._async_functions: set[str] = set()
        self._task_scope_depth = 0

    def compile_program(self, stmts: List["IR"]) -> ProgramIR:
        functions: Dict[str, FunctionIR] = {}
        entry_instructions: List[Instruction] = []
        classes: Dict[str, ClassIR] = {}
        types: Dict[str, TypeIR] = {}
        operator_overloads: List[OperatorOverloadIR] = []
        self._async_functions = {
            self._qualify_name(stmt.name) for stmt in stmts if isinstance(stmt, Fn) and stmt.is_async
        }
        self._task_scope_depth = 0

        for stmt in stmts:
            if isinstance(stmt, Fn):
                functions[self._qualify_name(stmt.name)] = self._compile_function(stmt)
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
            elif isinstance(stmt, TypeDef):
                if not self._allow_match:
                    raise NotImplementedError("native codegen does not yet support type definitions")
                self._register_type(stmt, types)
            else:
                raw = self._compile_stmt(stmt)
                entry_instructions.extend(self._shift_labels(raw, len(entry_instructions)))

        entry_instructions.append(Instruction(Opcode.RETURN))
        return ProgramIR(
            entry=entry_instructions,
            functions=functions,
            classes=classes,
            types=types,
            operator_overloads=operator_overloads,
        )

    def _compile_function(self, fn: "Fn") -> FunctionIR:
        body_instrs: List[Instruction] = []
        self._task_scope_depth = 0
        for stmt in fn.body:
            raw = self._compile_stmt(stmt)
            body_instrs.extend(self._shift_labels(raw, len(body_instrs)))
        body_instrs.append(Instruction(Opcode.RETURN))
        return FunctionIR(
            name=self._qualify_name(fn.name),
            params=[param.name for param in fn.params],
            instructions=body_instrs,
        )

    def _compile_method(self, md: "MethodDef") -> FunctionIR:
        body_instrs: List[Instruction] = []
        self._task_scope_depth = 0
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
        self._task_scope_depth = 0
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
        if isinstance(stmt, Import):
            binding = self._import_binding_name(stmt.module, stmt.alias)
            return [
                Instruction(Opcode.PUSH_CONST, stmt.module),
                Instruction(Opcode.CALL, ("__import", 1)),
                Instruction(Opcode.STORE, binding),
            ]
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
            instructions: List[Instruction] = []
            instructions.extend(self._compile_expr(stmt.expr))
            if self._task_scope_depth:
                instructions.extend(self._task_scope_exit_instrs())
            instructions.append(Instruction(Opcode.RETURN))
            return instructions
        if isinstance(stmt, CallStmt):
            if "." in stmt.name:
                obj_name, method_name = stmt.name.split(".", 1)
                expr = MethodCall(Var(obj_name, pos=stmt.pos), method_name, stmt.args, pos=stmt.pos)
            else:
                expr = Call(self._qualify_name(stmt.name), stmt.args, pos=stmt.pos)
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
        if isinstance(stmt, TaskBlock):
            instructions: List[Instruction] = [Instruction(Opcode.CALL, ("__task_scope_enter", 0))]
            self._task_scope_depth += 1
            for inner in stmt.body:
                nested = self._compile_stmt(inner)
                instructions.extend(self._shift_labels(nested, len(instructions)))
            self._task_scope_depth -= 1
            instructions.append(Instruction(Opcode.CALL, ("__task_scope_exit", 0)))
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
        if isinstance(expr, VariantCtor):
            if not self._allow_match:
                raise NotImplementedError("native codegen does not yet support variant constructors")
            return self._compile_variant_ctor(expr)
        if isinstance(expr, Match):
            if not self._allow_match:
                raise NotImplementedError("native codegen does not yet support match expressions")
            return self._compile_match(expr)
        if isinstance(expr, Spawn):
            return self._compile_spawn(self._qualify_name(expr.name), expr.args)
        if isinstance(expr, Await):
            instructions = self._compile_expr(expr.expr)
            instructions.append(Instruction(Opcode.CALL, ("join", 1)))
            return instructions
        if isinstance(expr, Bin):
            instructions = self._compile_expr(expr.a)
            instructions.extend(self._compile_expr(expr.b))
            instructions.append(Instruction(Opcode.BINARY, expr.op))
            return instructions
        if isinstance(expr, Call):
            if expr.name in {"__new", "new", "heap_get", "heap_set", "delete"} and not self._allow_heap:
                raise NotImplementedError("native codegen does not yet support heap allocations")
            call_name = self._qualify_name(expr.name)
            if call_name in self._async_functions:
                return self._compile_spawn(call_name, expr.args)
            instructions: List[Instruction] = []
            for arg in expr.args:
                instructions.extend(self._compile_expr(arg))
            instructions.append(Instruction(Opcode.CALL, (call_name, len(expr.args))))
            return instructions
        raise NotImplementedError(f"native codegen does not yet support expression {type(expr).__name__}")

    def _next_tmp(self) -> str:
        self._tmp_index += 1
        return f"__tmp_heap_{self._tmp_index}"

    def _compile_variant_ctor(self, expr: "VariantCtor") -> List[Instruction]:
        instructions: List[Instruction] = [
            Instruction(Opcode.PUSH_CONST, expr.variant),
            Instruction(Opcode.PUSH_CONST, expr.type_name),
        ]
        for name, value in expr.fields:
            instructions.append(Instruction(Opcode.PUSH_CONST, name))
            instructions.extend(self._compile_expr(value))
        instructions.append(Instruction(Opcode.CALL, ("__variant_new", 2 + 2 * len(expr.fields))))
        return instructions

    def _compile_spawn(self, name: str, args: List["IR"]) -> List[Instruction]:
        instructions: List[Instruction] = [Instruction(Opcode.PUSH_CONST, name)]
        for arg in args:
            instructions.extend(self._compile_expr(arg))
        instructions.append(Instruction(Opcode.CALL, ("__spawn", 1 + len(args))))
        return instructions

    def _compile_match(self, expr: "Match") -> List[Instruction]:
        instructions = self._compile_expr(expr.expr)
        tmp_name = self._next_tmp()
        instructions.append(Instruction(Opcode.STORE, tmp_name))

        end_jump_indices: List[int] = []
        for case in expr.cases:
            pattern = case.pattern
            if isinstance(pattern, VariantPattern):
                instructions.append(Instruction(Opcode.LOAD, tmp_name))
                instructions.append(Instruction(Opcode.CALL, ("__variant_tag", 1)))
                instructions.append(Instruction(Opcode.PUSH_CONST, pattern.variant))
                instructions.append(Instruction(Opcode.BINARY, "=="))
                jump_false_index = len(instructions)
                instructions.append(Instruction(Opcode.JUMP_IF_FALSE, None))
                instructions.extend(self._compile_pattern_bindings(pattern, tmp_name))
                instructions.extend(self._compile_expr(case.body))
                end_jump_indices.append(len(instructions))
                instructions.append(Instruction(Opcode.JUMP, None))
                instructions[jump_false_index] = Instruction(Opcode.JUMP_IF_FALSE, len(instructions))
            elif isinstance(pattern, WildcardPattern):
                if pattern.name:
                    instructions.append(Instruction(Opcode.LOAD, tmp_name))
                    instructions.append(Instruction(Opcode.STORE, pattern.name))
                instructions.extend(self._compile_expr(case.body))
                end_jump_indices.append(len(instructions))
                instructions.append(Instruction(Opcode.JUMP, None))
            else:
                raise NotImplementedError(f"native codegen does not yet support {type(pattern).__name__} patterns")

        instructions.append(Instruction(Opcode.LOAD, tmp_name))
        instructions.append(Instruction(Opcode.CALL, ("__match_error", 1)))

        end_index = len(instructions)
        for jump_index in end_jump_indices:
            instructions[jump_index] = Instruction(Opcode.JUMP, end_index)
        return instructions

    def _compile_pattern_bindings(self, pattern: "VariantPattern", tmp_name: str) -> List[Instruction]:
        instructions: List[Instruction] = []
        field_names: List[str] = []
        if pattern.positional_bindings is not None:
            field_names = self._variant_field_order(pattern.variant)
            if field_names is None:
                raise NotImplementedError(
                    f"native codegen requires type information for positional pattern {pattern.variant}"
                )
            if len(pattern.positional_bindings) > len(field_names):
                raise RuntimeError(
                    f"positional pattern for {pattern.variant} has too many fields ({len(pattern.positional_bindings)})"
                )
            for index, bind in enumerate(pattern.positional_bindings):
                if bind is None:
                    continue
                instructions.append(Instruction(Opcode.LOAD, tmp_name))
                instructions.append(Instruction(Opcode.PUSH_CONST, field_names[index]))
                instructions.append(Instruction(Opcode.CALL, ("__variant_get", 2)))
                instructions.append(Instruction(Opcode.STORE, bind))
        for fname, bind in pattern.bindings.items():
            if bind is None:
                continue
            instructions.append(Instruction(Opcode.LOAD, tmp_name))
            instructions.append(Instruction(Opcode.PUSH_CONST, fname))
            instructions.append(Instruction(Opcode.CALL, ("__variant_get", 2)))
            instructions.append(Instruction(Opcode.STORE, bind))
        return instructions

    def _qualify_name(self, name: str) -> str:
        if not self._module_namespace or "." in name:
            return name
        return f"{self._module_namespace}.{name}"

    @staticmethod
    def _import_binding_name(module: str, alias: str | None) -> str:
        if alias:
            return alias
        stripped = module.lstrip(".") or module
        return stripped.split(".")[-1]

    @staticmethod
    def _method_name(class_name: str, method_name: str) -> str:
        return f"{class_name}.{method_name}"

    def _operator_name(self, opdef: "OpDef") -> str:
        return self._qualify_name(f"__op_{opdef.op}_{opdef.a_type}_{opdef.b_type}")

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

    def _register_type(self, stmt: "TypeDef", types: Dict[str, TypeIR]) -> None:
        if stmt.variants:
            variants = {variant.name: list(variant.fields) for variant in stmt.variants}
            types[stmt.name] = TypeIR(name=stmt.name, variants=variants)
            for variant_name, fields in variants.items():
                self._variant_fields[variant_name] = [fname for fname, _ in fields]
        elif stmt.fields is not None:
            types[stmt.name] = TypeIR(name=stmt.name, fields=list(stmt.fields))
            self._variant_fields[stmt.name] = [fname for fname, _ in stmt.fields]
        else:
            types[stmt.name] = TypeIR(name=stmt.name)

    def _variant_field_order(self, variant: str) -> List[str] | None:
        return self._variant_fields.get(variant)

    def _task_scope_exit_instrs(self) -> List[Instruction]:
        return [Instruction(Opcode.CALL, ("__task_scope_exit", 0)) for _ in range(self._task_scope_depth)]
