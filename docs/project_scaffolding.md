# Project scaffolding & CLI ergonomics

This document defines the initial scaffolding templates and CLI ergonomics for
creating TinyLanguage projects. The goal is a minimal, predictable layout that
is easy to evolve as the package manager matures.

## Goals

- Provide a single, documented entry-point for new projects.
- Keep generated layouts small and idiomatic to TinyLanguage conventions.
- Ensure the generated layout works with the planned `tiny.toml` manifest and
  module-resolution rules in `docs/package_module_roadmap.md`.
- Make the CLI version-aware so future changes can introduce new templates
  without breaking existing projects.

## CLI design

### Entry point

`tiny pkg init` creates a new TinyLanguage project in the target directory.

```bash
# Use the current default template (versioned behind the scenes).
tiny pkg init

# Explicitly request a template version.
tiny pkg init --template v1

# Scaffold into a specific folder.
tiny pkg init ./weather-cli
```

### Flags and behavior

- `--template <version>`
  - Select a template version (`v1`, `v2`, etc.).
  - Defaults to the latest stable template supported by the CLI.
- `--name <slug>`
  - Override the generated package name (defaults to the directory name).
  - Must pass the manifest slug rules.
- `--bin` / `--lib`
  - `--bin` (default) generates a `main.tiny` entry point.
  - `--lib` generates a `lib.tiny` entry point and skips CLI-specific assets.
- `--with-tests`
  - Adds a minimal test harness and a sample test file.
- `--force`
  - Overwrite existing files if the target directory is not empty.

### Versioned ergonomics

The CLI exposes a stable `tiny pkg init` interface while allowing template
versions to evolve:

- Template metadata is stored in a `template.version` field inside `tiny.toml`.
- The CLI can warn when the template version is deprecated and offer an upgrade
  path (`tiny pkg upgrade-template`).
- Existing projects keep working even if the CLI defaults change, because the
  template version is recorded in the manifest.

## Template v1 layout

```text
project-root/
├─ tiny.toml
├─ README.md
├─ src/
│  ├─ main.tiny        # or lib.tiny for --lib
│  └─ __init__.tiny    # optional helper namespace entry
├─ tests/              # only with --with-tests
│  └─ main_test.tiny
└─ .gitignore
```

Reference files for this layout live in
[`docs/project_template_v1/`](./project_template_v1/).

### Generated files

#### `tiny.toml`

```toml
[package]
name = "example-app"
version = "0.1.0"

[package.template]
version = "v1"
kind = "bin" # "bin" or "lib"
```

#### `src/main.tiny` (bin template)

```tiny
fn main()
  print("Hello from TinyLanguage!")
end
```

#### `src/lib.tiny` (lib template)

```tiny
fn hello(name)
  return "Hello, " + name + "!"
end
```

#### `tests/main_test.tiny` (optional)

```tiny
fn test_hello()
  assert(hello("Tiny") == "Hello, Tiny!")
end
```

#### `.gitignore`

```
# TinyLanguage artifacts
build/
.tiny-cache/
```

## Upgrade path

`tiny pkg upgrade-template` should:

- Read `package.template.version` and compare it against the CLI-supported
  template versions.
- Offer a diff-aware upgrade (reuse `tiny fmt` and `tiny lint` for safety).
- Document any breaking changes in generated files (e.g., new manifest keys).

## Future template ideas

- Add `examples/` or `scripts/` folders for common workflows.
- Introduce workspace templates (`tiny pkg init --workspace`) with a root
  manifest and per-package subdirectories.
- Support `--with-ci` to generate a minimal CI workflow for formatting and
  tests.
