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

## Manifest schema (`tiny.toml`)

The manifest defines package metadata and dependency constraints. It should be
friendly to hand edits while remaining strict enough for tooling to validate.

### Required keys

```toml
[package]
name = "example-app"         # Lowercase slug, can include dashes.
version = "0.1.0"            # SemVer package version.
```

### Validation rules

- `package.name` is required, must be lowercase `a-z`, `0-9`, and `-`, start
  with a letter, end with a letter or digit, and be 2-64 characters long.
- `package.version` is required and must follow SemVer `MAJOR.MINOR.PATCH`
  (no leading zeroes unless the number is `0`). Pre-release and build metadata
  are allowed (e.g., `1.2.3-alpha.1+build.7`).
- `package.description` is optional; if present, keep it under 160 characters.
- `package.license` is optional; if present, prefer SPDX identifiers.
- `package.authors` is optional; if present, each entry must be a non-empty
  string (optionally with an email in angle brackets).
- `package.homepage` and `package.repository` are optional; if present, they
  must be valid `http://` or `https://` URLs.
- Dependency names in `dependencies`, `dev-dependencies`, and
  `build-dependencies` must follow the same slug rules as `package.name`.
- Dependency entries must be either a version constraint string or a table with
  exactly one of `version` or `path` (optional `registry` only with `version`).
- `dependencies.*.version` must be a valid SemVer constraint (e.g., `^1.2`,
  `~0.9`, `>=1.0 <2.0`).
- `dependencies.*.path` must be a relative path and may not escape the workspace
  root when normalized.
- `registries.*` values must be valid `http://` or `https://` URLs, and the
  `default` key is required if any dependency uses a registry override.

### Optional metadata

```toml
[package]
description = "One-line summary of the package."
license = "MIT"
authors = ["Ada Lovelace <ada@example.com>"]
homepage = "https://example.com"
repository = "https://github.com/example/example-app"
```

### Dependency tables

Dependencies are grouped by scope. Each dependency can be a version constraint,
or a structured entry for path/registry overrides.

```toml
[dependencies]
http = "^1.2"
json = { version = "~0.9", registry = "https://registry.tiny-lang.org" }

[dev-dependencies]
test-utils = "^0.3"

[build-dependencies]
codegen = { version = ">=1.0 <2.0" }
```

### Local path dependencies

```toml
[dependencies]
my-lib = { path = "../my-lib" }
```

### Registry configuration

```toml
[registries]
default = "https://registry.tiny-lang.org"
internal = "https://packages.internal.example.com"
```

### Reference example

```toml
[package]
name = "weather-cli"
version = "0.4.2"
description = "CLI for fetching weather summaries."
license = "Apache-2.0"
authors = ["TinyLanguage Team <team@tinylang.dev>"]
repository = "https://github.com/tiny-lang/weather-cli"

[dependencies]
http = "^1.2"
json = "~0.9"
cli = { version = ">=0.5 <1.0" }
config = { path = "../config" }

[dev-dependencies]
test-utils = "^0.3"

[registries]
default = "https://registry.tiny-lang.org"
```

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

- [x] Draft the `tiny.toml` manifest schema and add a reference example.
- [x] Document validation rules for manifest fields (required keys, slug rules,
  version format, and URL validation).
- [ ] Define error messages and diagnostics for invalid manifest files.
- [ ] Add a `tiny pkg init` template that matches the documented manifest schema.
- [ ] Extend docs with a dependency override example (path + registry fallback).
- [ ] Define the `tiny.lock` schema (resolved versions, sources, checksums).
- [ ] Specify namespace resolution rules for `local`, `std`, and `pkg` imports.
- [ ] Implement dependency resolution with SemVer constraints and lockfile
  persistence.
- [ ] Add CLI stubs for `tiny pkg init`, `tiny pkg add`, and `tiny pkg resolve`.
- [ ] Document vendoring behavior and layout for `tiny pkg vendor`.
- [ ] Update `docs/open_tasks.md` and `docs/roadmap_next.md` with package/module
  milestones and links to this roadmap.
