# Open tasks

This file tracks only active work items for TinyLanguage. Completed tasks are
archived in `docs/open_tasks_archive.md`.

## Current tasks

The active work items are tracked in the refreshed near-term backlog and the
sections below.

## Refreshed near-term backlog (published 2026-02-02)

Timebox: 2026-02-02 to 2026-03-16 (6 weeks).

1. **Stabilize formatter + lints + LSP workflows** (Owner: Tooling)
   - Success: Documented formatter rules, lint profiles, and LSP smoke tests.

## Near-term priorities (next 4-6 weeks)

- [ ] Stabilize formatter + lints + LSP workflows.
  - Owner: Tooling
  - Success: Documented formatter rules, lint profiles, and LSP smoke tests.

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

- [ ] Optional type inference and gradual typing track updates.
- [ ] Module resolution and package manager roadmap implementation.
- [ ] Conformance + cross-backend parity suite expansion.
