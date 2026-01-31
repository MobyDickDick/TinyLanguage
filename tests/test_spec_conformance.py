"""Conformance tests for TinyLanguage spec fixtures."""

from __future__ import annotations

from dataclasses import dataclass
import pathlib

from tiny_language import TinyLangError, _format_error_for_source, compile_and_run

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC_ROOT = PROJECT_ROOT / "tests" / "spec"


@dataclass
class ExecutionResult:
    """Capture stdout, stderr, and exit status for a spec fixture run."""

    stdout: str
    stderr: str
    exit_code: int


def _module_namespace_for_path(path: pathlib.Path) -> str:
    try:
        rel = path.resolve().relative_to(pathlib.Path.cwd())
        return ".".join(rel.with_suffix("").parts)
    except Exception:  # noqa: BLE001 - fallback for non-relative paths
        return path.stem


def _run_spec_fixture(source: str, fixture_path: pathlib.Path) -> ExecutionResult:
    try:
        output = compile_and_run(
            source,
            module_namespace=_module_namespace_for_path(fixture_path),
            module_path=fixture_path,
            stream_output=False,
        )
        return ExecutionResult(stdout=output, stderr="", exit_code=0)
    except Exception as exc:  # noqa: BLE001 - normalize into stderr output
        if isinstance(exc, TinyLangError):
            stderr = _format_error_for_source(source, exc)
        else:
            stderr = str(exc)
        return ExecutionResult(stdout="", stderr=stderr, exit_code=1)


def _load_expected(fixture_path: pathlib.Path, suffix: str) -> str:
    expected_path = fixture_path.with_suffix(suffix)
    if not expected_path.exists():
        raise AssertionError(f"Missing expected output file: {expected_path}")
    return expected_path.read_text(encoding="utf-8")


def _discover_spec_fixtures() -> list[pathlib.Path]:
    if not SPEC_ROOT.exists():
        return []
    return sorted(SPEC_ROOT.rglob("*.tiny"))


def test_spec_fixtures_match_snapshots() -> None:
    """Ensure spec fixtures match their expected stdout/stderr snapshots."""

    fixtures = _discover_spec_fixtures()
    assert fixtures, "No spec fixtures found under tests/spec."
    for fixture_path in fixtures:
        source = fixture_path.read_text(encoding="utf-8")
        expected_stdout = _load_expected(fixture_path, ".stdout")
        expected_stderr = _load_expected(fixture_path, ".stderr")
        result = _run_spec_fixture(source, fixture_path)
        assert result.stdout == expected_stdout
        assert result.stderr == expected_stderr
        if expected_stderr:
            assert result.exit_code == 1
        else:
            assert result.exit_code == 0
