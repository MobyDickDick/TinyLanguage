"""Experimental native code generator and bytecode VM for TinyLanguage.

This module translates a subset of the AST into a small stack-based
bytecode and executes it with a tiny VM. It is intentionally scoped to
cover the tutorial-style examples first (literals, arithmetic, control
flow, simple functions, and `print`). Unsupported constructs raise
``NotImplementedError`` so gaps remain visible with precise source positions.
"""

from typing import Dict, List, Optional

from native_ir import ClassIR, FunctionIR, Instruction, Opcode, OperatorOverloadIR, ProgramIR, TypeIR
from tiny_errors import SourcePos, SourceSpan, format_error


class NativeCodeGenerator:
    """Convert TinyLanguage AST nodes into bytecode instructions."""

    def __init__(
        self,
        *,
        allow_heap: bool = False,
        allow_match: bool = False,
        module_namespace: str | None = None,
        source: str | None = None,
    ) -> None:
        self._allow_heap = allow_heap
        self._allow_match = allow_match
        self._module_namespace = module_namespace
        self._tmp_index = 0
        self._variant_fields: Dict[str, List[str]] = {}
        self._async_functions: set[str] = set()
        self._task_scope_depth = 0
        self._source = source

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
                    raise self._error("native codegen does not yet support type definitions", node=stmt)
                self._register_type(stmt, types)
            else:
                raw = self._compile_stmt(stmt)
                entry_instructions.extend(self._shift_labels(raw, len(entry_instructions)))

        entry_instructions.append(self._instr(Opcode.RETURN))
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
        body_instrs.append(self._instr(Opcode.RETURN, node=fn))
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
        body_instrs.append(self._instr(Opcode.RETURN, node=md))
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
        body_instrs.append(self._instr(Opcode.RETURN, node=opdef))
        return FunctionIR(name=name, params=[opdef.a_name, opdef.b_name], instructions=body_instrs)

    def _shift_labels(self, instructions: List[Instruction], offset: int) -> List[Instruction]:
        shifted: List[Instruction] = []
        for instr in instructions:
            if instr.op in {Opcode.JUMP, Opcode.JUMP_IF_FALSE} and instr.arg is not None:
                shifted.append(Instruction(instr.op, instr.arg + offset, span=instr.span))
            else:
                shifted.append(instr)
        return shifted

    def _compile_stmt(self, stmt: "IR") -> List[Instruction]:
        if isinstance(stmt, Let):
            return self._compile_binding(stmt.name, stmt.expr, stmt)
        if isinstance(stmt, Assign):
            return self._compile_binding(stmt.name, stmt.expr, stmt)
        if isinstance(stmt, Import):
            binding = self._import_binding_name(stmt.module, stmt.alias)
            return [
                self._instr(Opcode.PUSH_CONST, stmt.module, stmt),
                self._instr(Opcode.CALL, ("__import", 1), stmt),
                self._instr(Opcode.STORE, binding, stmt),
            ]
        if isinstance(stmt, Print):
            instructions: List[Instruction] = []
            for expr in stmt.exprs:
                instructions.extend(self._compile_expr(expr))
            instructions.append(self._instr(Opcode.PRINT, len(stmt.exprs), stmt))
            return instructions
        if isinstance(stmt, Flush):
            return [self._instr(Opcode.FLUSH, node=stmt)]
        if isinstance(stmt, If):
            return self._compile_if(stmt)
        if isinstance(stmt, While):
            return self._compile_while(stmt)
        if isinstance(stmt, Switch):
            return self._compile_switch(stmt)
        if isinstance(stmt, Return):
            instructions: List[Instruction] = []
            instructions.extend(self._compile_expr(stmt.expr))
            if self._task_scope_depth:
                instructions.extend(self._task_scope_exit_instrs())
            instructions.append(self._instr(Opcode.RETURN, node=stmt))
            return instructions
        if isinstance(stmt, CallStmt):
            if "." in stmt.name:
                obj_name, method_name = stmt.name.split(".", 1)
                expr = MethodCall(Var(obj_name, pos=stmt.pos), method_name, stmt.args, pos=stmt.pos)
            else:
                expr = Call(self._qualify_name(stmt.name), stmt.args, pos=stmt.pos)
            instructions = self._compile_expr(expr)
            instructions.append(self._instr(Opcode.POP, node=stmt))
            return instructions
        if isinstance(stmt, FieldAssign):
            instructions = self._compile_expr(stmt.obj)
            instructions.append(self._instr(Opcode.PUSH_CONST, stmt.name, stmt))
            instructions.extend(self._compile_expr(stmt.expr))
            instructions.append(self._instr(Opcode.CALL, ("__field_set", 3), stmt))
            instructions.append(self._instr(Opcode.POP, node=stmt))
            return instructions
        if isinstance(stmt, TaskBlock):
            instructions: List[Instruction] = [self._instr(Opcode.CALL, ("__task_scope_enter", 0), stmt)]
            self._task_scope_depth += 1
            for inner in stmt.body:
                nested = self._compile_stmt(inner)
                instructions.extend(self._shift_labels(nested, len(instructions)))
            self._task_scope_depth -= 1
            instructions.append(self._instr(Opcode.CALL, ("__task_scope_exit", 0), stmt))
            return instructions
        raise self._error(f"native codegen does not yet support {type(stmt).__name__}", node=stmt)

    def _compile_if(self, stmt: "If") -> List[Instruction]:
        instructions = self._compile_expr(stmt.cond)
        jump_false_index = len(instructions)
        instructions.append(self._instr(Opcode.JUMP_IF_FALSE, None, stmt))

        then_block = []
        for inner in stmt.then:
            nested = self._compile_stmt(inner)
            then_block.extend(self._shift_labels(nested, len(instructions) + len(then_block)))
        then_block.append(self._instr(Opcode.JUMP, None, stmt))

        else_block = []
        for inner in stmt.els:
            nested = self._compile_stmt(inner)
            else_block.extend(self._shift_labels(nested, len(instructions) + len(then_block) + len(else_block)))

        else_start = len(instructions) + len(then_block)
        instructions[jump_false_index] = Instruction(
            Opcode.JUMP_IF_FALSE, else_start, span=instructions[jump_false_index].span
        )

        end_of_then = len(instructions) + len(then_block) + len(else_block)
        then_block[-1] = Instruction(Opcode.JUMP, end_of_then, span=then_block[-1].span)

        instructions.extend(then_block)
        instructions.extend(else_block)
        return instructions

    def _compile_while(self, stmt: "While") -> List[Instruction]:
        instructions: List[Instruction] = []
        loop_start = 0
        cond_instrs = self._compile_expr(stmt.cond)
        instructions.extend(cond_instrs)
        jump_out_index = len(instructions)
        instructions.append(self._instr(Opcode.JUMP_IF_FALSE, None, stmt))

        body_instrs: List[Instruction] = []
        for inner in stmt.body:
            nested = self._compile_stmt(inner)
            body_instrs.extend(self._shift_labels(nested, len(instructions) + len(body_instrs)))
        body_instrs.append(self._instr(Opcode.JUMP, loop_start, stmt))

        loop_exit = len(instructions) + len(body_instrs)
        instructions[jump_out_index] = Instruction(
            Opcode.JUMP_IF_FALSE, loop_exit, span=instructions[jump_out_index].span
        )

        instructions.extend(body_instrs)
        return instructions

    def _compile_switch(self, stmt: "Switch") -> List[Instruction]:
        instructions = self._compile_expr(stmt.expr)
        target_name = self._next_tmp()
        instructions.append(self._instr(Opcode.STORE, target_name, stmt))

        end_jump_indices: List[int] = []
        default_case = None

        for case in stmt.cases:
            if case.value is None:
                default_case = case
                continue
            condition_instrs = [self._instr(Opcode.LOAD, target_name, case)]
            condition_instrs.extend(self._compile_expr(case.value))
            condition_instrs.append(self._instr(Opcode.BINARY, "==", case))
            jump_false_index = len(instructions) + len(condition_instrs)
            condition_instrs.append(self._instr(Opcode.JUMP_IF_FALSE, None, case))
            instructions.extend(condition_instrs)

            body_instrs: List[Instruction] = []
            for inner in case.body:
                nested = self._compile_stmt(inner)
                body_instrs.extend(self._shift_labels(nested, len(instructions) + len(body_instrs)))
            instructions.extend(body_instrs)
            jump_end_index = len(instructions)
            instructions.append(self._instr(Opcode.JUMP, None, case))

            next_case_start = len(instructions)
            instructions[jump_false_index] = Instruction(
                Opcode.JUMP_IF_FALSE, next_case_start, span=instructions[jump_false_index].span
            )
            end_jump_indices.append(jump_end_index)

        if default_case is not None:
            default_instrs: List[Instruction] = []
            for inner in default_case.body:
                nested = self._compile_stmt(inner)
                default_instrs.extend(self._shift_labels(nested, len(instructions) + len(default_instrs)))
            instructions.extend(default_instrs)

        end_target = len(instructions)
        for jump_index in end_jump_indices:
            instructions[jump_index] = Instruction(
                Opcode.JUMP, end_target, span=instructions[jump_index].span
            )
        return instructions

    def _compile_binding(self, name: str, expr: "IR", node: Optional["IR"] = None) -> List[Instruction]:
        instructions = self._compile_expr(expr)
        instructions.append(self._instr(Opcode.STORE, name, node or expr))
        return instructions

    def _compile_expr(self, expr: "IR") -> List[Instruction]:
        if isinstance(expr, Num):
            if "." in expr.txt or "e" in expr.txt or "E" in expr.txt:
                value = float(expr.txt)
                if ("e" in expr.txt or "E" in expr.txt) and "." not in expr.txt and value.is_integer():
                    value = int(value)
            else:
                value = int(expr.txt)
            return [self._instr(Opcode.PUSH_CONST, value, expr)]
        if isinstance(expr, Str):
            return [self._instr(Opcode.PUSH_CONST, expr.txt, expr)]
        if isinstance(expr, Bool):
            return [self._instr(Opcode.PUSH_CONST, expr.value, expr)]
        if isinstance(expr, Null):
            return [self._instr(Opcode.PUSH_CONST, None, expr)]
        if isinstance(expr, New):
            if not self._allow_heap:
                raise self._error("native codegen does not yet support heap allocations", node=expr)
            instructions = self._compile_expr(expr.size)
            instructions.append(self._instr(Opcode.CALL, ("__new", 1), expr))
            return instructions
        if isinstance(expr, NewLit):
            if not self._allow_heap:
                raise self._error("native codegen does not yet support heap allocations", node=expr)
            temp_name = self._next_tmp()
            instructions: List[Instruction] = [
                self._instr(Opcode.PUSH_CONST, len(expr.items), expr),
                self._instr(Opcode.CALL, ("__new", 1), expr),
                self._instr(Opcode.STORE, temp_name, expr),
            ]
            for idx, item in enumerate(expr.items):
                instructions.append(self._instr(Opcode.LOAD, temp_name, item))
                instructions.append(self._instr(Opcode.PUSH_CONST, idx, item))
                instructions.extend(self._compile_expr(item))
                instructions.append(self._instr(Opcode.CALL, ("heap_set", 3), item))
                instructions.append(self._instr(Opcode.POP, node=item))
            instructions.append(self._instr(Opcode.LOAD, temp_name, expr))
            return instructions
        if isinstance(expr, Var):
            return [self._instr(Opcode.LOAD, expr.name, expr)]
        if isinstance(expr, Field):
            instructions = self._compile_expr(expr.obj)
            instructions.append(self._instr(Opcode.PUSH_CONST, expr.name, expr))
            instructions.append(self._instr(Opcode.CALL, ("__field_get", 2), expr))
            return instructions
        if isinstance(expr, MethodCall):
            instructions = self._compile_expr(expr.obj)
            instructions.append(self._instr(Opcode.PUSH_CONST, expr.name, expr))
            for arg in expr.args:
                instructions.extend(self._compile_expr(arg))
            instructions.append(self._instr(Opcode.CALL, ("__method_call", 2 + len(expr.args)), expr))
            return instructions
        if isinstance(expr, ClassNew):
            instructions: List[Instruction] = [self._instr(Opcode.PUSH_CONST, expr.name, expr)]
            for name, value in expr.init:
                instructions.append(self._instr(Opcode.PUSH_CONST, name, expr))
                instructions.extend(self._compile_expr(value))
            instructions.append(self._instr(Opcode.CALL, ("__class_new", 1 + 2 * len(expr.init)), expr))
            return instructions
        if isinstance(expr, VariantCtor):
            if not self._allow_match:
                raise self._error("native codegen does not yet support variant constructors", node=expr)
            return self._compile_variant_ctor(expr)
        if isinstance(expr, Match):
            if not self._allow_match:
                raise self._error("native codegen does not yet support match expressions", node=expr)
            return self._compile_match(expr)
        if isinstance(expr, Spawn):
            return self._compile_spawn(self._qualify_name(expr.name), expr.args, node=expr)
        if isinstance(expr, Await):
            instructions = self._compile_expr(expr.expr)
            instructions.append(self._instr(Opcode.CALL, ("join", 1), expr))
            return instructions
        if isinstance(expr, Bin):
            instructions = self._compile_expr(expr.a)
            instructions.extend(self._compile_expr(expr.b))
            instructions.append(self._instr(Opcode.BINARY, expr.op, expr))
            return instructions
        if isinstance(expr, Call):
            if expr.name == "flush":
                if expr.args:
                    raise self._error("flush expects no arguments", node=expr)
                return [self._instr(Opcode.FLUSH, None, expr), self._instr(Opcode.PUSH_CONST, None, expr)]
            if expr.name in {"__new", "new", "heap_get", "heap_set", "delete"} and not self._allow_heap:
                raise self._error("native codegen does not yet support heap allocations", node=expr)
            call_name = self._qualify_name(expr.name)
            if call_name in self._async_functions:
                return self._compile_spawn(call_name, expr.args, node=expr)
            instructions: List[Instruction] = []
            for arg in expr.args:
                instructions.extend(self._compile_expr(arg))
            instructions.append(self._instr(Opcode.CALL, (call_name, len(expr.args)), expr))
            return instructions
        raise self._error(
            f"native codegen does not yet support expression {type(expr).__name__}",
            node=expr,
        )

    def _next_tmp(self) -> str:
        self._tmp_index += 1
        return f"__tmp_heap_{self._tmp_index}"

    def _compile_variant_ctor(self, expr: "VariantCtor") -> List[Instruction]:
        instructions: List[Instruction] = [
            self._instr(Opcode.PUSH_CONST, expr.variant, expr),
            self._instr(Opcode.PUSH_CONST, expr.type_name, expr),
        ]
        for name, value in expr.fields:
            instructions.append(self._instr(Opcode.PUSH_CONST, name, expr))
            instructions.extend(self._compile_expr(value))
        instructions.append(self._instr(Opcode.CALL, ("__variant_new", 2 + 2 * len(expr.fields)), expr))
        return instructions

    def _compile_spawn(self, name: str, args: List["IR"], *, node: Optional["IR"] = None) -> List[Instruction]:
        instructions: List[Instruction] = [self._instr(Opcode.PUSH_CONST, name, node)]
        for arg in args:
            instructions.extend(self._compile_expr(arg))
        instructions.append(self._instr(Opcode.CALL, ("__spawn", 1 + len(args)), node))
        return instructions

    def _compile_match(self, expr: "Match") -> List[Instruction]:
        instructions = self._compile_expr(expr.expr)
        tmp_name = self._next_tmp()
        instructions.append(self._instr(Opcode.STORE, tmp_name, expr))
        result_tmp = self._next_tmp()

        end_jump_indices: List[int] = []
        for case in expr.cases:
            pattern = case.pattern
            if isinstance(pattern, VariantPattern):
                instructions.append(self._instr(Opcode.LOAD, tmp_name, case))
                instructions.append(self._instr(Opcode.CALL, ("__variant_tag", 1), case))
                instructions.append(self._instr(Opcode.PUSH_CONST, pattern.variant, pattern))
                instructions.append(self._instr(Opcode.BINARY, "==", case))
                jump_false_index = len(instructions)
                instructions.append(self._instr(Opcode.JUMP_IF_FALSE, None, case))
                instructions.append(self._instr(Opcode.LOAD, tmp_name, case))
                instructions.append(self._instr(Opcode.PUSH_CONST, pattern.variant, pattern))
                instructions.append(self._instr(Opcode.CALL, ("__variant_assume", 2), case))
                instructions.append(self._instr(Opcode.STORE, tmp_name, case))
                instructions.extend(self._compile_pattern_bindings(pattern, tmp_name))
                instructions.extend(self._compile_expr(case.body))
                instructions.append(self._instr(Opcode.STORE, result_tmp, case))
                end_jump_indices.append(len(instructions))
                instructions.append(self._instr(Opcode.JUMP, None, case))
                instructions[jump_false_index] = Instruction(
                    Opcode.JUMP_IF_FALSE, len(instructions), span=instructions[jump_false_index].span
                )
            elif isinstance(pattern, WildcardPattern):
                if pattern.name:
                    instructions.append(self._instr(Opcode.LOAD, tmp_name, case))
                    instructions.append(self._instr(Opcode.STORE, pattern.name, case))
                instructions.extend(self._compile_expr(case.body))
                instructions.append(self._instr(Opcode.STORE, result_tmp, case))
                end_jump_indices.append(len(instructions))
                instructions.append(self._instr(Opcode.JUMP, None, case))
            else:
                raise self._error(
                    f"native codegen does not yet support {type(pattern).__name__} patterns",
                    node=pattern,
                )

        instructions.append(self._instr(Opcode.LOAD, tmp_name, expr))
        instructions.append(self._instr(Opcode.CALL, ("__match_error", 1), expr))

        end_index = len(instructions)
        for jump_index in end_jump_indices:
            instructions[jump_index] = Instruction(Opcode.JUMP, end_index, span=instructions[jump_index].span)
        instructions.append(self._instr(Opcode.LOAD, result_tmp, expr))
        return instructions

    def _compile_pattern_bindings(self, pattern: "VariantPattern", tmp_name: str) -> List[Instruction]:
        instructions: List[Instruction] = []
        field_names: List[str] = []
        if pattern.positional_bindings is not None:
            field_names = self._variant_field_order(pattern.variant)
            if field_names is None:
                raise self._error(
                    f"native codegen requires type information for positional pattern {pattern.variant}",
                    node=pattern,
                )
            if len(pattern.positional_bindings) > len(field_names):
                raise RuntimeError(
                    f"positional pattern for {pattern.variant} has too many fields ({len(pattern.positional_bindings)})"
                )
            for index, bind in enumerate(pattern.positional_bindings):
                if bind is None:
                    continue
                instructions.append(self._instr(Opcode.LOAD, tmp_name, pattern))
                instructions.append(self._instr(Opcode.PUSH_CONST, field_names[index], pattern))
                instructions.append(self._instr(Opcode.CALL, ("__variant_get", 2), pattern))
                instructions.append(self._instr(Opcode.STORE, bind, pattern))
        for fname, bind in pattern.bindings.items():
            if bind is None:
                continue
            instructions.append(self._instr(Opcode.LOAD, tmp_name, pattern))
            instructions.append(self._instr(Opcode.PUSH_CONST, fname, pattern))
            instructions.append(self._instr(Opcode.CALL, ("__variant_get", 2), pattern))
            instructions.append(self._instr(Opcode.STORE, bind, pattern))
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
        return [self._instr(Opcode.CALL, ("__task_scope_exit", 0)) for _ in range(self._task_scope_depth)]

    def _error(
        self,
        message: str,
        *,
        node: Optional["IR"] = None,
        span: Optional[SourceSpan] = None,
    ) -> NotImplementedError:
        resolved_span = span or getattr(node, "span", None)
        pos = resolved_span.start if resolved_span is not None else getattr(node, "pos", SourcePos.origin())
        rendered = message
        if self._source is not None:
            rendered = format_error(self._source, resolved_span or pos, message)
        return NotImplementedError(rendered)

    @staticmethod
    def _span_for(node: "IR") -> Optional[SourceSpan]:
        span = getattr(node, "span", None)
        if span is not None:
            return span
        pos = getattr(node, "pos", None)
        if isinstance(pos, SourcePos):
            return SourceSpan(pos, pos)
        return None

    def _instr(self, op: Opcode, arg: object | None = None, node: Optional["IR"] = None) -> Instruction:
        return Instruction(op, arg, span=self._span_for(node) if node is not None else None)
