# TinyLanguage v1.0 Definition of Done (DoD)

This document defines the release criteria for TinyLanguage v1.0. A v1.0
release is considered complete only when all criteria below are satisfied.

## 1. Diagnostics & error reporting

- Parser, linter, and runtime diagnostics must:
  - Report accurate source spans (line/column) for every error path.
  - Use a unified error format and naming convention across subsystems.
  - Include actionable error messages with consistent categorization.
- Regression tests cover representative diagnostics for parser, linter, and
  runtime errors.

## 2. Type discipline

- The language specification explicitly documents allowed and disallowed type
  changes (reassignments, inferred changes, casts).
- Tests cover both valid and invalid type transitions.
- The v1.0 scope for any type inference is documented as either in-scope or
  deferred beyond v1.0.

## 3. Runtime safety

- Heap diagnostics are fully covered for:
  - Invalid pointer usage.
  - Out-of-bounds access.
  - Double delete.
  - Leak tracking.
- Regression tests validate nested arrays, deep recursion, and OOB cases with
  stable error messages.

## 4. Tooling & developer workflows

- CLI documentation clearly defines the interpreter and native workflows.
- Formatter and lint workflows are documented, and CI checks exist for the
  standard profiles.
- LSP tests (hover, completion, diagnostics) run reliably in CI and are treated
  as a gating check.

## 5. Backend parity & release scope

- Interpreter behavior is the golden reference; parity tests are enforced in CI.
- The C backend has a documented, stable feature subset with a published matrix.
- The LLVM backend is explicitly marked as experimental and non-blocking for
  v1.0.

## 6. Spec-freeze scope

- No new syntax or grammar changes are permitted after the v1.0 spec freeze.
- Only bug fixes, documentation clarifications, and non-semantic tooling updates
  are allowed in the frozen window.
- Any exception requires release-owner approval and must be documented as a
  release note or known limitation.

## 7. Release & stabilization gates

- Release notes summarize breaking changes and known limitations.
- A full regression run (interpreter + native + LSP) is green.
- The v1.0 release is approved after all criteria are satisfied.
