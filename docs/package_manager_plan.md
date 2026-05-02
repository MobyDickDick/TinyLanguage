# Package manager plan

This plan defines how TinyLanguage will ship a minimal, reproducible package
manager with clear registry layout, lockfiles, and semantic-versioning
expectations. It builds on `docs/package_module_roadmap.md` and focuses on the
first concrete implementation milestones.

## Goals

- Ensure deterministic dependency resolution via lockfiles.
- Provide a registry layout that can scale from a single hosted index to
  multiple registries.
- Define semantic-versioning rules and upgrade workflows.
- Keep the initial CLI surface minimal but extensible.

## Non-goals (v0)

- No compiled artifact caching or binary distribution.
- No private registry auth beyond token-based HTTP authorization.
- No dependency graph visualizer or advanced resolution strategies (e.g.,
  multi-version installs within one project).

## Versioning policy

- **SemVer required** for all published packages.
- **API compatibility**: breaking changes require a major bump; additive changes
  require minor; fixes require patch.
- **Pre-releases**: allowed for `-alpha`, `-beta`, `-rc` tags; the resolver may
  only pick prereleases when explicitly requested.
- **Resolution rule**: the resolver selects the newest compatible version
  within constraints, then pins it in the lockfile.

## Registry layout

The registry is split into two layers for flexibility:

1. **Index service** (metadata + versions)
   - `GET /api/v1/index/<package>` returns JSON metadata (versions, dist URLs,
     checksums, required TinyLanguage version).
   - Supports HTTP caching via ETag/If-None-Match for offline-friendly updates.
2. **Distribution storage** (package artifacts)
   - `GET /dist/<package>/<version>.tar.gz` returns a tarball of the package
     source.
   - Artifacts are content-addressed (checksum in metadata) to prevent tampering.

### Registry metadata schema (initial)

```json
{
  "name": "http",
  "versions": {
    "1.2.0": {
      "dist": "https://registry.tiny-lang.org/dist/http/1.2.0.tar.gz",
      "sha256": "<hex>",
      "tiny": ">=1.0.0",
      "published_at": "2025-02-01T12:00:00Z"
    }
  }
}
```

## Lockfile format (`tiny.lock`)

- `tiny.lock` is TOML for human readability.
- It records every resolved package version, its source registry, and checksum.
- It captures the exact dependency graph to guarantee repeatable installs.

```toml
[metadata]
format = 1
resolver = "semver-v1"

[[package]]
name = "http"
version = "1.2.0"
registry = "https://registry.tiny-lang.org"
checksum = "sha256:<hex>"

  [package.dependencies]
  json = "^0.9"
```

## Manifest + CLI workflow

### Manifest (`tiny.toml`)

The manifest format is defined in `docs/package_module_roadmap.md`. The package
manager validates it and enforces SemVer constraints.

### CLI commands (v0)

- `tiny pkg init`: create `tiny.toml` and a default `src/` layout.
- `tiny pkg add <name>[@<constraint>]`: update manifest, resolve, write
  `tiny.lock`.
- `tiny pkg remove <name>`: drop dependency from the manifest and update
  `tiny.lock` after re-resolving.
- `tiny pkg update [<name>]`: refresh locked versions within constraints.
- `tiny pkg vendor`: download sources to `vendor/`, emit `vendor/README.md` for
  auditing, and rewrite lockfile sources. Refuses to run if the lockfile
  `manifest_hash` does not match the current `tiny.toml` (lockfile drift).
- `tiny pkg publish`: validate, package, and upload to registry (token-based).

#### `tiny pkg publish --dry-run` (spec)

Purpose: validate and assemble a publish payload without performing any network
operations. The command is meant to mirror the real publish flow while making
the staged artifacts inspectable for review and CI checks.

**Inputs**

- `tiny.toml` (package metadata, dependencies, and registry configuration).
- `tiny.lock` (resolved dependency versions + checksums).
- Package source tree rooted at the project (defaults to current working
  directory).
- Optional flags: `--registry <url>` override; `--output-dir <path>` to direct
  staging artifacts; `--profile <name>` to select a manifest profile.
- Environment: `TINY_PKG_TOKEN` **must be ignored** in dry-run mode to enforce
  the no-network guarantee.

**Outputs**

- Exit code `0` when validation passes and all artifacts are staged.
- Non-zero exit when validation fails (missing metadata, invalid SemVer,
  lockfile drift, or missing required files).
- A human-readable summary of what would be uploaded (package name, version,
  registry URL, artifact sizes, and checksum).

**Expected artifacts (staged on disk)**

- `publish/<name>-<version>.tar.gz`: source tarball matching the registry layout.
- `publish/<name>-<version>.json`: registry metadata payload (dist URL placeholder,
  checksum, TinyLanguage version range, publish timestamp placeholder).
- `publish/manifest.json`: build manifest containing source file list, total
  bytes, and the computed SHA-256 for the tarball.

### Minimal package manager UX (v0)

The first release focuses on a small, teachable workflow that covers project
bootstrap, dependency changes, and reproducible builds.

1. **Initialize**: `tiny pkg init` creates `tiny.toml`, a `src/` directory, and
   an empty `tiny.lock` stub so the project is immediately reproducible.
2. **Add dependencies**: `tiny pkg add <name>[@<constraint>]` writes the
   dependency to `tiny.toml`, resolves versions, and updates `tiny.lock` with
   the full graph and checksums.
3. **Remove dependencies**: `tiny pkg remove <name>` deletes the entry from
   `tiny.toml`, re-resolves, and rewrites `tiny.lock` to drop unused packages.
4. **Refresh locks**: `tiny pkg update [<name>]` upgrades resolved versions
   within constraints and rewrites `tiny.lock`.
5. **Vendor for offline builds**: `tiny pkg vendor` verifies the lockfile is
   in sync with `tiny.toml` (matching `manifest_hash`), then downloads sources
   into `vendor/`, rewrites lockfile sources to the vendored paths, and emits
   `vendor/README.md` with an audit summary (manifest hash, registry sources,
   and the full dependency list).
6. **Reproducible installs**: the interpreter + tooling read `tiny.lock` by
   default; when it is missing or out of date, the CLI refuses to run without
   an explicit `tiny pkg add/update` to restore determinism.

## Resolution strategy

1. Load `tiny.toml` dependencies.
2. Resolve versions using registry metadata and SemVer constraints.
3. Prefer local path overrides when `dependency-overrides` are configured.
4. Write the resolved graph into `tiny.lock`.
5. Install by downloading packages into a local cache and extracting into
   `vendor/` when requested.

## Backwards compatibility and migration

- **Lockfile format changes** increment `metadata.format` and preserve prior
  parsers for at least one major TinyLanguage release.
- **Registry protocol changes** version the API path (`/api/v1/` → `/api/v2/`).
- **Migration tooling**: `tiny pkg lock --migrate` updates lockfiles to the
  latest supported format.

## Milestones

1. **Plan finalized** (this document): lockfile format, registry layout, CLI
   scope defined.
2. **Resolver prototype**: implement SemVer resolution and lockfile writing.
3. **Registry prototype**: simple HTTP index + dist server.
4. **CLI integration**: `tiny pkg init/add/update` wired into the interpreter.
5. **Publishing flow**: authentication, tarball upload, metadata update.

## Open questions

- ✅ Resolved (2026-04-25): `tiny.lock` now carries a top-level
  `toolchain = "<constraint>"` field when `tiny.toml` declares
  `[package].tiny_language`. Older toolchains can refuse incompatible lockfiles
  before dependency resolution.
- ✅ Resolved (2026-05-02): ship registry metadata signing in a staged rollout rather than day one.
  - Phase 1 (v1.1): publish unsigned index metadata over TLS with deterministic hashes in `tiny.lock`.
  - Phase 2 (v1.2): add optional signature verification (`tiny pkg verify --signatures`) and publish root keys in repo docs.
  - Phase 3 (v1.3): require signatures for official registry channels; keep an explicit `--allow-unsigned` escape hatch for private mirrors.
