# TinyLanguage Feature Cheat Sheet

Quick reference to core language features with links to the full `.tiny` demos. All commands assume you are running from the repository root and have set `PYTHONPATH=src` if you use the Python interop.

## Quickstart
- Run a program: `python src/tiny_language.py <path_to_file.tiny>`
- Compare interpreter vs. native backend: add `--native-backend`.
- Format: `python src/tiny_language.py --format <path>`

## Core building blocks
- **Variables & arithmetic**: `src_tiny/demo.tiny` shows `define`, basic operators, and `print`.
- **Control flow**: `src_tiny/all_features.tiny` includes `if`/`else`, `while`, and required returns.
- **Functions**: `src_tiny/all_features.tiny` defines free functions and demonstrates positional arguments.

## Types and signatures
- **Annotated parameters & returns**: `src_tiny/typing_demo.tiny` checks gradual typing and exhaustiveness.
- **Optional returns**: `src_tiny/result_demo.tiny` illustrates `Result`-style return patterns.

## Namespaces and modules
- **Namespaces**: `src_tiny/namespace_demo.tiny` groups utilities and calls them with qualification.
- **Imports & stdlib**: `src_tiny/stdlib_io_random_demo.tiny` uses `import`, I/O, and randomness.

## Classes and operators
- **Classes & methods**: `src_tiny/class_demo.tiny` defines fields, constructor wrappers, and methods.
- **Operator overloading**: `src_tiny/operator_overloading_demo.tiny` overrides `+` and `==` for `Point`.

## Pattern matching and ADTs
- **Tagged unions**: `src_tiny/match_demo.tiny` introduces `type` definitions and enforces exhaustiveness in `match`.

## Heap, arrays, and collections
- **Pointers/heap**: `src_tiny/heap_pointer_demo.tiny` demonstrates `new`, `heap_get`/`heap_set`, and `delete`.
- **Collections**: `src_tiny/stdlib_collections_demo.tiny` uses `Map`, `Set`, `Deque`, and shows mutations.

## Concurrency and async
- **Tasks & pipelines**: `src_tiny/concurrency_demo.tiny` and `src_tiny/concurrency_pipeline.tiny` cover `spawn`, `join`, and token cancellation.
- **Parallel map**: `src_tiny/parallel_map.tiny` combines tasks with aggregation.

## Interop with Python
- **FFI basics**: `src_tiny/python_math_demo.tiny` and `src_tiny/python_json_demo.tiny` show `Python.import_module`/`Python.call` with an allowlist.
- **Namespaces + typing**: `src_tiny/python_namespace_typed_demo.tiny` wraps Python calls in `namespace PyInterop` with annotated signatures.

## Native backend
- **Try the bytecode path**: Run `python src/tiny_language.py --native-backend src_tiny/all_features.tiny` and compare the output with an interpreter run without the flag.
- **Smoke tests**: `python -m pytest tests/test_native_codegen.py -q` checks which AST nodes are supported already.

## Error patterns and lints
- **Unused return value**: A call without assignment can trigger `[E011] function ... discards return value` (see `src_tiny/typing_demo.tiny`).
- **Missing returns**: Missing returns in typed functions yield `[E010] not all paths return a value`.

## Helpful combos
- **Formatter + diagnostics**: Format first (`--format`), then use `python src/language_server_cli.py --file <file> diagnostics` for clear lints.
- **Rosetta examples**: `src_tiny/rosetta_fibonacci.tiny` offers a small standalone program to validate recursion/loops.
