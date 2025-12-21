# Cross-language compatibility

This note highlights TinyLanguage constructs that do not map cleanly to other mainstream languages (Python, JavaScript/TypeScript, C++, Julia) and suggests portable alternatives when transpiling or hand-porting code.

## Multiple inheritance and operator overloads

- **Why it is tricky**: TinyLanguage classes support multiple inheritance and free-standing operator overloads (e.g., `operator +`). Many popular targets differ: JavaScript lacks operator overloading entirely; Go avoids inheritance; TypeScript supports only single inheritance; and C++/Python allow operator overloading but tie it closely to class methods.
- **Portable alternative**: Prefer single inheritance plus composition. Model overloads as named functions (e.g., `point_add(a, b)`) or protocol-style methods (`a.add(b)`) that all targets can express. Keep numeric operators to primitive types when interop is required.

## Algebraic data types and exhaustive `match`

- **Why it is tricky**: Tagged unions with exhaustive `match` expressions have no 1:1 mapping in JavaScript or C++. TypeScript provides discriminated unions but relies on conventions; Python has `match` but no exhaustiveness checks; C++17 `std::variant` requires visitor boilerplate.
- **Portable alternative**: Encode variants as structs/maps with a `tag`/`kind` field and variant-specific payload fields. Replace `match` with a `switch`/`if` ladder that checks the tag and raises a clear error in the default branch to preserve TinyLanguage's exhaustiveness guarantees.

## Heap pointers and manual tagging

- **Why it is tricky**: Heap primitives such as `new[...]`, `heap_get`/`heap_set`, explicit `tag` metadata, and `delete` expose manual pointer semantics. Garbage-collected languages (Python/JavaScript) do not expose raw pointers, while C++ requires explicit ownership rules.
- **Portable alternative**: Map heap arrays to native lists/vectors, store tags as explicit struct/map fields, and avoid manual deletion by leaning on the host language's lifetime model. When targeting C++, wrap allocations in RAII holders (e.g., `std::vector`, `std::unique_ptr`) instead of raw pointers.

## Structured cancellation tokens

- **Why it is tricky**: TinyLanguage's `Async.token`, `cancel`, and `link` APIs assume cooperative cancellation and structured task ownership. Python's `asyncio` lacks built-in cancellation tokens; JavaScript Promises do not cancel; C++ threads/futures have no standardised token before C++20's `stop_token`.
- **Portable alternative**: Thread a `token` argument through long-running functions and check `is_cancelled` manually. In JavaScript, model tokens as AbortController/AbortSignal pairs; in Python, pass `asyncio.Event` or a custom flag; in C++, use `std::stop_token` where available or an atomic boolean guarded by mutex/condition variable checks.

## Namespaces versus module systems

- **Why it is tricky**: TinyLanguage namespaces group functions without module files, while imports cache modules by fully qualified names. JavaScript/TypeScript rely on ES modules, Python on packages, and C++ on headers/translation units, so naive transpilation can create name collisions or repeated side effects.
- **Portable alternative**: Map namespaces to static classes or module objects per target language and ensure imports resolve to a single module instance (e.g., a singleton module object in JS or a Python module-level cache). Avoid relying on side effects during import; prefer explicit initialiser functions to align with languages that do not guarantee single execution.

## Runtime-enforced gradual typing

- **Why it is tricky**: TinyLanguage enforces annotated parameter/return types at runtime and checks exhaustiveness of returns. JavaScript and Python do not enforce type hints by default; C++/Julia rely on compile-time types and cannot mirror runtime checks directly.
- **Portable alternative**: Add explicit guard functions at call boundaries (e.g., `assertNumber(x)`) or opt into existing runtime type-checking libraries (TypeScript `ts-runtime`, Python `typeguard`). For C++/Julia targets, prefer static typing and document behavioural expectations, since inserting runtime guards everywhere can bloat code.
