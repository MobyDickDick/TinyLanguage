# Performance budgets and profiling baselines

This document establishes concrete performance budgets for each TinyLanguage
backend and defines the baseline measurements used to detect regressions. It is
intended to be read alongside `docs/runtime_performance_goals.md` and updated
whenever the benchmark suite or backend capabilities change.

## Scope

The budgets and baselines below cover the backends that ship with TinyLanguage
and the microbenchmark suite in `benchmarks/microbenchmarks.py`:

- Interpreter (reference backend)
- Native backend (C/native pipeline)
- LLVM backend (when available)
- Python backend (transpiled Python execution)
- Native Python bytecode backend

## Budget targets (relative to interpreter)

Budgets are defined as **minimum expected speedups** (or maximum slowdowns) on
microbenchmarks. The interpreter remains the 1.0x baseline.

| Backend | tight_loop | recursive_calls | heap_roundtrip | map_operations | Startup/CLI budget |
| --- | --- | --- | --- | --- | --- |
| Interpreter | 1.0x (baseline) | 1.0x (baseline) | 1.0x (baseline) | 1.0x (baseline) | <= 250ms for `tiny_language_cli` hello-world |
| Native (C) | >= 2.0x | >= 1.8x | >= 1.5x | >= 1.4x | <= 400ms |
| LLVM | >= 2.5x | >= 2.0x | >= 1.8x | >= 1.6x | <= 450ms |
| Python | <= 1.5x slowdown | <= 1.5x slowdown | <= 1.3x slowdown | <= 1.3x slowdown | <= 350ms |
| Native Python bytecode | >= 2.0x | >= 1.8x | >= 1.4x | >= 1.4x | <= 400ms |

Notes:
- The startup/CLI budgets are measured using a simple hello-world program via
  `src/tiny_language_cli.py` or the packaged CLI. The goal is to keep tooling
  commands responsive even as backends optimize for throughput.
- Budgets apply to the **average** timing reported by the benchmark script.
- When a backend does not yet support a benchmark case, mark the case as
  "blocked" in the baseline table and track the missing capability before
  enforcing the budget.

## Baseline capture workflow

1. Run the microbenchmarks with deterministic settings:

   ```bash
   python benchmarks/microbenchmarks.py --backend interpreter native --repeat 3 --warmup 1
   ```

2. Record the `avg=...ms` values per backend/case in the baseline table below.
3. If a backend fails on a benchmark (missing opcode or lint rule), note the
   failure and open a follow-up task to restore parity.

### Repeatable profiling capture workflow

Use this flow whenever you refresh `benchmarks/performance_baselines.json` or
investigate a regression report so captured artifacts are comparable.

1. **Create an artifact folder** under a dated path:

   ```bash
   mkdir -p artifacts/perf/$(date +%Y-%m-%d)/raw
   ```

2. **Capture a baseline benchmark JSON** with fixed run parameters:

   ```bash
   python benchmarks/microbenchmarks.py \
     --backend interpreter native native_py \
     --repeat 5 \
     --warmup 2 \
     --json-out artifacts/perf/$(date +%Y-%m-%d)/raw/microbenchmarks.json
   ```

3. **Snapshot host/tool metadata** into a sidecar file for reproducibility:

   ```bash
   python -V > artifacts/perf/$(date +%Y-%m-%d)/raw/environment.txt
   uname -a >> artifacts/perf/$(date +%Y-%m-%d)/raw/environment.txt
   git rev-parse HEAD >> artifacts/perf/$(date +%Y-%m-%d)/raw/environment.txt
   ```

4. **Capture flamegraphs for any benchmark that regresses >=10%** relative to
   the current baseline (or all benchmarks during a major refresh).
   - Linux (`perf`): record + fold + render SVG flamegraph.
   - Cross-platform fallback (`py-spy`):

     ```bash
     py-spy record \
       --output artifacts/perf/$(date +%Y-%m-%d)/raw/tight_loop_native.svg \
       -- python benchmarks/microbenchmarks.py --backend native --case tight_loop --repeat 1 --warmup 0
     ```

5. **Copy/update the canonical baseline snapshot** and keep the raw capture for
   auditability:

   ```bash
   cp artifacts/perf/$(date +%Y-%m-%d)/raw/microbenchmarks.json benchmarks/performance_baselines.json
   ```

6. **Tag the snapshot in version control** after merge so future triage can
   diff against a stable reference:
   - Tag format: `perf-baseline-YYYY-MM-DD`.
   - Include date, commit SHA, and benchmark command in the tag annotation.

### Perf regression triage checklist

When CI or local checks report a regression, complete this checklist before
closing the incident:

- [ ] Re-run the budget check locally and save stdout/stderr logs.
- [ ] Diff current vs baseline JSON (`benchmarks/performance_baselines.json`) and
      list all cases above the 15% threshold.
- [ ] Capture at least one flamegraph per regressed benchmark/backend pair.
- [ ] Confirm whether the regression reproduces on a clean checkout.
- [ ] File a regression ticket with links to required artifacts:
      - benchmark JSON diff
      - raw benchmark output log
      - flamegraph SVG(s)
      - environment metadata (`python -V`, OS/kernel, commit SHA)
      - suspected culprit commit (if identified)
- [ ] Add the ticket link to the next baseline update PR and note whether the
      baseline should be held or intentionally rebaselined.

## CI enforcement

CI runs the microbenchmarks against the baseline snapshot stored in
`benchmarks/performance_baselines.json` and enforces the budget ratios defined
there. The check also flags regressions when a backend average is more than
15% slower than the recorded baseline. To run the same check locally:

```bash
python tools/performance/check_performance_budgets.py
```

## Baseline snapshot (2026-02-01)

Environment notes:
- Captured locally on developer hardware using the default interpreter and
  native backend.
- Heap safety diagnostics (`heap_get failed`) are expected during
  `heap_roundtrip` and do not invalidate the timing capture.

| Backend | tight_loop avg | recursive_calls avg | heap_roundtrip avg | map_operations avg |
| --- | --- | --- | --- | --- |
| Interpreter | 339.00ms | 221.34ms | 567.65ms | 187.51ms |
| Native (C) | 136.53ms | 96.14ms | 340.18ms | 106.87ms |
| Native Python bytecode | 42.67ms | 28.37ms | blocked (unknown function in heap bench) | blocked (unknown variable in Map bench) |
| Python | blocked (binary operator `<` not supported yet) | blocked | blocked | blocked |
| LLVM | not captured (backend not available in this environment) | not captured | not captured | not captured |

## Regression rules

- A regression is any change that violates the budget targets above or pushes a
  backend's average runtime more than **15% slower** than its recorded baseline
  for two consecutive runs.
- When a regression is detected, capture a short repro program and add it to
  the microbenchmark suite or a focused test fixture.
- Update this document with new baseline rows whenever benchmark definitions
  or backend capabilities change.
