# Standard library expansion tasks

This checklist derives concrete work items from the standard library expansion
plan so implementation can proceed in small, testable steps.

## Phase 1 tasks (high-value, low-risk)

- [x] Define the `stdlib.path` API surface (join/split/basename/dirname/extension,
  normalize, directory filtering) and map each helper to runtime capabilities.
  - Deliverables: API table in `docs/stdlib_expansion_tasks.md` (this file) plus
    updates to `docs/stdlib_expansion_plan.md` if new helpers are added.
  - Dependencies: confirm which helpers can be built from `File` primitives vs.
    need runtime additions in `src/tiny_language_runtime.py`.
  - API table (draft for `stdlib/path.tiny`):

    | Helper | Signature | Behavior | Runtime mapping |
    | --- | --- | --- | --- |
    | `join` | `join(parts: [string]) -> string` | Join path parts using `/`, ignore empty parts, avoid duplicate separators. | Tiny implementation with `String.join`, `Collections.filter`, `String.contains`. |
    | `split` | `split(path: string) -> [string]` | Split on `/` after normalization; preserve leading empty entry for absolute paths. | Tiny implementation with `String.split` + normalization helper. |
    | `basename` | `basename(path: string) -> string` | Return final path segment; empty string for trailing `/`. | Tiny implementation with `split` + last non-empty helper. |
    | `dirname` | `dirname(path: string) -> string` | Return parent path without trailing separator; empty string if none. | Tiny implementation with `split` + slice/join helpers. |
    | `extension` | `extension(path: string) -> string` | Return suffix after last `.` in basename; empty string if none. | Tiny implementation with `basename` + `String.last_index`. |
    | `normalize` | `normalize(path: string) -> string` | Collapse `.` segments, resolve `..` where possible, replace `\\` with `/`, collapse repeated `/`. | Tiny implementation with `String.replace`, `String.split`, stack-based reduce. |
    | `is_absolute` | `is_absolute(path: string) -> bool` | `true` when path starts with `/` or drive prefix (`C:`). | Tiny implementation with `String.starts_with` and drive-prefix check. |
    | `filter_dir` | `filter_dir(dir: string, pattern: string) -> [string]` | List directory entries and filter by simple glob (`*` suffix/prefix) using normalized paths. | Needs runtime helper (e.g., `File.listdir`) or `stdlib.os.listdir` wrapper. |
- [x] Implement runtime helpers for `stdlib.path` (path normalization + join
  semantics) and add Tiny wrappers in `stdlib/path.tiny`.
  - Deliverables: runtime helper functions + Tiny wrapper module and parity
    mapping notes.
- [x] Add tests for `stdlib.path` covering cross-platform separators, extension
  handling, and error cases (invalid inputs).
  - Deliverables: `tests/detailtests/test_stdlib_path.py` with fixture-based
    coverage for join/split/basename/dirname and invalid inputs.
- [x] Define the `stdlib.os` API surface (environment access, cwd, listdir,
  platform identifiers) with explicit platform guarantees.
  - Deliverables: API table + platform behavior notes.
  - API table (draft for `stdlib/os.tiny`):

    | Helper | Signature | Behavior | Runtime mapping |
    | --- | --- | --- | --- |
    | `getenv` | `getenv(key: string) -> string?` | Return the environment value for `key`, or `null` when unset. | Runtime helper reading `os.environ`/`getenv`. |
    | `setenv` | `setenv(key: string, value: string) -> bool` | Set `key` to `value`; return `true` on success. | Runtime helper mapping to `setenv`/`putenv`. |
    | `unsetenv` | `unsetenv(key: string) -> bool` | Remove `key` from the environment; return `true` if removed. | Runtime helper mapping to `unsetenv`. |
    | `cwd` | `cwd() -> string` | Return the current working directory as an absolute path. | Runtime helper mapping to `os.getcwd`. |
    | `chdir` | `chdir(path: string) -> bool` | Change the process working directory; return `true` on success. | Runtime helper mapping to `os.chdir`. |
    | `listdir` | `listdir(path: string) -> [string]` | Return entry names (not full paths) sorted lexicographically. | Runtime helper mapping to `os.listdir`. |
    | `platform` | `platform() -> string` | Return `"linux"`, `"darwin"`, `"windows"`, or `"unknown"`. | Runtime helper mapping to `sys.platform`. |
    | `path_separator` | `path_separator() -> string` | Return the platform path separator (`"/"` or `"\\"`). | Runtime helper mapping to `os.sep`. |
  - Platform behavior notes:
    - `listdir` sorts entries for deterministic tests; the runtime helper should
      normalize ordering instead of relying on OS iteration order.
    - `platform` maps `sys.platform` values to stable identifiers: `"linux"`
      for `linux*`, `"darwin"` for `darwin`, `"windows"` for `win32` or
      `cygwin`, otherwise `"unknown"`.
    - `cwd` and `chdir` should return normalized paths (use `/` separators) so
      Tiny code can compare results across backends.
    - `getenv` returns `null` (not empty string) when keys are missing to
      distinguish unset variables from intentionally empty values.
- [x] Implement runtime helpers + `stdlib/os.tiny` wrappers, including error
  handling for missing environment keys.
  - Deliverables: runtime helpers in `src/tiny_language_runtime.py` and wrapper
    module in `stdlib/os.tiny` with docstrings.
- [x] Add tests for `stdlib.os` covering environment reads/writes, listdir, and
  stable platform identifiers.
  - Deliverables: `tests/detailtests/test_stdlib_os.py` with deterministic
    temporary directory fixtures.
- [x] Add `stdlib/json.tiny` wrapper for the existing `JSON` namespace and add
  parity tests for `parse`/`stringify`/`validate`.
  - Deliverables: wrapper module plus parity tests in
    `tests/detailtests/test_stdlib_json.py`.
- [x] Define `stdlib.csv` parsing/serialization behavior (delimiter, quotes,
  headers) and confirm deterministic output expectations.
  - Deliverables: spec notes + examples in `docs/stdlib_expansion_plan.md`.
- [x] Implement `stdlib.csv` helpers (Tiny or runtime) with round-trip tests for
  simple and quoted data.
  - Deliverables: `stdlib/csv.tiny` + tests in
    `tests/detailtests/test_stdlib_csv.py`.
- [x] Define `stdlib.time` API requirements (wall clock vs. monotonic, sleep
  semantics) and confirm backend support.
  - Deliverables: runtime capability matrix + decision notes.
  - API requirements (draft for `stdlib/time.tiny`):

    | Helper | Signature | Behavior | Runtime mapping |
    | --- | --- | --- | --- |
    | `now_ms` | `now_ms() -> number` | Return wall-clock epoch time in milliseconds (UTC). | Runtime helper mapping to `time.time()` × 1000. |
    | `monotonic_ms` | `monotonic_ms() -> number` | Return monotonic time in milliseconds for measuring elapsed durations. | Runtime helper mapping to `time.monotonic()` × 1000. |
    | `sleep_ms` | `sleep_ms(ms: number) -> number` | Sleep for at least `ms` milliseconds (clamp negatives to 0) and return elapsed milliseconds. | Runtime helper mapping to `time.sleep(ms / 1000)`. |
    | `now_iso` | `now_iso() -> string` | Return an ISO 8601 timestamp in UTC (e.g., `2025-01-01T00:00:00Z`). | Runtime helper using `datetime.datetime.utcnow().isoformat() + "Z"`. |

  - Decision notes:
    - Expose both wall-clock and monotonic clocks so callers can choose stable
      elapsed-time measurements without being affected by clock adjustments.
    - `sleep_ms` uses monotonic time to compute elapsed duration; it must not
      return before the requested time unless interrupted by the runtime
      cancellation model (treat negative values as 0 for a yield-only sleep).
    - The initial API stays in milliseconds to align with existing runtime
      timeout settings (e.g., `join` and task-scope timeouts).
    - `now_iso` provides a human-readable timestamp for logs without requiring
      callers to format epoch values manually.

  - Runtime capability matrix (initial target):

    | Capability | Interpreter runtime | Native VM | LLVM/C backend |
    | --- | --- | --- | --- |
    | Epoch time (`now_ms`) | `time.time()` | Needs native helper (clock + epoch) | Needs native helper (clock + epoch) |
    | Monotonic time (`monotonic_ms`) | `time.monotonic()` | Needs native helper (monotonic clock) | Needs native helper (monotonic clock) |
    | Sleep (`sleep_ms`) | `time.sleep()` | Needs native helper (sleep) | Needs native helper (sleep) |
    | ISO timestamp (`now_iso`) | `datetime.utcnow()` | Needs native helper (format) | Needs native helper (format) |
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
