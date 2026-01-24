# Stdlib consolidation decision tasks

Use this task list to evaluate whether the TinyLanguage stdlib should remain
split between `stdlib/` (Tiny `.tiny` sources) and `src/stdlib/` (native
registrations + curated Tiny sources), or be consolidated into a single root.

## Tasks

### 1) Capture the current state
- [x] Document how `tiny_language_runtime.py` resolves the stdlib search root.
- [x] Summarize what lives in `stdlib/` vs. `src/stdlib/` (include any overlap).
- [x] Note any packaging/distribution assumptions about both directories.

Current behavior highlights:
- The module resolver treats `stdlib.*` imports as a special case and resolves them
  from the repository root `stdlib/` directory. Non-stdlib imports continue to use
  `TINYPATH`, the current working directory, and the runtime location as search roots.
- `stdlib/` now hosts all Tiny `.tiny` modules (e.g. `math`, `random`, `string`,
  `statistics`, `json`, `os`, `pathlib`, `collections`, `io`, `datetime`).
- `src/stdlib/__init__.py` remains the native registration layer for runtime-backed
  namespaces (Math, String, Collections, File, JSON, Async, etc.).
- Packaging assumptions: Tiny source modules are expected under `stdlib/`, while
  the Python runtime package continues to live under `src/`.

### 2) Evaluate option A: keep the split
- [x] Confirm that existing Tiny programs import from `stdlib/` implicitly.
- [x] Identify maintenance cost or confusion caused by two roots.
- [x] Record any advantages of keeping native registration separate.

Notes:
- Tiny programs already use `import stdlib.*`, which aligns with the `stdlib/` root.
- Two separate Tiny source roots created duplication, divergent module content, and
  unclear ownership for updates.
- The native registration layer is still valuable, so it remains isolated in
  `src/stdlib/__init__.py` even as Tiny sources consolidate elsewhere.

### 3) Evaluate option B: consolidate into a single root
- [x] Choose a target root (`src/stdlib/` or `stdlib/`) and justify why.
- [x] Identify import-path changes required for existing programs.
- [x] Assess how native registration can coexist with Tiny sources in one root.
- [x] List tooling/tests/docs that would need updates.

Decision details:
- Target root: `stdlib/`, because it already matches the public import namespace and
  is referenced throughout docs/tests.
- Import paths remain `import stdlib.*`; no changes required for callers.
- Native registration stays in `src/stdlib/__init__.py` and is accessed via
  `register_stdlib`, so Tiny sources can live exclusively in `stdlib/`.
- Updates required: module resolver search paths, stdlib source tests, and relocation
  of Tiny stdlib source files into `stdlib/`.

### 4) Decide and record
- [x] Select the preferred option.
- [x] Record rationale, decision owner, and decision date.

### 5) Plan migration (if consolidating)
- [x] Update runtime search logic for a single stdlib root.
- [x] Move Tiny `.tiny` modules into the chosen root.
- [x] Update docs and tests to use the new import paths.
- [x] Provide deprecation notes and a compatibility shim (if needed).
- [x] Remove legacy root references after the grace period.

#### Deprecation notes + compatibility shim

- **Legacy stdlib root**: The runtime no longer falls back to `src/stdlib/` for
  Tiny `.tiny` modules. All Tiny stdlib sources must live under `stdlib/`.
- **Migration required?** Not for import paths. Tiny code continues to use
  `import stdlib.*`. Only file locations are enforced.
- **How to migrate**: Move any legacy `.tiny` files from `src/stdlib/` into the
  top-level `stdlib/` directory, keeping the same filenames.

## Decision log

- **Chosen option**: Consolidate Tiny stdlib sources under `stdlib/`.
- **Rationale**: Aligns with the public import namespace, removes duplicated
  module sources, and keeps the native registration layer isolated in `src/stdlib/__init__.py`.
- **Decision owner**: Codex (automated documentation task).
- **Date**: 2026-01-24
