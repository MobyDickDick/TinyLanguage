import json
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
TINY_LANGUAGE = PROJECT_ROOT / "src" / "tiny_language.py"
PYTHON_COMPILER_CLI = PROJECT_ROOT / "src" / "tiny_language_compiler_cli.py"
TINY_COMPILER_CLI = PROJECT_ROOT / "src_tiny" / "tiny_language_compiler_cli.tiny"


@dataclass(frozen=True)
class CompilerSnapshot:
    source: str
    args: list[str]
    stdout: str
    stderr: str
    returncode: int


EXPECTED_C_SOURCE = r"""#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>

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

static Value stack_pop(Stack *stack);

typedef struct {
    int64_t size;
    Value *cells;
} HeapAllocation;

typedef struct HeapMeta {
    int64_t ptr;
    int64_t size;
    bool freed;
    struct HeapMeta *next;
} HeapMeta;

static HeapMeta *heap_meta_head = NULL;

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

static const char *value_type_label(Value value) {
    switch (value.type) {
        case VAL_NULL: return "Null";
        case VAL_BOOL: return "Bool";
        case VAL_INT: return "int";
        case VAL_DOUBLE: return "float";
        case VAL_STRING: return "string";
    }
    return "unknown";
}

static void heap_error(const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
    exit(1);
}

static void runtime_error(const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
    exit(1);
}

static int64_t value_to_index(Value value) {
    if (value.type == VAL_INT) {
        return value.as.int_value;
    }
    if (value.type == VAL_DOUBLE) {
        double raw = value.as.double_value;
        int64_t as_int = (int64_t)raw;
        if ((double)as_int == raw) {
            return as_int;
        }
        heap_error("heap access error: index %g is not an integer index", raw);
    }
    heap_error("heap access error: index %s is not numeric", value_type_label(value));
    return 0;
}

static int64_t value_to_pointer(Value value, const char *op) {
    if (value.type == VAL_INT) {
        return value.as.int_value;
    }
    if (value.type == VAL_DOUBLE) {
        double raw = value.as.double_value;
        int64_t as_int = (int64_t)raw;
        if ((double)as_int == raw) {
            return as_int;
        }
        heap_error("heap %s error: pointer %g is not an integer pointer", op, raw);
    }
    heap_error("heap %s error: pointer %s is not numeric", op, value_type_label(value));
    return 0;
}

static HeapMeta *heap_find_meta(int64_t ptr) {
    for (HeapMeta *node = heap_meta_head; node != NULL; node = node->next) {
        if (node->ptr == ptr) {
            return node;
        }
    }
    return NULL;
}

static HeapMeta *heap_require_meta(int64_t ptr, const char *op) {
    if (ptr < 1) {
        heap_error(
            "heap %s error: pointer %lld is invalid (must refer to a live positive allocation)",
            op,
            (long long)ptr
        );
    }
    HeapMeta *meta = heap_find_meta(ptr);
    if (!meta) {
        heap_error("heap %s error: unknown pointer %lld", op, (long long)ptr);
    }
    if (meta->freed) {
        heap_error(
            "heap %s error: pointer %lld was already freed (size %lld)",
            op,
            (long long)ptr,
            (long long)meta->size
        );
    }
    return meta;
}

static int64_t value_to_size(Value value) {
    if (value.type == VAL_INT) {
        return value.as.int_value;
    }
    if (value.type == VAL_DOUBLE) {
        double raw = value.as.double_value;
        int64_t as_int = (int64_t)raw;
        if ((double)as_int == raw) {
            return as_int;
        }
        heap_error("alloc error: size %g is not an integer", raw);
    }
    heap_error("alloc error: size %s is not numeric", value_type_label(value));
    return 0;
}

static int64_t heap_new_size(Value value) {
    int64_t size = value_to_size(value);
    if (size < 0) {
        heap_error("alloc error: negative size");
    }
    return size;
}

static int64_t heap_new_allocation(int64_t size) {
    HeapAllocation *alloc = malloc(sizeof(HeapAllocation));
    alloc->size = size;
    alloc->cells = calloc((size_t)size, sizeof(Value));
    int64_t ptr = (int64_t)(intptr_t)alloc;
    HeapMeta *meta = calloc(1, sizeof(HeapMeta));
    meta->ptr = ptr;
    meta->size = size;
    meta->freed = false;
    meta->next = heap_meta_head;
    heap_meta_head = meta;
    return ptr;
}

static Value heap_get(Value ptr_value, Value idx_value) {
    int64_t ptr = value_to_pointer(ptr_value, "access");
    int64_t idx = value_to_index(idx_value);
    HeapMeta *meta = heap_require_meta(ptr, "access");
    if (idx < 0 || idx >= meta->size) {
        heap_error(
            "heap access error: index %lld out of range for pointer %lld (size %lld)",
            (long long)idx,
            (long long)ptr,
            (long long)meta->size
        );
    }
    HeapAllocation *alloc = (HeapAllocation *)(intptr_t)ptr;
    return alloc->cells[idx];
}

static Value heap_set(Value ptr_value, Value idx_value, Value value) {
    int64_t ptr = value_to_pointer(ptr_value, "access");
    int64_t idx = value_to_index(idx_value);
    HeapMeta *meta = heap_require_meta(ptr, "access");
    if (idx < 0 || idx >= meta->size) {
        heap_error(
            "heap access error: index %lld out of range for pointer %lld (size %lld)",
            (long long)idx,
            (long long)ptr,
            (long long)meta->size
        );
    }
    HeapAllocation *alloc = (HeapAllocation *)(intptr_t)ptr;
    alloc->cells[idx] = value;
    return VAL_INT_VALUE(0);
}

static Value heap_len(Value ptr_value) {
    int64_t ptr = value_to_pointer(ptr_value, "access");
    HeapMeta *meta = heap_require_meta(ptr, "access");
    return VAL_INT_VALUE(meta->size);
}

static Value heap_delete(Value ptr_value) {
    int64_t ptr = value_to_pointer(ptr_value, "delete");
    HeapMeta *meta = heap_require_meta(ptr, "delete");
    meta->freed = true;
    HeapAllocation *alloc = (HeapAllocation *)(intptr_t)ptr;
    free(alloc->cells);
    free(alloc);
    return VAL_INT_VALUE(0);
}

static Value heap_leak_report(void) {
    int64_t count = 0;
    for (HeapMeta *node = heap_meta_head; node != NULL; node = node->next) {
        if (!node->freed) {
            count += 1;
        }
    }
    return VAL_INT_VALUE(count);
}

static bool call_builtin(const char *name, int argc, Stack *stack, Value *out) {
    if (strcmp(name, "new") == 0 || strcmp(name, "__new") == 0) {
        if (argc != 1) {
            runtime_error("Runtime error: %s expects 1 arg, got %d", name, argc);
        }
        Value size_value = stack_pop(stack);
        int64_t size = heap_new_size(size_value);
        int64_t ptr = heap_new_allocation(size);
        *out = VAL_INT_VALUE(ptr);
        return true;
    }
    if (strcmp(name, "heap_get") == 0) {
        if (argc != 2) {
            runtime_error("Runtime error: heap_get expects 2 args, got %d", argc);
        }
        Value idx_value = stack_pop(stack);
        Value ptr_value = stack_pop(stack);
        *out = heap_get(ptr_value, idx_value);
        return true;
    }
    if (strcmp(name, "heap_set") == 0) {
        if (argc != 3) {
            runtime_error("Runtime error: heap_set expects 3 args, got %d", argc);
        }
        Value value = stack_pop(stack);
        Value idx_value = stack_pop(stack);
        Value ptr_value = stack_pop(stack);
        *out = heap_set(ptr_value, idx_value, value);
        return true;
    }
    if (strcmp(name, "heap_len") == 0) {
        if (argc != 1) {
            runtime_error("Runtime error: heap_len expects 1 arg, got %d", argc);
        }
        Value ptr_value = stack_pop(stack);
        *out = heap_len(ptr_value);
        return true;
    }
    if (strcmp(name, "heap_leak_report") == 0) {
        if (argc != 0) {
            runtime_error("Runtime error: heap_leak_report expects 0 args, got %d", argc);
        }
        *out = heap_leak_report();
        return true;
    }
    if (strcmp(name, "delete") == 0) {
        if (argc != 1) {
            runtime_error("Runtime error: delete expects 1 arg, got %d", argc);
        }
        Value ptr_value = stack_pop(stack);
        *out = heap_delete(ptr_value);
        return true;
    }
    return false;
}

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
                Value builtin_result;
                if (call_builtin(
                    instr.arg.as.call_value.name,
                    instr.arg.as.call_value.argc,
                    &stack,
                    &builtin_result
                )) {
                    stack_push(&stack, builtin_result);
                    break;
                }
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

static Instruction entry_instructions[] = {
    {OP_PUSH_CONST, ARG_VALUE_VALUE(VAL_INT_VALUE(1))},
    {OP_PUSH_CONST, ARG_VALUE_VALUE(VAL_INT_VALUE(2))},
    {OP_BINARY, ARG_STRING_VALUE("+")},
    {OP_PRINT, ARG_INT_VALUE(1)},
    {OP_RETURN, ARG_NONE_VALUE},
};

static Function *functions = NULL;
static int function_count = 0;

int main(void) {
    Program program;
    program.entry = entry_instructions;
    program.entry_count = (int)(sizeof(entry_instructions) / sizeof(entry_instructions[0]));
    program.functions = functions;
    program.function_count = function_count;
    env_init(&program.globals);
    execute_program(&program);
    return 0;
}
"""


SNAPSHOTS = [
    CompilerSnapshot(
        source="print(1 + 2);",
        args=["--emit-c"],
        stdout=EXPECTED_C_SOURCE,
        stderr="",
        returncode=0,
    ),
    CompilerSnapshot(
        source="def x = ;",
        args=["--emit-c"],
        stdout="",
        stderr=(
            "[E000] unexpected token SYM (line 1, col 9)\n"
            "> 1 | def x = ;\n"
            "    |         ^\n"
        ),
        returncode=1,
    ),
]


def run_python_compiler_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH")])
        ),
    }
    return subprocess.run(
        [sys.executable, str(PYTHON_COMPILER_CLI), *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def run_tiny_compiler_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH")])
        ),
        "TINYLANG_ARGS": json.dumps(args),
        "TINYLANG_EXIT": "1",
    }
    return subprocess.run(
        [sys.executable, str(TINY_LANGUAGE), str(TINY_COMPILER_CLI)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def assert_compiler_snapshot(snapshot: CompilerSnapshot, tmp_path: pathlib.Path) -> None:
    program_path = tmp_path / "program.tiny"
    program_path.write_text(snapshot.source, encoding="utf-8")
    args = [str(program_path), *snapshot.args]

    python_proc = run_python_compiler_cli(args)
    assert python_proc.stdout == snapshot.stdout
    assert python_proc.stderr == snapshot.stderr
    assert python_proc.returncode == snapshot.returncode

    tiny_proc = run_tiny_compiler_cli(args)
    assert tiny_proc.stdout == snapshot.stdout
    assert tiny_proc.stderr == snapshot.stderr
    assert tiny_proc.returncode == snapshot.returncode


def test_tiny_compiler_cli_parity_snapshots(tmp_path: pathlib.Path) -> None:
    for snapshot in SNAPSHOTS:
        assert_compiler_snapshot(snapshot, tmp_path)
