# Release candidate checklist

This checklist is the CI-gated baseline for release-candidate readiness. Update
it whenever release criteria change, and keep every CI-gated item checked.

## CI gate checklist
- [x] Docstring lint passes for the required CLI/API entry points.
- [x] Formatter + lint gate passes.
- [x] LSP workflow tests pass (rename, references, code actions).
- [x] Full pytest suite passes (`--assert-no-heap-leaks`).
- [x] Release artifacts build successfully (unsigned).
- [x] Interpreter/C backend/native backend parity smoke suite passes with
      identical stdout/stderr snapshots and matching process exit codes for
      each scenario.

### Required parity smoke scenarios

Run each scenario via all execution paths (`tiny run`, `tiny c run`,
`tiny native run`) and compare output + exit status before sign-off:

- [x] Happy-path program execution for arithmetic + control-flow basics.
- [x] Stdlib-heavy script covering file I/O and JSON parse/serialize round-trip.
- [x] Deterministic runtime error case (e.g. out-of-bounds access) verifying
      identical diagnostic code/message class and non-zero exit code.
- [x] CLI argument forwarding case that confirms argument ordering/escaping is
      preserved across backends.

## Manual follow-ups (not CI-gated)
- [x] Confirm release notes are updated and linked in `CHANGELOG.md`.
- [x] Verify demo commands in `docs/release_candidate_runthrough.md`.
- [x] Capture any new follow-up fixes with dates + commit links.
- [x] Attach the parity-run command transcript (or CI job URL) to the release
      sign-off ticket for auditability.

### Follow-up fixes log
- 2026-02-08: No follow-up fixes identified for this release candidate.
