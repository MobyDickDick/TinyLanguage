# Open tasks

This list captures the currently planned work items for TinyLanguage. The tasks
are grouped by area and can be tackled independently.

## Frontend / language

- [ ] Improve error positions and messages (tokens + AST nodes carry line/column; unify error type with optional `SourceSpan`).
- [ ] Refine the linter (must-use across control flow; unreachable-code warnings).

## Type discipline

- [ ] Prevent implicit type changes (e.g., `def i = 5; i = 0.5;` ⇒ error unless explicitly allowed).
- [ ] Add optional simple type inference (e.g., `def x = 0;` ⇒ `number`).

## Runtime

- [ ] Harden the heap API (invalid pointer diagnostics, out-of-bounds details, double-delete detection, leak tracking).
- [ ] Expand the test suite (nested arrays, many `new/delete` pairs, deep recursion, heap-API error scenarios).

## Tooling

- [ ] Improve CLI wrapper ergonomics and documentation.
- [ ] Stabilize formatter + lints + language-server workflows.

## Structured concurrency

- [ ] Add `async`/`await` syntax while keeping `spawn`/`join` for compatibility.
- [ ] Introduce channel primitives (`Async.channel`, `Async.send`, `Async.recv`, `Async.close`) after task scopes stabilize.
- [ ] Formalize cancellation token semantics for joins, timeouts, and linked tasks.

## Native backends

- [ ] Keep the C backend stable and documented.
- [ ] Continue LLVM emission experiments and validation coverage.

## Stdlib + compatibility

- [ ] Port prioritized Python stdlib modules (`math`, `random`, `string`, `datetime`) with comparison tests.
- [ ] Ship a small Julia subset (e.g., `Statistics` with `mean`/`std`) and document API differences.
