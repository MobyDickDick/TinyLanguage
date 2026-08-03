# Open tasks

This file tracks only active work items for TinyLanguage. Completed tasks are
archived in `docs/open_tasks_archive.md`.

## Current tasks

## Next documented work package (completed 2026-08-03)

- [x] **Complete the TinyCPU AP 6 symbolic ISA control surface**
  (Owner: TinyCPU/Hardware)
  - Success: extend the provisional hardware decode boundary across every
    addressing mode, arithmetic and logic operation, jump, I/O instruction,
    and sticky-error path; parameterized structural checks must cover every
    instruction defined by the Python ISA.
  - Result: the six-bit provisional decoder now exposes every symbolic ISA
    control, all three branch-condition inputs, and all six error-set outputs;
    the machine-readable profile and tests derive complete coverage from
    `INSTRUCTION_SET`, while the AP 5 countdown remains frozen.
  - Follow-up: AP 7 must assign versioned opcodes and a word layout and use an
    encoder to produce the ROM image and listing.

## Next documented work package (completed 2026-08-03)

- [x] **Integrate the TinyCPU AP 5 core program**
  (Owner: TinyCPU/Hardware)
  - Success: load a reproducible counting-loop fixture and compare every
    clock-edge state, output, and halt result with the Python VM.
  - Result: the provisional ROM now contains a core-only countdown program;
    its 17-edge JSON trace freezes PC, accumulator validity, flags, watched
    memory, output, and halt state, and a reusable comparator reports divergent
    edge fields.
  - Follow-up: AP 6 can extend the remaining addressing modes, arithmetic,
    logic, jumps, and I/O while retaining the AP 5 trace as a core regression.

## Next documented work package (completed 2026-08-03)

- [x] **Implement TinyCPU AP 4 fetch and decode**
  (Owner: TinyCPU/Hardware)
  - Success: add a 12-bit PC, instruction ROM, and decode/control path for
    `LOAD_CONST`, `STORE_ADDRESS`, `ADD_ADDRESS`, `JUMP_NOT_ZERO`, `PRINT`, and
    `HALT`; an out-of-range PC must set `ADDR` and halt with an error.
  - Result: the connected `FetchDecode` sheet exposes the six core controls,
    operand and PC state, selects sequential or conditional-jump PC updates,
    and turns the program-limit comparison into `SET_ADDR` plus `HALT_ERROR`.
    The machine-readable contract and structural regressions freeze AP 4.
  - Follow-up: AP 5 must load a reproducible counting-loop fixture and compare
    every clock-edge state, output, and halt result with the Python VM.

## Next documented work package (completed 2026-08-03)

- [x] **Implement TinyCPU AP 3 memory and error registers**
  (Owner: TinyCPU/Hardware)
  - Success: connect value and validity RAM to one address, write-enable, and
    clock interface; implement all six set-dominant sticky error flags with a
    shared `CLEAR_ERROR`; freeze both interfaces in the hardware profile and
    structural regressions.
  - Result: the Logisim `Memory` and `ErrorFlags` sheets are connected, the
    contract inspector validates their pins and logic components, and AP 3 is
    marked complete in the hardware roadmap.
  - Follow-up: AP 4 must add PC, instruction ROM, and fetch/decode control for
    the documented core instruction subset.

## Next documented work package (completed 2026-08-03)

- [x] **Reject duplicate keys in YAML block mappings**
  (Owner: Language/Stdlib)
  - Success: reject duplicate mapping keys instead of silently retaining the
    last value, and identify the duplicate's one-based source line at the root,
    in nested mappings, and in inline mapping entries inside block lists.
  - Result: the conservative YAML parser now reports duplicate keys with their
    source line, and parameterized regressions cover all three mapping shapes.
  - Follow-up: advanced YAML features such as anchors, aliases, tags, complex
    keys, and multi-document streams remain explicit non-goals.

## Next documented work package (completed 2026-08-02)

- [x] **Add line-aware diagnostics for malformed YAML block collections**
  (Owner: Language/Stdlib)
  - Success: deterministic parse failures identify the offending source line
    for inconsistent indentation, tab indentation, and mixed collection styles.
  - Result: YAML block-parser errors now include one-based input line numbers,
    with parameterized regressions covering the three malformed-input classes.
  - Follow-up: advanced YAML features such as anchors, aliases, tags, complex
    keys, and multi-document streams remain explicit non-goals.

## Next documented work package (completed 2026-08-02)

- [x] **Support inline mapping entries inside YAML block lists**
  (Owner: Language/Stdlib)
  - Success: parse sequence items whose first string-keyed mapping entry shares
    the dash line (for example, `- name: Tiny`), including continuation keys
    and recursively nested block collections.
  - Result: inline mapping items are normalized into the recursive block
    parser, and a regression locks multiple mapping items, scalar continuation
    keys, nested lists, and colon-containing scalar values to exact JSON.
  - Follow-up: advanced YAML features such as quoted keys, anchors, aliases,
    tags, and multi-document streams remain explicit non-goals.

## Next documented work package (completed 2026-07-26)

- [x] **Extend `stdlib.yaml` parsing to nested block collections**
  (Owner: Language/Stdlib)
  - Success: parse consistently indented block-style lists and string-keyed
    maps recursively while retaining JSON-compatible scalar types.
  - Result: the conservative YAML parser now recognizes nested map/list blocks,
    empty mapping values introduce child collections, and a regression locks a
    mixed map/list document to its exact JSON representation.
  - Follow-up: inline mapping entries inside block lists (for example,
    `- name: Tiny`) remain outside this small grammar and need separate scope.

## Next documented work package (completed 2026-07-26)

- [x] **Lock `stdlib.yaml` JSON-compatible scalar round-trip coverage**
  (Owner: Language/Stdlib)
  - Success: reparse deterministic YAML serialization and verify that integers,
    negative and decimal numbers, booleans, nulls, empty and Unicode strings,
    and inline lists retain their values and scalar types.
  - Result: YAML scalar parsing now delegates valid JSON scalar text to the
    runtime JSON parser, while plain YAML strings remain strings; a regression
    checks the complete reparsed structure against the typed source values.
  - Follow-up: nested block-style lists and maps remain outside the conservative
    initial YAML subset and require a separately scoped parser extension.

## Open-task audit (2026-07-22)

- [x] **Re-validate the documented backlog before opening the next cycle**
  (Owner: Project Lead)
  - Result: no unchecked checklist entries (`- [ ]`) remain in the tracked
    planning surfaces (`docs/`, `documentation_tasks.md`, and `README.md`)
    as of 2026-07-22, so there is no implementation-ready documented work
    package to execute without first adding newly scoped work.
  - Follow-up: start the next cycle by triaging fresh candidates into this
    file with owners, success criteria, and acceptance notes before future
    "next documented work package" requests are executed.


## Next documented work package (completed 2026-07-22)

- [x] **Lock `stdlib.csv` parser round-trip edge coverage**
  (Owner: Language/Stdlib)
  - Success: add a deterministic CSV round-trip regression for quoted fields,
    embedded newlines, and CRLF input normalization, as called out by the data
    interchange parser round-trip follow-up in `docs/stdlib_expansion_plan.md`.
  - Result: `tests/detailtests/test_stdlib_csv.py` now reparses serialized CSV
    output and verifies stable row counts plus field preservation for embedded
    delimiters and multiline fields.
  - Follow-up: YAML remains optional for Phase 2 and should receive equivalent
    round-trip coverage once a backend implementation is available.

## Active timebox (2026-02-15 refresh)

The following items were promoted from the roadmap into an active execution
window. They remain open until the listed success criteria are met.

- [x] **Improve source-span accuracy in parser/interpreter diagnostics**
  (Owner: Frontend)
  - Success: parser/runtime errors include stable line+column spans and at
    least one regression test locks in the emitted span for malformed input.
  - Notes: added `test_parser_error_reports_stable_multiline_span_for_malformed_input`
    in `tests/detailtests/test_spans.py` to lock parser `TinyLangError` span
    coordinates and rendered line context for malformed input.

- [x] **Strengthen heap API diagnostics and safety checks** (Owner: Runtime)
  - Success: invalid pointer, out-of-bounds access, and double-delete paths
    produce distinct user-facing messages with dedicated detail tests.
  - Notes: added `tests/detailtests/test_heap_api_diagnostics_messages.py`
    with dedicated coverage for invalid-pointer (`heap_get(0, 0)`),
    out-of-bounds (`heap_get(ptr, 5)`), and double-delete diagnostics,
    asserting each path emits the expected user-facing message pattern.

- [x] **Expand heap stress/regression coverage** (Owner: Runtime)
  - Success: add tests for nested arrays, larger `new/delete` churn, and deep
    recursion interaction with heap allocation/deallocation.
  - Notes: expanded `tests/detailtests/test_heap_api_errors.py` with dedicated
    nested-pointer, high-churn allocation/deallocation, and deep-recursion
    heap-unwind scenarios that assert leak-report stability and expected output.

- [x] **Tooling ergonomics pass for CLI + formatter/LSP workflow docs**
  (Owner: Tooling)
  - Success: `docs/cli_workflows.md` and
    `docs/language_server_workflows.md` each receive one end-to-end workflow
    update validated by the corresponding tests.
  - Notes: `docs/cli_workflows.md` now documents the typecheck-then-backend
    execution workflow and `docs/language_server_workflows.md` documents the
    project formatting/code-actions roundtrip; both flows are locked by
    `test_tiny_cli_typecheck_then_backend_run_workflow` and
    `test_cli_project_formatting_hook_matches_format_output`.


## Priority execution update (2026-05-02)

- [x] **Process highest-priority active task** (Owner: Project Lead)
  - Result: no unchecked (`- [ ]`) tasks remain in tracked planning documents
    (`docs/`, `documentation_tasks.md`) as of 2026-05-02, so execution focus
    shifts to preparing the next triage cycle and promoting new candidates into
    the upcoming active timebox.


## Next documented step (executed 2026-05-04)

- [x] **Prepare the next triage cycle candidate slate** (Owner: Project Lead)
  - Success: promote at least three clearly scoped candidates into a dated, owner-tagged shortlist so the upcoming triage meeting can convert them into an active timebox without re-discovery work.
  - Notes: consolidated a 2026-06 triage shortlist with owners, sequencing, and acceptance outcomes directly in this tracker so the next planning pass can promote items without additional discovery.

### 2026-06 triage shortlist (ready for promotion)

1. **Typecheck CI gate trial** (Owner: Language/Tooling) — completed 2026-06-06
   - Outcome target: add an opt-in CI job that runs type-check/lint mode on a curated fixture set and publishes a baseline report for false-positive review.
   - Result: added a manually dispatched `typecheck-gate-trial` CI job, a deterministic reporting tool, three manifest-backed fixtures (including an E009 positive control), and regression coverage for baseline drift and review-required findings.
2. **Native backend error-parity audit** (Owner: Runtime/Compiler) — completed 2026-06-06
   - Outcome target: run a focused interpreter vs. native error-message parity audit and capture remaining deltas as bounded follow-up issues.
   - Result: added an executable exact-message parity matrix, documented the audit method and passing scenarios, and bounded the remaining native `len` and exception-metadata deltas as `NBEP-001` and `NBEP-002`.
3. **Package manager reproducibility hardening** (Owner: Ecosystem) — completed 2026-06-11
   - Outcome target: extend lockfile reproducibility coverage with additional path edge-cases and document the deterministic rendering contract.
   - Result: lockfile rendering now lexically normalizes redundant path segments and dependency-override paths, TOML-escapes every persisted string, and is covered by repeated-write, LF-ending, quoted-path, override, and dot-segment regressions. The byte-level ordering, path, encoding, and checksum rules are documented in `docs/package_manager_plan.md`.

## Next documented work package (completed 2026-06-12)

- [x] **NBEP-001: implement native `len` built-in parity**
  (Owner: Runtime/Compiler)
  - Success: valid string, collection, and heap-pointer calls return the same
    value in the interpreter and native VM; unsized values produce the exact
    interpreter `E005` diagnostic.
  - Result: added native `len` dispatch and parity regressions for all supported
    value categories, moved the unsized-value scenario into the exact-message
    matrix, and closed `NBEP-001` in the audit document.
  - Follow-up: `NBEP-002` remains separately bounded to exception metadata and
    deliberately does not change CLI-rendered diagnostics.

- [x] **NBEP-002: inventory native exception metadata parity**
  (Owner: Runtime/Compiler)
  - Success: inventory error type, code, hint, position, and span for every
    scenario in the native error-parity audit; publish the intended Python API
    contract without changing CLI-rendered text.
  - Result: added an executable metadata matrix for all five audit scenarios and
    documented the supported distinction between structured `TinyLangError`
    failures and opaque native `RuntimeError` failures. Backend-neutral clients
    use the already parity-checked rendered diagnostic.
  - Follow-up: no bounded issues remain from the focused native error-parity
    audit; future deltas receive new issue identifiers and explicit scope.

## Next documented work package (completed 2026-06-13)

- [x] **Resolve the `stdlib.path` architecture and normalization contract**
  (Owner: Language/Stdlib)
  - Success: decide whether `stdlib.path` wraps `File` or owns a dedicated
    namespace; document the filesystem boundary and lock the decision with a
    regression covering nonexistent paths plus lexical `.`/`..` reduction.
  - Result: selected a dedicated, filesystem-independent `Path` namespace,
    documented the boundary in the expansion plan, made `Path.join` apply the
    same lexical normalization as `Path.normalize`, and added an end-to-end
    regression proving path operations do not require the target to exist.
  - Follow-up: the next unresolved Phase 1 decision is the cross-platform
    guarantee for `stdlib.os` separators, case sensitivity, and environment
    variable handling.

## Next documented work package (completed 2026-06-20)

- [x] **Close stale conformance-strategy follow-ups**
  (Owner: Tooling/QA)
  - Success: resolve the remaining open follow-up bullets in
    `docs/conformance_compatibility_test_strategy.md` by tying stdlib ownership
    to the suite-boundary matrix and revalidating the local smoke command
    against the 60-second feedback budget.
  - Result: the stdlib ownership follow-up now points to explicit spec/parity/
    compatibility responsibilities, and the smoke-subset follow-up records the
    `python src/run_all.py --smoke` validation performed on 2026-06-20.
  - Follow-up: future smoke-tier expansions should keep the same command under
    60 seconds or move slower checks into nightly/full CI lanes.

## Next documented work package (completed 2026-06-20)

- [x] **Define the `stdlib.os` cross-platform contract**
  (Owner: Language/Stdlib)
  - Success: document separator, case-sensitivity, and environment-variable
    behavior, and lock the contract with regression coverage.
  - Result: `docs/stdlib_expansion_plan.md` now documents the Phase 1
    `stdlib.os` portability boundary; `os.env_case_sensitive()` exposes host
    environment key semantics; and `tests/detailtests/test_stdlib_os.py` covers
    separator, platform, cwd normalization, directory ordering, missing env,
    unset-missing, and case-sensitivity behavior.
  - Follow-up: file-system case sensitivity remains an explicitly host-owned
    property; future package tooling should rely on exact-case fixture paths or
    add a separate capability probe before enforcing case-folding rules.

## Planning notes

- [x] Verified all historical checklist entries below this section remain
  archived/completed and can stay unchanged.
- [x] Promoted a focused set of open tasks from the roadmap so the backlog has
  clear in-progress candidates again.

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

## Open-task audit (2026-04-05)

- [x] Re-read all documentation checklists to identify the next unchecked work item and execute it to completion.
  - Result: no unchecked checklist items remain in `docs/` or in the root documentation task files (`documentation_tasks.md`).
  - Follow-up: kept the backlog in a fully closed state and recorded this verification pass so the next cycle can start by adding new scoped tasks instead of re-auditing historical ones.

## Open-task audit (2026-04-17)

- [x] Re-validated the documentation backlog to find the next unchecked documented task and execute it.
  - Result: there are still no unchecked checklist entries (`- [ ]`) in `docs/`, `documentation_tasks.md`, or `README.md`; the next actionable step is to add newly scoped tasks for the upcoming cycle before further execution work.
  - Follow-up: backlog remains intentionally closed; future "next open task" requests should begin by triaging and adding a new concrete unchecked item into `docs/open_tasks.md`.

## Open-task audit (2026-04-25)

- [x] Convert one documented package-manager open question into an implemented, test-backed decision.
  - Result: `tiny.lock` now persists an optional top-level `toolchain` constraint derived from `[package].tiny_language` in `tiny.toml`, and the behavior is covered by lockfile reproducibility tests.
  - Follow-up: keep the second package-manager open question (signed registry metadata) for the next planning cycle, because it depends on registry threat-model and deployment decisions.


## Priority execution update (2026-05-02, follow-up)

- [x] **Process highest-priority documented open question (package registry signing)** (Owner: Ecosystem)
  - Result: resolved the remaining package-manager open question in `docs/package_manager_plan.md` with a phased decision for metadata signing (v1.1 informational hashes, v1.2 optional verification, v1.3 required signatures for official channels).

## TinyCPU execution update (2026-08-03)

- [x] **AP 7: Maschinenformat und Tooling** (Owner: TinyCPU)
  - Result: froze the version-1 22-bit machine-word layout and opcode table,
    added a range-checking encoder/decoder that emits Logisim ROM images and
    listings, and loaded the generated AP 5 countdown image into the circuit.
  - Verification: instruction-wide roundtrip tests and artifact/circuit parity
    tests protect the encoding contract; AP 8 remains the next work package.
