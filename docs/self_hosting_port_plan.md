# TinyLanguage self-hosting port plan

This document breaks down the work needed to port core Python modules to TinyLanguage itself. The goal is to ship a parallel Tiny implementation that can run the existing demos and tests while keeping the Python version as a reference.

## Target modules (inventory)

The repository splits the interpreter and tooling into a handful of focused modules:

- `tiny_language_lexer.py` / `tiny_language_parser.py`: front-end that turns source into AST nodes.
- `tiny_language_ast.py`: definitions for AST nodes shared across interpreter, transpilers, and native backends.
- `tiny_language_runtime.py` / `tiny_language_eval.py`: interpreter runtime, built-ins, and evaluation loop.
- `tiny_language_linter.py`: static checks such as must-use rules, unreachable code, and type consistency.
- `tiny_language_transpilers.py`: helpers for lowering AST to other language-specific renderers.
- `tiny_language_codegen_native.py` / `native_ir.py` / `native_vm.py`: native backend prototype and VM.
- `tiny_language_cli.py` / `tiny_lang_cli.py` / `language_server_cli.py`: CLI entry points and language-server wiring.
- Shared utilities (`tiny_language_api.py`, `formatter.py`, `tiny_errors.py`, `tiny_language_preamble.py`).

## Porting priorities

1. **Core execution path** (front-end + interpreter): start with `tiny_language_lexer.py`, `tiny_language_parser.py`, `tiny_language_ast.py`, `tiny_language_runtime.py`, and `tiny_language_eval.py` so Tiny code can lex/parse/evaluate other Tiny programs.
2. **Diagnostics**: port `tiny_language_linter.py` after the interpreter so we retain must-use/unreachable diagnostics in self-hosted runs.
3. **Interop and tooling**: port `tiny_language_transpilers.py` and CLI wrappers (`tiny_language_cli.py`, `tiny_lang_cli.py`) to exercise end-to-end flows from Tiny sources.
4. **Native backend**: once the interpreter is stable, mirror `native_ir.py`, `tiny_language_codegen_native.py`, and `native_vm.py` to validate the native path under Tiny.
5. **Language server**: translate `language_server.py` and `language_server_cli.py` last; depends on the prior steps and ensures LSP features survive the migration.

## Translation guidelines

- Keep Python and Tiny files side by side (e.g., `src_tiny/lexer.tiny`) with matching module names and short docstrings describing parity with the Python original.
- Mirror public APIs and error messages so existing tests map directly; add adapters only when a Tiny runtime limitation requires it.
- Prefer incremental commits per module cluster (lexer/parser, interpreter, linter, tooling) to keep reviews small.
- Add snapshot-style tests that run the Python and Tiny implementations against the same inputs and compare outputs or error codes.

## Testing and validation checklist

- Interpreter parity: for each migrated module, run the relevant sections of `tests/test_tiny_language.py` through both Python and Tiny entry points (document any expected deviations).
- CLI coverage: exercise `python src/tiny_language_cli.py --file sample.tiny` and the Tiny-hosted equivalent once available.
- Native backend smoke tests: reuse `run_all.py` scenarios to compare interpreter vs. native execution paths.
- Language server: record sample `initialize`, `textDocument/hover`, and `textDocument/completion` exchanges using both hosts.

## Bootstrap milestone: Python-independent self-hosting compiler

This milestone defines how TinyLanguage reaches a **Python-independent bootstrap**
path while preserving deterministic outputs across hosts. The milestone is split
into platform seed requirements, reproducible bootstrap stages, and parity
validation gates that must pass before release promotion.

### Seed executable requirements (trust anchor per OS)

Each supported OS starts from a minimal, signed seed executable named
`tiny-seed` that can compile the self-hosting compiler core from source.

| OS | Required seed artifact | Mandatory capabilities | Packaging + trust requirements |
| --- | --- | --- | --- |
| Windows (x86_64) | `tiny-seed-windows-x86_64.exe` | Parse + type-check + emit native object files for the compiler core; deterministic file ordering; stable diagnostics. | Authenticode signature, SHA-256 checksum in release manifest, reproducible build attestation. |
| macOS (arm64 + x86_64) | `tiny-seed-macos-universal2` | Same compiler-core subset as Windows plus deterministic universal-binary linking pipeline. | Notarized + codesigned artifact, SHA-256 checksum, reproducibility metadata (builder image + toolchain hash). |
| Linux (x86_64 + arm64) | `tiny-seed-linux-<arch>` | Same compiler-core subset plus deterministic archive/link behavior under glibc baseline. | Detached signature (`.sig`), SHA-256 checksum, containerized reproducible build recipe reference. |

Seed executables are intentionally minimal and only include the language/runtime
surface needed to build the first Tiny-hosted compiler binary.

### Reproducible bootstrap steps

1. **Pin inputs**
   - Check out a tagged source revision.
   - Resolve the pinned toolchain set (`VERSION`, lockfiles, and release metadata).
2. **Stage A — Python-hosted reference build**
   - Build compiler artifact `compiler_py_host` via the existing Python-hosted path.
   - Record provenance: commit SHA, platform, toolchain digest, and output hash.
3. **Stage B — seed build**
   - Use `tiny-seed` for the platform to compile the Tiny compiler sources into
     `compiler_seed_host`.
   - Persist full build logs and normalized command transcript under `var/bootstrap/`.
4. **Stage C — Tiny self-rebuild**
   - Run `compiler_seed_host` to rebuild the same compiler sources, producing
     `compiler_tiny_host`.
   - Re-run once more (`compiler_tiny_host` rebuilding itself) to produce
     `compiler_tiny_host_round2`.
5. **Stage D — reproducibility check**
   - Compare normalized hashes of `compiler_tiny_host` and
     `compiler_tiny_host_round2`; they must match bit-for-bit after permitted
     metadata normalization (timestamp/path stripping).
6. **Publish bootstrap bundle**
   - Store seed artifact metadata, all stage hashes, parity report, and logs as
     release artifacts for the milestone checkpoint.

### Parity validation gates (Python-hosted vs Tiny-hosted)

Promotion is blocked unless all gates below pass on each supported OS:

1. **Compiler output parity gate**
   - Build a fixed corpus with `compiler_py_host` and `compiler_tiny_host`.
   - Produced IR/native outputs must be byte-identical after canonical
     normalization rules.
2. **Diagnostics parity gate**
   - Error codes and primary diagnostic spans must match across both hosts for
     the regression corpus (parser, type, runtime, module-resolution failures).
3. **Behavior parity gate**
   - Execute the conformance/parity suites against artifacts produced by both
     hosts; pass/fail sets must be identical.
4. **Bootstrap stability gate**
   - Self-rebuild round-trip hash equality (`round1 == round2`) is required per OS.
5. **Performance guardrail gate**
   - Tiny-hosted compiler build/runtime performance must remain within agreed
     tolerance against Python-hosted baselines (documented in
     `docs/performance_budgets_and_baselines.md`).

### Milestone exit criteria

The self-hosting bootstrap milestone is complete when:

- Seed executables for Windows/macOS/Linux are published with signatures and
  checksums.
- The reproducible bootstrap flow above is automated and archived for at least
  one tagged release candidate per OS.
- All parity validation gates pass for that release candidate with no open
  blocker-level deviations.

## Next tasks

- **AST + runtime parity:** ✅ Completed alignment for `src_tiny/tiny_language_ast.tiny`, `src_tiny/tiny_language_runtime.tiny`, and `src_tiny/tiny_language_eval.tiny` with their Python counterparts, keeping built-in behaviors and error messages delegated to the Python runtime for parity.
- **Native backend parity:** ✅ Mirrored `src/native_ir.py`, `src/tiny_language_codegen_native.py`, and `src/native_vm.py` into their `src_tiny/` equivalents, keeping opcode names, formatting, and error messages aligned.
- **Transpiler + CLI parity:** ✅ ensure `src_tiny/tiny_language_transpilers.tiny`, `src_tiny/tiny_language_cli.tiny`, and `src_tiny/tiny_lang_cli.tiny` match Python outputs/flags; add snapshot parity checks alongside existing tests (see `tests/detailtests/test_tiny_transpilers.py` and `tests/detailtests/test_tiny_language_cli_self_host.py`).
- **Validation updates:** ✅ add parity notes and progress to the status table below as each cluster lands.

## Status tracking

Track progress in this table as modules are ported. An empty "Tiny parity" cell means work is still pending.

| Module cluster | Python source | Tiny parity file | Status | Notes |
| --- | --- | --- | --- | --- |
| Lexer + parser | `src/tiny_language_lexer.py`, `src/tiny_language_parser.py` | `src_tiny/tiny_language_lexer.tiny`, `src_tiny/tiny_language_parser.tiny` | ✅ Complete | Lexer/parser parity is implemented; see the parity notes below for the validation checklist. Smoke-tested via `tests/test_tiny_parser_self_host.py` and `tests/test_language_spec_grammar.py`. |
| AST + runtime | `src/tiny_language_ast.py`, `src/tiny_language_runtime.py`, `src/tiny_language_eval.py` | `src_tiny/tiny_language_ast.tiny`, `src_tiny/tiny_language_runtime.tiny`, `src_tiny/tiny_language_eval.tiny` | ✅ Complete | Runtime/eval continue delegating to the stitched Python module for behavior and error message parity. Interpreter coverage includes `tests/test_tiny_language.py`. |
| Linter | `src/tiny_language_linter.py` | `src_tiny/tiny_language_linter.tiny` | ✅ Complete | Python/Tiny parity verified in `tests/test_linter_parity.py`. |
| Transpilers | `src/tiny_language_transpilers.py` | `src_tiny/tiny_language_transpilers.tiny` | ✅ Complete | Renderers/parsers mirrored for Python/Julia/JS/C++; parity snapshot tests cover renderer output. |
| Native backend | `src/native_ir.py`, `src/tiny_language_codegen_native.py`, `src/native_vm.py` | `src_tiny/native_ir.tiny`, `src_tiny/tiny_language_codegen_native.tiny`, `src_tiny/native_vm.tiny` | ✅ Complete | Opcode names, formatting, and error messages match the Python backend outputs. |
| CLI / LSP | `src/tiny_language_cli.py`, `src/tiny_lang_cli.py`, `src/language_server.py`, `src/language_server_cli.py` | `src_tiny/tiny_language_cli.tiny`, `src_tiny/tiny_lang_cli.tiny`, `src_tiny/language_server.tiny`, `src_tiny/language_server_cli.tiny` | ✅ Complete | Tiny CLI exercises completions/hover/diagnostics through the Python language server helpers; Tiny language server helpers remain available for future wiring. |

### Lexer + parser parity notes

- The Tiny scaffolding now lives in `src_tiny/tiny_language_lexer.tiny` and `src_tiny/tiny_language_parser.tiny`. Both files mirror the public entry points (token container, keyword/builtin sets, parser shell) so future ports can plug in logic without reshuffling signatures.
- Porting steps to complete parity:
### Open tasks

_None_

### Closed tasks

  - [x] Translate the lexer’s tokenization rules, including multi-character operators (`&&`, `||`, `<=`, `>=`, `!=`) and escape handling inside strings.

  - [x] Map keyword detection to the Tiny `Set` helpers already used for `KEYWORDS`/`BUILTINS`; keep `SourcePos` increments identical to the Python version for error spans.

  - [x] Recreate the recursive-descent parser with the same statement/expr split as `Parser.parse_stmt`/`parse_expr`, ensuring `_attach_span` produces spans compatible with `tiny_language_ast.tiny`.

  - [x] Validate with the existing parser and interpreter tests by swapping in the Tiny implementations once the runtime accepts Tiny modules.
As each Tiny module lands, update the table and link the implementation path under `src_tiny/` for quick navigation.
