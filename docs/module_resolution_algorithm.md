# Module resolution algorithm (shared across backends)

This document specifies the deterministic module-resolution algorithm used by
TinyLanguage tooling, the interpreter runtime, and compiled/native backends that
reuse the shared helpers in `src/tiny_language_module_resolution.py`.

## Goals

- **Deterministic results**: the same import path always maps to the same set of
  candidate files given the same project layout, search paths, and lockfile.
- **Explicit namespaces**: `std.*` and `pkg.*` imports never fall back to local
  modules.
- **Portable behavior**: the algorithm is shared so diagnostics, linters, and
  runtime resolution behave identically.

## Inputs

- **Import path**: the raw import string (e.g. `std.io`, `pkg.http.client`,
  `app.utils`, `.helpers`).
- **Caller context**:
  - `caller_namespace` (module namespace of the importing file), used for
    relative imports.
  - `caller_path` (filesystem path of the importing file), used to locate
    relative modules and the project root.
- **Resolution configuration** (`ModuleResolutionConfig`):
  - `search_paths`: ordered list of local roots. Defaults to `TINYPATH` entries
    (if set) followed by the current working directory and the TinyLanguage
    source root.
  - `stdlib_root`: canonical stdlib root (resolved from `src/../stdlib`).
  - `project_root`: the nearest directory containing `tiny.toml`, `tiny.lock`,
    or `vendor/` (determined by walking upward from the caller or CWD).

## Algorithm overview

### 1) Normalize relative import paths

Relative imports start with one or more `.` characters. The resolver:

1. Counts leading dots.
2. Walks upward in the caller namespace by the same number of segments.
3. Appends any remaining suffix segments.

If the caller namespace is missing or the leading dots walk beyond the namespace
root, resolution fails with `E008`.

### 2) Select resolution strategy by namespace prefix

The import namespace drives all subsequent lookup behavior:

- **`std.*`**: map the suffix path directly to the stdlib root.
- **`pkg.*`**: consult the lockfile/vendor tree in the project root.
- **Unprefixed**: treat as a local module under the caller directory and
  configured search roots.

There is **no implicit fallback** between these namespaces.

### 3) Build candidate filesystem paths

For each module path segment list `foo.bar.baz`, the resolver considers two
shapes under each root:

1. `foo/bar/baz.tiny`
2. `foo/bar/baz/__init__.tiny`

These candidates are ordered deterministically by root order and shape order.

#### Local modules (unprefixed)

Roots are consulted in this order:

1. `caller_path.parent` (if present).
2. `search_paths` (from `TINYPATH`, then default roots).

#### Standard library (`std.*`)

Only the `stdlib_root` is consulted.

#### External packages (`pkg.*`)

1. Read `tiny.lock` for dependency entries matching the package name.
2. For each matching entry, compute the package root:
   - `source = "path"`: `vendor/local/<name>/<version>` when vendored, otherwise
     the explicit `path` relative to the project root.
   - `source = "registry"`: `vendor/<registry_host>/<name>/<version>`.
   - `source = "git"`: `vendor/git/<name>/<version>`.
3. For each package root, probe `<root>/src/` first, then `<root>/`.

If no lockfile entries are present, the resolver falls back to local search
roots (caller + `search_paths`) to keep development workflows viable.

## Error handling and diagnostics

- Failed resolution yields `E008` and includes the original import name.
- Relative import errors are raised before any filesystem access.
- Consumers may log or surface the ordered candidate list for debugging.

## Test coverage

Edge-case coverage is maintained in `tests/detailtests/test_module_resolution_algorithm.py`:

- Relative import traversal errors.
- Deterministic candidate ordering for stdlib modules.
- Lockfile + vendor-derived resolution for `pkg.*` imports.
- Precedence checks for package workflows: local path overrides first,
  then vendored registry roots, then vendored git roots.

## Notes for backend integrations

Native backends should reuse the shared helpers rather than reimplementing
lookup logic. This ensures that compiled code and the interpreter resolve the
same module names and produce consistent diagnostics.
