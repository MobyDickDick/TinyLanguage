# Changelog

All notable changes to TinyLanguage will be documented in this file.

## 1.0.0 (planned)

Release notes: [`docs/release_notes_v1.md`](docs/release_notes_v1.md).

### Added
- Installed `tiny project` and `tiny c` workflows, VS Code runtime discovery from
  the selected Python environment, portable project settings, and isolated
  CLI/editor acceptance tooling.
- Imports preserve buffered output and the selected debugger output mode in
  multi-file programs.
- Installable Python wheel/sdist metadata and `tiny`, `tiny-project`, `tiny-pkg`,
  `tinyc`, and `tiny-lsp` commands with bundled runtime and Tiny stdlib assets.
- `tiny --version` for installed and frozen runtimes; runtime imports keep
  stitched traceback source in memory without rewriting installation files.
- Artifact build/rebuild checks, standalone packaging spec, normalized VSIX
  generation, dependency inventories and platform artifact CI (qualification pending).
- Stable interpreter + core language scope for the 1.0.0 release.
- Baseline documentation covering the language spec, CLI usage, and stdlib.

### Known issues / limitations
- LLVM and native/C compiler backends remain experimental and are out of scope for 1.0.0.
- Performance guarantees remain outside the 1.0.0 scope. Packaging implementation
  is available; full release qualification is tracked in `docs/open_tasks.md`.
