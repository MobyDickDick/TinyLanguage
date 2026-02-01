# Release migration guides

This document records migration guidance for each major TinyLanguage release.
Each section should capture any behavior changes, deprecations, or required
workflow updates.

## 1.0.0

**Who this applies to:** Users coming from pre-1.0 development snapshots.

**Migration impact:** No migration steps are required for 1.0.0 because this is
our first major release. For earlier internal snapshots, follow the current
README and `docs/language_spec.md` for updated CLI usage and language behavior.

### Compatibility reminders

- The interpreter remains the reference implementation.
- The native VM + LLVM pipeline remain experimental and may lag behind full
  language coverage. Use the interpreter for full feature support.
- See `docs/release_compatibility_matrix.md#100-current` for the full backend
  compatibility matrix for this release.

## Update checklist for future major releases

When preparing a new major release:

1. Summarize breaking changes, removed flags, and deprecated APIs.
2. Provide step-by-step updates for CLI flags, project layout, or stdlib module
   renames.
3. Link to compatibility notes in `docs/release_compatibility_matrix.md`.
4. Add any required code migration examples.
