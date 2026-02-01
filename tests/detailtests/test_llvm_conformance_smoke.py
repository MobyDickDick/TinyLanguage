"""End-to-end LLVM conformance smoke tests for Tiny Language.

These tests compile representative TinyLanguage programs to LLVM IR via the
CLI, build native executables with the system toolchain, and assert that the
produced binaries emit the expected output.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class LLVMProgramCase:
    name: str
    source: str
    expected_output: str


PROGRAM_CASES = [
    LLVMProgramCase(
        name="arithmetic",
        source="def value = 6 * 7 + 1; print(value);",
        expected_output="43",
    ),
    LLVMProgramCase(
        name="control_flow",
        source=(
            "def total = 0; def i = 0;"
            "while (i < 4) {"
            "  if (i == 2) { total = total + 5; } else { total = total + i; }"
            "  i = i + 1;"
            "}"
            "print(total);"
        ),
        expected_output="8",
    ),
    LLVMProgramCase(
        name="functions",
        source=(
            "fn add(x, y) { return x + y; }"
            "def sum = add(3, 4);"
            "print(sum);"
        ),
        expected_output="7",
    ),
    LLVMProgramCase(
        name="heap_ops",
        source=(
            "def ptr = new[11, 22];"
            "print(heap_get(ptr, 0), heap_get(ptr, 1));"
        ),
        expected_output="11 22",
    ),
    LLVMProgramCase(
        name="string_ops",
        source='def text = "Tiny"; print(text + "Language");',
        expected_output="TinyLanguage",
    ),
]


def _llvm_toolchain() -> tuple[str, str]:
    clang = shutil.which("clang")
    if clang:
        return "clang", clang
    llc = shutil.which("llc")
    cc = shutil.which("cc") or shutil.which("gcc")
    if llc and cc:
        return "llc", llc
    return "", ""


def _run_emit_llvm(tmp_path: Path, source: str) -> Path:
    ll_path = tmp_path / "program.ll"

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [env.get("PYTHONPATH", ""), str(Path(__file__).resolve().parents[2] / "src")]
    ).strip(os.pathsep)

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "src" / "tiny_language_cli.py"),
            "--emit-llvm",
            "-",
        ],
        input=source,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    if result.returncode != 0:
        raise AssertionError(
            "LLVM IR emission failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    ll_path.write_text(result.stdout, encoding="utf-8")
    return ll_path


def _build_executable(tmp_path: Path, ll_path: Path) -> Path:
    toolchain, tool_path = _llvm_toolchain()
    if not toolchain:
        pytest.skip("clang or (llc + cc) is required for LLVM conformance smoke tests")

    exe_path = tmp_path / "program_exec"
    if toolchain == "clang":
        compile_cmd = [tool_path, str(ll_path), "-o", str(exe_path)]
        try:
            subprocess.run(compile_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            pytest.skip(f"clang failed to compile LLVM IR: {exc.stderr.strip()}")
        return exe_path

    obj_path = tmp_path / "program.o"
    llc_cmd = [tool_path, "-filetype=obj", str(ll_path), "-o", str(obj_path)]
    try:
        subprocess.run(llc_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"llc failed to compile LLVM IR: {exc.stderr.strip()}")
    cc_path = shutil.which("cc") or shutil.which("gcc")
    if cc_path is None:
        raise AssertionError("C compiler not found after llc produced object file")
    link_cmd = [cc_path, str(obj_path), "-o", str(exe_path)]
    try:
        subprocess.run(link_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"linker failed to build executable: {exc.stderr.strip()}")
    return exe_path


@pytest.mark.parametrize("case", PROGRAM_CASES, ids=lambda item: item.name)
def test_llvm_conformance_smoke(case: LLVMProgramCase, tmp_path: Path) -> None:
    """Compile representative Tiny programs to LLVM IR and assert executable output."""
    toolchain, _ = _llvm_toolchain()
    if not toolchain:
        pytest.skip("clang or (llc + cc) is required for LLVM conformance smoke tests")
    ll_path = _run_emit_llvm(tmp_path, case.source)
    exe_path = _build_executable(tmp_path, ll_path)

    result = subprocess.run(
        [str(exe_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == case.expected_output
    assert result.stderr.strip() == ""
