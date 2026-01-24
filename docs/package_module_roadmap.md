# Package & module system roadmap

This document outlines a staged plan for introducing packages and modules to
TinyLanguage. It focuses on namespacing, versioning, dependency resolution,
lockfiles, and a minimal CLI that can evolve into a full package manager.

## Goals

- Provide a predictable module namespace scheme that keeps local, stdlib, and
  external packages distinct.
- Enable reproducible builds via lockfiles and stable dependency resolution.
- Keep early tooling minimal (import + vendor) while allowing growth into a
  registry-backed ecosystem.

## Scope (v0: foundational decisions)

### Namespaces and module identifiers

- **Local modules**: Resolve relative to the project root (default) and the
  local `src/` tree (e.g., `import my_app.utils`).
- **Standard library**: Reserve a `std` namespace (e.g., `import std.io`,
  `import std.json`) that maps to the canonical stdlib root.
- **External packages**: Use a `pkg` namespace (e.g., `import pkg.http`) to
  avoid ambiguity with local modules.
- **Optional org namespace**: Allow `pkg.org_name.module` to disambiguate
  community packages when registries arrive.

### Versioning model

- Adopt SemVer for published packages (major.minor.patch).
- Define compatibility rules per major version: changes in major versions may
  break API; minor/patch are additive/fixes.
- Use a lockfile to pin resolved versions and ensure deterministic builds.

### Dependency resolution

- Allow version constraints in a project manifest (range operators such as
  `^1.2`, `~1.2`, or `>=1.2 <2.0`).
- Resolve dependencies by selecting the newest compatible version, then lock
  the result to the lockfile.
- Treat local path dependencies as higher priority than registry packages.

### Lockfile strategy

- Introduce `tiny.lock` in project roots.
- Lockfile records resolved versions, source (registry, path), and checksums.
- The interpreter/tooling should refuse to resolve new versions unless explicitly
  updated via the CLI.

## Minimal CLI (phase 1)

Introduce a small set of commands, likely as extensions of `tiny` or `tinyc`.

- `tiny pkg init` — create a `tiny.toml` manifest with name/version metadata.
- `tiny pkg add <name>@<version>` — add a dependency and update `tiny.lock`.
- `tiny pkg resolve` — resolve and pin dependencies without fetching packages
  (for CI or offline builds).
- `tiny pkg vendor` — fetch external packages into `vendor/` and update
  `tiny.lock`.
- `tiny pkg list` — display resolved dependencies and their sources.

Notes:
- Phase 1 assumes a simple registry URL configured via environment variable or
  `tiny.toml` (e.g., `registry_url`).
- Vendoring is optional but provides deterministic builds before a full package
  cache exists.

## Evolution (phase 2+)

- Add registry discovery and authentication for publishing.
- Introduce workspace/monorepo support (multiple packages sharing a lockfile).
- Support dependency overrides and patching (local edits to a registry package).
- Add `tiny pkg publish` with semantic version guards and compatibility checks.

## Risks and mitigations

- **Namespace conflicts**: Reserve `std` and `pkg` to avoid ambiguity, require
  explicit prefixes for external packages.
- **Lockfile drift**: Enforce lockfile checks in CI; require `tiny pkg resolve`
  before builds that change dependency graphs.
- **Backward compatibility**: Document migration rules when the namespace or
  manifest format evolves.

## Deliverables checklist

- Manifest format (`tiny.toml`) specification and examples.
- Lockfile schema (`tiny.lock`) and resolution rules.
- CLI subcommands and UX expectations.
- Documentation updates in `docs/open_tasks.md` and `docs/roadmap_next.md` as
  roadmap milestones.

## Derived tasks

These tasks translate the roadmap into actionable work items that can be tracked
in the main backlog.

- [ ] Draft the `tiny.toml` manifest schema and add a reference example.
- [ ] Define the `tiny.lock` schema (resolved versions, sources, checksums).
- [ ] Specify namespace resolution rules for `local`, `std`, and `pkg` imports.
- [ ] Implement dependency resolution with SemVer constraints and lockfile
  persistence.
- [ ] Add CLI stubs for `tiny pkg init`, `tiny pkg add`, and `tiny pkg resolve`.
- [ ] Document vendoring behavior and layout for `tiny pkg vendor`.
- [ ] Update `docs/open_tasks.md` and `docs/roadmap_next.md` with package/module
  milestones and links to this roadmap.
