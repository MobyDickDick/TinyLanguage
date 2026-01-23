# Open tasks

This list captures the currently planned work items for TinyLanguage. The tasks
are grouped by area and can be tackled independently.

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

- [x] Harden the heap API (invalid pointer diagnostics, out-of-bounds details, double-delete detection, leak tracking).
- [x] Expand the test suite (nested arrays, many `new/delete` pairs, deep recursion, heap-API error scenarios).

## Test coverage for Tiny programs

- [x] Add regression tests for remaining `src_tiny` demos and utilities not covered by `tests/` or `src/run_all.py` (notably: `stdlib_collections_demo.tiny`, `tiny_language_compiler_cli.tiny`, `tiny_language_eval.tiny`, `factorial.tiny`, `simpelst_Python_program.tiny`, `native_python_bytecode.tiny`, `python_namespace_typed_demo.tiny`, `Simpelst_Tiny_Language_Programm.tiny`, `tiny_language_preamble.tiny`, `tiny_language.tiny`, `try_catch_demo.tiny`, `tiny_language_codegen_c.tiny`, `test_flush.tiny`, `copy_rosetta_samples.tiny`, `tinyc_cli.tiny`, `run_all.tiny`, `tiny_language_codegen_py.tiny`, `rosetta_fizzbuzz.tiny`, `tiny_language_codegen_llvm.tiny`, `transpile_rosetta.tiny`, `rosetta_word_count.tiny`, `formatter.tiny`, `tiny_language_api.tiny`, `match_demo.tiny`, `fizzbuzz.tiny`, `stdlib_io_random_demo.tiny`, `tiny_language_runtime.tiny`, `rosetta_factorial.tiny`, `result_demo.tiny`, `language_server.tiny`, `console_sum.tiny`, `tiny_errors.tiny`, `tiny_language_highlighting.tiny`).
- [x] Add regression coverage for standalone Tiny demos outside `src_tiny` (e.g., `str_tiny/returned_params_demo.tiny`, `examples/rosetta/*/*.tiny`, `src/sum_product_match.tiny`).
- [x] Add test programs for the Tiny stdlib implementations that are currently untested (`src/stdlib/{string,math,collections,random,io}.tiny` and `stdlib/{string,math,random}.tiny`).

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
- [x] Ship a small Julia subset (e.g., `Statistics` with `mean`/`std`) and document API differences.

## Future roadmap ideas

- [x] Extend the Tiny stdlib with additional Python-style modules (e.g., `json`, `pathlib`, `os`) and add comparison tests.
- [x] Stabilize the native compiler CLI with release-ready flags, diagnostics, and optimization profiles.
- [x] Expand self-hosting parity coverage with broader Python-vs-Tiny snapshot tests.
- [x] Build a spec-compliance test suite that validates the documented EBNF grammar and lexer/token rules.
- [x] Close remaining backend feature gaps so the native VM and LLVM pipelines match interpreter capabilities.
- [x] Grow the tooling ecosystem with richer language-server features, debugging workflows, and project scaffolding commands.
