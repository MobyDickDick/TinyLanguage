from pathlib import Path

from tiny_language_transpilers import PythonTranspiler, TinyLanguageTranspiler


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "examples" / "rosetta" / "python"
EXPECTED_DIR = ROOT / "examples" / "rosetta" / "expected"


def translate_python_to_tiny(path: Path) -> str:
    program_ir = PythonTranspiler().from_source(path.read_text())
    return TinyLanguageTranspiler().to_source(program_ir)


def assert_snapshot(name: str) -> None:
    python_path = PYTHON_DIR / f"{name}.py"
    expected_path = EXPECTED_DIR / f"{name}.tiny"
    assert python_path.exists(), f"Missing Python sample: {python_path}"  # pragma: no cover - guardrail
    assert expected_path.exists(), f"Missing snapshot: {expected_path}"  # pragma: no cover - guardrail

    generated = translate_python_to_tiny(python_path).strip()
    expected = expected_path.read_text().strip()
    assert generated == expected


def test_fizzbuzz_snapshot():
    assert_snapshot("fizzbuzz")


def test_fibonacci_snapshot():
    assert_snapshot("fibonacci")
