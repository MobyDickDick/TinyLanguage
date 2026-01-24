# TinyLanguage 1.0.0 Release Notes

## Summary

TinyLanguage 1.0.0 is the first stable, interpreter-focused release. It locks
the core language syntax, interpreter runtime semantics, and a baseline standard
library API surface. LLVM/C backends remain experimental and are explicitly out
of scope for the 1.0 stability guarantees.

## Highlights

- **Stable core language + interpreter** with the 1.0 scope defined in
  `docs/release_plan_v1.md`.
- **Documented language spec** in `docs/language_spec.md`, aligned with the
  interpreter behavior.
- **Standard library baseline** documented in `docs/stdlib_compatibility.md`.
- **CLI + tutorial parity** verified in `README.md` and `docs/tutorial.md`.
- **Regression coverage** maintained via the core `pytest` suite and
  `run_all.py` smoke checks.

## What is stable in 1.0

- The **interpreter** and its documented semantics in
  `docs/language_spec.md`.
- The **core stdlib surface** documented in `docs/stdlib_compatibility.md`.
- **CLI workflows** described in `README.md` and demo command docs.

## What remains experimental

- **LLVM backend** and **native/C compiler** pipelines.
- Performance guarantees and optimization profiles.
- Any tooling or scripts not covered by the 1.0 scope checklist.

## Known issues

- LLVM and native/C compiler backends remain experimental and out of scope for
  1.0 stability guarantees.
- Performance guarantees and packaging/distribution workflows are not part of
  the 1.0 scope.

## Upgrade and compatibility notes

- 1.0 is intended to be **backwards compatible** with programs that conform to
  the 1.0 language spec.
- Breaking changes require a future 2.0 plan.

## Tag + release workflow

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

- [x] Changelog entry verified and complete.
- [x] Version file matches the changelog.
- [x] Tag created locally (`v1.0.0`); push to a remote when available.
- [ ] Tag pushed to the release remote.
- [ ] Release notes published.
