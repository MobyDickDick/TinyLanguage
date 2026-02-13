"""Smoke and regression tests for the parity runner."""

from __future__ import annotations

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from parity_runner import (  # noqa: E402
    BackendResult,
    Fixture,
    FixtureMetadata,
    _compare_backend,
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
