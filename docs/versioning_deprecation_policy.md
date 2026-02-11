# Versioning and deprecation policy

This policy defines how TinyLanguage versions are assigned, how changes are
classified, and how deprecations are announced and retired. It is the canonical
reference for release notes, migration guides, and compatibility guarantees.

## Scope

The policy applies to:

- The TinyLanguage language specification and interpreter behavior.
- Standard library APIs and modules.
- Tooling and CLIs shipped with the project (formatter, linter, language server,
  compiler CLI, and project scaffolding tools).

## Versioning model (SemVer)

TinyLanguage uses Semantic Versioning (`MAJOR.MINOR.PATCH`). The current release
version is stored in `VERSION`, and changes are documented in `CHANGELOG.md`.

### Release types

- **Patch release (`x.y.Z`)**
  - Bug fixes that do **not** change documented behavior.
  - Performance improvements or internal refactors with no user-visible impact.
  - Documentation corrections and clarifications.
- **Minor release (`x.Y.z`)**
  - Backwards-compatible language features.
  - New stdlib modules, functions, or tooling capabilities that do not break
    existing code.
  - Deprecation warnings are introduced here.
- **Major release (`X.y.z`)**
  - Breaking changes to language semantics, stdlib APIs, or tooling contracts.
  - Removal of deprecated features or APIs.
  - Changes that require source updates or behavior migration.

### What counts as a breaking change

A change is **breaking** if it:

- Alters evaluation order, scoping, or error-handling rules in a way that can
  change program output or runtime behavior.
- Modifies or removes a public stdlib API, module, or CLI flag that existing
  code depends on.
- Changes default tooling behaviors in a way that produces different runtime
  results (not merely additional diagnostics).

## Deprecation lifecycle

Deprecations must be explicit, documented, and time-bound.

1. **Announcement (minor release)**
   - Deprecations are announced in `CHANGELOG.md` and relevant documentation.
   - The alternative or replacement must be specified.
2. **Warning period (at least one minor release)**
   - Tooling should emit deprecation warnings when the deprecated feature is
     used, where feasible.
   - A compatibility shim (alias, wrapper, or fallback) is maintained when the
     change is practical to support.
3. **Removal (next major release or later)**
   - Deprecated features may be removed in a major release.
   - Migration notes must be included in the release guide, with examples of the
     required changes.

## Stdlib module move / rename checklist

When a standard-library module path changes (for example, a merge, split, or
namespace rename), maintainers must complete the checklist below so users have
a predictable upgrade path.

1. **Announce the move in a minor release (`N`)**
   - Add a dedicated changelog item that states:
     - old import path,
     - new import path,
     - first release that emits warnings,
     - planned major release for removal.
   - Update `docs/stdlib_compatibility.md` and the compatibility matrix to show
     the module is in a deprecation window.
2. **Provide an aliasing compatibility layer during `N` and `N+1`**
   - Keep the old import path as a runtime alias/wrapper to the new module for
     at least one full minor release after announcement.
   - Ensure docs and examples prefer the new import path, while still showing
     that the old path remains temporarily supported.
3. **Emit deprecation warnings on old-path imports during `N` and `N+1`**
   - Warning text should include:
     - old and new import paths,
     - target major release where old path is removed,
     - link to migration notes.
   - Warnings should be visible in CLI/test workflows and suppressible only via
     the standard project-wide warning controls.
4. **Remove old path in the next major release (`N+2` major boundary)**
   - Delete aliasing code and mark the old module path as removed.
   - Provide final migration examples in the major-release upgrade guide.

### Recommended warning timeline for stdlib moves

- **Minor `N`**: Announce + alias + warnings enabled by default.
- **Minor `N+1`**: Continue alias + warnings; do not introduce new features on
  the old path.
- **Major `N+2`**: Remove alias and old path, keep migration references in
  release notes.

### Minimum guarantees

- Deprecations remain available for **at least one minor release** after first
  announcement.
- Removals happen **only in a major release**.
- Critical security fixes may ship in patch releases, but they still follow the
  deprecation/removal rules for public APIs.

## Experimental or provisional features

Experimental features (marked as such in documentation or release notes) may
change in minor releases. They should be opt-in via configuration or explicit
syntax, and the docs must include a stability disclaimer.

## Documentation and release artifacts

Each release must include:

- Updated `VERSION` and `CHANGELOG.md` entries.
- Migration notes for breaking changes or deprecations (see
  `docs/release_migration_guides.md`).
- Updates to the language specification in `docs/language_spec.md` when
  semantics change.

## Enforcement

- CI and test suites should gate changes that contradict this policy.
- The language specification is the source of truth for language semantics; any
  change to behavior must be reflected in the spec and in the changelog.
