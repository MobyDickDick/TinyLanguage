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
- `tiny pkg update [<name>]`: refresh locked versions within constraints.
- `tiny pkg vendor`: download sources to `vendor/` and rewrite lockfile sources.
- `tiny pkg publish`: validate, package, and upload to registry (token-based).

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

- Should `tiny.lock` include resolved TinyLanguage version constraints so older
  toolchains can refuse incompatible lockfiles?
- Should the registry support signed metadata (TUF-style) from day one?
