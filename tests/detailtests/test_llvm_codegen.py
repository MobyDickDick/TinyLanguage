import os
import subprocess
import sys
from pathlib import Path

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
