# Standard library expansion tasks

This checklist derives concrete work items from the standard library expansion
plan so implementation can proceed in small, testable steps.

## Phase 1 tasks (high-value, low-risk)

- [ ] Define the `stdlib.path` API surface (join/split/basename/dirname/extension,
  normalize, directory filtering) and map each helper to runtime capabilities.
- [ ] Implement runtime helpers for `stdlib.path` (path normalization + join
  semantics) and add Tiny wrappers in `stdlib/path.tiny`.
- [ ] Add tests for `stdlib.path` covering cross-platform separators, extension
  handling, and error cases (invalid inputs).
- [ ] Define the `stdlib.os` API surface (environment access, cwd, listdir,
  platform identifiers) with explicit platform guarantees.
- [ ] Implement runtime helpers + `stdlib/os.tiny` wrappers, including error
  handling for missing environment keys.
- [ ] Add tests for `stdlib.os` covering environment reads/writes, listdir, and
  stable platform identifiers.
- [ ] Add `stdlib/json.tiny` wrapper for the existing `JSON` namespace and add
  parity tests for `parse`/`stringify`/`validate`.
- [ ] Define `stdlib.csv` parsing/serialization behavior (delimiter, quotes,
  headers) and confirm deterministic output expectations.
- [ ] Implement `stdlib.csv` helpers (Tiny or runtime) with round-trip tests for
  simple and quoted data.
- [ ] Define `stdlib.time` API requirements (wall clock vs. monotonic, sleep
  semantics) and confirm backend support.
- [ ] Implement `stdlib.time` helpers and add smoke tests for timestamps and
  sleeps (with deterministic tolerance thresholds).

## Phase 2 tasks (data interchange + text processing)

- [ ] Define the minimal regex syntax subset and document unsupported constructs.
- [ ] Add a `stdlib.regex` module with match/search/replace APIs and tests for
  capture groups and failure cases.
- [ ] Decide on `stdlib.yaml` scope (optional) and add parser/serializer stubs
  with round-trip tests if approved.
- [ ] Introduce `stdlib.logging` with structured JSON output and file helpers;
  add tests for formatting and file writes.
- [ ] Add `stdlib.argparse` with flag/positional parsing and update CLI demos;
  add tests for error messages and defaults.

## Phase 3 tasks (platform integration)

- [ ] Draft capability/permission model for network/process/file-watching APIs.
- [ ] Define `stdlib.http` API shape and error model; add mocked tests for
  timeouts and invalid inputs.
- [ ] Define `stdlib.process` API for spawning and exit codes; add capability-
  gated tests for error paths.
- [ ] Define `stdlib.fswatch` behavior and add capability-gated tests.

## Cross-cutting tasks (all phases)

- [ ] Add a shared stdlib test harness for module-level unit tests to reduce
  duplication across `tests/detailtests`.
- [ ] Add parity tests that assert module wrappers match runtime namespaces.
- [ ] Add documentation examples for each module and exercise them via tests.
- [ ] Update backend smoke tests to include new stdlib modules as they land.
