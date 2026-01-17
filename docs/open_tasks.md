# Open tasks

This list captures the currently planned work items for TinyLanguage. The tasks
are grouped by area and can be tackled independently.

## Next tasks (shortlist)

- [x] Add regression coverage for `JSON.stringify` round-tripping heap-backed
  collections (`Map`, `Set`, `Deque`) and nested lists.
- [ ] Expand CLI smoke tests to include failure cases for `File.remove` and
  missing-path diagnostics in stdlib helpers.
- [ ] Add snapshot tests for LSP `hover`/`completion` flows in the self-hosted
  Tiny language server entry points.

## Frontend / language

- [x] Improve error positions and messages (tokens + AST nodes carry line/column; unify error type with optional `SourceSpan`).
- [x] Refine the linter (must-use across control flow; unreachable-code warnings).

## Type discipline

- [x] Prevent implicit type changes (e.g., `def i = 5; i = 0.5;` ⇒ error unless explicitly allowed).
- [x] Add optional simple type inference (e.g., `def x = 0;` ⇒ `number`).

## Runtime

- [x] Harden the heap API (invalid pointer diagnostics, out-of-bounds details, double-delete detection, leak tracking).
- [x] Expand the test suite (nested arrays, many `new/delete` pairs, deep recursion, heap-API error scenarios).

## Test coverage for Tiny programs

- [x] Add regression tests for remaining `src_tiny` demos and utilities not covered by `tests/` or `src/run_all.py` (notably: `stdlib_collections_demo.tiny`, `tiny_language_compiler_cli.tiny`, `tiny_language_eval.tiny`, `factorial.tiny`, `simpelst_Python_program.tiny`, `native_python_bytecode.tiny`, `python_namespace_typed_demo.tiny`, `Simpelst_Tiny_Language_Programm.tiny`, `tiny_language_preamble.tiny`, `tiny_language.tiny`, `try_catch_demo.tiny`, `tiny_language_codegen_c.tiny`, `test_flush.tiny`, `copy_rosetta_samples.tiny`, `tinyc_cli.tiny`, `run_all.tiny`, `tiny_language_codegen_py.tiny`, `rosetta_fizzbuzz.tiny`, `tiny_language_codegen_llvm.tiny`, `transpile_rosetta.tiny`, `rosetta_word_count.tiny`, `formatter.tiny`, `tiny_language_api.tiny`, `match_demo.tiny`, `fizzbuzz.tiny`, `stdlib_io_random_demo.tiny`, `tiny_language_runtime.tiny`, `rosetta_factorial.tiny`, `result_demo.tiny`, `language_server.tiny`, `console_sum.tiny`, `tiny_errors.tiny`, `tiny_language_highlighting.tiny`).
- [x] Add regression coverage for standalone Tiny demos outside `src_tiny` (e.g., `str_tiny/returned_params_demo.tiny`, `examples/rosetta/*/*.tiny`, `src/sum_product_match.tiny`).
- [x] Add test programs for the Tiny stdlib implementations that are currently untested (`src/stdlib/{string,math,collections,random,io}.tiny` and `stdlib/{string,math,random}.tiny`).

## Tooling

- [x] Improve CLI wrapper ergonomics and documentation.
- [x] Stabilize formatter + lints + language-server workflows.

## Structured concurrency

- [x] Add `async`/`await` syntax while keeping `spawn`/`join` for compatibility.
- [x] Introduce channel primitives (`Async.channel`, `Async.send`, `Async.recv`, `Async.close`) after task scopes stabilize.
- [x] Formalize cancellation token semantics for joins, timeouts, and linked tasks.

## Native backends

- [x] Keep the C backend stable and documented.
- [x] Continue LLVM emission experiments and validation coverage.

## Stdlib + compatibility

- [x] Port prioritized Python stdlib modules (`math`, `random`, `string`, `datetime`) with comparison tests.
- [x] Ship a small Julia subset (e.g., `Statistics` with `mean`/`std`) and document API differences.

## Future roadmap ideas

- [x] Extend the Tiny stdlib with additional Python-style modules (e.g., `json`, `pathlib`, `os`) and add comparison tests.
- [x] Stabilize the native compiler CLI with release-ready flags, diagnostics, and optimization profiles.
- [x] Expand self-hosting parity coverage with broader Python-vs-Tiny snapshot tests.
- [x] Build a spec-compliance test suite that validates the documented EBNF grammar and lexer/token rules.
- [x] Close remaining backend feature gaps so the native VM and LLVM pipelines match interpreter capabilities.
- [x] Grow the tooling ecosystem with richer language-server features, debugging workflows, and project scaffolding commands.
