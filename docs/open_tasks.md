# Open tasks

This file tracks only active work items for TinyLanguage. Completed tasks are
archived in `docs/open_tasks_archive.md`.

## Current tasks

The active work items are tracked in the refreshed near-term backlog and the
sections below.

## Refreshed near-term backlog (published 2026-02-02)

Timebox: 2026-02-02 to 2026-03-16 (6 weeks).

1. **Stabilize formatter + lints + LSP workflows** (Owner: Tooling) ✅
   - Success: Documented formatter rules, lint profiles, and LSP smoke tests.
   - Completed: See `docs/formatter_rules.md`, `docs/developer_tooling_workflows.md`,
     and `docs/lsp_smoke_tests.md` (archived in `docs/open_tasks_archive.md`).

## Near-term priorities (next 4-6 weeks)

No active near-term items. Completed tasks are archived in
`docs/open_tasks_archive.md`.

## Proposed production-readiness tasks (draft for next planning cycle)

These are suggested tasks to move TinyLanguage from a capable prototype toward
a fully functional, production-ready language. They are intentionally concrete
and testable so they can be promoted into the formal backlog as needed.

### Language + runtime stability
- [ ] Close remaining semantic ambiguities with executable spec tests (e.g.,
  numeric overflow, error propagation, evaluation order in edge cases).
- [ ] Stabilize runtime error taxonomy with machine-readable codes and update
  all backends to emit consistent error metadata.

### Package + module system (MVP → usable)
- [ ] Implement a real package manager prototype (`tiny pkg`) with dependency
  resolution, lockfiles, and offline cache support.
- [ ] Add semver-aware dependency constraints and a minimal registry schema.
- [ ] Define a reproducible module-resolution algorithm shared by interpreter
  and native backends, including tests for edge cases.

### Standard library completeness
- [ ] Ship “core IO” parity (`fs`, `path`, `process`, `env`, `time`) with
  parity tests against Python behavior.
- [ ] Expand networking and serialization modules (`http`, `json`, `toml`)
  with fuzzed round-trip tests.
- [ ] Publish a stability/maturity tier for each stdlib module and a policy for
  deprecations.

### Tooling + DX
- [ ] Add end-to-end LSP acceptance tests for rename, references, and code
  actions across a multi-file project.
- [ ] Provide a first-class formatter + lint baseline for CI and editor
  integration (single command to enforce).
- [ ] Improve debugger parity (breakpoints, variable inspection, async tasks)
  with a canonical test suite.

### Distribution + releases
- [ ] Produce signed, reproducible release artifacts for all supported OSes
  and include SBOMs in release bundles.
- [ ] Publish upgrade guides and automated migration tooling for each minor
  release.
- [ ] Establish a release-candidate checklist that is run in CI.

### Performance + reliability
- [ ] Lock in performance budgets per backend and enforce regression alerts in
  CI with baseline snapshots.
- [ ] Expand fuzzing coverage (lexer/parser/runtime) and require nightly runs.
- [ ] Add stress tests for concurrency primitives and memory-pressure handling.

## Expansion roadmap follow-ups

- [x] Define the Julia subset target and list functions in `docs/julia_subset.md`.
  - Owner: Language/Stdlib
  - Success: Documented function list with examples and scope boundaries.
- [x] Implement `mean` + `std` in a new statistics module with tests.
  - Owner: Stdlib
  - Success: `stdlib/statistics.tiny` plus tests comparing outputs to Python/NumPy where feasible.
- [x] Expand parity tests for multi-line/nested error spans.
  - Owner: Tooling
  - Success: Regression suite verifies identical formatting for complex spans.
- [x] Add a regression matrix for self-hosting modules.
  - Owner: Tooling
  - Success: Documented matrix with last-verified versions and known deviations.

## Longer-term backlog (unprioritized)

- [x] Conformance + cross-backend parity suite expansion.
  - Added parity fixtures for function branching and looped arithmetic in
    `tests/parity/`.
