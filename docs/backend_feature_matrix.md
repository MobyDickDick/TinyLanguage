# Backend feature matrix

This matrix summarizes which TinyLanguage language/runtime features are available in each execution backend. It focuses on runtime support; the parser, linter, and type checker are shared across backends and run before code generation.

Legend:

- ✅ Supported
- ⚠️ Limited / partial support
- ❌ Not supported

## Core language

| Feature | Interpreter | Native VM (`--native-backend`) | C/LLVM pipeline (`--emit-llvm`, `--emit-exe`) |
| --- | --- | --- | --- |
| Literals (`number`, `string`, `bool`, `null`) | ✅ | ✅ | ⚠️ Numeric + strings + bools only (subset) |
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
| Heap (`new`, `heap_get`, `heap_set`, `delete`) | ✅ | ✅ | ⚠️ Basic heap ops (no runtime safety checks) |
| Array literals (`new[ a, b, c ]`) | ✅ | ✅ | ❌ |
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

## Open backend work items (by feature)

These task lists capture the remaining feature gaps for the non-interpreter backends so they can be tracked and tackled incrementally.

### Native VM (`--native-backend`)

### Open tasks

- [ ] Classes and methods
  - [ ] Define object layout metadata for class instances in the native runtime.
  - [ ] Lower method dispatch to vtable lookups or direct offsets in native IR.
  - [ ] Support `this` binding and field access in the VM execution loop.

- [ ] Operator overloading
  - [ ] Extend native IR to carry operator overload resolution results.
  - [ ] Map overloaded operators to runtime method calls in the VM.

- [ ] Pattern matching + ADTs
  - [ ] Encode ADT constructors in native IR and allocate tagged values in the runtime.
  - [ ] Implement match dispatch on tags with destructuring.

- [ ] Collections (`Map`, `Set`, `Deque`)
  - [ ] Port collection runtime implementations into the native VM.
  - [ ] Expose collection constructors and methods through the VM call interface.

- [ ] Concurrency (`spawn`, `join`, tokens)
  - [ ] Define a VM scheduling model for concurrent tasks.
  - [ ] Implement token synchronization primitives in the native runtime.

- [ ] Module imports
  - [ ] Add module loader support for native VM execution.
  - [ ] Cache and reuse module initialization across runs.

- [ ] Python interop
  - [ ] Define native VM bridges for `Python.import_module` and `Python.call`.
  - [ ] Validate argument/return marshalling in the VM runtime.

### Closed tasks

- [x] Heap operations
  - [x] Implement `new`, `heap_get`, `heap_set`, and `delete` in the native VM runtime.
  - [x] Add runtime safety checks for double-free and out-of-bounds access.
  - [x] Extend native IR lowering to emit heap operations with typed offsets.

- [x] Array literals
  - [x] Represent array literals in native IR and lower them in the VM interpreter loop.
  - [x] Add bounds checking and length metadata in the runtime heap model.
  - [x] Wire array operations into standard library helpers (where applicable).
### C/LLVM pipeline (`--emit-llvm`, `--emit-exe`)

### Open tasks

- [ ] Heap operations
  - [ ] Port heap op lowering from the native IR into LLVM IR.
  - [ ] Implement runtime safety checks and error reporting in the C/LLVM runtime helpers.

- [ ] Array literals
  - [ ] Introduce array allocation helpers in the LLVM runtime ABI.
  - [ ] Lower array literals to runtime calls and wire bounds checks.

- [ ] Classes and methods
  - [ ] Define class layouts in the LLVM runtime and generate constructors.
  - [ ] Emit method dispatch (vtable or direct) in the LLVM IR.

- [ ] Operator overloading
  - [ ] Emit overloaded operator calls in the LLVM IR.
  - [ ] Ensure overloaded operators link against runtime helpers.

- [ ] Pattern matching + ADTs
  - [ ] Represent ADTs with tagged unions in LLVM.
  - [ ] Lower `match` into tag dispatch + payload extraction.

- [ ] Collections (`Map`, `Set`, `Deque`)
  - [ ] Port collection runtime to C/LLVM helpers.
  - [ ] Generate bindings for collection methods in the LLVM IR.

- [ ] Concurrency (`spawn`, `join`, tokens)
  - [ ] Define C runtime entry points for task scheduling.
  - [ ] Lower spawn/join operations to runtime calls.

- [ ] Module imports
  - [ ] Generate per-module initialization functions in LLVM IR.
  - [ ] Emit a module loader in the runtime and link it into executables.

- [ ] Python interop
  - [ ] Define a C/LLVM FFI bridge for Python interop APIs.
  - [ ] Stabilize argument conversion and reference lifetime management.

### Closed tasks

- [x] Full literal and type coverage
  - [x] Add `null` lowering and a runtime sentinel representation.
  - [x] Support non-numeric variables and assignments beyond the numeric subset.
