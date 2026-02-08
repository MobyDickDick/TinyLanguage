# Open tasks

This file tracks only active work items for TinyLanguage. Completed tasks are
archived in `docs/open_tasks_archive.md`.

## Current tasks

The active work items are tracked in the refreshed near-term backlog and the
sections below.

## Refreshed near-term backlog (published 2026-03-20)

Timebox: 2026-03-20 to 2026-05-01 (6 weeks).

1. **Refresh the roadmap with a concrete minor-release milestone** (Owner: Project Lead)
   - Success: `docs/roadmap_next.md` includes a dated milestone section with
     3-5 deliverables and cross-links to the corresponding backlog items.
2. **Expand module-resolution regression coverage for package workflows** (Owner: Ecosystem)
   - Success: Add edge-case tests for vendor cache + local override precedence,
     plus a short note in `docs/module_resolution_algorithm.md` describing the
     precedence order tested.
3. **Add LSP formatting-hook acceptance coverage** (Owner: Tooling)
   - Success: A new multi-file LSP test validates formatting hooks and documents
     the request/response shape in `docs/language_server_workflows.md`.
4. **Define a repeatable profiling capture workflow** (Owner: Runtime)
   - Success: `docs/performance_budgets_and_baselines.md` describes a step-by-step
     profiling capture flow and identifies the baseline artifacts to store.

## Newly proposed backlog items (drafts)

The tasks below are newly formulated and meant to be triaged into the active
backlog once ownership and sequencing are confirmed.

1. **Ship a package publish dry-run workflow** (Owner: Ecosystem)
   - Success: `docs/package_manager_plan.md` documents a `tiny pkg publish --dry-run`
     workflow and `tools/tiny_pkg_publish.py` supports an explicit dry-run mode that
     emits the staged payload without network side effects.
2. **Document debugger trace workflows for async tasks** (Owner: Tooling)
   - Success: `docs/debugger_guide.md` adds a walkthrough for stepping through
     async tasks, including the expected output from `tiny debug trace` when
     multiple tasks are scheduled.
3. **Add reproducible perf regression triage playbook** (Owner: Runtime)
   - Success: `docs/performance_budgets_and_baselines.md` includes a playbook
     for diffing baseline JSONs, capturing flamegraphs, and filing regression
     tickets with the required artifacts.
4. **Define a module deprecation workflow for stdlib moves** (Owner: Language/Stdlib)
   - Success: `docs/versioning_deprecation_policy.md` includes a checklist for
     stdlib moves (announce, warn, provide alias, remove) and references the
     existing compatibility matrix.

### Concrete tasks derived from the drafts

- [x] Draft a `tiny pkg publish --dry-run` CLI spec section that enumerates inputs,
  outputs, and expected artifacts for review in `docs/package_manager_plan.md`.
- [ ] Add a minimal dry-run execution path in `tools/tiny_pkg_publish.py` that
  serializes the payload to disk and returns a non-zero exit code when validation
  fails.
- [ ] Capture an async-task debugging transcript (commands + outputs) and embed
  it in `docs/debugger_guide.md` as a worked example.
- [ ] Extend `docs/performance_budgets_and_baselines.md` with a checklist for
  capturing flamegraphs, tagging baseline snapshots, and filing regressions with
  links to artifacts.
- [ ] Add a stdlib deprecation checklist entry to
  `docs/versioning_deprecation_policy.md`, including the expected warning
  timeline and aliasing strategy.

## Near-term priorities (next 4-6 weeks)

Active items are tracked in the refreshed backlog above.

**Next milestone:** 2026-05 minor release planning checkpoint (roadmap refresh
with scoped deliverables and owners).

## Package tooling execution plan (proposed)

Concrete next steps derived from the package/module roadmap to move from
documentation into implementation.

- [x] Emit a vendor summary (`vendor/README.md`) during `tiny pkg vendor` for
  auditability (manifest hash + dependency list).
- [x] Add lockfile drift checks that fail `tiny pkg vendor` when
  `manifest_hash` does not match the current `tiny.toml`.
- [x] Add unit coverage for `tiny pkg vendor` readme output and lockfile drift
  validation.
- [x] Document the package CLI workflows in `docs/package_manager_plan.md` with
  the new vendor audit output and lockfile drift behavior.

## Proposed production-readiness tasks (draft for next planning cycle)

These are suggested tasks to move TinyLanguage from a capable prototype toward
a fully functional, production-ready language. They are intentionally concrete
and testable so they can be promoted into the formal backlog as needed.

### Language + runtime stability
- [x] Close remaining semantic ambiguities with executable spec tests (e.g.,
  numeric overflow, error propagation, evaluation order in edge cases).
  - Notes: added targeted spec tests for error propagation and overflow edges in
    `tests/detailtests/test_semantics_suite.py` and
    `tests/detailtests/test_number_overflow.py`.

### Package + module system (MVP → usable)
- [x] Add semver-aware dependency constraints and a minimal registry schema.
  - Notes: `src/tiny_pkg_resolution.py` parses SemVer constraints and resolves
    registry versions; `docs/package_manager_plan.md` documents the initial
    registry metadata schema with checksum fields.
- [x] Define a reproducible module-resolution algorithm shared by interpreter
  and native backends, including tests for edge cases.
  - Notes: documented the algorithm in `docs/module_resolution_algorithm.md`
    and added edge-case tests in
    `tests/detailtests/test_module_resolution_algorithm.py`.

### Standard library completeness
- [x] Ship “core IO” parity (`fs`, `path`, `process`, `env`, `time`) with
  parity tests against Python behavior.
  - Notes: added `stdlib.fs` wrapper plus parity coverage for `fs`, POSIX-style
    `path`, and `time`; existing `os` env tests cover `env`, and process parity
    remains scoped to the mock-backed API surface.
- [x] Expand networking and serialization modules (`http`, `json`, `toml`)
  with fuzzed round-trip tests.
  - Notes: added TOML stdlib wrapper, mock HTTP echo handling, and fuzzed
    round-trip tests for JSON/TOML/HTTP in the detail test suite.
- [x] Publish a stability/maturity tier for each stdlib module and a policy for
  deprecations.
  - Notes: maturity tiers and module status live in
    `docs/stdlib_compatibility.md`, with the deprecation policy defined in
    `docs/versioning_deprecation_policy.md`.

### Tooling + DX
- [x] Add end-to-end LSP acceptance tests for rename, references, and code
  actions across a multi-file project.
  - Notes: CLI tests now exercise `references`, `rename`, and `code-actions`
    against a multi-file project fixture in
    `tests/detailtests/test_language_server_cli.py`.
- [x] Provide a first-class formatter + lint baseline for CI and editor
  integration (single command to enforce).
  - Notes: `tools/format_lint_baseline.py` provides a unified formatter + lint
    runner with `--check`/`--apply` modes for CI and editor tasks.
- [x] Improve debugger parity (breakpoints, variable inspection, async tasks)
  with a canonical test suite.
  - Notes: added async breakpoint scope coverage to the debugger hook tests in
    `tests/detailtests/test_debugger_hooks.py` to validate spawned-task locals.

### Distribution + releases
- [x] Produce signed, reproducible release artifacts for all supported OSes
  and include SBOMs in release bundles.
- [x] Publish upgrade guides and automated migration tooling for each minor
  release.
  - Notes: added `docs/release_minor_upgrade_guides.md`, a migration recipe
    registry (`docs/release_minor_migration_recipes.json`), and the automation
    entry point `tools/release/prepare_minor_upgrade.py`.
- [x] Establish a release-candidate checklist that is run in CI.
  - Notes: added `docs/release_candidate_checklist.md`, a CI gate script in
    `tools/release/check_release_candidate_checklist.py`, and wired it into
    `.github/workflows/ci.yml`.

### Performance + reliability
- [x] Lock in performance budgets per backend and enforce regression alerts in
  CI with baseline snapshots.
  - Notes: baseline snapshot tracked in `benchmarks/performance_baselines.json`
    and enforced in CI via `tools/performance/check_performance_budgets.py`.
- [x] Expand fuzzing coverage (lexer/parser/runtime) and require nightly runs.
  - Notes: added lexer/parser fuzz coverage in
    `tests/detailtests/test_benchmark_and_fuzz.py` and scheduled nightly runs
    via `.github/workflows/nightly-fuzz.yml`.
- [x] Add stress tests for concurrency primitives and memory-pressure handling.
  - Notes: added stress coverage for spawn/join and repeated heap allocations in
    `tests/detailtests/test_concurrency.py`.

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
