#!/usr/bin/env python3
"""Run the opt-in typing lint gate and write a deterministic review report."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter
from typing import Any

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "typecheck_ci" / "manifest.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "ci" / "typecheck-baseline.json"

sys.path.insert(0, str(SRC_ROOT))

from language_server import TinyLanguageServer  # noqa: E402


def _relative_path(path: pathlib.Path) -> str:
    """Render repository files without machine-specific absolute prefixes."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _diagnostic_record(diagnostic: Any) -> dict[str, Any]:
    """Convert one language-server diagnostic into stable JSON fields."""
    return {
        "code": diagnostic.code,
        "severity": diagnostic.severity,
        "range": list(diagnostic.range),
        "message": diagnostic.message.splitlines()[0],
        "phase": diagnostic.phase,
        "source": diagnostic.source,
    }


def run_gate(manifest_path: pathlib.Path, output_path: pathlib.Path) -> tuple[dict[str, Any], bool]:
    """Check all manifest fixtures, persist the report, and return its status."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture_reports: list[dict[str, Any]] = []
    unexpected_total = 0
    missing_total = 0

    for fixture in manifest["fixtures"]:
        source_path = PROJECT_ROOT / fixture["path"]
        source = source_path.read_text(encoding="utf-8")
        diagnostics = TinyLanguageServer(source, lint_profile="typing").diagnostics()
        diagnostic_records = [_diagnostic_record(item) for item in diagnostics]
        expected_codes = list(fixture.get("expected_diagnostic_codes", []))
        actual_codes = [item["code"] for item in diagnostic_records]

        unexpected = list((Counter(actual_codes) - Counter(expected_codes)).elements())
        missing = list((Counter(expected_codes) - Counter(actual_codes)).elements())
        unexpected_total += len(unexpected)
        missing_total += len(missing)
        fixture_reports.append(
            {
                "path": _relative_path(source_path),
                "purpose": fixture["purpose"],
                "expected_diagnostic_codes": expected_codes,
                "diagnostics": diagnostic_records,
                "unexpected_diagnostic_codes": unexpected,
                "missing_expected_diagnostic_codes": missing,
                "status": "pass" if not unexpected and not missing else "review-required",
            }
        )

    passed = unexpected_total == 0 and missing_total == 0
    report = {
        "schema_version": 1,
        "lint_profile": "typing",
        "manifest": _relative_path(manifest_path),
        "summary": {
            "fixture_count": len(fixture_reports),
            "diagnostic_count": sum(len(item["diagnostics"]) for item in fixture_reports),
            "unexpected_diagnostic_count": unexpected_total,
            "missing_expected_diagnostic_count": missing_total,
            "passed": passed,
        },
        "fixtures": fixture_reports,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report, passed


def main(argv: list[str] | None = None) -> int:
    """Parse command-line arguments and run the curated typecheck gate."""
    parser = argparse.ArgumentParser(
        description="Run the curated TinyLanguage typing-lint CI gate",
    )
    parser.add_argument("--manifest", type=pathlib.Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report, passed = run_gate(args.manifest, args.output)
    summary = report["summary"]
    print(
        "Typecheck CI gate: "
        f"{summary['fixture_count']} fixtures, "
        f"{summary['diagnostic_count']} diagnostics, "
        f"{summary['unexpected_diagnostic_count']} unexpected, "
        f"{summary['missing_expected_diagnostic_count']} missing expected."
    )
    print(f"Baseline report: {_relative_path(args.output)}")
    if not passed:
        print("Typecheck CI gate requires false-positive/baseline review.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
