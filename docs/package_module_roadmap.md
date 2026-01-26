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

### Namespace resolution rules

These rules describe how the resolver maps an import path to a module source.
They should be applied consistently across the interpreter, compiler, and
tooling so users see the same behavior everywhere.

1. **Parse the import path** into segments separated by `.`.
2. **Check reserved prefixes**:
   - `std.<path>` resolves to the canonical stdlib root, regardless of local
     files with the same name.
   - `pkg.<path>` resolves to the package graph defined in `tiny.toml` +
     `tiny.lock` (or `vendor/` when present).
3. **Resolve unprefixed imports (`local` namespace)**:
   - Look for a module under the project root `src/` tree first (for example,
     `import app.utils` → `src/app/utils.tiny` or `src/app/utils/__init__.tiny`).
   - If not found, fall back to other project-local search roots (e.g.,
     `./app/utils.tiny`), but never probe `std` or `pkg` namespaces implicitly.
4. **No implicit fallback across namespaces**:
   - If `std.foo` is missing, do not try `pkg.foo` or local equivalents.
   - If `pkg.foo` is missing, do not try `std.foo` or local equivalents.
5. **Collision rules**:
   - Local modules may shadow each other by directory order only within the
     local search roots; they can never shadow `std` or `pkg` modules.
   - `pkg` namespace is owned by the resolver; local modules cannot use
     `pkg.*` or `std.*` prefixes.
6. **Error reporting**:
   - When resolution fails, report which namespace was attempted and list the
     roots consulted (e.g., `std`, `pkg`, or local roots), so users can fix the
     import path or adjust configuration.

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

### Dependency overrides (path + registry fallback)

Use overrides to point a dependency at a local checkout while keeping the
registry constraint as the default resolution when the override path is absent.
The resolver should prefer the override path if it exists; otherwise it should
fall back to the registry version declared in `dependencies`.

```toml
[dependencies]
http = { version = "^1.2", registry = "https://registry.tiny-lang.org" }

[dependency-overrides]
http = { path = "../http" }
```

In this example, a developer can work against `../http` locally. CI or other
environments without the override path will resolve `http` from the registry
using the `^1.2` constraint.

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

## Lockfile schema (`tiny.lock`)

The lockfile captures fully resolved dependencies so builds are deterministic.
The format is TOML to keep it easy to diff and hand-inspect, but it should be
treated as tool-managed. All paths are stored normalized with `/` separators.

### Top-level fields

- `lockfile_version` (required): Integer schema version. Start at `1`.
- `manifest_hash` (required): SHA-256 hash of the normalized `tiny.toml`
  contents to detect drift.
- `generated_at` (required): ISO 8601 timestamp in UTC (e.g.,
  `2024-05-12T14:05:00Z`).
- `registry` (optional): Default registry URL used when resolving `pkg`
  dependencies.

### Dependency entries

Dependencies are grouped by the manifest section they came from. Each entry
must include:

- `name`: package name (slug).
- `version`: resolved SemVer string.
- `source`: one of `registry`, `path`, or `git`.
- `checksum`: checksum of the resolved package contents (hex SHA-256). For
  path dependencies, checksum is of the local directory snapshot at lock time.

Additional fields by source:

- `registry`: `registry` URL and `registry_checksum` (optional checksum of the
  registry index entry).
- `path`: `path` relative to the workspace root.
- `git`: `url` plus exactly one of `rev` or `tag`.

### Example lockfile

```toml
lockfile_version = 1
manifest_hash = "9a7c1b4d08f2fba51e5d95de8d0e0b9f21a7c6d4b29f0a7126a1ac5c6d7e2b3a"
generated_at = "2024-05-12T14:05:00Z"
registry = "https://registry.tiny-lang.org"

[[dependencies]]
name = "http"
version = "1.2.4"
source = "registry"
checksum = "c7d8f2ad12a67caa903987b2b5a8c1e0447e5f0f8b13796bc3e60bdcbd147c11"
registry = "https://registry.tiny-lang.org"
registry_checksum = "2f9b4a70d1f5b6a77c1e87f4c0a92e2c8817e9d0a2c98b0a548c0f5a0a1e118e"

[[dependencies]]
name = "config"
version = "0.1.0"
source = "path"
path = "../config"
checksum = "6a9bc4e1f035bb5df08a0e26f3ed9a5cbfbaedb8012b6b6d8a0d390b532a6f19"

[[dependencies]]
name = "cli"
version = "0.5.2"
source = "git"
url = "https://github.com/tiny-lang/cli"
rev = "4f9a0d8b12c3f6f7a9b2c4d5e6f7a8b9c0d1e2f3"
checksum = "59e24c5f58b9e8f6b5c4a1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2"
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

### `tiny pkg init` template

Use the following template as the baseline manifest emitted by `tiny pkg init`.
It mirrors the schema above and includes commented examples for optional
dependency formats:

- [`docs/tiny_pkg_init_template.toml`](./tiny_pkg_init_template.toml)

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
- [x] Define error messages and diagnostics for invalid manifest files.
- [x] Add a `tiny pkg init` template that matches the documented manifest schema.
- [x] Extend docs with a dependency override example (path + registry fallback).
- [x] Define the `tiny.lock` schema (resolved versions, sources, checksums).
- [x] Specify namespace resolution rules for `local`, `std`, and `pkg` imports.
- [ ] Implement dependency resolution with SemVer constraints and lockfile
  persistence.
- [ ] Add CLI stubs for `tiny pkg init`, `tiny pkg add`, and `tiny pkg resolve`.
- [ ] Document vendoring behavior and layout for `tiny pkg vendor`.
- [ ] Update `docs/open_tasks.md` and `docs/roadmap_next.md` with package/module
  milestones and links to this roadmap.

## Manifest diagnostics (error messages + codes)

Use the following error catalog whenever `tiny.toml` fails validation. Each
diagnostic includes a stable error code, the expected user-facing message, and
the location to highlight in tooling (file + line/column). When multiple issues
are present, emit the highest-severity error first, then list remaining
diagnostics in document order.

| Code | Severity | Message | When to emit | Highlight |
| --- | --- | --- | --- | --- |
| `PKG001` | error | `Manifest is missing required key "<key>".` | A required top-level field (e.g., `package`, `version`) is absent. | Key name in schema reference. |
| `PKG002` | error | `Invalid package name "<name>": expected kebab-case slug.` | `package.name` fails the slug regex from the validation rules. | Offending value. |
| `PKG003` | error | `Invalid version "<version>": expected SemVer "MAJOR.MINOR.PATCH".` | `version` does not match SemVer requirements. | Offending value. |
| `PKG004` | error | `Dependency "<dep>" must specify exactly one source (version, path, or git).` | A dependency entry has zero or multiple source keys. | Dependency entry. |
| `PKG005` | error | `Dependency path "<path>" does not exist.` | A `path` dependency points to a missing directory. | Path value. |
| `PKG006` | error | `Git dependency "<dep>" is missing required key "<key>".` | `git` dependency is missing `url` or `rev/tag`. | Missing key or dependency block. |
| `PKG007` | error | `Unsupported key "<key>" in manifest section "<section>".` | Extra keys not in the schema are found. | Offending key. |
| `PKG008` | error | `Duplicate dependency name "<dep>" in "<section>".` | Same dependency appears twice in `dependencies`/`dev-dependencies`. | Duplicate entry. |
| `PKG009` | error | `Dependency version constraint "<constraint>" is invalid.` | Constraint cannot be parsed as SemVer range. | Constraint value. |
| `PKG010` | warning | `Dependency "<dep>" has no explicit version; using "*" for resolution.` | A dependency lists only a `git` URL without a ref, or omits `version`. | Dependency entry. |

### Notes for tooling

- Always include the manifest filename in error output, e.g.
  `tiny.toml:12:5 PKG003 Invalid version "1.0".`
- If the parser fails before a section can be identified, report `PKG001` with
  the missing key rather than a generic syntax error, then include the parser
  detail as a secondary note.
- For `PKG005`, check path existence relative to the manifest directory and
  normalize separators for display.
