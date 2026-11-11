"""Smoke and regression tests for the parity runner."""

from __future__ import annotations

import pathlib
import sys
import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from parity_runner import (  # noqa: E402
    BackendResult,
    Fixture,
    FixtureMetadata,
    _compare_backend,
    _check_expected,
    _load_metadata,
    main,
)


def test_parity_runner_on_fixtures() -> None:
    """Run parity checks on the bundled fixtures using core backends."""
    parity_dir = PROJECT_ROOT / "tests" / "parity"
    exit_code = main(
        [
            "--fixtures",
            str(parity_dir),
            "--backend",
            "interpreter",
            "--backend",
            "native",
        ]
    )
    assert exit_code == 0


def test_compare_backend_normalizes_error_prefixes_per_stream() -> None:
    """Keep stdout/stderr separate while normalizing error diagnostics."""
    fixture = Fixture(
        name="error_case",
        path=PROJECT_ROOT / "tests" / "parity" / "error_span_nested_block.tiny",
        metadata=FixtureMetadata(),
    )
    baseline = BackendResult(stdout="ok\n", stderr="RuntimeError - bad input\n", exit_code=1)
    candidate = BackendResult(stdout="ok\n", stderr="error: bad input\n", exit_code=1)

    diffs = _compare_backend(
        fixture=fixture,
        baseline_name="interpreter",
        baseline=baseline,
        candidate_name="native",
        candidate=candidate,
        keep_stack_traces=False,
    )

    assert diffs == []


def test_compare_backend_reports_stdout_and_stderr_diffs_independently() -> None:
    """Parity diff output should identify stream-specific mismatches."""
    fixture = Fixture(
        name="stream_case",
        path=PROJECT_ROOT / "tests" / "parity" / "sum_loop.tiny",
        metadata=FixtureMetadata(),
    )
    baseline = BackendResult(stdout="value\n", stderr="", exit_code=0)
    candidate = BackendResult(stdout="", stderr="value\n", exit_code=0)

    diffs = _compare_backend(
        fixture=fixture,
        baseline_name="interpreter",
        baseline=baseline,
        candidate_name="native",
        candidate=candidate,
        keep_stack_traces=False,
    )

    assert len(diffs) == 2
    assert "stdout" in diffs[0]
    assert "stderr" in diffs[1]


def test_shared_crash_is_not_parity_success(tmp_path, monkeypatch):
    import parity_runner

    (tmp_path / "example.tiny").write_text("print(1);", encoding="utf-8")
    crash = lambda *args: BackendResult(stderr="shared regression", exit_code=1)
    monkeypatch.setattr(parity_runner, "_run_interpreter", crash)
    monkeypatch.setattr(parity_runner, "_run_native", crash)
    assert main(["--fixtures", str(tmp_path), "--backend", "interpreter", "--backend", "native"]) == 1


def test_metadata_cannot_override_requested_backend_and_empty_execution_fails(tmp_path, monkeypatch):
    import parity_runner

    fixture = tmp_path / "example.tiny"
    fixture.write_text("print(1);", encoding="utf-8")
    fixture.with_suffix(".meta.json").write_text('{"backends": ["native"]}', encoding="utf-8")
    def unexpected(*args):
        pytest.fail("metadata overrode the explicitly requested backend")
    monkeypatch.setattr(parity_runner, "_run_native", unexpected)
    assert main(["--fixtures", str(tmp_path), "--backend", "interpreter"]) == 1


def test_snapshot_catches_shared_wrong_output_even_if_normalization_would_erase_it(tmp_path):
    path = tmp_path / "example.tiny"
    path.with_suffix(".stdout").write_text("", encoding="utf-8")
    fixture = Fixture("example", path, FixtureMetadata())
    assert _check_expected(fixture, "interpreter", BackendResult(stdout="TinyLanguage corruption\n"))


def test_error_metadata_requires_a_contract_diagnostic(tmp_path):
    path = tmp_path / "example.tiny"
    path.with_suffix(".meta.json").write_text('{"expected_exit_code": 1}', encoding="utf-8")
    with pytest.raises(ValueError, match="diagnostic"):
        _load_metadata(path)


def test_all_missing_backends_produce_failure(tmp_path, monkeypatch):
    import parity_runner

    (tmp_path / "example.tiny").write_text("print(1);", encoding="utf-8")
    monkeypatch.setattr(parity_runner, "_run_c_backend", lambda *args: BackendResult(skipped=True, skip_reason="missing"))
    assert main(["--fixtures", str(tmp_path), "--backend", "c"]) == 1
