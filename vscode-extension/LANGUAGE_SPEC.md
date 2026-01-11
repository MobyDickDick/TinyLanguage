# TinyLanguage: Stable Language Specification

This guide provides a concise, implementation-stable reference for TinyLanguage. It is tailored for editor tooling (like the VS Code extension) and for users who need clear, non-changing expectations about syntax, typing, and common rules.

## Core syntax

- **Statements**: end with semicolons (`;`). Blocks are delimited by `{ ... }`.
- **Bindings**: `def name = expression;` declares immutable bindings. Use simple expressions, function calls, or struct literals on the right-hand side.
- **Functions**: `fn name(params) { ... }` declares a function. Methods follow the same syntax and live inside classes or namespaces.
- **Control flow**: `if (cond) { ... } else { ... }` and `while (cond) { ... }` mirror the examples in `src_tiny/demo.tiny` and `src_tiny/namespace_demo.tiny`.
- **Imports**: `import path.to.module;` loads another `.tiny` file. Optional aliasing uses `import path.to.module as alias;`.
- **Comments**: `// line comments` are supported; block comments are not.

## Types and gradual typing

- **Primitive types**: `number`, `string`, `Bool`, and `Null` are built in.
- **Composite types**: structs via `{ field: value }`, arrays via `new[...]`, classes with fields/methods, and tagged unions declared with `type`/`match`.
- **Optional annotations**: Parameters and returns may specify types (`fn f(x: number) -> number { ... }`). Add `?` to accept `Null` (e.g., `string?`).
- **Runtime enforcement**: Annotated parameters and return values are checked at runtime. Missing returns on any control-flow path raise exhaustiveness errors.
- **Type stability**: Reassignments must keep the inferred or annotated type; type changes result in `E014` errors (see `docs/language_spec.md`).

## Must-use and lints

- **Unused bindings**: Unused locals or parameters trigger diagnostics unless prefixed with `_` (e.g., `_unused`).
- **Imports before code**: Import statements must be grouped before other statements to satisfy formatter/linter expectations.

## Error handling

- **Try/catch**: `try { ... } catch(err) { ... }` wraps failures. The `err` object exposes `code`, `message`, optional `hint`, and a `stack` array.
- **Result helpers**: `Result.ok(value)` / `Result.err(error)` plus `Result.is_ok`/`Result.is_err` and `Result.unwrap_or` allow explicit success/failure without throwing.

## Standard library highlights

- **Math**: `abs`, `pow`, `sqrt`, `max`, `min`, `clamp`, `round`, `floor`, `ceil`, `sign`.
- **String**: `split`, `join`, `contains`, `upper`, `lower`, `trim`, `repeat`.
- **Collections**: `Collections.len`, `push`, `pop`, `slice`, `contains`; `Map`, `Set`, and `Deque` namespaces with the expected CRUD operations.
- **Random**: `Random.random`, `randint`, `choice`, `shuffle`.
- **File/JSON**: `File.read`, `write`, `exists`, `remove`; `JSON.parse` and `JSON.stringify` for structured data.

## Heap and pointers

- **Allocation**: `new(size)` allocates a pointer with the requested slots; `new[items]` allocates an array literal.
- **Access**: `heap_get(pointer, index)` / `heap_set(pointer, index, value)` operate on heap arrays; out-of-bounds accesses are errors.
- **Lifecycle**: `delete(pointer)` frees a pointer; double-deletes or invalid pointers are errors. Use tags via `tag(pointer, "Type")` to annotate heap values.

## Concurrency

- **Tasks**: `spawn fnCall(...)` starts a concurrent task; `join(handle)` waits for and returns its result.
- **Cancellation**: `Async.token`, `cancel(token, reason)`, `is_cancelled(token)`, `reason(token)`, and `link(token, handle)` implement structured cancellation for cooperative tasks.

## Formatting rules

- **Spacing**: One space around operators and after commas; four-space indentation inside blocks.
- **Imports**: Sorted and placed before other statements. Aliases use `as` with a single space on each side.
- **Semicolons**: Required at statement ends. Formatter preserves comments while normalizing spacing.

## Example checklist

- Hello world: `python tiny_language.py src_tiny/hello_world.tiny`.
- Linter/formatter: `python tiny_language.py --format path/to/file.tiny`.
- Interpreter vs. native backend: `python -m tiny_lang_cli --file src_tiny/demo.tiny --backend interpreter`.

This document is intended to stay stable so that editor integrations and users have a clear baseline for TinyLanguage behavior.
