from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tiny_language import compile_to_c_executable, compile_to_llvm_ir_via_c


def _find_compiler() -> str | None:
    preferred = os.environ.get("TINYLANG_C_COMPILER")
    candidates = [preferred, "cc", "clang", "gcc"]
    for candidate in candidates:
        if not candidate:
            continue
        if shutil.which(candidate):
            return candidate
    return None


def _find_clang() -> str | None:
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
    compiler = _find_compiler()
    if compiler is None:
        pytest.skip("no C compiler available for C backend tests")

    output_path = tmp_path / "tiny_program"
    source = source_path.read_text(encoding="utf-8")
    compile_to_c_executable(source, output_path, compiler=compiler)

    result = subprocess.check_output([str(output_path)], text=True)
    assert result == expected


def test_emit_llvm_ir_via_c() -> None:
    compiler = _find_clang()
    if compiler is None:
        pytest.skip("clang not available for LLVM IR emission")

    source = "print(1 + 2);"
    llvm_ir = compile_to_llvm_ir_via_c(source, compiler=compiler)

    assert "define" in llvm_ir
