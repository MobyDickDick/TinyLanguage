# Changelog

All notable changes to TinyLanguage will be documented in this file.

## 1.0.0 (planned)

Release notes: [`docs/release_notes_v1.md`](docs/release_notes_v1.md).

### Added
- Source-bound release regression evidence (commands, logs, JUnit and artifact
  hashes) replaces the Markdown-checkbox gate. Candidate scope and remaining
  release qualification are documented in `docs/release_scope_v1.md`.
- Installed `tiny project` and `tiny c` workflows, VS Code runtime discovery from
  the selected Python environment, portable project settings, and isolated
  CLI/editor acceptance tooling.
- Imports preserve buffered output and the selected debugger output mode in
  multi-file programs.
- Installable Python wheel/sdist metadata and `tiny`, `tiny-project`, `tiny-pkg`,
  `tinyc`, and `tiny-lsp` commands with bundled runtime and Tiny stdlib assets.
- `tiny --version` for installed and frozen runtimes; ordinary runtime module
  imports work without generating or compiling concatenated source.
- Artifact build/rebuild checks, standalone packaging spec, normalized VSIX
  generation, dependency inventories and platform artifact CI (qualification pending).
- Candidate interpreter + core language stability target for 1.0.0
  (qualification pending).
- Baseline documentation covering the language spec, CLI usage, and stdlib.

### Fixed
- LLVM division now preserves fractional results for integer operands, including
  inferred function returns and later numeric operations. Integer and floating
  zero divisors report an error and exit predictably. The bounded AUD-001 repair
  and remaining numeric limits are documented in `docs/independent_correctness_audit.md`.
- Runtime modules now declare their own dependencies and share canonical AST
  classes. The compatible public facade replaces source stitching; tracebacks
  identify maintained files, and read-only concurrent installed imports are
  exercised by the package verifier. See `docs/runtime_module_boundaries.md`.
- Interval `+`, `-`, `*`, `/` now enclose pointwise real results with directed
  outward rounding, correct division across zero, explicit empty/unbounded and
  exterior sets, and safe integer/Number conversion. Neighbor envelopes use
  infinite directions. Legacy Math interval estimates are marked `approximate`;
  the contract and migration notes are in `docs/interval_arithmetic_contract.md`.
- Opt-in copy-on-call now copies mutable arguments independently of return
  expressions; scalar calculations and alias returns cannot grant writes to
  caller data. Shared/cyclic graph copying preserves aliases across arguments.
  Method receivers stay shared. This changes the previous escape behavior;
  migration and measured costs are in `docs/copy_on_call_contract.md`.
- LLVM executable builds now link a C `main` launcher for the emitted
  `tiny_main` entry point, including fresh-install platform qualification.
- Unchanged module summaries retain their original bytes and timestamps across
  Windows/Linux, preventing false candidate-source changes from CRLF conversion.

### Known issues / limitations
- Interval arithmetic and opt-in copy-on-call remain outside the frozen
  stability target. Interval guarantees cover the four documented operators
  on the reference interpreter; Math interval estimates and compiler backends
  have no enclosure promise. Copy-on-call's revised
  contract and numeric-pointer/manual-cleanup limits are documented separately.
- LLVM and native/C compiler backends remain experimental and are out of scope for 1.0.0.
- Performance guarantees remain outside the 1.0.0 scope. Packaging implementation
  is available; full release qualification is tracked in `docs/open_tasks.md`.
