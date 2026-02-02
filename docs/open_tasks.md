# Open tasks

This file tracks only active work items for TinyLanguage. Completed tasks are
archived in `docs/open_tasks_archive.md`.

## Current tasks

- [ ] Publish a refreshed near-term backlog (owners + success criteria).
  - Owner: Project Lead
  - Success: Top 5 tasks below are confirmed, prioritized, and time-boxed.

## Near-term priorities (next 4-6 weeks)

- [ ] Improve error positions and messages (line/column spans, unified error type).
  - Owner: Language Core
  - Success: Source spans propagate through tokens + AST; diagnostics include consistent line/column ranges.
- [ ] Refine linter “must-use” and unreachable-code checks.
  - Owner: Language Core
  - Success: Lints cover control-flow exits and flag unreachable code with tests.
- [ ] Harden heap API diagnostics (invalid pointer, bounds, double-delete, leak tracking).
  - Owner: Runtime
  - Success: Interpreter reports detailed heap failures; regression tests cover error cases.
- [ ] Stabilize formatter + lints + LSP workflows.
  - Owner: Tooling
  - Success: Documented formatter rules, lint profiles, and LSP smoke tests.
- [ ] Expand native backend stability docs (C backend + LLVM status).
  - Owner: Native Backends
  - Success: `docs/c_backend.md` and LLVM notes updated with current limitations and usage.

## Expansion roadmap follow-ups

- [ ] Add a `datetime` parity map and a minimal TL subset with snapshot tests.
  - Owner: Stdlib
  - Success: `stdlib/datetime.tiny` scope documented and tested against known inputs.
- [ ] Define the Julia subset target and list functions in `docs/julia_subset.md`.
  - Owner: Language/Stdlib
  - Success: Documented function list with examples and scope boundaries.
- [ ] Implement `mean` + `std` in a new statistics module with tests.
  - Owner: Stdlib
  - Success: `stdlib/statistics.tiny` plus tests comparing outputs to Python/NumPy where feasible.
- [ ] Add self-hosting parity snapshots for CLI + LSP diagnostics.
  - Owner: Tooling
  - Success: Parity tests compare Python vs Tiny CLIs for exit codes + diagnostics formatting.
- [ ] Expand parity tests for multi-line/nested error spans.
  - Owner: Tooling
  - Success: Regression suite verifies identical formatting for complex spans.
- [ ] Add a regression matrix for self-hosting modules.
  - Owner: Tooling
  - Success: Documented matrix with last-verified versions and known deviations.

## Longer-term backlog (unprioritized)

- [ ] Optional type inference and gradual typing track updates.
- [ ] Module resolution and package manager roadmap implementation.
- [ ] Conformance + cross-backend parity suite expansion.
