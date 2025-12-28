import os
import subprocess
import sys
from pathlib import Path

import pytest

from native_ir import Instruction, Opcode, ProgramIR
from tiny_language import compile_to_llvm_ir
from tiny_language_codegen_llvm import LLVMCodeGenerator


def test_compile_to_llvm_ir_emits_arithmetic_ir() -> None:
    source = "define a = 1 + 2; print(a);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "define i32 @tiny_main()" in llvm_ir
    assert "add i64" in llvm_ir
    assert "store i64 3" not in llvm_ir  # arithmetic should happen in SSA temps
    assert "@.fmt_i64" in llvm_ir


def test_compile_to_llvm_ir_includes_target_metadata() -> None:
    source = "define a = 1; print(a);"

    llvm_ir = compile_to_llvm_ir(
        source,
        target_triple="x86_64-unknown-linux-gnu",
        data_layout="e-m:e-i64:64-f80:128-n8:16:32:64-S128",
    )

    lines = llvm_ir.splitlines()
    assert lines[0] == 'target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"'
    assert lines[1] == 'target triple = "x86_64-unknown-linux-gnu"'


def test_cli_emits_llvm_ir(tmp_path) -> None:
    source = "define value = 5 * 2; print(value);"
    script = tmp_path / "program.tiny"
    script.write_text(source, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [env.get("PYTHONPATH", ""), str(Path(__file__).resolve().parents[2] / "src")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [sys.executable, "-m", "tiny_language_cli", "--file", str(script), "--emit-llvm"],
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
    source = "print(1); print(2.0);"

    llvm_ir = compile_to_llvm_ir(source)

    assert '@.fmt_i64 = private unnamed_addr constant [5 x i8] c"%ld\\0A\\00"' in llvm_ir
    assert '@.fmt_double = private unnamed_addr constant [5 x i8] c"%lf\\0A\\00"' in llvm_ir
    assert "getelementptr inbounds [5 x i8], [5 x i8]* @.fmt_i64" in llvm_ir
    assert "getelementptr inbounds [5 x i8], [5 x i8]* @.fmt_double" in llvm_ir


def test_llvm_codegen_supports_function_calls() -> None:
    source = "fn add(x, y) { return x + y; } print(add(2, 3));"

    llvm_ir = compile_to_llvm_ir(source)

    assert "define i64 @add(i64 %x.arg, i64 %y.arg)" in llvm_ir
    assert "call i64 @add(i64 2, i64 3)" in llvm_ir


def test_pop_is_ignored_in_llvm_codegen() -> None:
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

    assert "call i32 (i8*, ...) @printf" in ir
    assert "i64 2" in ir
    assert "i64 1" not in ir  # popped value should not reach the output


def test_llvm_codegen_handles_modulo_operation() -> None:
    source = "define value = 5 % 2; print(value);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "srem i64" in llvm_ir
    assert "@.fmt_i64" in llvm_ir


def test_llvm_codegen_handles_float_modulo_operation() -> None:
    source = "define value = 5.0 % 2.0; print(value);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "frem double" in llvm_ir
    assert "@.fmt_double" in llvm_ir


def test_llvm_codegen_emits_integer_and_float_comparisons() -> None:
    source = "define a = 3 > 1; define b = 2.0 <= 4.0; print(a, b);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "icmp sgt i64" in llvm_ir
    assert "fcmp ole double" in llvm_ir
    # bool prints are widened to i64 in the printf call
    assert "zext i1" in llvm_ir


def test_cli_emits_llvm_ir_for_comparisons(tmp_path) -> None:
    source = "define a = 2 == 2; define b = 1.5 != 3.0; print(a, b);"
    script = tmp_path / "program.tiny"
    script.write_text(source, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [env.get("PYTHONPATH", ""), str(Path(__file__).resolve().parents[2] / "src")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [sys.executable, "-m", "tiny_language_cli", "--file", str(script), "--emit-llvm"],
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
    source = "define a = 9 % 4; define b = 7.5 % 2.5; print(a, b);"
    script = tmp_path / "program.tiny"
    script.write_text(source, encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [env.get("PYTHONPATH", ""), str(Path(__file__).resolve().parents[2] / "src")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [sys.executable, "-m", "tiny_language_cli", "--file", str(script), "--emit-llvm"],
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
    source = "print(1); flush(); print(2);"

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i32 @fflush(i8* null)" in llvm_ir
    assert llvm_ir.count("call i32 (i8*, ...) @printf") == 2


def test_llvm_codegen_handles_if_and_while_control_flow() -> None:
    source = """
define i = 0;
while (i < 2) {
    i = i + 1;
}
if (i == 2) {
    print(i);
}
"""

    llvm_ir = compile_to_llvm_ir(source)

    assert llvm_ir.count("br i1") == 2
    assert "block" in llvm_ir


def test_llvm_codegen_emits_string_prints() -> None:
    source = 'print("hello");'

    llvm_ir = compile_to_llvm_ir(source)

    assert '@.str0 = private unnamed_addr constant [6 x i8] c"hello\\00"' in llvm_ir
    assert "@.fmt_str" in llvm_ir
    assert "call i32 (i8*, ...) @printf" in llvm_ir


def test_llvm_codegen_emits_heap_calls() -> None:
    source = "define ptr = new(1); heap_set(ptr, 0, 42); print(heap_get(ptr, 0));"

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @new(i64 1)" in llvm_ir
    assert "call i64 @heap_set(i64" in llvm_ir
    assert "call i64 @heap_get(i64" in llvm_ir


def test_llvm_codegen_emits_heap_string_helpers() -> None:
    source = 'define ptr = new(1); heap_set(ptr, 0, "hello"); print(heap_get(ptr, 0));'

    llvm_ir = compile_to_llvm_ir(source)

    assert "call i64 @heap_set_str(i64" in llvm_ir
    assert "call i8* @heap_get_str(i64" in llvm_ir


def test_llvm_codegen_emits_branches_for_jump_ops() -> None:
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
