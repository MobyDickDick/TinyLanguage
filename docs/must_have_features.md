# TinyLanguage 1.0 must-have interpreter features

This document captures the **must-have interpreter features** for the TinyLanguage
1.0 release scope. It is intended to make the scope explicit, track what is
considered stable, and link to the primary documentation and demos that
represent the implemented behavior.

## Scope alignment

The 1.0 release scope is **interpreter + core language only**. Experimental
backends (LLVM/C) remain out of scope for stability guarantees.

## Must-have feature set

These items are considered required for the interpreter release line and are
already implemented in the current TinyLanguage interpreter.

### Core language
- **Syntax and semantics** defined by the language spec.
  - See: [`docs/language_spec.md`](language_spec.md).
- **Variables, arithmetic, control flow** (`def`, `if`/`else`, `while`).
  - See: `src_tiny/all_features.tiny` and `src_tiny/demo.tiny` in the
    [feature cheat sheet](feature_cheat_sheet.md).
- **Functions** with positional parameters and returns.
  - See: `src_tiny/all_features.tiny`.
- **Type annotations and simple inference** where supported by the interpreter.
  - See: `src_tiny/typing_demo.tiny`.
- **Namespaces and imports**, including stdlib access.
  - See: `src_tiny/namespace_demo.tiny` and `src_tiny/stdlib_io_random_demo.tiny`.
- **Classes and methods**, plus operator overloading for user-defined types.
  - See: `src_tiny/class_demo.tiny` and `src_tiny/operator_overloading_demo.tiny`.
- **Pattern matching and tagged unions** (`match`, `type`).
  - See: `src_tiny/match_demo.tiny`.
- **Error handling** via `try`/`catch` and diagnostic spans.
  - See: `docs/language_spec.md` for syntax and semantics.

### Runtime and safety
- **Heap and pointer primitives** (`new`, `delete`, `heap_get`, `heap_set`)
  with safety diagnostics.
  - See: `src_tiny/heap_pointer_demo.tiny` and `docs/heap_usage_guidelines.md`.
- **Collections** (`Map`, `Set`, `Deque`, arrays) and core stdlib modules.
  - See: `src_tiny/stdlib_collections_demo.tiny` and
    [`docs/stdlib_compatibility.md`](stdlib_compatibility.md).
- **Concurrency primitives** (`spawn`, `join`, task handles, cancellation
  tokens).
  - See: `src_tiny/concurrency_demo.tiny` and `docs/structured_concurrency.md`.

### Tooling and workflow (interpreter scope)
- **CLI and formatting** workflows for running and formatting programs.
  - See: `README.md` and `docs/tutorial.md`.
- **Language server integration** and linting defaults.
  - See: `docs/language_server_workflows.md` and `docs/feature_cheat_sheet.md`.

## Maintenance notes

- Keep this list synchronized with `docs/language_spec.md` and
  `docs/stdlib_compatibility.md` when adding or changing core behavior.
- Add new demos or update the feature cheat sheet when introducing new
  must-have capabilities.
