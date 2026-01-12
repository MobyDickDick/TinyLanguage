import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
SRC_TINY = PROJECT_ROOT / "src_tiny"

sys.path.append(str(SRC_ROOT))

from tiny_language import Lexer, Parser  # noqa: E402

PROGRAMS = [
    "stdlib_collections_demo.tiny",
    "tiny_language_compiler_cli.tiny",
    "tiny_language_eval.tiny",
    "factorial.tiny",
    "simpelst_Python_program.tiny",
    "native_python_bytecode.tiny",
    "python_namespace_typed_demo.tiny",
    "Simpelst_Tiny_Language_Programm.tiny",
    "tiny_language_preamble.tiny",
    "tiny_language.tiny",
    "try_catch_demo.tiny",
    "tiny_language_codegen_c.tiny",
    "test_flush.tiny",
    "copy_rosetta_samples.tiny",
    "tinyc_cli.tiny",
    "run_all.tiny",
    "tiny_language_codegen_py.tiny",
    "rosetta_fizzbuzz.tiny",
    "tiny_language_codegen_llvm.tiny",
    "transpile_rosetta.tiny",
    "rosetta_word_count.tiny",
    "formatter.tiny",
    "tiny_language_api.tiny",
    "match_demo.tiny",
    "fizzbuzz.tiny",
    "stdlib_io_random_demo.tiny",
    "tiny_language_runtime.tiny",
    "rosetta_factorial.tiny",
    "result_demo.tiny",
    "language_server.tiny",
    "console_sum.tiny",
    "tiny_errors.tiny",
    "tiny_language_highlighting.tiny",
]


@pytest.mark.parametrize("program", PROGRAMS)
def test_src_tiny_programs_parse(program):
    source = (SRC_TINY / program).read_text(encoding="utf-8")

    Parser(Lexer(source), source).parse()
