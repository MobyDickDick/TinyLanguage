# Open tasks archive

Archived from `docs/open_tasks.md` on 2026-03-19.

## Proposed production-readiness tasks (completed)

### Standard library completeness
- [x] Publish a stability/maturity tier for each stdlib module and a policy for
  deprecations.
  - Notes: module tiers are defined in `docs/stdlib_compatibility.md`, with the
    deprecation policy captured in `docs/versioning_deprecation_policy.md`.

Archived from `docs/open_tasks.md` on 2026-02-06.

## Proposed production-readiness tasks (completed)

### Package + module system (MVP → usable)
- [x] Add semver-aware dependency constraints and a minimal registry schema.
  - Notes: `src/tiny_pkg_resolution.py` resolves SemVer constraints and selects
    registry versions from a minimal JSON index; `docs/package_manager_plan.md`
    documents the initial registry metadata schema with checksum fields.

Archived from `docs/open_tasks.md` on 2026-03-19.

## Proposed production-readiness tasks (completed)

### Package + module system (MVP → usable)
- [x] Implement a real package manager prototype (`tiny pkg`) with dependency
  resolution, lockfiles, and offline cache support.
  - Notes: wired `tiny pkg` into the main CLI entrypoints, extended vendoring
    to download and cache registry artifacts under `.tiny-cache`, and added
    checksum verification for cached archives.

Archived from `docs/open_tasks.md` on 2026-03-18.

## Proposed production-readiness tasks (completed)

### Language + runtime stability
- [x] Stabilize runtime error taxonomy with machine-readable codes and update
  all backends to emit consistent error metadata.
  - Notes: centralized runtime error codes + hints in `src/tiny_language_error_codes.py`,
    routed parser/runtime/native VM classification through the shared helper, and
    ensured native VM formatting includes codes and hints.

Archived from `docs/open_tasks.md` on 2026-02-06.

## Proposed production-readiness tasks (completed)

### Language + runtime stability
- [x] Close remaining semantic ambiguities with executable spec tests (e.g.,
  numeric overflow, error propagation, evaluation order in edge cases).
  - Notes: added targeted spec tests for error propagation/evaluation order and
    numeric overflow edges in `tests/detailtests/test_semantics_suite.py` and
    `tests/detailtests/test_number_overflow.py`.

Archived from `docs/open_tasks.md` on 2026-02-06.

## Proposed production-readiness tasks (completed)

### Language + runtime stability
- [x] Freeze a language spec v1.0 by tagging mandatory vs. experimental
  features, then gate “v1-only” programs in CI.
  - Notes: added a v1 feature-status section in `docs/language_spec.md` and
    enforced v1-only gating for experimental syntax in CLI + parser entrypoints.

Archived from `docs/open_tasks.md` on 2026-03-17.

## Longer-term backlog (completed)

- [x] Module resolution and package manager roadmap implementation.
  - Notes: implemented std/pkg module resolution rules and package CLI workflows
    (`tiny pkg init/add/remove/update/vendor`) with lockfile-aware vendoring.

Archived from `docs/open_tasks.md` on 2026-02-06.

## Longer-term backlog (completed)

- [x] Optional type inference and gradual typing track updates.
  - Notes: updated optional inference guidance and typing track status in
    `docs/gradual_typing.md` and `docs/typing_track_plan.md`.

Archived from `docs/open_tasks.md` on 2026-03-16.

## Near-term priorities (completed)

- [x] Stabilize formatter + lints + LSP workflows.
  - Owner: Tooling
  - Success: Documented formatter rules, lint profiles, and LSP smoke tests.
  - References: `docs/formatter_rules.md`, `docs/developer_tooling_workflows.md`,
    `docs/lsp_smoke_tests.md`.

Archived from `docs/open_tasks.md` on 2026-02-05.

## Near-term priorities (completed)

- [x] Refine linter “must-use” and unreachable-code checks.
  - Owner: Language Core
  - Success: Lints cover control-flow exits and flag unreachable code with tests.

Archived from `docs/open_tasks.md` on 2026-02-04.

## Refreshed near-term backlog (completed)

- [x] Improve error positions and messages (line/column spans, unified error type).
  - Owner: Language Core
  - Success: Source spans propagate through tokens + AST; diagnostics include consistent line/column ranges.

Archived from `docs/open_tasks.md` on 2026-02-03.

## Expansion roadmap follow-ups (completed)

- [x] Add self-hosting parity snapshots for CLI + LSP diagnostics.
  - Owner: Tooling
  - Success: Parity tests compare Python vs Tiny CLIs for exit codes + diagnostics formatting.

Archived from `docs/open_tasks.md` on 2026-02-02.

## Native backend documentation updates (completed)

- [x] Expand native backend stability docs (C backend + LLVM status).
  - Owner: Native Backends
  - Success: `docs/c_backend.md` and LLVM notes updated with current limitations and usage.

Archived from `docs/open_tasks.md` on 2026-02-02.

## Backlog refresh (completed)

- [x] Publish a refreshed near-term backlog (owners + success criteria).
  - Owner: Project Lead
  - Success: Top 5 tasks confirmed, prioritized, and time-boxed in
    `docs/open_tasks.md`.

Archived from `docs/open_tasks.md` on 2026-02-01.

# Open tasks

This list captures the currently planned work items for TinyLanguage. The tasks
are grouped by area and can be tackled independently.

## Backlog refresh (active)

The items below keep the backlog actionable. They should be completed before
adding new multi-week features so that priorities and ownership stay current.

- [x] Refresh the backlog from `docs/roadmap_next.md` and record the top
  3-5 near-term tasks with clear owners and success criteria.
  - **Finalize language spec alignment** (Owner: Language Core Lead)
    - Success: `docs/language_spec.md` updated with evaluation order, scoping,
      error handling, and concurrency semantics; referenced by tests or lints.
  - **Shared diagnostic schema rollout** (Owner: Tooling Lead)
    - Success: interpreter + tooling emit the same structured error fields and
      formatting with parity coverage in tests.
  - **LSP feature expansion** (Owner: Developer Experience Lead)
    - Success: rename, references, code actions, and formatting hooks supported
      and documented with request/response matrix.
  - **Package/module resolution plan** (Owner: Ecosystem Lead)
    - Success: module resolution rules finalized and package manager roadmap
      milestones captured in `docs/package_module_roadmap.md`.
- [x] Add a short "next milestone" section that names the target release or
  timeframe for the refreshed tasks.
- **Next milestone:** Post-1.0 stabilization + roadmap kick-off, targeting the
  next minor release and a 4-6 week execution window for the backlog refresh
  items above.
- [x] Confirm that completed tasks are archived so this file only tracks
  current work.

## Full-language readiness (new)

See `docs/full_language_readiness.md` for a centralized checklist of remaining
work needed to ship TinyLanguage as a complete, production-ready programming
language.

## Roadmap refresh (proposed)
- [x] Publish a TinyLanguage roadmap document that groups planned work by
  language core, type system, runtime, tooling, and ecosystem maturity.
- [x] Expand the language specification with explicit evaluation-order rules,
  concurrency semantics, and versioning/deprecation policies.
- [x] Plan an optional static typing track (annotations + gradual typing) and
  identify the minimal type-checking passes needed for early wins. (See
  `docs/typing_track_plan.md`.)
- [x] Define a package/module system roadmap (namespaces, versioning, lockfiles,
  dependency resolution) and outline a minimal CLI for it. (See
  `docs/package_module_roadmap.md`.)
- [x] Document runtime-performance goals (interpreter vs. C/LLVM backends),
  including optimization phases and profiling workflows.
- [x] Outline a conformance and compatibility test strategy (spec tests +
  cross-backend parity suites). (See
  `docs/conformance_compatibility_test_strategy.md`.)
- [x] Create a standard library expansion plan with prioritized modules and
  test coverage expectations. (See `docs/stdlib_expansion_plan.md`.)
- [x] Break down the stdlib expansion plan into actionable implementation tasks.
  (See `docs/stdlib_expansion_tasks.md`.)

## Roadmap-derived tasks (from `docs/roadmap_next.md`)
- [x] Align the language specification updates with the roadmap's language core
  scope (evaluation order, scoping, error handling, concurrency).
- [x] Define a shared diagnostic error schema for interpreter + tooling.
- [x] Introduce optional type annotations with a gradual-typing strategy.
  (Documented in `docs/gradual_typing.md`.)
- [x] Build a minimal type-checking pass that can run in lints/CI.
- [x] Document optimization stages and performance targets for interpreter, C,
  and LLVM backends.
- [x] Establish profiling + benchmarking workflows for regression tracking.
- [x] Expand LSP features (rename, references, code actions, formatting hooks).
- [x] Improve debugging workflows (breakpoints, watch expressions, variable
  views). (See `docs/debugger_workflows.md`.)
- [x] Draft project scaffolding/templates and versioned CLI ergonomics.
- [x] Specify module resolution rules (local vs. stdlib vs. external packages).
  (See `docs/package_module_roadmap.md`.)
- [x] Define a package manager plan (lockfiles, registry layout, semantic
  versioning). (See `docs/package_module_roadmap.md`.)
- [x] Maintain conformance + cross-backend parity test suites.
- [x] Publish compatibility matrices and migration guides for major releases.

## Next tasks (shortlist)
- [x] Add CI/regression checks that assert no live heap allocations remain after
  test runs (use `heap_leak_report` or equivalent harness output).
- [x] Formalize ownership/aliasing rules for heap pointers (single-owner or
  borrow model) and update language docs + lint rules accordingly.
- [x] Parity pass: bring native VM and LLVM/C backends up to interpreter-level
  heap safety checks (invalid pointer/index, double delete, leak diagnostics).
- [x] Standardize developer tooling workflows (LSP defaults, lint profiles) and
  document recommended editor setup.
- [x] Expand stdlib coverage with parity tests for missing or incomplete
  Python-style modules (prioritize commonly used APIs).
- [x] Extend LSP capabilities beyond hover/completion (rename, references, code
  actions, formatting hooks) and document the supported request matrix.
- [x] Improve debugging workflows by specifying breakpoint, watch, and variable
  view behavior for the debugger adapters + CLI tooling.
- [x] Draft project scaffolding/templates and versioned CLI ergonomics for new
  packages, including a minimal init flow and workspace layout.
- [x] Specify module resolution precedence (local vs. stdlib vs. external
  packages) and define how ambiguous imports are surfaced to users.
- [x] Define a package manager plan that covers lockfiles, registry layout,
  semantic versioning, and dependency graph resolution.
- [x] Maintain conformance + cross-backend parity test suites with a published
  compatibility matrix and upgrade/migration guides per release.

## Follow-up tasks from docs (active)

These items consolidate next steps and open questions called out in other
documentation so they can be tracked alongside the main backlog.

### Release plan follow-ups (from `docs/release_plan_v1.md`)
- [x] Add this follow-up tracking section for release-plan and math-syntax items.
- [x] Audit `docs/language_spec.md` against current interpreter behavior.
- [x] Audit `docs/tutorial.md` + demo commands against current CLI output.
- [x] Expand regression coverage for recent fixes and high-risk features.
- [x] Write release notes and finalize the release tag/publishing checklist.
- [x] Schedule a release candidate window and perform a full doc + demo run-through
  (see `docs/release_candidate_runthrough.md`).

### Math syntax experiments (from `docs/math_syntax_exploration.md`)
- [x] Trial the `#[ ... ]` formula delimiter with existing precedence rules.
- [x] Decide whether formula mode needs a separate operator table.
- [x] Define formatter rules for math blocks to keep diffs minimal.

## Release 1.0 readiness checklist (open)
- [x] Must-have interpreter features implemented and documented.
- [x] Language spec updated and consistent with current behavior.
- [x] README, tutorial, and demo command docs verified against current CLI output.
- [x] Versioning/location for `1.0.0` documented and updated (stored in `VERSION`,
  `CHANGELOG.md`, and release tags).
- [x] Release notes + tag plan prepared.

## Release 1.0 scope checklist (complete)
- [x] Scope frozen (interpreter + core language only).
- [x] Language spec audited and updated against current interpreter behavior.
- [x] Tutorial audited and demo commands verified.
- [x] Regression suite expanded for recent fixes and high-risk features.

## Goals and research ideas (requested)

These items are exploratory and may need deeper design/prototyping before they
become concrete tasks.

- [x] Inventory Python entrypoint scripts and map Tiny equivalents (plus gaps)
  in `docs/python_program_parity.md`.
- [x] Convert remaining Python entrypoint scripts into Tiny programs, keeping
  parity snapshots and documenting any Tiny-only rewrites needed for features
  that do not map 1:1.
- [x] Document every program line (Tiny + Python) with both high-level intent
  and line-level rationale; rely on structured cross-references when repeating
  patterns. (See `docs/program_line_reference_generate_doc_reference.md`.)
- [x] Minimize heap usage by preferring fixed-size arrays or stack-friendly
  constructs where semantics allow it (requires a clear ownership/mutation model
  to avoid accidental aliasing). See `docs/heap_usage_guidelines.md`.
- [x] Explore math-oriented syntax/notation (tuple-based block forms, formula
  syntax, stack-edit or LaTeX-like constructs) with careful incremental trials
  to avoid destabilizing readability or tooling. See
  `docs/math_syntax_exploration.md`.
- [x] Establish a "strict-by-default" safety profile to reduce unintended side
  effects and runtime errors (explicit mutability, purity annotations, stricter
  effect boundaries, and safer defaults in the stdlib). See
  `docs/strict_by_default_safety_profile.md`.

## Additional suggested tasks

- [x] Define a formal, testable semantics suite for side effects and evaluation
  order so strict-mode guarantees are measurable.
- [x] Add static analysis checks for heap/array aliasing and bounds safety to
  guide the heap-to-array migration effort.
- [x] Evaluate a documentation tooling pipeline (e.g., docstrings + generated
  reference) to make line-level commentary manageable at scale.

## Recently completed tasks

- [x] Publish upgrade guides and automated migration tooling for each minor
  release (see `docs/release_minor_upgrade_guides.md` and
  `tools/release/prepare_minor_upgrade.py`).
- [x] Enable heap lifetime lints by default (opt-out flag) and document the new
  default safety posture.
- [x] Evaluate a documentation tooling pipeline and add a deterministic docstring
  reference generator plus usage notes for future upkeep.
- [x] Create a Python-to-Tiny migration guide with known gaps, recommended
  refactors, and tooling automation opportunities.
- [x] Re-evaluate `{}` usage: clarify that curly braces are reserved for struct
  literals/destructuring, and document when to use ordered arrays or stdlib
  `Set`/`Map` types instead of unordered literals.
- [x] Define a manual heap-lifetime safety profile and add opt-in lints that
  detect use-after-free and leak-prone pointer rebinding in the interpreter.
- [x] Keep the structured concurrency demo in `src_tiny/` updated as new task
  scope features land (e.g., timeout policies, new task metadata).
- [x] Review the native backend error suite when adding new opcodes to ensure
  diagnostics stay aligned with the interpreter. (Started: added a check that
  verifies the supported-opcode list stays in sync with the enum.)
- [x] Add a focused regression suite for native backend error diagnostics,
  covering `NotImplementedError` cases and unknown opcode handling.
- [x] Document module import constraints for the native/LLVM pipeline in
  `docs/native_compiler.md`, including examples of allowed module literals.
- [x] Add a Tiny demo that exercises structured concurrency task scopes and
  cancellation tokens, plus a short README in `src_tiny/` describing the flow.
- [x] Add regression coverage for `JSON.stringify` round-tripping heap-backed
  collections (`Map`, `Set`, `Deque`) and nested lists.
- [x] Expand CLI smoke tests to include failure cases for `File.remove` and
  missing-path diagnostics in stdlib helpers.
- [x] Add snapshot tests for LSP `hover`/`completion` flows in the self-hosted
  Tiny language server entry points.

## Frontend / language

- [x] Improve error positions and messages (tokens + AST nodes carry line/column; unify error type with optional `SourceSpan`).
- [x] Refine the linter (must-use across control flow; unreachable-code warnings).

## Type discipline

- [x] Prevent implicit type changes (e.g., `def i = 5; i = 0.5;` ⇒ error unless explicitly allowed).
- [x] Add optional simple type inference (e.g., `def x = 0;` ⇒ `number`).

## Runtime

- [x] Harden the heap API (invalid pointer diagnostics, out-of-bounds details, double-delete detection, leak tracking, and boolean pointer/index rejection).
- [x] Expand the test suite (nested arrays, many `new/delete` pairs, deep recursion, heap-API error scenarios).

## Test coverage for Tiny programs

- [x] Add regression tests for remaining `src_tiny` demos and utilities not covered by `tests/` or `src/run_all.py` (notably: `stdlib_collections_demo.tiny`, `tiny_language_compiler_cli.tiny`, `tiny_language_eval.tiny`, `factorial.tiny`, `simpelst_Python_program.tiny`, `native_python_bytecode.tiny`, `python_namespace_typed_demo.tiny`, `Simpelst_Tiny_Language_Programm.tiny`, `tiny_language_preamble.tiny`, `tiny_language.tiny`, `try_catch_demo.tiny`, `tiny_language_codegen_c.tiny`, `test_flush.tiny`, `copy_rosetta_samples.tiny`, `tinyc_cli.tiny`, `run_all.tiny`, `tiny_language_codegen_py.tiny`, `rosetta_fizzbuzz.tiny`, `tiny_language_codegen_llvm.tiny`, `transpile_rosetta.tiny`, `rosetta_word_count.tiny`, `formatter.tiny`, `tiny_language_api.tiny`, `match_demo.tiny`, `fizzbuzz.tiny`, `stdlib_io_random_demo.tiny`, `tiny_language_runtime.tiny`, `rosetta_factorial.tiny`, `result_demo.tiny`, `language_server.tiny`, `console_sum.tiny`, `tiny_errors.tiny`, `tiny_language_highlighting.tiny`).
- [x] Add regression coverage for standalone Tiny demos outside `src_tiny` (e.g., `str_tiny/returned_params_demo.tiny`, `examples/rosetta/*/*.tiny`, `src/sum_product_match.tiny`).
- [x] Add test programs for the Tiny stdlib implementations that are currently untested (`stdlib/{string,math,collections,random,io}.tiny`).

## Tooling

- [x] Improve CLI wrapper ergonomics and documentation.
- [x] Stabilize formatter + lints + language-server workflows.

## Structured concurrency

- [x] Add `async`/`await` syntax while keeping `spawn`/`join` for compatibility.
- [x] Introduce channel primitives (`Async.channel`, `Async.send`, `Async.recv`, `Async.close`) after task scopes stabilize.
- [x] Formalize cancellation token semantics for joins, timeouts, and linked tasks.

## Native backends

- [x] Keep the C backend stable and documented.
- [x] Continue LLVM emission experiments and validation coverage.

## Stdlib + compatibility

- [x] Port prioritized Python stdlib modules (`math`, `random`, `string`, `datetime`) with comparison tests.
- [x] Add a `datetime` parity map plus ISO parsing/formatting snapshot tests.
- [x] Ship a small Julia subset (e.g., `Statistics` with `mean`/`std`) and document API differences.

## Future roadmap ideas

- [x] Extend the Tiny stdlib with additional Python-style modules (e.g., `json`, `pathlib`, `os`) and add comparison tests.
- [x] Stabilize the native compiler CLI with release-ready flags, diagnostics, and optimization profiles.
- [x] Expand self-hosting parity coverage with broader Python-vs-Tiny snapshot tests.
- [x] Build a spec-compliance test suite that validates the documented EBNF grammar and lexer/token rules.
- [x] Close remaining backend feature gaps so the native VM and LLVM pipelines match interpreter capabilities.
- [x] Grow the tooling ecosystem with richer language-server features, debugging workflows, and project scaffolding commands.


## Completed language work archived on 2026-10-21

The completed TinyLanguage entries below were moved from the active task
list when the deployment-readiness work packages were opened. Historical
completion notes describe their original scope; they do not supersede the
current acceptance criteria in `docs/open_tasks.md`.

- [x] **Enforce ASCII semantics for portable regex escapes**
  (Owner: Language/Stdlib; completed 2026-08-25)
  - Scope: close the Phase 2 determinism gap between the documented ASCII-only
    `\\d`, `\\w`, and `\\s` escapes and Python's default Unicode regex mode.
  - Result: the runtime now compiles the supported regex subset in explicit
    ASCII mode without restricting Unicode literals, classes, or wildcards.
  - Verification: the focused stdlib regression distinguishes ASCII from
    Arabic-Indic digits, accented word characters, and non-breaking spaces
    while retaining Unicode wildcard behavior.

- [x] **Expose a directory-scoped file-system case-sensitivity probe**
  (Owner: Language/Stdlib; completed 2026-08-25)
  - Scope: promote the deferred `stdlib.os` package-tooling capability question
    into a bounded API instead of inferring file-system behavior from the host
    platform.
  - Result: `os.filesystem_case_sensitive(path)` performs a cleanup-safe probe
    in an existing writable directory, while the portability contract keeps
    exact-case paths as the rule for read-only tooling.
  - Verification: the stdlib regression compares the Tiny result with an
    independent host probe and proves that no probe file remains afterward.

- [x] **Port statically approved quarantined sources to TinyLanguage**
  (Owner: Tooling/Program Generator)
  - Scope: execute the next pipeline stage in `docs/tiny_program_daemon.md`
    without weakening the quarantine or executing third-party source.
  - Result: the automatic porter revalidates provenance and the exact passing
    scan report, translates only the supported Python IR subset (or copies
    approved Tiny text), and atomically emits a hashed, versioned audit record.
  - Boundary: every result is marked `ported-unexecuted`; only the separate
    sandbox-test stage may evaluate it.

- [x] **Deepen generated-program loop termination analysis**
  (Owner: Tooling/Program Generator)
  - Scope: execute the first follow-up criterion in
    `docs/tiny_program_daemon.md` by replacing line-local infinite-loop checks
    with analysis of complete structured cyclic control-flow regions.
  - Result: validation now extracts balanced `while` bodies, recognizes
    literal infinite conditions independent of whitespace, and requires a
    provable update of the comparison's induction variable inside the loop.
  - Verification: focused regressions cover progress through a nested block,
    a loop that updates only unrelated state, and a spaced literal condition.

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

## Program-generator validation update (2026-08-22)

- [x] **Require provably non-zero division operands** (Owner: Tooling/Program Generator)
  - Scope: execute the next follow-up criterion in
    `docs/tiny_program_daemon.md` after structured loop termination analysis.
  - Result: generated programs now accept division only when conservative local
    evidence proves the divisor non-zero; literal zero, unknown parameters, and
    reassignment after a returning zero guard are rejected.
  - Verification: focused regressions cover a returning zero guard, an
    unguarded parameter, and invalidation of guard evidence by reassignment.

## Program-generator resource-bounds update (2026-08-22)

- [x] **Bound generated heap allocations and loop iterations** (Owner: Tooling/Program Generator)
  - Scope: execute the next follow-up criterion in
    `docs/tiny_program_daemon.md` after non-zero divisor analysis.
  - Result: generated programs require fixed heap sizes of at most 4096 slots
    and statically provable comparison-loop bounds of at most 10,000 iterations.
    The logistic-map template now exposes its existing eight-step limit directly
    in the loop condition so it satisfies the same conservative gate.
  - Verification: focused regressions cover accepted bounded resources, dynamic
    heap sizes, excessive iteration counts, and parameter-dependent loop bounds.

## Program-generator determinism update (2026-08-22)

- [x] **Add an optional deterministic generation profile** (Owner: Tooling/Program Generator)
  - Scope: execute the next follow-up criterion in
    `docs/tiny_program_daemon.md` after resource-bound validation.
  - Result: `--deterministic` rejects generated programs that call supported
    time or random sources, while the default profile remains backward
    compatible and documentation text cannot trigger false positives.
  - Verification: focused regressions cover time and random calls, the opt-in
    default, comment/string handling, and CLI activation.

## Program-generator readability update (2026-08-22)

- [x] **Enforce generated-program style and readability rules**
  (Owner: Tooling/Program Generator)
  - Scope: execute the final follow-up criterion in
    `docs/tiny_program_daemon.md` after the deterministic generation profile.
  - Result: generated programs require an explanatory comment and `snake_case`
    declarations, with category-specific limits of 80 or 100 source lines.
  - Verification: focused regressions cover missing comments, invalid function
    and variable names, category limits, and all curated default templates.

## Program-source quarantine update (2026-08-22)

- [x] **Acquire allowlisted external sources into quarantine**
  (Owner: Tooling/Program Generator)
  - Scope: execute the first documented pipeline package after completing the
    local generator quality criteria; acquisition must never execute or parse
    downloaded content.
  - Result: a dedicated CLI accepts HTTPS sources only from RosettaCode and raw
    GitHub, enforces a 256 KiB default limit, revalidates redirect targets, and
    atomically stores non-executable bytes with provenance and a SHA-256 digest.
  - Verification: focused regressions cover byte-exact retention, metadata and
    permissions, rejected schemes/hosts/credentials/ports/redirects, and the
    size boundary. Security scanning remains the next pipeline package.

## Program-source security-scan update (2026-08-22)

- [x] **Statically scan quarantined external sources**
  (Owner: Tooling/Program Generator)
  - Scope: execute the second documented import-pipeline package without
    parsing, importing, or executing untrusted content.
  - Result: the scanner verifies the immutable payload against its provenance,
    permits only UTF-8 `.py` and `.tiny` sources, rejects binary and dangerous
    static signatures, and writes an atomic versioned verdict. Only a passing
    report names automatic porting as an allowed next stage.
  - Verification: focused regressions cover a passing report, content-type and
    signature rejections, tampered provenance, symlinks, and report permissions.
    Automatic TinyLanguage porting remains the next pipeline package.

## Program-source sandbox update (2026-08-23)

- [x] **Run and assess approved ports under resource limits**
  (Owner: Tooling/Program Generator)
  - Scope: execute the next documented import-pipeline package after automatic
    porting without trusting a stale or substituted output artifact.
  - Result: the sandbox stage revalidates the port report and output hash, runs
    TinyLanguage in an isolated child process with an empty working directory,
    timeout and OS resource ceilings, and records a versioned pass/fail report.
  - Verification: focused regressions cover a successful program, a runtime
    failure that is not promoted, and byte tampering after port approval.
    Optional GUI-wrapper generation remains the next pipeline package.

## Program-source GUI-wrapper update (2026-08-23)

- [x] **Generate an optional GUI for approved sandbox results**
  (Owner: Tooling/Program Generator)
  - Scope: complete the final documented import-pipeline package without
    allowing a desktop launcher to bypass the preceding sandbox boundary.
  - Result: the generator revalidates the exact source and captured-output
    hashes from a passing sandbox report, embeds that output in a read-only Tk
    presentation, and records source, output, and wrapper hashes in a versioned
    audit report.
  - Verification: focused regressions compile the generated launcher, confirm
    that it contains no subprocess execution path, and reject failed or
    subsequently tampered sandbox results. The documented pipeline is complete.
