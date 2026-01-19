# TinyLanguage v1.0 Task Backlog (Issue List)

This file documents the prioritized task list for a v1.0 release.
It is based on the roadmap areas (Frontend/Language, Type discipline, Runtime,
Tooling, Native backends) as well as the validation goals from the
self-hosting port plan.

## A. Release fundamentals (Scope & DoD)

1. **Document v1.0 DoD (release criteria)** ✅
   - **Description:** Clearly define when TinyLanguage is considered “v1.0-complete.”
   - **DoD:** Document contains clear criteria for diagnostics, type discipline,
     runtime safety, tooling, and backend scope.
   - **Owner docs:** `docs/release_v1_dod.md`

2. **Define spec-freeze scope**
   - **Description:** Decide which syntax/features remain stable for the v1.0 release.
   - **DoD:** Release document includes a section that excludes syntax changes for v1.0.

## B. Diagnostics & Language Core

3. **Verify source-span/position consistency**
   - **Description:** Make error diagnostics consistent across parser/linter/runtime.
   - **DoD:** Tests cover line/column accuracy across all error paths.

4. **Define a unified error format**
   - **Description:** Unify error classes/format (parser, linter, runtime).
   - **DoD:** Documented error format + regression tests.

## C. Type Discipline v1

5. **Finalize rules for type changes**
   - **Description:** Define explicit rules for type changes.
   - **DoD:** Documentation + tests for allowed/disallowed type changes.

6. **Define optional type inference (scope)**
   - **Description:** Decide whether “simple type inference” is part of v1.0.
   - **DoD:** Clear scope documented (“in v1.0” or “post-v1.0”).

## D. Runtime Safety (Heap/API)

7. **Full coverage for heap diagnostics**
   - **Description:** invalid pointer, out-of-bounds, double delete, leak tracking.
   - **DoD:** Tests for all error cases; diagnostics are consistent.

8. **Expand heap regression tests**
   - **Description:** Test cases for nested arrays, deep recursion, OOB.
   - **DoD:** Expanded regression suite with stable error messages.

## E. Tooling & Developer Experience

9. **Stabilize CLI workflows**
   - **Description:** Document interpreter/native CLI flows consistently.
   - **DoD:** CLI guide updated + smoke tests for standard flows.

10. **Define formatter/lint workflows**
    - **Description:** Standard lint profiles, formatter workflow, CI checks.
    - **DoD:** Documentation + CI checks defined.

11. **LSP workflows as CI gate**
    - **Description:** Lock LSP tests (hover/completion/diagnostics).
    - **DoD:** Tests run reliably in CI.

## F. Backend Parity & Release Candidate

12. **Interpreter as the “golden path”**
    - **Description:** Interpreter parity as a hard requirement for v1.0.
    - **DoD:** Parity tests enforced in CI.

13. **Stabilize C backend (feature subset)**
    - **Description:** Document the supported feature subset.
    - **DoD:** Documentation + feature matrix updated.

14. **Mark LLVM backend as experimental**
    - **Description:** Explicit documentation + known limitations.
    - **DoD:** LLVM scope explicitly “non-blocking” for v1.0.

## G. Release & Stabilization

15. **Release notes + breaking changes**
    - **Description:** Summarize final API/syntax changes.
    - **DoD:** Release notes include breaking changes + known limitations.

16. **Final regression run (RC)**
    - **Description:** Full test run (interpreter + native + LSP).
    - **DoD:** All gates green; v1.0 release approved.
