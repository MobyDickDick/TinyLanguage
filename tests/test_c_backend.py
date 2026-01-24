"""Tests for c backend."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tiny_language import compile_to_c_executable, compile_to_llvm_ir_via_c


def _find_compiler() -> str | None:
    """Helper to find compiler."""
    preferred = os.environ.get("TINYLANG_C_COMPILER")
    candidates = [preferred, "cc", "clang", "gcc"]
    for candidate in candidates:
        if not candidate:
            continue
        if shutil.which(candidate):
            return candidate
    return None


def _find_clang() -> str | None:
    """Helper to find clang."""
    candidates = ["clang"]
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    return None


@pytest.mark.parametrize(
    "source_path,expected",
    [
        (Path("examples/c_backend/hello_world.tiny"), "Hello World\n"),
        (Path("examples/c_backend/function_return.tiny"), "5\n"),
    ],
)
def test_c_backend_examples(tmp_path: Path, source_path: Path, expected: str) -> None:
    """Test that c backend examples."""
    compiler = _find_compiler()
    if compiler is None:
        pytest.skip("no C compiler available for C backend tests")

    output_path = tmp_path / "tiny_program"
    source = source_path.read_text(encoding="utf-8")
    compile_to_c_executable(source, output_path, compiler=compiler)

    result = subprocess.check_output([str(output_path)], text=True)
    assert result == expected


def test_emit_llvm_ir_via_c() -> None:
    """Test that emit llvm ir via c."""
    compiler = _find_clang()
    if compiler is None:
        pytest.skip("clang not available for LLVM IR emission")

    source = "print(1 + 2);"
    llvm_ir = compile_to_llvm_ir_via_c(source, compiler=compiler)

    assert "define" in llvm_ir


def test_emit_llvm_ir_via_c_cli(tmp_path: Path) -> None:
    """Test that emit llvm ir via c cli."""
    compiler = _find_clang()
    if compiler is None:
        pytest.skip("clang not available for LLVM IR emission")

    source_path = tmp_path / "sample.tiny"
    source_path.write_text("print(1 + 2);", encoding="utf-8")
    out_path = tmp_path / "sample.ll"
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [src_path, env.get("PYTHONPATH")]))

    subprocess.check_call(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "src" / "tiny_language_compiler_cli.py"),
            str(source_path),
            "--emit-llvm",
            str(out_path),
            "--compiler",
            compiler,
        ],
        env=env,
    )

    assert out_path.exists()
    assert "def" in out_path.read_text(encoding="utf-8")
