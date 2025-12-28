import os
import pathlib
import shutil
import subprocess
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
FIXTURES_ROOT = pathlib.Path(__file__).resolve().parent / "fixtures"


def _find_clang() -> str | None:
    return shutil.which("clang")


def _run_compiler_cli(command):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
        ),
    }
    return subprocess.run(
        [sys.executable, "src/tiny_language_compiler_cli.py", *command],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def test_emit_llvm_bitcode_creates_artifact(tmp_path: pathlib.Path) -> None:
    compiler = _find_clang()
    if compiler is None:
        pytest.skip("clang not available for LLVM bitcode emission")

    program_path = FIXTURES_ROOT / "hello_world.tiny"
    output_path = tmp_path / "hello.bc"

    result = _run_compiler_cli(
        [str(program_path), "--emit-bc", str(output_path), "--compiler", compiler]
    )

    assert result.returncode == 0
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_emit_c_accepts_debug_flag() -> None:
    program_path = FIXTURES_ROOT / "hello_world.tiny"

    result = _run_compiler_cli([str(program_path), "--emit-c", "--debug"])

    assert result.returncode == 0
    assert "int main" in result.stdout
