# Backend feature matrix

This matrix summarizes which TinyLanguage language/runtime features are available in each execution backend. It focuses on runtime support; the parser, linter, and type checker are shared across backends and run before code generation.

Legend:

- ✅ Supported
- ⚠️ Limited / partial support
- ❌ Not supported

## Core language

| Feature | Interpreter | Native VM (`--native-backend`) | C/LLVM pipeline (`--emit-llvm`, `--emit-exe`) |
| --- | --- | --- | --- |
| Literals (`number`, `string`, `bool`, `null`) | ✅ | ✅ | ⚠️ Numeric + strings only (subset) |
| Variables (`define`, assignment) | ✅ | ✅ | ✅ (numeric subset) |
| Arithmetic (`+`, `-`, `*`, `/`) | ✅ | ✅ | ✅ (numeric subset) |
| Comparisons (`==`, `<`, `>`, etc.) | ✅ | ✅ | ✅ (numeric/boolean subset) |
| `if` / `else` | ✅ | ✅ | ✅ (simple control flow) |
| `while` loops | ✅ | ✅ | ✅ (simple control flow) |
| Functions + `return` | ✅ | ✅ | ✅ (simple, typed by inference) |
| Recursion | ✅ | ✅ | ✅ (within numeric subset) |
| `print` | ✅ | ✅ | ✅ (simple output) |

## Data structures and advanced language features

| Feature | Interpreter | Native VM (`--native-backend`) | C/LLVM pipeline (`--emit-llvm`, `--emit-exe`) |
| --- | --- | --- | --- |
| Heap (`new`, `heap_get`, `heap_set`, `delete`) | ✅ | ❌ (optional internal flag only) | ❌ |
| Array literals (`[a, b, c]`) | ✅ | ❌ | ❌ |
| Classes / methods | ✅ | ❌ | ❌ |
| Operator overloading | ✅ | ❌ | ❌ |
| Pattern matching + ADTs | ✅ | ❌ | ❌ |
| Collections (`Map`, `Set`, `Deque`) | ✅ | ❌ | ❌ |
| Concurrency (`spawn`, `join`, tokens) | ✅ | ❌ | ❌ |

## Interop and tooling

| Feature | Interpreter | Native VM (`--native-backend`) | C/LLVM pipeline (`--emit-llvm`, `--emit-exe`) |
| --- | --- | --- | --- |
| Module imports (`import`, namespaces) | ✅ | ❌ | ❌ |
| Python interop (`Python.import_module`, `Python.call`) | ✅ | ❌ | ❌ |
| Formatter / lints | ✅ | ✅ (shared frontend) | ✅ (shared frontend) |

## Notes

- The native VM and LLVM prototype intentionally target the tutorial-style subset. Unsupported constructs raise `NotImplementedError` so gaps remain visible.
- The LLVM/C pipeline lowers the native IR; if a feature is not in the native VM subset, it is also unavailable in the LLVM output.
- For the most up-to-date subset details, see `docs/native_compiler.md` and the code generator headers in `src/tiny_language_codegen_native.py` and `src/tiny_language_codegen_llvm.py`.
