# Release candidate checklist

Release qualification is pending. The canonical scope, evidence map and commands
are in [release_scope_v1.md](release_scope_v1.md). Boxes are a review aid; CI
verifies executed commands, source identity, JUnit/log hashes and artifacts.
Historical checked boxes did not retain sufficient candidate evidence and have
been reopened.

## CI gate checklist
- [ ] Required CLI/API docstring lint and formatter/lint checks pass.
- [ ] LSP workflow tests pass without skips.
- [ ] Interpreter contract/specification and executable documentation pass
      without skips, including independent arithmetic expectations.
- [ ] Experimental interpreter/native VM parity checks pass without skips.
- [ ] Full pytest suite passes (`--assert-no-heap-leaks`); optional/platform
      skips remain explicitly reported and are not passing backend evidence.
- [ ] Unsigned HEAD source archive builds; version, commit, checksums and payload
      hashes verify. Candidate sources are committed and match the test records.

### Required parity smoke scenarios

Compare only implemented subsets. Canonical CLI options are in
[cli_workflows.md](cli_workflows.md); the native VM uses `--native-backend`.
`tiny run` and `tiny native run` are not the documented interpreter entry points.

- [ ] Native VM execution and error parity for fixtures in `tests/parity/`
      and `test_native_backend_error_parity.py`.
- [ ] Required C/LLVM subset compilation and execution in all sixteen platform
      qualification jobs; no missing-tool skips count as success.
- [ ] Installed argument forwarding, file/JSON and multi-file workflows pass
      within the installed interpreter scope. C has no imports or heap support;
      do not claim interpreter/C parity for those operations.

## Delivery and release approval

- [ ] Package 1: all target artifacts, immutable inputs, independent rebuilds,
      complete inventory, release-key signatures and retained provenance pass.
- [ ] Package 2: installed/editor acceptance identifies the actual candidate
      artifacts (existing Windows checkpoint is linked in open tasks).
- [ ] Package 3: all sixteen platform jobs pass for the candidate commit.
- [ ] Attach candidate commit, CI run/artifact IDs and manual acceptance records.
- [ ] Approve release notes, migration guidance, tag and publication only after
      the candidate and delivery evidence has been reviewed.

### Follow-up fixes log
- 2026-02-08: Historical checklist claimed no follow-up fixes; that statement
  does not qualify the current candidate.
- 2026-11-02: Replaced checkbox-only validation with source-bound executed
  checks; reconciled experimental backend scope and reopened unproven delivery
  and publication claims. Package 5 remains open for candidate qualification.
