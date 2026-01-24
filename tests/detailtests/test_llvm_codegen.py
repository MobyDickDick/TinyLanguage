"""LLVM codegen regression tests for Tiny Language.

These tests focus on the LLVM IR output produced by the compiler and verify
that major language features lower into the expected IR constructs.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from native_ir import Instruction, Opcode, ProgramIR
from tiny_language import compile_to_llvm_ir
from tiny_language_codegen_llvm import LLVMCodeGenerator


def _tiny_main_body(llvm_ir: str) -> str:
    """Return the body of the generated tiny_main function for assertions."""
    lines = llvm_ir.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.startswith("define i32 @tiny_main()"):
            start = idx + 1
            break
    if start is None:
        raise AssertionError("tiny_main function not found in LLVM IR")
    for end in range(start, len(lines)):
        if lines[end] == "}":
            return "\n".join(lines[start:end])
    raise AssertionError("tiny_main function did not terminate as expected")


def test_compile_to_llvm_ir_emits_arithmetic_ir() -> None:
    """Arithmetic expressions should lower into SSA temporaries."""
    source = "def a = 1 + 2; print(a);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "define i32 @tiny_main()" in llvm_ir
    assert "add i64" in llvm_ir
    assert "store i64 3" not in llvm_ir  # arithmetic should happen in SSA temps
    assert "@.fmt_i64" in llvm_ir


def test_compile_to_llvm_ir_includes_target_metadata() -> None:
    """Target triple and data layout are preserved when provided."""
    source = "def a = 1; print(a);"

    llvm_ir = compile_to_llvm_ir(
        source,
        target_triple="x86_64-unknown-linux-gnu",
        data_layout="e-m:e-i64:64-f80:128-n8:16:32:64-S128",
    )

    lines = llvm_ir.splitlines()
    assert lines[0] == 'target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"'
    assert lines[1] == 'target triple = "x86_64-unknown-linux-gnu"'


def test_cli_emits_llvm_ir(tmp_path) -> None:
    """CLI --emit-llvm should output integer math operations."""
    source = "def value = 5 * 2; print(value);"
    script = tmp_path / "program.tiny"
    script.write_text(source, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [env.get("PYTHONPATH", ""), str(Path(__file__).resolve().parents[2] / "src")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "src" / "tiny_language_cli.py"),
            "--file",
            str(script),
            "--emit-llvm",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "fmul" not in result.stdout  # integer math should stay integer
    assert "mul i64" in result.stdout
    assert "@.fmt_i64" in result.stdout


def test_llvm_codegen_emits_full_format_string_lengths() -> None:
    """Printf format constants must include newline and null terminators."""
    source = "print(1); print(2.0);"

    llvm_ir = compile_to_llvm_ir(source)

    assert '@.fmt_i64 = private unnamed_addr constant [5 x i8] c"%ld\\0A\\00"' in llvm_ir
    assert '@.fmt_double = private unnamed_addr constant [5 x i8] c"%lf\\0A\\00"' in llvm_ir
    assert "getelementptr inbounds [5 x i8], [5 x i8]* @.fmt_i64" in llvm_ir
    assert "getelementptr inbounds [5 x i8], [5 x i8]* @.fmt_double" in llvm_ir


def test_llvm_codegen_supports_function_calls() -> None:
    """Function declarations and call sites should exist in the IR."""
    source = "fn add(x, y) { return x + y; } print(add(2, 3));"

    llvm_ir = compile_to_llvm_ir(source)

    assert "define i64 @add(i64 %x.arg, i64 %y.arg)" in llvm_ir
    assert "call i64 @add(i64 2, i64 3)" in llvm_ir


def test_llvm_codegen_supports_module_imports(tmp_path) -> None:
    """Imports emit init routines and qualified symbol names."""
    helper = tmp_path / "helper.tiny"
    helper.write_text("fn add(x, y) { return x + y; }", encoding="utf-8")
    main = tmp_path / "main.tiny"
    main.write_text("import helper; print(helper.add(1, 2));", encoding="utf-8")

    llvm_ir = compile_to_llvm_ir(main.read_text(encoding="utf-8"), module_path=main)
    main_ir = _tiny_main_body(llvm_ir)

    assert "define i64 @helper.add(i64 %x.arg, i64 %y.arg)" in llvm_ir
    assert "define i64 @helper.__init()" in llvm_ir
    assert "call i64 @helper.__init()" in main_ir
    assert "call i64 @helper.add(i64 1, i64 2)" in main_ir


def test_llvm_codegen_supports_python_interop() -> None:
    """Python interop should reference import/call runtime helpers."""
    source = """
def math = Python.import_module("math", new["sqrt"]);
def value = Python.call("math", "sqrt", new[9]);
def other = math.sqrt(16);
print(value);
print(other);
"""

    llvm_ir = compile_to_llvm_ir(source)
    main_ir = _tiny_main_body(llvm_ir)

    assert "declare i64 @__py_import_module(i8*, i64)" in llvm_ir
    assert "declare i64 @__py_call(i8*, i8*, i64, i64, i64)" in llvm_ir
    assert "call i64 @__py_import_module" in main_ir
    assert "call i64 @__py_call" in main_ir


def test_llvm_codegen_supports_spawn_and_join() -> None:
    """Async spawn/join should call the runtime helpers."""
    source = """
async fn add(x, y) { return x + y; }
def handle = spawn add(2, 3);
def result = await handle;
print(result);
"""

    llvm_ir = compile_to_llvm_ir(source)
    main_ir = _tiny_main_body(llvm_ir)

    assert "define i64 @__spawn_i64" in llvm_ir
    assert "define i64 @__join_i64" in llvm_ir
    assert "call i64 @__spawn_i64" in main_ir
    assert "call i64 @__join_i64" in main_ir


def test_llvm_codegen_supports_async_tokens() -> None:
    """Async token primitives should appear in the IR."""
    source = """
fn quick() { return 1; }

def token = Async.token();
def handle = spawn quick();
def linked = Async.link(token, handle);
def cancelled = Async.cancel(token, "stop");
print(Async.is_cancelled(token));
print(Async.reason(token));
print(linked, cancelled);
"""

    llvm_ir = compile_to_llvm_ir(source)
    main_ir = _tiny_main_body(llvm_ir)

    assert "define i64 @__async_token" in llvm_ir
    assert "define i1 @__async_cancel" in llvm_ir
    assert "define i1 @__async_is_cancelled" in llvm_ir
    assert "define i8* @__async_reason" in llvm_ir
    assert "define i1 @__async_link" in llvm_ir
    assert "call i64 @__async_token" in main_ir
    assert "call i1 @__async_cancel" in main_ir
    assert "call i1 @__async_is_cancelled" in main_ir
    assert "call i8* @__async_reason" in main_ir
    assert "call i1 @__async_link" in main_ir


def test_llvm_codegen_supports_class_methods() -> None:
    """Class method lowering should reference heap operations."""
    source = """
class Point {
  x: number;
  y: number;

  fn sum(self) {
    return self.x + self.y;
  }
}

def p = new Point { x: 1; y: 2; };
print(p.sum());
"""

    llvm_ir = compile_to_llvm_ir(source)
    main_ir = _tiny_main_body(llvm_ir)

    assert "define i64 @Point.sum" in llvm_ir
    assert "call i64 @__new(i64 3)" in main_ir
    assert "call i64 @Point.sum" in main_ir
    assert "call i64 @heap_get" in llvm_ir


def test_llvm_codegen_supports_field_get_and_set() -> None:
    """Field access should use heap get/set helpers."""
    source = """
class Point {
  x: number;
  y: number;
}

def p = new Point { x: 1; y: 2; };
p.x = 5;
print(p.x, p.y);
"""

    llvm_ir = compile_to_llvm_ir(source)
    main_ir = _tiny_main_body(llvm_ir)

    assert "call i64 @heap_set" in main_ir
    assert "call i64 @heap_get" in main_ir


def test_llvm_codegen_emits_operator_overload_calls() -> None:
    """Operator overloads should be emitted as explicit runtime calls."""
    source = """
operator + (a: number, b: number) -> number { return a - b; }
def total = 2 + 3;
print(total);
"""

    llvm_ir = compile_to_llvm_ir(source)
    main_ir = _tiny_main_body(llvm_ir)

    assert "call i64 @__op_+_number_number" in main_ir


def test_pop_is_ignored_in_llvm_codegen() -> None:
    """POP instructions should not leak into the final IR."""
    program = ProgramIR(
        entry=[
            Instruction(Opcode.PUSH_CONST, 1),
            Instruction(Opcode.POP),
            Instruction(Opcode.PUSH_CONST, 2),
            Instruction(Opcode.PRINT, 1),
        ],
        functions={},
    )

    ir = LLVMCodeGenerator().compile_program(program)
    main_ir = _tiny_main_body(ir)

    assert "call i32 (i8*, ...) @printf" in main_ir
    assert "i64 2" in main_ir
    assert "i64 1" not in main_ir  # popped value should not reach the output


def test_llvm_codegen_handles_modulo_operation() -> None:
    """Modulo should use signed remainder for integers."""
    source = "def value = 5 % 2; print(value);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "srem i64" in llvm_ir
    assert "@.fmt_i64" in llvm_ir


def test_llvm_codegen_handles_float_modulo_operation() -> None:
    """Modulo should use floating remainder for doubles."""
    source = "def value = 5.0 % 2.0; print(value);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "frem double" in llvm_ir
    assert "@.fmt_double" in llvm_ir


def test_llvm_codegen_emits_integer_and_float_comparisons() -> None:
    """Comparisons should use appropriate integer and float predicates."""
    source = "def a = 3 > 1; def b = 2.0 <= 4.0; print(a, b);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "icmp sgt i64" in llvm_ir
    assert "fcmp ole double" in llvm_ir
    # bool prints are widened to i64 in the printf call
    assert "zext i1" in llvm_ir


def test_cli_emits_llvm_ir_for_comparisons(tmp_path) -> None:
    """CLI output should include comparison predicates for mixed types."""
    source = "def a = 2 == 2; def b = 1.5 != 3.0; print(a, b);"
    script = tmp_path / "program.tiny"
    script.write_text(source, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [env.get("PYTHONPATH", ""), str(Path(__file__).resolve().parents[2] / "src")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "src" / "tiny_language_cli.py"),
            "--file",
            str(script),
            "--emit-llvm",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "icmp eq i64" in result.stdout
    assert "fcmp one double" in result.stdout
    assert "@.fmt_i64" in result.stdout


def test_cli_emits_llvm_ir_for_modulo(tmp_path) -> None:
    """CLI output should include integer and float modulo helpers."""
    source = "def a = 9 % 4; def b = 7.5 % 2.5; print(a, b);"
    script = tmp_path / "program.tiny"
    script.write_text(source, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [env.get("PYTHONPATH", ""), str(Path(__file__).resolve().parents[2] / "src")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "src" / "tiny_language_cli.py"),
            "--file",
            str(script),
            "--emit-llvm",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "srem i64" in result.stdout
    assert "frem double" in result.stdout
    assert "@.fmt_i64" in result.stdout
    assert "@.fmt_double" in result.stdout


def test_llvm_codegen_emits_flush_calls() -> None:
    """Flush should lower to fflush(NULL) between print calls."""
    source = "print(1); def _unused19 = flush(); print(2);"

    llvm_ir = compile_to_llvm_ir(source)
    main_ir = _tiny_main_body(llvm_ir)

    assert "call i32 @fflush(i8* null)" in main_ir
    assert main_ir.count("call i32 (i8*, ...) @printf") == 2


def test_llvm_codegen_handles_if_and_while_control_flow() -> None:
    """Loops and conditionals should produce branch instructions."""
    source = """
def i = 0;
while (i < 2) {
    i = i + 1;
}
if (i == 2) {
    print(i);
}
"""

    llvm_ir = compile_to_llvm_ir(source)
    main_ir = _tiny_main_body(llvm_ir)

    assert main_ir.count("br i1") == 2
    assert "block" in main_ir


def test_llvm_codegen_emits_string_prints() -> None:
    """String literals should be emitted as global constants."""
    source = 'print("hello");'

    llvm_ir = compile_to_llvm_ir(source)

    assert '@.str0 = private unnamed_addr constant [6 x i8] c"hello\\00"' in llvm_ir
    assert "@.fmt_str" in llvm_ir
    assert "call i32 (i8*, ...) @printf" in llvm_ir


def test_llvm_codegen_supports_non_numeric_variables() -> None:
    """Non-numeric locals should get appropriate stack allocations."""
    source = 'def greeting = "hi"; def ok = true; print(greeting, ok);'

    llvm_ir = compile_to_llvm_ir(source)

    assert '@.str0 = private unnamed_addr constant [3 x i8] c"hi\\00"' in llvm_ir
    assert "alloca i8*" in llvm_ir
    assert "alloca i1" in llvm_ir
    assert "store i8*" in llvm_ir
    assert "store i1 1" in llvm_ir
    assert "zext i1" in llvm_ir


def test_llvm_codegen_supports_null_literal_prints() -> None:
    """Null literals should route through the string formatting path."""
    source = "print(Null);"

    llvm_ir = compile_to_llvm_ir(source)

    assert 'c"Null\\00"' in llvm_ir
    assert "icmp eq i8* null, null" in llvm_ir
    assert "@.fmt_str" in llvm_ir


def test_llvm_codegen_emits_heap_calls() -> None:
    """Heap helper calls should be present for raw heap usage."""
    source = "def ptr = new(1); def ignored1 = heap_set(ptr, 0, 42); print(heap_get(ptr, 0));"

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @new(i64 1)" in llvm_ir
    assert "call i64 @heap_set(i64" in llvm_ir
    assert "call i64 @heap_get(i64" in llvm_ir


def test_llvm_codegen_emits_heap_string_helpers() -> None:
    """Heap string helpers should be generated for string accessors."""
    source = 'def ptr = new(1); def ignored1 = heap_set(ptr, 0, "hello"); print(heap_get(ptr, 0));'

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @heap_set_str(i64" in llvm_ir
    assert "call i8* @heap_get_str(i64" in llvm_ir


def test_llvm_codegen_emits_array_literal_heap_helpers() -> None:
    """Array literals should use __new and heap_set_str helpers."""
    source = 'def ptr = new["hello", "world"]; print(heap_get(ptr, 1));'

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @__new(i64 2)" in llvm_ir
    assert "call i64 @heap_set_str(i64" in llvm_ir
    assert "call i8* @heap_get_str(i64" in llvm_ir


def test_llvm_codegen_emits_typed_heap_helpers() -> None:
    """Typed heap helpers should appear for double/bool fields."""
    source = """
def ptr = new(2);
def ignored34 = heap_set(ptr, 0, 1.5);
def ignored35 = heap_set(ptr, 1, true);
print(heap_get(ptr, 0), heap_get(ptr, 1));
"""

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @heap_set_double(i64" in llvm_ir
    assert "call i64 @heap_set_bool(i64" in llvm_ir
    assert "call double @heap_get_double(i64" in llvm_ir
    assert "call i1 @heap_get_bool(i64" in llvm_ir


def test_llvm_codegen_defines_heap_runtime_helpers() -> None:
    """Runtime helpers should be defined alongside the emitted IR."""
    source = "def ptr = new(1); def ignored1 = heap_set(ptr, 0, 1); print(heap_get(ptr, 0));"

    llvm_ir = compile_to_llvm_ir(source)

    assert "define i64 @__new(i64 %size)" in llvm_ir
    assert "define i64 @heap_get(i64 %ptr, i64 %idx)" in llvm_ir
    assert "define i64 @heap_set(i64 %ptr, i64 %idx, i64 %value)" in llvm_ir
    assert "define i8* @heap_get_str(i64 %ptr, i64 %idx)" in llvm_ir
    assert "define double @heap_get_double(i64 %ptr, i64 %idx)" in llvm_ir
    assert "define i1 @heap_get_bool(i64 %ptr, i64 %idx)" in llvm_ir
    assert "define i64 @heap_set_str(i64 %ptr, i64 %idx, i8* %value)" in llvm_ir
    assert "define i64 @heap_set_double(i64 %ptr, i64 %idx, double %value)" in llvm_ir
    assert "define i64 @heap_set_bool(i64 %ptr, i64 %idx, i1 %value)" in llvm_ir
    assert "define i64 @delete(i64 %ptr)" in llvm_ir


def test_llvm_codegen_emits_collection_helpers() -> None:
    """Collection stdlib helpers should be referenced in the IR."""
    source = """
def m = Map.new();
def _unused26 = Map.set(m, 1, 2);
print(Map.get(m, 1, 0));

def s = Set.new();
print(Set.add(s, 5));

def q = Deque.new();
def _p = Deque.push_right(q, 9);
print(Deque.pop_left(q));
"""

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @__map_new()" in llvm_ir
    assert "call i64 @__map_set" in llvm_ir
    assert "call i64 @__map_get" in llvm_ir
    assert "call i64 @__set_new()" in llvm_ir
    assert "call i1 @__set_add" in llvm_ir
    assert "call i64 @__deque_new()" in llvm_ir
    assert "call i64 @__deque_push_right" in llvm_ir
    assert "call i64 @__deque_pop_left" in llvm_ir


def test_llvm_codegen_emits_collection_accessors() -> None:
    """Collection accessors should lower to helper calls."""
    source = """
def m = Map.new();
def _unused0 = Map.set(m, 1, 2);
def _unused1 = Map.keys(m);
def _unused2 = Map.values(m);
def _unused3 = Map.entries(m);

def s = Set.new();
def _unused4 = Set.to_list(s);

def q = Deque.new();
def _unused5 = Deque.push_left(q, 7);
def _unused6 = Deque.peek_left(q);
def _unused7 = Deque.peek_right(q);
def _unused8 = Deque.pop_right(q);
"""

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @__map_keys" in llvm_ir
    assert "call i64 @__map_values" in llvm_ir
    assert "call i64 @__map_entries" in llvm_ir
    assert "call i64 @__set_to_list" in llvm_ir
    assert "call i64 @__deque_peek_left" in llvm_ir
    assert "call i64 @__deque_peek_right" in llvm_ir
    assert "call i64 @__deque_pop_right" in llvm_ir


def test_llvm_codegen_emits_heap_bounds_checks() -> None:
    """Heap bounds checks should include error helper and pointer math."""
    source = "def ptr = new(2); def ignored1 = heap_set(ptr, 1, 1); print(heap_get(ptr, 1));"

    llvm_ir = compile_to_llvm_ir(source)

    assert "define i64 @__heap_bounds_error(i64 %idx, i64 %ptr, i64 %size)" in llvm_ir
    assert "add i64 %size, 1" in llvm_ir
    assert "getelementptr i64, i64* %data, i64 -1" in llvm_ir


def test_llvm_codegen_emits_branches_for_jump_ops() -> None:
    """Jump opcodes should map to labeled branches."""
    program = ProgramIR(
        entry=[
            Instruction(Opcode.PUSH_CONST, 0),
            Instruction(Opcode.JUMP_IF_FALSE, 4),
            Instruction(Opcode.PUSH_CONST, 1),
            Instruction(Opcode.PRINT, 1),
            Instruction(Opcode.PUSH_CONST, 2),
            Instruction(Opcode.PRINT, 1),
            Instruction(Opcode.RETURN),
        ],
        functions={},
    )

    llvm_ir = LLVMCodeGenerator().compile_program(program)

    assert "icmp ne i64" in llvm_ir
    assert "br i1" in llvm_ir
    assert "block0:" in llvm_ir
    assert "block2:" in llvm_ir
    assert "block4:" in llvm_ir


def test_llvm_codegen_reports_missing_lowering_with_context() -> None:
    """Missing lowerings should raise with helpful context."""
    program = ProgramIR(
        entry=[
            Instruction(Opcode.PUSH_CONST, 1),
            Instruction(Opcode.PUSH_CONST, 2),
            Instruction(Opcode.BINARY, "**"),
            Instruction(Opcode.PRINT, 1),
        ],
        functions={},
    )

    with pytest.raises(
        NotImplementedError,
        match=r"LLVM prototype missing lowering: operator \*\* not supported "
        r"\(instruction: BINARY '\*\*'\)",
    ):
        LLVMCodeGenerator().compile_program(program)


def test_llvm_codegen_reports_mixed_type_arithmetic_with_context() -> None:
    """Mixed-type arithmetic should raise with type details."""
    program = ProgramIR(
        entry=[
            Instruction(Opcode.PUSH_CONST, 1),
            Instruction(Opcode.PUSH_CONST, 1.5),
            Instruction(Opcode.BINARY, "+"),
            Instruction(Opcode.PRINT, 1),
        ],
        functions={},
    )

    with pytest.raises(
        NotImplementedError,
        match=r"LLVM prototype missing lowering: mixed-type arithmetic not supported "
        r"\(i64 vs double\) \(instruction: BINARY '\+'\)",
    ):
        LLVMCodeGenerator().compile_program(program)


def test_llvm_codegen_supports_match_and_variants() -> None:
    """Match expressions and variants should emit heap lookups."""
    source = """
type Shape {
  Circle { radius: number };
  Rectangle { width: number, height: number };
}

fn area(shape) {
  return match shape {
    case Circle { radius: r }: r;
    case Rectangle { width: w, height: h }: w + h;
  };
}

def c = Circle { radius: 2 };
print(area(c));
"""

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @__new(i64 2)" in llvm_ir
    assert "call i64 @heap_set_str" in llvm_ir
    assert "call i8* @heap_get_str" in llvm_ir
    assert "icmp eq i8*" in llvm_ir
