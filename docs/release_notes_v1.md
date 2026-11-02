# TinyLanguage 1.0.0 Release Notes (draft)

## Summary

TinyLanguage 1.0.0 is a planned, interpreter-focused release. Qualification is
pending; `VERSION` does not prove publication. The
[candidate contract](release_scope_v1.md) defines the proposed stable syntax,
interpreter semantics, CLI and stdlib surface and links executable evidence.
Native VM, bytecode, transpilers, LLVM and C remain experimental.

## Highlights

- **Candidate core language + interpreter contract** defined in
  `docs/release_scope_v1.md` (acceptance pending).
- **Documented language spec** in `docs/language_spec.md`, aligned with the
  interpreter behavior.
- **Standard library baseline** documented in `docs/stdlib_compatibility.md`.
- **CLI + tutorial parity** verified in `README.md` and `docs/tutorial.md`.
- **Regression coverage** maintained via the core `pytest` suite and
  `src/run_all.py` smoke checks.

## Candidate stability target

- The **interpreter** and its documented semantics in
  `docs/language_spec.md`.
- The **core stdlib surface** documented in `docs/stdlib_compatibility.md`.
- **CLI workflows** described in `README.md` and demo command docs.

## What remains experimental

- **Native VM**, **native Python bytecode**, **Python transpilation**, **LLVM**
  and **C** pipelines.
- Performance guarantees and optimization profiles.
- Any tooling or scripts not covered by the 1.0 scope checklist.

## Known issues

- LLVM and native/C compiler backends remain experimental and out of scope for
  1.0 stability guarantees.
- Copy-on-call escape inference and guaranteed interval enclosure have open
  correctness work (packages 7–8) and are excluded from the frozen contract.
- Performance guarantees remain out of scope. Packaging/distribution and
  platform qualification are mandatory release gates in packages 1–3 and are
  still pending; local implementation checkpoints do not close them.

## Upgrade and compatibility notes

- 1.0 is intended to be **backwards compatible** with programs that conform to
  the 1.0 language spec.
- Breaking changes require a future 2.0 plan.

## Tag + release workflow

Complete the candidate evidence gate and delivery packages 1–3 before tagging
or publication. The steps below are instructions for the release owner, not
evidence that these actions have occurred.

1. **Finalize the changelog**: verify `CHANGELOG.md` includes a complete 1.0.0
   entry with Added/Changed/Fixed and Known issues sections.
2. **Verify versioning**: confirm `VERSION` is set to `1.0.0` and matches the
   changelog entry.
3. **Create the tag**:
   - `git tag -a v1.0.0 -m "TinyLanguage 1.0.0"`
4. **Push the tag**:
   - `git push origin v1.0.0`
5. **Publish release notes** (GitHub):
   - Title: `TinyLanguage 1.0.0`
   - Body: copy the Summary + Highlights + Known issues from this document and
     link to `CHANGELOG.md`.
6. **Post-release verification**:
   - Ensure the tag is visible in the remote repository.
   - Confirm release notes render correctly and link to docs.

## Checklist for release readiness

- [ ] Candidate and delivery acceptance evidence reviewed for the release commit.
- [ ] Final changelog and release notes approved.
- [x] Planned version `1.0.0` matches `VERSION` and the changelog.
- [ ] Release tag verified for the approved candidate commit.
- [ ] Tag pushed to the release remote and release notes published.
