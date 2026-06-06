"""Tests for the opt-in typecheck CI baseline gate."""

from __future__ import annotations

import json
from pathlib import Path

from tools.typecheck_ci_gate import DEFAULT_MANIFEST, run_gate


def test_curated_typecheck_baseline_passes_and_is_deterministic(tmp_path: Path) -> None:
    """The committed fixture expectations should produce a stable passing report."""
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"

    first_report, first_passed = run_gate(DEFAULT_MANIFEST, first_output)
    second_report, second_passed = run_gate(DEFAULT_MANIFEST, second_output)

    assert first_passed is True
    assert second_passed is True
    assert first_report == second_report
    assert first_output.read_text(encoding="utf-8") == second_output.read_text(encoding="utf-8")
    assert first_report["summary"] == {
        "fixture_count": 3,
        "diagnostic_count": 1,
        "unexpected_diagnostic_count": 0,
        "missing_expected_diagnostic_count": 0,
        "passed": True,
    }


def test_typecheck_gate_flags_unexpected_diagnostic_for_review(tmp_path: Path) -> None:
    """New diagnostics must fail the trial and remain visible in its JSON report."""
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    manifest["fixtures"][2]["expected_diagnostic_codes"] = []
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "report.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report, passed = run_gate(manifest_path, output_path)

    assert passed is False
    assert report["summary"]["unexpected_diagnostic_count"] == 1
    assert report["fixtures"][2]["unexpected_diagnostic_codes"] == ["E009"]
    assert report["fixtures"][2]["status"] == "review-required"
    assert json.loads(output_path.read_text(encoding="utf-8")) == report
