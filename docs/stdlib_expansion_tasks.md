# Standard library expansion tasks

This checklist derives concrete work items from the standard library expansion
plan so implementation can proceed in small, testable steps.

## Phase 1 tasks (high-value, low-risk)

- [ ] Define the `stdlib.path` API surface (join/split/basename/dirname/extension,
  normalize, directory filtering) and map each helper to runtime capabilities.
  - Deliverables: API table in `docs/stdlib_expansion_tasks.md` (this file) plus
    updates to `docs/stdlib_expansion_plan.md` if new helpers are added.
  - Dependencies: confirm which helpers can be built from `File` primitives vs.
    need runtime additions in `src/tiny_language_runtime.py`.
- [ ] Implement runtime helpers for `stdlib.path` (path normalization + join
  semantics) and add Tiny wrappers in `stdlib/path.tiny`.
  - Deliverables: runtime helper functions + Tiny wrapper module and parity
    mapping notes.
- [ ] Add tests for `stdlib.path` covering cross-platform separators, extension
  handling, and error cases (invalid inputs).
  - Deliverables: `tests/detailtests/test_stdlib_path.py` with fixture-based
    coverage for join/split/basename/dirname and invalid inputs.
- [ ] Define the `stdlib.os` API surface (environment access, cwd, listdir,
  platform identifiers) with explicit platform guarantees.
  - Deliverables: API table + platform behavior notes.
- [ ] Implement runtime helpers + `stdlib/os.tiny` wrappers, including error
  handling for missing environment keys.
  - Deliverables: runtime helpers in `src/tiny_language_runtime.py` and wrapper
    module in `stdlib/os.tiny` with docstrings.
- [ ] Add tests for `stdlib.os` covering environment reads/writes, listdir, and
  stable platform identifiers.
  - Deliverables: `tests/detailtests/test_stdlib_os.py` with deterministic
    temporary directory fixtures.
- [ ] Add `stdlib/json.tiny` wrapper for the existing `JSON` namespace and add
  parity tests for `parse`/`stringify`/`validate`.
  - Deliverables: wrapper module plus parity tests in
    `tests/detailtests/test_stdlib_json.py`.
- [ ] Define `stdlib.csv` parsing/serialization behavior (delimiter, quotes,
  headers) and confirm deterministic output expectations.
  - Deliverables: spec notes + examples in `docs/stdlib_expansion_plan.md`.
- [ ] Implement `stdlib.csv` helpers (Tiny or runtime) with round-trip tests for
  simple and quoted data.
  - Deliverables: `stdlib/csv.tiny` + tests in
    `tests/detailtests/test_stdlib_csv.py`.
- [ ] Define `stdlib.time` API requirements (wall clock vs. monotonic, sleep
  semantics) and confirm backend support.
  - Deliverables: runtime capability matrix + decision notes.
- [ ] Implement `stdlib.time` helpers and add smoke tests for timestamps and
  sleeps (with deterministic tolerance thresholds).
  - Deliverables: `stdlib/time.tiny` + tests in
    `tests/detailtests/test_stdlib_time.py`.

## Phase 2 tasks (data interchange + text processing)

- [ ] Define the minimal regex syntax subset and document unsupported constructs.
  - Deliverables: regex syntax spec section + unsupported list in
    `docs/stdlib_expansion_plan.md`.
- [ ] Add a `stdlib.regex` module with match/search/replace APIs and tests for
  capture groups and failure cases.
  - Deliverables: `stdlib/regex.tiny` + `tests/detailtests/test_stdlib_regex.py`.
- [ ] Decide on `stdlib.yaml` scope (optional) and add parser/serializer stubs
  with round-trip tests if approved.
  - Deliverables: scope decision + `stdlib/yaml.tiny` stub + test placeholders.
- [ ] Introduce `stdlib.logging` with structured JSON output and file helpers;
  add tests for formatting and file writes.
  - Deliverables: `stdlib/logging.tiny` + `tests/detailtests/test_stdlib_logging.py`.
- [ ] Add `stdlib.argparse` with flag/positional parsing and update CLI demos;
  add tests for error messages and defaults.
  - Deliverables: `stdlib/argparse.tiny`, updated demo references, and
    `tests/detailtests/test_stdlib_argparse.py`.

## Phase 3 tasks (platform integration)

- [ ] Draft capability/permission model for network/process/file-watching APIs.
  - Deliverables: capability model section in `docs/stdlib_expansion_plan.md`.
- [ ] Define `stdlib.http` API shape and error model; add mocked tests for
  timeouts and invalid inputs.
  - Deliverables: `stdlib/http.tiny` stub + mocked tests with capability gates.
- [ ] Define `stdlib.process` API for spawning and exit codes; add capability-
  gated tests for error paths.
  - Deliverables: `stdlib/process.tiny` stub + capability-gated tests.
- [ ] Define `stdlib.fswatch` behavior and add capability-gated tests.
  - Deliverables: `stdlib/fswatch.tiny` stub + capability-gated tests.

## Cross-cutting tasks (all phases)

- [ ] Add a shared stdlib test harness for module-level unit tests to reduce
  duplication across `tests/detailtests`.
  - Deliverables: shared helper module + docstring on standard fixture layout.
- [ ] Add parity tests that assert module wrappers match runtime namespaces.
  - Deliverables: cross-module parity test helpers + smoke coverage.
- [ ] Add documentation examples for each module and exercise them via tests.
  - Deliverables: example snippets in docs + tests that execute them.
- [ ] Update backend smoke tests to include new stdlib modules as they land.
  - Deliverables: smoke-test matrix update in `tests/` and documentation notes.
