# Release candidate checklist

This checklist is the CI-gated baseline for release-candidate readiness. Update
it whenever release criteria change, and keep every CI-gated item checked.

## CI gate checklist
- [x] Docstring lint passes for the required CLI/API entry points.
- [x] Formatter + lint gate passes.
- [x] LSP workflow tests pass (rename, references, code actions).
- [x] Full pytest suite passes (`--assert-no-heap-leaks`).
- [x] Release artifacts build successfully (unsigned).

## Manual follow-ups (not CI-gated)
- [x] Confirm release notes are updated and linked in `CHANGELOG.md`.
- [x] Verify demo commands in `docs/release_candidate_runthrough.md`.
- [x] Capture any new follow-up fixes with dates + commit links.

### Follow-up fixes log
- 2026-02-08: No follow-up fixes identified for this release candidate.
