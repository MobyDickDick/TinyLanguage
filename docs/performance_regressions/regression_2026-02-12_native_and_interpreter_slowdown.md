# Regression ticket: 2026-02-12 native/interpreter slowdown investigation

## Summary

A benchmark diff captured on 2026-02-12 showed multiple apparent slowdowns above
15% versus `benchmarks/performance_baselines.json` for interpreter and native
backend measurements. A clean-checkout rerun did **not** reproduce the issue,
which indicates the slowdown was likely environmental/noise-related rather than
an actionable code regression in the checked-in baseline.

## Artifacts

- Benchmark JSON diff:
  - `artifacts/perf/2026-02-12/raw/baseline_diff.md`
- Raw benchmark output logs:
  - `artifacts/perf/2026-02-12/logs/microbenchmarks.stdout.log`
  - `artifacts/perf/2026-02-12/logs/microbenchmarks.stderr.log`
- Flamegraph SVGs:
  - `artifacts/perf/2026-02-12/raw/flamegraphs/heap_roundtrip_native.svg`
  - `artifacts/perf/2026-02-12/raw/flamegraphs/map_operations_interpreter.svg`
  - `artifacts/perf/2026-02-12/raw/flamegraphs/heap_roundtrip_interpreter.svg`
  - `artifacts/perf/2026-02-12/raw/flamegraphs/map_operations_native.svg`
  - `artifacts/perf/2026-02-12/raw/flamegraphs/tight_loop_interpreter.svg`
  - `artifacts/perf/2026-02-12/raw/flamegraphs/recursive_calls_interpreter.svg`
  - `artifacts/perf/2026-02-12/raw/flamegraphs/recursive_calls_native-python-bytecode.svg`
  - `artifacts/perf/2026-02-12/raw/flamegraphs/tight_loop_native.svg`
  - `artifacts/perf/2026-02-12/raw/flamegraphs/recursive_calls_native.svg`
- Environment metadata:
  - `artifacts/perf/2026-02-12/logs/clean_checkout_environment.txt`
- Clean-checkout validation logs:
  - `artifacts/perf/2026-02-12/logs/clean_checkout_budget_check.stdout.log`
  - `artifacts/perf/2026-02-12/logs/clean_checkout_budget_check.stderr.log`

## Reproduction status

- Initial triage capture: regression **observed**.
- Clean-checkout rerun (`/tmp/TinyLanguage-clean`): regression **not observed**;
  `python tools/performance/check_performance_budgets.py` exited successfully
  and reported "Performance budgets within limits."

## Suspected culprit

No single culprit commit identified. Given non-reproduction on a clean clone,
the most likely causes are runtime variability, host contention, or transient
measurement noise.

## Baseline decision

Hold the current baseline (`benchmarks/performance_baselines.json`) unchanged.
Do not rebaseline based on this incident.

## Follow-ups

1. Re-run the same benchmark command in CI and compare variance across at least
   three consecutive runs before opening a code-change regression.
2. If regression reappears consistently, attach culprit commit candidates and
   open a dedicated fix PR with focused microbenchmark changes.
