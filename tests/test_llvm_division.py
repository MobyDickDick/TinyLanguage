"""AUD-001: compile and execute true division against independent exact values."""

from fractions import Fraction
import json
import shutil
import subprocess

import pytest

from tiny_language import compile_to_executable, compile_to_llvm_ir
from tools.correctness_audit import assess, known_gap, worker
from tools.correctness_cases import arithmetic_case


@pytest.fixture
def compiler(request):
    path = shutil.which("clang")
    if path is None:
        if request.config.getoption("--require-backend-toolchains"):
            pytest.fail("AUD-001 acceptance requires clang; emission alone is insufficient")
        pytest.skip("clang is required for executable division checks")
    return path


def test_exact_arithmetic_audit_executes_all_160_observations(tmp_path, compiler):
    case = arithmetic_case()
    result_path = tmp_path / "result.json"
    worker(case, "llvm", compiler, tmp_path, result_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert assess(case, result) == "passed", result
    assert result["stages"] == {
        "frontend": "passed", "codegen": "passed", "compile": "passed", "execute": "passed",
    }
    assert len(result["stdout"].splitlines()) == 160


@pytest.mark.parametrize("source, expected", [
    ("print(7/2); print(-7/2); print(7/(0-2)); print(-7/(0-2));", ["7/2", "-7/2", "-7/2", "7/2"]),
    ("print(8/2); print(0/3); print(1/16);", ["4", "0", "1/16"]),
    ("print(-9223372036854775808/-1);", ["9223372036854775808"]),
    ("def q = 7/2; print(q+2); print(2+q); print(q*2); print(7/q/4);", ["11/2", "11/2", "7", "1/2"]),
    ("fn half(n) { return n/2; } print(half(-7)); print(half(7)+1);", ["-7/2", "9/2"]),
    ("fn ratio(a,b) { return a/b; } print(ratio(7,2)); print(ratio(-7,2));", ["7/2", "-7/2"]),
    ("fn shifted(n) { return n/2+1; } print(shifted(7));", ["9/2"]),
    ("fn above(n) { if (n/2 > 3) { return 9; } return 0; } print(above(7));", ["9"]),
    ("print(7.0/2); print(7/2.0); print(7.0/2.0);", ["7/2", "7/2", "7/2"]),
])
def test_quotients_survive_storage_calls_and_numeric_use(source, expected, tmp_path, compiler):
    # The corpus intentionally uses exactly representable dyadic quotients.
    executable = tmp_path / "division.exe"
    compile_to_executable(source, executable, compiler=compiler)
    result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert [Fraction(line) for line in result.stdout.splitlines()] == [Fraction(x) for x in expected]


@pytest.mark.parametrize("expression", ["1/0", "1.0/0.0", "1/-0.0", "1/(0-0)"])
def test_division_by_zero_exits_before_later_effects(expression, tmp_path, compiler):
    executable = tmp_path / "zero.exe"
    compile_to_executable(f'print({expression}); print("unreachable");', executable, compiler=compiler)
    result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert result.stdout == "division by zero\n"
    assert result.stderr == ""


def test_integer_division_promotes_to_double_but_other_integer_math_stays_integer():
    ir = compile_to_llvm_ir("print(-7/2); print(7+2); print(7*2);")
    assert "sitofp i64" in ir
    assert "fdiv double" in ir
    assert "sdiv" not in ir
    assert "add i64" in ir
    assert "mul i64" in ir


def test_historical_truncation_is_a_regression_not_an_allowed_gap():
    case = arithmetic_case()
    truncated = "".join(f"{int(Fraction(line))}\n" for line in case.expected.splitlines())
    record = dict(backend="llvm", exit_code=0, stdout=truncated, stderr="",
                  stages={name: "passed" for name in ("frontend", "codegen", "compile", "execute")})
    assert assess(case, record) == "failed"
    assert known_gap(case, "llvm", record) is None
