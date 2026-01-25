# Conformance + compatibility test strategy

This document outlines how TinyLanguage should validate its language
specification and ensure consistent behavior across the interpreter, C backend,
LLVM backend, and native VM.

## Goals

- Prove that the language spec is executable via automated tests.
- Detect behavioral drift between backends early.
- Provide clear, actionable diagnostics when a backend diverges.
- Keep compatibility promises measurable for each release.

## Test suite layers

### 1) Spec conformance suite

**Purpose:** Validate that the language specification is correct and complete,
using tests that map directly to spec requirements.

- Organize tests by spec chapter (lexing, parsing, evaluation order, control
  flow, runtime errors, stdlib semantics, etc.).
- Each test case must reference the relevant spec section in a comment header.
- Tests should include both valid programs and expected error cases.
- Output is compared against canonical snapshots (stdout, stderr, exit code).

**Artifacts:**

- `tests/spec/` directory with Tiny programs + expected outputs.
- Snapshot files that capture compiler/interpreter diagnostics.

### 2) Cross-backend parity suite

**Purpose:** Ensure the interpreter, C backend, LLVM backend, and native VM
produce equivalent results for the same Tiny programs.

- Reuse the spec test fixtures when possible to avoid duplication.
- Run each fixture in every backend that supports it.
- Normalize outputs to account for benign differences (e.g., backend version
  banners) before comparisons.
- Track backend skips explicitly (e.g., feature not yet supported) to avoid
  silent regression.

**Artifacts:**

- `tests/parity/` directory with backend-compatible fixtures.
- A parity runner that invokes each backend and diffs outputs.

### 3) Compatibility and regression suite

**Purpose:** Guard known bug fixes, CLI behavior, and compatibility promises.

- Keep explicit regression tests for previously fixed issues.
- Include CLI smoke tests (help output, error formatting, exit codes).
- Maintain compatibility tests for language features with deprecation plans.

**Artifacts:**

- `tests/regressions/` for known issues.
- `tests/cli/` for CLI behavior snapshots.

## Required metadata for each test

Every fixture should declare:

- **Scope:** spec section or feature area.
- **Expected outcome:** success or error (with error type/message).
- **Backend support:** whether the test is valid for interpreter, C, LLVM,
  native VM.
- **Stability tier:** core (must pass) or experimental (can be skipped).

## Automation workflow

1. **Spec suite run:** Use the interpreter as the primary reference.
2. **Parity run:** Execute the same fixtures in all backends, diff normalized
   outputs against the interpreter.
3. **Compatibility run:** Execute regression and CLI snapshots.
4. **Reporting:** Summarize failures by backend + spec section.

## Backend output normalization spec

Parity comparisons depend on stable, backend-agnostic output. The normalization
step should transform raw stdout/stderr into a canonical form before diffing.

### Scope

Apply normalization to both stdout and stderr, including error diagnostics and
CLI banners emitted by any backend runner.

### Strip or replace

- **Version banners + backend headers:** Remove lines that match known banner
  prefixes such as `TinyLanguage`, `tinyc`, `tiny-language`, or backend labels
  like `Interpreter`, `C backend`, `LLVM backend`, `Native VM`. If a banner must
  remain for a specific test, the fixture should opt out of normalization and
  compare raw output instead.
- **Timing data:** Remove lines or fragments that report durations, compilation
  times, or perf counters (e.g., `time=`, `elapsed`, `ms`, `ns`).
- **Absolute paths:** Replace absolute filesystem prefixes with a placeholder
  like `<ROOT>` while retaining the relative suffix.
- **Process IDs / random seeds:** Replace numeric tokens tied to PID, port, or
  random seeds with `<ID>` or `<SEED>` placeholders.

### Canonicalize formatting

- **Line endings:** Convert Windows `\r\n` to `\n`.
- **Whitespace:** Trim trailing whitespace on each line; collapse repeated
  blank lines to a single blank line.
- **Error prefixes:** Normalize backend-specific error headers to a common
  prefix such as `error:` and warnings to `warning:` while leaving the message
  body intact.
- **Stack traces:** If stack traces are expected, normalize file paths and line
  numbers as described above; otherwise strip stack traces entirely.

### Normalization output

Emit the normalized stdout/stderr as separate snapshots so parity comparisons
can still distinguish stream differences. The normalization rules should be
centralized in a single helper so new backend runners stay aligned.

## CI expectations

- Spec tests are required for every PR that changes language semantics.
- Parity suite should run on CI for backends that are available in the build
  environment.
- Compatibility suite must run on every merge to main.

## Open follow-ups

- Implement the normalization helper in the parity runner (including error
  diagnostics and stdout/stderr separation).
- Decide which suite owns stdlib behavior vs. spec vs. parity.
- Add a small smoke subset for quick developer feedback.

## Derived tasks

- [x] Draft a normalization spec for backend output (what is stripped, what is
  canonicalized, and how version banners are handled).
- [ ] Define ownership boundaries between spec, parity, and compatibility
  suites (including stdlib behavior expectations).
- [ ] Add a smoke subset that runs in under 60 seconds for local developer
  feedback.
- [x] Create a `tests/spec/` skeleton with one example fixture and snapshot
  layout to document the expected structure.
- [ ] Implement a parity runner that executes the same fixtures across
  interpreter, C, LLVM, and native VM backends and diffs normalized outputs.
