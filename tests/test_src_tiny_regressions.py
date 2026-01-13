from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tiny_language import Lexer, Parser, Runtime, compile_and_run

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_TINY = PROJECT_ROOT / "src_tiny"

SIMPLE_DEMOS = [
    "stdlib_collections_demo.tiny",
    "tiny_language_eval.tiny",
    "factorial.tiny",
    "native_python_bytecode.tiny",
    "python_namespace_typed_demo.tiny",
    "Simpelst_Tiny_Language_Programm.tiny",
    "tiny_language_preamble.tiny",
    "tiny_language.tiny",
    "try_catch_demo.tiny",
    "tiny_language_codegen_c.tiny",
    "test_flush.tiny",
    "tiny_language_codegen_py.tiny",
    "rosetta_fizzbuzz.tiny",
    "tiny_language_codegen_llvm.tiny",
    "rosetta_word_count.tiny",
    "formatter.tiny",
    "tiny_language_api.tiny",
    "match_demo.tiny",
    "fizzbuzz.tiny",
    "tiny_language_runtime.tiny",
    "rosetta_factorial.tiny",
    "result_demo.tiny",
    "tiny_errors.tiny",
    "tiny_language_highlighting.tiny",
]

ADDITIONAL_RUN_DEMOS = [
    "fibonacci.tiny",
    "hello_world.tiny",
    "python_fn_demo.tiny",
    "python_json_demo.tiny",
    "python_math_demo.tiny",
    "python_proxy_pipeline_demo.tiny",
]

ADDITIONAL_PARSE_DEMOS = [
    "language_server_cli.tiny",
    "native_ir.tiny",
    "native_vm.tiny",
    "tiny_lang_cli.tiny",
    "tiny_language_ast.tiny",
    "tiny_language_cli.tiny",
    "tiny_language_codegen_native.tiny",
    "tiny_language_lexer.tiny",
    "tiny_language_linter.tiny",
    "tiny_language_parser.tiny",
    "tiny_language_transpilers.tiny",
]


def _run_demo(path: Path, *, runtime: Runtime | None = None) -> str:
    source = path.read_text(encoding="utf-8")
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(Path.cwd())
        namespace = ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001
        namespace = resolved.stem
    runtime = runtime or Runtime(source)
    return compile_and_run(
        source,
        runtime=runtime,
        module_namespace=namespace,
        module_path=resolved,
        stream_output=False,
        repl_mode=True,
    )

def _parse_demo(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    Parser(Lexer(source), source).parse()


@pytest.mark.parametrize("demo_name", SIMPLE_DEMOS)
def test_src_tiny_demo_smoke(demo_name: str) -> None:
    demo_path = SRC_TINY / demo_name
    assert demo_path.exists()
    _run_demo(demo_path)

@pytest.mark.parametrize("demo_name", ADDITIONAL_RUN_DEMOS)
def test_src_tiny_additional_demo_smoke(demo_name: str) -> None:
    demo_path = SRC_TINY / demo_name
    assert demo_path.exists()
    _run_demo(demo_path)


@pytest.mark.parametrize("demo_name", ADDITIONAL_PARSE_DEMOS)
def test_src_tiny_additional_demo_parses(demo_name: str) -> None:
    demo_path = SRC_TINY / demo_name
    assert demo_path.exists()
    _parse_demo(demo_path)


def test_console_sum_demo_handles_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    out = _run_demo(SRC_TINY / "console_sum.tiny")
    assert "Summe:" in out


def test_stdlib_io_random_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tmp").mkdir()
    monkeypatch.chdir(tmp_path)
    out = _run_demo(SRC_TINY / "stdlib_io_random_demo.tiny")
    assert "true" in out


def test_simpelst_python_program_parses() -> None:
    source = (SRC_TINY / "simpelst_Python_program.tiny").read_text(encoding="utf-8")
    Parser(Lexer(source), source).parse()


def test_transpile_rosetta_parses() -> None:
    source = (SRC_TINY / "transpile_rosetta.tiny").read_text(encoding="utf-8")
    Parser(Lexer(source), source).parse()


def test_language_server_parses() -> None:
    source = (SRC_TINY / "language_server.tiny").read_text(encoding="utf-8")
    Parser(Lexer(source), source).parse()


def test_copy_rosetta_samples_parses() -> None:
    source = (SRC_TINY / "copy_rosetta_samples.tiny").read_text(encoding="utf-8")
    Parser(Lexer(source), source).parse()


def test_compiler_cli_wrappers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = tmp_path / "sample.tiny"
    sample.write_text("print(1);\n", encoding="utf-8")
    monkeypatch.setenv("TINYLANG_ARGS", json.dumps([str(sample), "--emit-c"]))
    _run_demo(SRC_TINY / "tiny_language_compiler_cli.tiny")
    _run_demo(SRC_TINY / "tinyc_cli.tiny")


def test_run_all_tiny_wrapper() -> None:
    demo_path = SRC_TINY / "run_all.tiny"
    runtime = Runtime(demo_path.read_text(encoding="utf-8"))
    runtime.register_native("main", lambda: 0)
    _run_demo(demo_path, runtime=runtime)
