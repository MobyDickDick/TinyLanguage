"""C backend prototype for TinyLanguage.

This module emits a self-contained C program that embeds the native bytecode
and a tiny stack-based VM. The generator only targets the same subset supported
by ``NativeCodeGenerator`` (literals, arithmetic, control flow, functions, and
print). The resulting C source is meant for inspection or piping into a system
compiler like ``clang`` or ``gcc``.
"""

import json
import textwrap
from dataclasses import dataclass, field
from typing import Iterable, List

from native_ir import Instruction, Opcode, ProgramIR


@dataclass
class _FunctionBlock:
    name: str
    params: List[str]
    instructions: List[Instruction]


@dataclass
class _ProgramLayout:
    entry: List[Instruction]
    functions: List[_FunctionBlock]
    strings: List[str] = field(default_factory=list)


class CCodeGenerator:
    """Translate ``ProgramIR`` into C source with an embedded VM."""

    def compile_program(self, program: ProgramIR) -> str:
        layout = self._collect_program(program)
        lines: List[str] = []
        lines.extend(self._header())
        lines.append("")
        lines.extend(self._emit_runtime())
        lines.append("")
        lines.extend(self._emit_data(layout))
        lines.append("")
        lines.extend(self._emit_main())
        return "\n".join(lines)

    def _format_opcode(self, op: Opcode) -> str:
        return op.value if isinstance(op, Opcode) else str(op)

    def _supported_opcodes(self) -> str:
        return ", ".join(self._format_opcode(op) for op in Opcode)

    def _unsupported_opcode(self, instr: Instruction) -> None:
        op_name = self._format_opcode(instr.op)
        raise NotImplementedError(
            f"C backend does not support opcode {op_name}. Supported opcodes: {self._supported_opcodes()}."
        )

    def _collect_program(self, program: ProgramIR) -> _ProgramLayout:
        functions = [
            _FunctionBlock(name=fn.name, params=list(fn.params), instructions=list(fn.instructions))
            for fn in program.functions.values()
        ]
        strings: List[str] = []
        for instr in program.entry:
            strings.extend(self._strings_for_instruction(instr))
        for fn in functions:
            for instr in fn.instructions:
                strings.extend(self._strings_for_instruction(instr))
        return _ProgramLayout(entry=list(program.entry), functions=functions, strings=sorted(set(strings)))

    def _strings_for_instruction(self, instr: Instruction) -> List[str]:
        strings: List[str] = []
        if instr.op in {Opcode.LOAD, Opcode.STORE, Opcode.BINARY}:
            strings.append(str(instr.arg))
        elif instr.op == Opcode.CALL:
            name, _argc = instr.arg
            strings.append(str(name))
        elif instr.op == Opcode.PUSH_CONST and isinstance(instr.arg, str):
            strings.append(instr.arg)
        return strings

    def _header(self) -> List[str]:
        return [
            "#include <math.h>",
            "#include <stdbool.h>",
            "#include <stdint.h>",
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "#include <string.h>",
        ]

    def _emit_runtime(self) -> List[str]:
        runtime = r"""
        typedef enum {
            OP_PUSH_CONST,
            OP_LOAD,
            OP_STORE,
            OP_BINARY,
            OP_PRINT,
            OP_FLUSH,
            OP_JUMP,
            OP_JUMP_IF_FALSE,
            OP_CALL,
            OP_POP,
            OP_RETURN
        } Opcode;

        typedef enum {
            VAL_NULL,
            VAL_BOOL,
            VAL_INT,
            VAL_DOUBLE,
            VAL_STRING
        } ValueType;

        typedef struct {
            ValueType type;
            union {
                bool bool_value;
                int64_t int_value;
                double double_value;
                const char *string_value;
            } as;
        } Value;

        typedef struct {
            const char *name;
            int argc;
        } CallArg;

        typedef enum {
            ARG_NONE,
            ARG_INT,
            ARG_STRING,
            ARG_CALL,
            ARG_VALUE
        } ArgKind;

        typedef struct {
            ArgKind kind;
            union {
                int64_t int_value;
                const char *string_value;
                CallArg call_value;
                Value value;
            } as;
        } Arg;

        typedef struct {
            Opcode op;
            Arg arg;
        } Instruction;

        typedef struct {
            const char *name;
            Value value;
        } Binding;

        typedef struct {
            Binding *items;
            int count;
            int capacity;
        } Env;

        typedef struct {
            const char *name;
            const char **params;
            int param_count;
            Instruction *instructions;
            int instruction_count;
        } Function;

        typedef struct {
            Instruction *instructions;
            int instruction_count;
            int ip;
            Env *locals;
            bool is_global;
        } Frame;

        typedef struct {
            Instruction *entry;
            int entry_count;
            Function *functions;
            int function_count;
            Env globals;
        } Program;

        typedef struct {
            Value *items;
            int count;
            int capacity;
        } Stack;

        #define ARG_NONE_VALUE (Arg){ARG_NONE}
        #define ARG_INT_VALUE(v) (Arg){ARG_INT, .as.int_value = (v)}
        #define ARG_STRING_VALUE(v) (Arg){ARG_STRING, .as.string_value = (v)}
        #define ARG_CALL_VALUE(name, argc) (Arg){ARG_CALL, .as.call_value = {(name), (argc)}}
        #define ARG_VALUE_VALUE(v) (Arg){ARG_VALUE, .as.value = (v)}

        #define VAL_NULL_VALUE (Value){VAL_NULL}
        #define VAL_BOOL_VALUE(v) (Value){VAL_BOOL, .as.bool_value = (v)}
        #define VAL_INT_VALUE(v) (Value){VAL_INT, .as.int_value = (v)}
        #define VAL_DOUBLE_VALUE(v) (Value){VAL_DOUBLE, .as.double_value = (v)}
        #define VAL_STRING_VALUE(v) (Value){VAL_STRING, .as.string_value = (v)}

        static void env_init(Env *env) {
            env->items = NULL;
            env->count = 0;
            env->capacity = 0;
        }

        static int env_find(Env *env, const char *name) {
            for (int i = 0; i < env->count; i++) {
                if (strcmp(env->items[i].name, name) == 0) {
                    return i;
                }
            }
            return -1;
        }

        static void env_set(Env *env, const char *name, Value value) {
            int index = env_find(env, name);
            if (index >= 0) {
                env->items[index].value = value;
                return;
            }
            if (env->count >= env->capacity) {
                env->capacity = env->capacity < 8 ? 8 : env->capacity * 2;
                env->items = realloc(env->items, sizeof(Binding) * env->capacity);
            }
            env->items[env->count].name = name;
            env->items[env->count].value = value;
            env->count += 1;
        }

        static bool env_get(Env *env, const char *name, Value *out) {
            int index = env_find(env, name);
            if (index >= 0) {
                *out = env->items[index].value;
                return true;
            }
            return false;
        }

        static void stack_init(Stack *stack) {
            stack->items = NULL;
            stack->count = 0;
            stack->capacity = 0;
        }

        static void stack_push(Stack *stack, Value value) {
            if (stack->count >= stack->capacity) {
                stack->capacity = stack->capacity < 8 ? 8 : stack->capacity * 2;
                stack->items = realloc(stack->items, sizeof(Value) * stack->capacity);
            }
            stack->items[stack->count++] = value;
        }

        static Value stack_pop(Stack *stack) {
            if (stack->count == 0) {
                fprintf(stderr, "Runtime error: pop from empty stack\n");
                exit(1);
            }
            return stack->items[--stack->count];
        }

        static bool value_truthy(Value value) {
            switch (value.type) {
                case VAL_NULL: return false;
                case VAL_BOOL: return value.as.bool_value;
                case VAL_INT: return value.as.int_value != 0;
                case VAL_DOUBLE: return value.as.double_value != 0.0;
                case VAL_STRING: return value.as.string_value && value.as.string_value[0] != '\0';
            }
            return false;
        }

        static void print_value(Value value) {
            switch (value.type) {
                case VAL_NULL:
                    printf("null");
                    break;
                case VAL_BOOL:
                    printf(value.as.bool_value ? "true" : "false");
                    break;
                case VAL_INT:
                    printf("%lld", (long long)value.as.int_value);
                    break;
                case VAL_DOUBLE:
                    printf("%.15g", value.as.double_value);
                    break;
                case VAL_STRING:
                    printf("%s", value.as.string_value ? value.as.string_value : "");
                    break;
            }
        }

        static Value make_bool(bool value) { return VAL_BOOL_VALUE(value); }

        static Value value_binary_op(Value left, Value right, const char *op) {
            if (strcmp(op, "&&") == 0 || strcmp(op, "and") == 0) {
                return make_bool(value_truthy(left) && value_truthy(right));
            }
            if (strcmp(op, "||") == 0 || strcmp(op, "or") == 0) {
                return make_bool(value_truthy(left) || value_truthy(right));
            }
            if (left.type == VAL_STRING && right.type == VAL_STRING && strcmp(op, "+") == 0) {
                size_t left_len = strlen(left.as.string_value);
                size_t right_len = strlen(right.as.string_value);
                char *joined = malloc(left_len + right_len + 1);
                memcpy(joined, left.as.string_value, left_len);
                memcpy(joined + left_len, right.as.string_value, right_len);
                joined[left_len + right_len] = '\0';
                return VAL_STRING_VALUE(joined);
            }
            bool use_double = left.type == VAL_DOUBLE || right.type == VAL_DOUBLE || strcmp(op, "/") == 0;
            double left_num = (left.type == VAL_DOUBLE) ? left.as.double_value : (double)left.as.int_value;
            double right_num = (right.type == VAL_DOUBLE) ? right.as.double_value : (double)right.as.int_value;
            if (strcmp(op, "+") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(left_num + right_num) : VAL_INT_VALUE((int64_t)(left_num + right_num));
            }
            if (strcmp(op, "-") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(left_num - right_num) : VAL_INT_VALUE((int64_t)(left_num - right_num));
            }
            if (strcmp(op, "*") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(left_num * right_num) : VAL_INT_VALUE((int64_t)(left_num * right_num));
            }
            if (strcmp(op, "/") == 0) {
                return VAL_DOUBLE_VALUE(left_num / right_num);
            }
            if (strcmp(op, "%") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(fmod(left_num, right_num)) : VAL_INT_VALUE((int64_t)left_num % (int64_t)right_num);
            }
            if (strcmp(op, "^") == 0) {
                return use_double ? VAL_DOUBLE_VALUE(pow(left_num, right_num)) : VAL_INT_VALUE((int64_t)pow(left_num, right_num));
            }
            if (strcmp(op, "==") == 0) {
                if (left.type == VAL_STRING && right.type == VAL_STRING) {
                    return make_bool(strcmp(left.as.string_value, right.as.string_value) == 0);
                }
                return make_bool(left_num == right_num);
            }
            if (strcmp(op, "!=") == 0) {
                if (left.type == VAL_STRING && right.type == VAL_STRING) {
                    return make_bool(strcmp(left.as.string_value, right.as.string_value) != 0);
                }
                return make_bool(left_num != right_num);
            }
            if (strcmp(op, "<") == 0) { return make_bool(left_num < right_num); }
            if (strcmp(op, ">") == 0) { return make_bool(left_num > right_num); }
            if (strcmp(op, "<=") == 0) { return make_bool(left_num <= right_num); }
            if (strcmp(op, ">=") == 0) { return make_bool(left_num >= right_num); }
            fprintf(stderr, "Runtime error: unsupported operator %s\n", op);
            exit(1);
        }

        static Function *find_function(Program *program, const char *name) {
            for (int i = 0; i < program->function_count; i++) {
                if (strcmp(program->functions[i].name, name) == 0) {
                    return &program->functions[i];
                }
            }
            return NULL;
        }

        static Value execute_frame(Program *program, Frame *frame) {
            Stack stack;
            stack_init(&stack);
            while (frame->ip < frame->instruction_count) {
                Instruction instr = frame->instructions[frame->ip++];
                switch (instr.op) {
                    case OP_PUSH_CONST:
                        stack_push(&stack, instr.arg.as.value);
                        break;
                    case OP_LOAD: {
                        Value value;
                        if (env_get(frame->locals, instr.arg.as.string_value, &value) ||
                            env_get(&program->globals, instr.arg.as.string_value, &value)) {
                            stack_push(&stack, value);
                        } else {
                            fprintf(stderr, "Runtime error: unknown variable %s\n", instr.arg.as.string_value);
                            exit(1);
                        }
                        break;
                    }
                    case OP_STORE: {
                        Value value = stack_pop(&stack);
                        env_set(frame->locals, instr.arg.as.string_value, value);
                        if (frame->is_global) {
                            env_set(&program->globals, instr.arg.as.string_value, value);
                        }
                        break;
                    }
                    case OP_BINARY: {
                        Value right = stack_pop(&stack);
                        Value left = stack_pop(&stack);
                        stack_push(&stack, value_binary_op(left, right, instr.arg.as.string_value));
                        break;
                    }
                    case OP_PRINT: {
                        int count = (int)instr.arg.as.int_value;
                        Value *values = malloc(sizeof(Value) * count);
                        for (int i = count - 1; i >= 0; i--) {
                            values[i] = stack_pop(&stack);
                        }
                        for (int i = 0; i < count; i++) {
                            print_value(values[i]);
                            if (i < count - 1) {
                                printf(" ");
                            }
                        }
                        free(values);
                        printf("\n");
                        break;
                    }
                    case OP_FLUSH:
                        fflush(stdout);
                        break;
                    case OP_JUMP:
                        frame->ip = (int)instr.arg.as.int_value;
                        break;
                    case OP_JUMP_IF_FALSE: {
                        Value cond = stack_pop(&stack);
                        if (!value_truthy(cond)) {
                            frame->ip = (int)instr.arg.as.int_value;
                        }
                        break;
                    }
                    case OP_CALL: {
                        Function *fn = find_function(program, instr.arg.as.call_value.name);
                        if (!fn) {
                            fprintf(stderr, "Runtime error: unknown function %s\n", instr.arg.as.call_value.name);
                            exit(1);
                        }
                        if (fn->param_count != instr.arg.as.call_value.argc) {
                            fprintf(stderr, "Runtime error: function %s expects %d args, got %d\n", fn->name, fn->param_count, instr.arg.as.call_value.argc);
                            exit(1);
                        }
                        Env locals;
                        env_init(&locals);
                        for (int i = fn->param_count - 1; i >= 0; i--) {
                            Value arg_val = stack_pop(&stack);
                            env_set(&locals, fn->params[i], arg_val);
                        }
                        Frame call_frame;
                        call_frame.instructions = fn->instructions;
                        call_frame.instruction_count = fn->instruction_count;
                        call_frame.ip = 0;
                        call_frame.locals = &locals;
                        call_frame.is_global = false;
                        Value result = execute_frame(program, &call_frame);
                        stack_push(&stack, result);
                        break;
                    }
                    case OP_POP:
                        stack_pop(&stack);
                        break;
                    case OP_RETURN:
                        if (stack.count > 0) {
                            return stack_pop(&stack);
                        }
                        return VAL_NULL_VALUE;
                }
            }
            return VAL_NULL_VALUE;
        }

        static Value execute_program(Program *program) {
            Frame frame;
            frame.instructions = program->entry;
            frame.instruction_count = program->entry_count;
            frame.ip = 0;
            frame.locals = &program->globals;
            frame.is_global = true;
            return execute_frame(program, &frame);
        }
        """
        return textwrap.dedent(runtime).strip().splitlines()

    def _emit_data(self, layout: _ProgramLayout) -> List[str]:
        lines: List[str] = []
        for index, fn in enumerate(layout.functions):
            symbol = self._fn_symbol(index)
            params = ", ".join(self._c_string(param) for param in fn.params)
            lines.append(f"static const char *params_{symbol}[] = {{{params}}};")
            lines.append(f"static Instruction instructions_{symbol}[] = {{")
            lines.extend(self._emit_instructions(fn.instructions, indent="    "))
            lines.append("};")
            lines.append("")
        lines.append("static Instruction entry_instructions[] = {")
        lines.extend(self._emit_instructions(layout.entry, indent="    "))
        lines.append("};")
        lines.append("")
        if layout.functions:
            lines.append("static Function functions[] = {")
            for index, fn in enumerate(layout.functions):
                symbol = self._fn_symbol(index)
                lines.append(
                    "    {" + f"{self._c_string(fn.name)}, params_{symbol}, {len(fn.params)}, "
                    f"instructions_{symbol}, {len(fn.instructions)}" + "},"
                )
            lines.append("};")
            lines.append("static int function_count = (int)(sizeof(functions) / sizeof(functions[0]));")
        else:
            lines.append("static Function *functions = NULL;")
            lines.append("static int function_count = 0;")
        return lines

    def _fn_symbol(self, index: int) -> str:
        return f"fn_{index}"

    def _emit_instructions(self, instructions: Iterable[Instruction], *, indent: str) -> List[str]:
        lines: List[str] = []
        for instr in instructions:
            lines.append(f"{indent}{self._instruction_literal(instr)},")
        return lines

    def _instruction_literal(self, instr: Instruction) -> str:
        if instr.op == Opcode.PUSH_CONST:
            return f"{{OP_PUSH_CONST, {self._arg_value(instr.arg)}}}"
        if instr.op == Opcode.LOAD:
            return f"{{OP_LOAD, {self._arg_string(instr.arg)}}}"
        if instr.op == Opcode.STORE:
            return f"{{OP_STORE, {self._arg_string(instr.arg)}}}"
        if instr.op == Opcode.BINARY:
            return f"{{OP_BINARY, {self._arg_string(instr.arg)}}}"
        if instr.op == Opcode.PRINT:
            return f"{{OP_PRINT, {self._arg_int(int(instr.arg))}}}"
        if instr.op == Opcode.FLUSH:
            return "{OP_FLUSH, ARG_NONE_VALUE}"
        if instr.op == Opcode.JUMP:
            return f"{{OP_JUMP, {self._arg_int(int(instr.arg))}}}"
        if instr.op == Opcode.JUMP_IF_FALSE:
            return f"{{OP_JUMP_IF_FALSE, {self._arg_int(int(instr.arg))}}}"
        if instr.op == Opcode.CALL:
            name, argc = instr.arg
            return f"{{OP_CALL, {self._arg_call(str(name), int(argc))}}}"
        if instr.op == Opcode.POP:
            return "{OP_POP, ARG_NONE_VALUE}"
        if instr.op == Opcode.RETURN:
            return "{OP_RETURN, ARG_NONE_VALUE}"
        self._unsupported_opcode(instr)

    def _arg_int(self, value: int) -> str:
        return f"ARG_INT_VALUE({value})"

    def _arg_string(self, value: str) -> str:
        return f"ARG_STRING_VALUE({self._c_string(value)})"

    def _arg_call(self, name: str, argc: int) -> str:
        return f"ARG_CALL_VALUE({self._c_string(name)}, {argc})"

    def _arg_value(self, value: object) -> str:
        return f"ARG_VALUE_VALUE({self._value_literal(value)})"

    def _value_literal(self, value: object) -> str:
        if value is None:
            return "VAL_NULL_VALUE"
        if isinstance(value, bool):
            return f"VAL_BOOL_VALUE({'true' if value else 'false'})"
        if isinstance(value, int) and not isinstance(value, bool):
            return f"VAL_INT_VALUE({value})"
        if isinstance(value, float):
            return f"VAL_DOUBLE_VALUE({value})"
        if isinstance(value, str):
            return f"VAL_STRING_VALUE({self._c_string(value)})"
        raise NotImplementedError(f"unsupported constant {value!r}")

    def _c_string(self, value: str) -> str:
        return json.dumps(value)

    def _emit_main(self) -> List[str]:
        return [
            "int main(void) {",
            "    Program program;",
            "    program.entry = entry_instructions;",
            "    program.entry_count = (int)(sizeof(entry_instructions) / sizeof(entry_instructions[0]));",
            "    program.functions = functions;",
            "    program.function_count = function_count;",
            "    env_init(&program.globals);",
            "    execute_program(&program);",
            "    return 0;",
            "}",
        ]
