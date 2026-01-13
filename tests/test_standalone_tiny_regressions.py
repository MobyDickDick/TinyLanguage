from __future__ import annotations

from pathlib import Path

import pytest

from tiny_language import Lexer, Parser, Runtime, compile_and_run

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_ROOT = PROJECT_ROOT / "examples" / "rosetta"
STR_TINY = PROJECT_ROOT / "str_tiny"
SRC_ROOT = PROJECT_ROOT / "src"

STANDALONE_DEMOS = [
    STR_TINY / "returned_params_demo.tiny",
    SRC_ROOT / "sum_product_match.tiny",
]

ROSETTA_DEMOS = sorted(EXAMPLES_ROOT.glob("*/*.tiny"))

RUN_ROSETTA_DEMOS = [
    demo
    for demo in ROSETTA_DEMOS
    if demo.name not in {"fizzbuzz.tiny"}
]

PARSE_ONLY_ROSETTA_DEMOS = [
    demo
    for demo in ROSETTA_DEMOS
    if demo.name in {"fizzbuzz.tiny"}
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


@pytest.mark.parametrize("demo_path", STANDALONE_DEMOS)
def test_standalone_demo_smoke(demo_path: Path) -> None:
    assert demo_path.exists()
    _run_demo(demo_path)


@pytest.mark.parametrize("demo_path", RUN_ROSETTA_DEMOS)
def test_rosetta_demo_smoke(demo_path: Path) -> None:
    assert demo_path.exists()
    _run_demo(demo_path)


@pytest.mark.parametrize("demo_path", PARSE_ONLY_ROSETTA_DEMOS)
def test_rosetta_demo_parses(demo_path: Path) -> None:
    assert demo_path.exists()
    _parse_demo(demo_path)
