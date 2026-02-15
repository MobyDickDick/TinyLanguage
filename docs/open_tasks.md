# Open tasks

This file tracks only active work items for TinyLanguage. Completed tasks are
archived in `docs/open_tasks_archive.md`.

## Current tasks

## Proposed next-cycle tasks (2026-06 draft)

The following items are intentionally left open (`- [ ]`) and are candidates
for triage into the next active timebox.

- [x] **Publish a language-server compatibility matrix per editor client**
  (Owner: Tooling)
  - Success: `docs/language_server_workflows.md` includes a matrix for VS Code,
    Neovim (LSP), and generic Language Server Protocol clients with supported
    capabilities (`hover`, `diagnostics`, `formatting`, `code actions`) and
    known caveats.
  - Notes: added the "Editor-client compatibility matrix" section and method-
    level caveats in `docs/language_server_workflows.md` covering VS Code,
    Neovim, and generic LSP client adapters.

- [x] **Add package lockfile reproducibility checks across platforms**
  (Owner: Ecosystem)
  - Success: A deterministic test verifies that the same `tiny.toml` generates
    identical lockfile content on Linux/macOS/Windows path conventions,
    including normalized separators and stable dependency ordering.
  - Notes: added `tests/detailtests/test_pkg_lockfile_reproducibility.py` and
    updated `src/tiny_pkg_resolution.py` to normalize dependency paths and
    sort dependency keys before lockfile rendering for stable output.

- [x] **Define interpreter/native parity gates for release candidates**
  (Owner: Runtime)
  - Success: `docs/release_candidate_checklist.md` adds explicit parity gates
    requiring key smoke programs to match output and error codes across
    interpreter, C backend, and native backend before release sign-off.
  - Notes: expanded `docs/release_candidate_checklist.md` with a CI parity gate,
    a required interpreter/C/native smoke scenario matrix, and a manual
    transcript-attachment requirement for release sign-off auditability.

- [x] **Add a stdlib API change budget for minor releases**
  (Owner: Language/Stdlib)
  - Success: `docs/versioning_deprecation_policy.md` defines a per-minor budget
    for additive vs. breaking stdlib changes and references the required
    migration-note template.
  - Notes: added the "Stdlib API change budget for minor releases" section to
    `docs/versioning_deprecation_policy.md`, including explicit additive/
    soft-breaking/hard-breaking limits and a required migration-note template
    tied to `docs/release_minor_upgrade_guides.md` and
    `docs/release_minor_guides/`.

## Open-task audit (2026-02-13)

- [x] Audited repository planning docs for unchecked checklist entries (`- [ ]`).
  - Result: no unchecked checklist tasks remain in `docs/` at audit time.
- [x] Promoted the next planning action for this cycle:
  - Run backlog triage for newly proposed items (owner assignment + sequencing) and either
    move accepted items into the refreshed near-term backlog or archive deferred items with rationale.

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

### Concrete tasks derived from refreshed backlog

- [x] Add a dated 2026-05 planning milestone section to `docs/roadmap_next.md`
  with 3-5 deliverables and cross-links to refreshed backlog items.
  - Notes: added the "2026-05 minor-release planning checkpoint" section with
    four deliverables, explicit backlog references, and milestone exit criteria
    in `docs/roadmap_next.md`.

- [x] Expand module-resolution regression coverage for package workflows,
  including local override + vendor precedence edge cases, and document the
  tested precedence order in `docs/module_resolution_algorithm.md`.
  - Notes: added package precedence tests in
    `tests/detailtests/test_module_resolution_algorithm.py` and documented
    local-override → registry-vendor → git-vendor ordering in
    `docs/module_resolution_algorithm.md`.

- [x] Add LSP formatting-hook acceptance coverage with a multi-file project
  workflow and document the formatting/code-action request/response payloads
  in `docs/language_server_workflows.md`.
  - Notes: added multi-file formatting-hook acceptance assertions in
    `tests/detailtests/test_language_server_cli.py`
    (`test_cli_project_formatting_hook_matches_format_output`) and aligned the
    workflow documentation examples in `docs/language_server_workflows.md`.

- [x] Define a repeatable profiling capture workflow in
  `docs/performance_budgets_and_baselines.md` that includes baseline capture,
  environment metadata snapshots, artifact retention paths, and post-merge
  baseline tagging guidance.
  - Notes: expanded the profiling workflow into an explicit runbook with
    deterministic benchmark commands, required artifact layout under
    `artifacts/perf/<date>/raw`, canonical baseline update steps, and
    version-control tag conventions for later regression triage.

## Newly proposed backlog items (drafts)

The tasks below are newly formulated and meant to be triaged into the active
backlog once ownership and sequencing are confirmed.

1. ✅ **Ship a package publish dry-run workflow** (Owner: Ecosystem, Completed)
   - Success: `docs/package_manager_plan.md` documents a `tiny pkg publish --dry-run`
     workflow and `tools/tiny_pkg_publish.py` supports an explicit dry-run mode that
     emits the staged payload without network side effects.
   - Status: Completed via the concrete tasks below (`docs/package_manager_plan.md`,
     `tools/tiny_pkg_publish.py`, and `tests/detailtests/test_tiny_pkg_publish.py`).
2. ✅ **Document debugger trace workflows for async tasks** (Owner: Tooling, Completed)
   - Success: `docs/debugger_guide.md` adds a walkthrough for stepping through
     async tasks, including the expected output from `tiny debug trace` when
     multiple tasks are scheduled.
   - Status: Completed via the concrete task below (`docs/debugger_guide.md`).
3. ✅ **Add reproducible perf regression triage playbook** (Owner: Runtime, Completed)
   - Success: `docs/performance_budgets_and_baselines.md` includes a playbook
     for diffing baseline JSONs, capturing flamegraphs, and filing regression
     tickets with the required artifacts.
   - Status: Completed via the concrete task below
     (`docs/performance_budgets_and_baselines.md`).
4. ✅ **Define a module deprecation workflow for stdlib moves** (Owner: Language/Stdlib, Completed)
   - Success: `docs/versioning_deprecation_policy.md` includes a checklist for
     stdlib moves (announce, warn, provide alias, remove) and references the
     existing compatibility matrix.
   - Status: Completed via the concrete task below (`docs/versioning_deprecation_policy.md`).
5. ✅ **Define a Python-independent self-hosting compiler bootstrap path** (Owner: Compiler/Runtime, Completed)
   - Success: `docs/self_hosting_port_plan.md` documents a staged bootstrap
     strategy where TinyLanguage can compile TinyLanguage without a Python
     runtime dependency, using a minimal platform-specific seed executable per
     target OS as the initial trust anchor.
   - Status: Completed via the concrete task below
     (`docs/self_hosting_port_plan.md`).
6. ✅ **Define an executable optimization plan for native builds** (Owner: Runtime/Compiler, Completed)
   - Success: `docs/native_compiler.md` and `docs/runtime_performance_goals.md`
     include a prioritized optimization backlog for generated executables
     (LLVM pass tuning, opt-level defaults, profile-guided workflow) plus
     benchmark-based acceptance criteria.
   - Status: Completed via the concrete tasks below
     (`docs/native_compiler.md`, `docs/runtime_performance_goals.md`).

### Concrete tasks derived from the drafts

- [x] Add an async-task debugger trace walkthrough to `docs/debugger_guide.md`
  that includes setup steps, the `tiny debug trace` invocation, and expected
  output for multiple concurrently scheduled tasks.
  - Notes: `docs/debugger_guide.md` now includes a CLI-first walkthrough with
    a runnable async sample, breakpoint configuration, expected trace output,
    and interpretation guidance for two concurrently scheduled tasks.

- [x] Draft a `tiny pkg publish --dry-run` CLI spec section that enumerates inputs,
  outputs, and expected artifacts for review in `docs/package_manager_plan.md`.
- [x] Add a minimal dry-run execution path in `tools/tiny_pkg_publish.py` that
  serializes the payload to disk and returns a non-zero exit code when validation
  fails.
  - Follow-up: `tools/tiny_pkg_publish.py` now requires the explicit `--dry-run`
    flag and exits with code `2` when invoked without it, keeping behavior aligned
    with the documented `tiny pkg publish --dry-run` workflow.
- [x] Capture an async-task debugging transcript (commands + outputs) and embed
  it in `docs/debugger_guide.md` as a worked example.
- [x] Extend `docs/performance_budgets_and_baselines.md` with a checklist for
  capturing flamegraphs, tagging baseline snapshots, and filing regressions with
  links to artifacts.
- [x] Add a stdlib deprecation checklist entry to
  `docs/versioning_deprecation_policy.md`, including the expected warning
  timeline and aliasing strategy.
- [x] Finalize the `stdlib.yaml` scope decision and replace the placeholder
  stub behavior with a minimal JSON-compatible implementation (mapping lines +
  JSON literals), including executable tests and examples.
  - Notes: `stdlib/yaml.tiny` now supports parsing `key: value` mappings,
    JSON-style scalar/list/map literals, and `load`/`dump` round-trips;
    coverage lives in `tests/detailtests/test_stdlib_yaml.py` and examples in
    `docs/stdlib_examples.md`.
- [x] Add a self-hosting compiler bootstrap milestone to
  `docs/self_hosting_port_plan.md` that defines seed executable requirements
  (Windows/macOS/Linux), reproducible bootstrap steps, and parity validation
  gates between Python-hosted and Tiny-hosted compilation outputs.
  - Notes: added a dedicated milestone section with per-OS seed trust-anchor
    requirements, staged reproducible bootstrap flow, explicit parity gates,
    and milestone exit criteria in `docs/self_hosting_port_plan.md`.
- [x] Add an executable-optimization milestone to `docs/native_compiler.md`
  that defines default `--llvm-opt-level` / `--opt-level` profiles, optional
  profile-guided optimization capture steps, and required benchmark deltas
  before changing release defaults.
  - Notes: added a dedicated milestone section in `docs/native_compiler.md`
    with profile defaults (`dev`/`release`/`max`), an optional PGO workflow,
    and explicit benchmark/stability/reproducibility gates for default changes.
    Added a matching prioritized optimization backlog + acceptance criteria in
    `docs/runtime_performance_goals.md` to keep cross-doc ownership aligned.

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
