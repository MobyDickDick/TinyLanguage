#!/usr/bin/env python3
"""Validate performance budgets against baseline snapshots."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

BASELINE_PATH = Path("benchmarks/performance_baselines.json")
BENCHMARK_SCRIPT = Path("benchmarks/microbenchmarks.py")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_benchmarks(
    *,
    backends: list[str],
    cases: list[str],
    repeat: int,
    warmup: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "benchmarks.json"
        command = [
            sys.executable,
            str(BENCHMARK_SCRIPT),
            "--repeat",
            str(repeat),
            "--warmup",
            str(warmup),
            "--json-output",
            str(output_path),
        ]
        if backends:
            command.append("--backend")
            command.extend(backends)
        if cases:
            command.append("--case")
            command.extend(cases)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                f"microbenchmarks failed with exit code {completed.returncode}"
            )
        return _load_json(output_path)


def _format_ratio(value: float) -> str:
    return f"{value:.2f}x"


def _ratio_below_budget(ratio: float, min_ratio: float) -> bool:
    """Return True when ``ratio`` is materially below ``min_ratio``.

    Benchmarks can vary slightly on shared CI hosts. We therefore allow a
    tiny relative tolerance (0.5%) plus two-decimal rounding before flagging
    a regression.
    """

    if ratio >= min_ratio:
        return False

    tolerance_ratio = min_ratio * 0.995
    if ratio >= tolerance_ratio:
        return False

    return round(ratio, 2) < round(tolerance_ratio, 2)


def _evaluate_results(
    *,
    results: dict[str, Any],
    baseline: dict[str, Any],
) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    benchmark_cases = baseline["benchmarks"]
    baseline_ms = baseline["baseline_ms"]
    budgets = baseline["budgets"]
    blocked = baseline.get("blocked", {})
    slowdown_threshold = baseline["regression"]["max_slowdown_ratio"]

    results_by_case = results["results"]

    for case in benchmark_cases:
        case_results = results_by_case.get(case, {})
        interpreter_result = case_results.get("interpreter")
        if not interpreter_result or "error" in interpreter_result:
            issues.append(f"{case}: interpreter missing or errored")
            continue
        interpreter_avg = interpreter_result["avg_ms"]
        interpreter_baseline = baseline_ms.get("interpreter", {}).get(case)
        if interpreter_baseline:
            if interpreter_avg > interpreter_baseline * slowdown_threshold:
                issues.append(
                    f"{case}: interpreter avg {interpreter_avg:.2f}ms exceeds"
                    f" baseline {interpreter_baseline:.2f}ms by >{slowdown_threshold:.2f}x"
                )

        for backend, budget_cases in budgets.items():
            backend_result = case_results.get(backend)
            baseline_avg = baseline_ms.get(backend, {}).get(case)
            blocked_reason = blocked.get(backend, {}).get(case)
            if not backend_result or "error" in backend_result:
                if blocked_reason or baseline_avg is None:
                    warnings.append(
                        f"{case}: {backend} unavailable (blocked: {blocked_reason})"
                    )
                    continue
                issues.append(f"{case}: {backend} missing or errored")
                continue
            if interpreter_avg == 0:
                issues.append(f"{case}: interpreter avg was zero; cannot compare ratios")
                continue
            backend_avg = backend_result["avg_ms"]
            ratio = interpreter_avg / backend_avg
            budget = budget_cases.get(case)
            if budget:
                min_ratio = budget["min_ratio"]
                if _ratio_below_budget(ratio, min_ratio):
                    issues.append(
                        f"{case}: {backend} ratio {_format_ratio(ratio)} below budget"
                        f" {_format_ratio(min_ratio)}"
                    )
            if baseline_avg:
                if backend_avg > baseline_avg * slowdown_threshold:
                    issues.append(
                        f"{case}: {backend} avg {backend_avg:.2f}ms exceeds baseline"
                        f" {baseline_avg:.2f}ms by >{slowdown_threshold:.2f}x"
                    )
            elif blocked_reason:
                warnings.append(
                    f"{case}: {backend} baseline blocked ({blocked_reason}); skipping regression check"
                )

    return issues, warnings


def _issue_key(issue: str) -> str:
    """Return the stable benchmark/backend category for a timing issue."""
    normalized = re.sub(r"\d+(?:\.\d+)?(?:ms|x)", "<measurement>", issue)
    return normalized


def _persistent_issues(first: list[str], second: list[str]) -> list[str]:
    """Keep second-run issues whose category also failed the first run."""
    first_keys = {_issue_key(issue) for issue in first}
    return [issue for issue in second if _issue_key(issue) in first_keys]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check TinyLanguage performance budgets against baselines."
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
        help="Path to baseline JSON (default: benchmarks/performance_baselines.json)",
    )
    parser.add_argument(
        "--backend",
        nargs="*",
        help="Limit to specific backends (defaults to baseline list)",
    )
    parser.add_argument(
        "--case",
        nargs="*",
        help="Limit to specific benchmark cases (defaults to baseline list)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="Number of timed runs per case/backend",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warmup runs per case/backend",
    )
    args = parser.parse_args()

    baseline = _load_json(args.baseline)
    backends = args.backend or baseline["backends"]
    cases = args.case or baseline["benchmarks"]

    try:
        results = _run_benchmarks(
            backends=backends,
            cases=cases,
            repeat=args.repeat,
            warmup=args.warmup,
        )
    except Exception as exc:
        print(f"Failed to run microbenchmarks: {exc}")
        return 1

    issues, warnings = _evaluate_results(results=results, baseline=baseline)

    # Shared CI hosts occasionally distort one backend for a single capture.
    # The documented regression policy requires two consecutive failures, so
    # retry once and fail only categories reproduced by the second capture.
    if issues:
        print("Performance budget issue detected; retrying once to confirm...")
        try:
            retry_results = _run_benchmarks(
                backends=backends,
                cases=cases,
                repeat=args.repeat,
                warmup=args.warmup,
            )
        except Exception as exc:
            print(f"Failed to rerun microbenchmarks: {exc}")
            return 1
        retry_issues, retry_warnings = _evaluate_results(
            results=retry_results, baseline=baseline
        )
        issues = _persistent_issues(issues, retry_issues)
        warnings.extend(retry_warnings)
        if not issues:
            warnings.append(
                "initial performance issue did not reproduce on the confirmation run"
            )

    if warnings:
        print("Performance budget warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if issues:
        print("Performance budget regressions:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("Performance budgets within limits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
