"""Acceptance for independent runtime modules and the compatible public facade."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from tools.release.verify_python_package import verify_immutable_imports


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("first", [
    "tiny_language_parser", "tiny_language_linter", "tiny_language_runtime",
    "tiny_language_eval", "tiny_language_codegen_py", "tiny_language_codegen_native",
    "tiny_language_codegen_c", "tiny_language_codegen_llvm", "tiny_language_api",
])
def test_fresh_imports_have_one_ast_and_runtime(first, tmp_path):
    """Import order must neither patch classes nor require the facade to run."""
    source = r'''
import importlib, sys
sys.path.insert(0, sys.argv[1])
importlib.import_module(sys.argv[2])
assert 'tiny_language' not in sys.modules
from tiny_language_parser import Parser
from tiny_language_lexer import Lexer
from tiny_language_runtime import Runtime, ReturnSignal
from tiny_language_runtime_environment import Environment
from tiny_language_ast import Fn
from tiny_language_codegen_native import NativeCodeGenerator
from tiny_language_codegen_py import PythonCodeGenerator
from tiny_language_eval import eval_stmt
program = 'fn twice(n) { return n * 2; } print(twice(21));'
statements = Parser(Lexer(program), program).parse()
assert type(statements[0]) is Fn
runtime = Runtime(program)
runtime.stream_output = False
runtime.eval_block(statements, Environment(parent=None, runtime=runtime))
assert ''.join(runtime.output).strip() == '42'
assert Runtime.eval_stmt is eval_stmt
NativeCodeGenerator().compile_program(statements)
PythonCodeGenerator().module_for_program(statements)
assert 'tiny_language' not in sys.modules
import tiny_language as facade
import tiny_language_api as api
assert facade.Runtime is Runtime
assert facade.Fn is Fn
assert facade.ReturnSignal is ReturnSignal
assert facade.compile_and_run is api.compile_and_run
assert facade._parse_and_lint is api._parse_and_lint
assert facade.compile_and_run(program, stream_output=False).strip() == '42'
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-c", source, str(ROOT / "src"), first],
                            cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_concurrent_imports_cannot_write_installation(tmp_path):
    """OS permissions deny rewriting sources and creating files in an installed layout."""
    installed = tmp_path / "installation"
    installed.mkdir()
    for path in (ROOT / "src").glob("*.py"):
        shutil.copyfile(path, installed / path.name)
    shutil.copytree(ROOT / "src/stdlib", installed / "stdlib",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for path in (ROOT / "stdlib").glob("*.tiny"):
        shutil.copyfile(path, installed / "stdlib" / path.name)
    report = verify_immutable_imports(Path(sys.executable), installed, tmp_path, dict(os.environ))
    assert len(report["processes"]) == 4
    assert all(result["os_write_denied"] for result in report["processes"])
    assert not (installed / "__pycache__").exists()


def test_read_only_acceptance_rejects_unrelated_directory(tmp_path):
    """Permission changes must stay inside the disposable installation workspace."""
    with pytest.raises(ValueError, match="disposable workspace"):
        verify_immutable_imports(Path(sys.executable), ROOT / "src", tmp_path, {})
