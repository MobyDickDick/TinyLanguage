# Backend feature matrix

This matrix summarizes which TinyLanguage language/runtime features are available in each execution backend. It focuses on runtime support; the parser, linter, and type checker are shared across backends and run before code generation.

All non-interpreter backends are **experimental**, including C and the native
VM. Supported cells below refer to the bounded executable examples in the
[independent correctness audit](independent_correctness_audit.md), not complete
language support or a stable release commitment. Its retained report separates
frontend acceptance, generation, compilation and execution; known failures are
never counted as support evidence. The 2026-11-06 run covers Windows x86-64 only.
See the [candidate contract and evidence map](release_scope_v1.md) and
[platform qualification status](platform_verification_acceptance.md).

Legend:

- ✅ Supported
- ⚠️ Limited / partial support
- ❌ Not supported

## Core language

| Feature | Interpreter | Native VM (`--native-backend`) | Native LLVM pipeline (`--emit-llvm`, `--emit-exe`) | C backend (`tinyc_cli`) |
| --- | --- | --- | --- | --- |
| Literals (`number`, `string`, `bool`, `Null`) | ✅ | ⚠️ `Null` prints `null` (AUD-003) | ⚠️ Boolean spelling and Windows large-integer output (AUD-002/003) | ⚠️ `Null` prints `null` (AUD-003) |
| Variables (`def`, assignment) | ✅ | ✅ | ✅ (numeric subset) | ✅ |
| Arithmetic (`+`, `-`, `*`, `/`) | ✅ | ✅ | ⚠️ Integer division truncates; zero division traps (AUD-001/010) | ⚠️ Nonzero basic subset; zero division continues with infinity (AUD-010) |
| Comparisons (`==`, `<`, `>`, etc.) | ✅ | ✅ | ✅ (numeric/boolean subset) | ✅ (basic subset) |
| `if` / `else` | ✅ | ✅ | ✅ (simple control flow) | ✅ |
| `while` loops | ✅ | ✅ | ✅ (simple control flow) | ✅ |
| Functions + `return` | ✅ | ✅ | ✅ (simple, typed by inference) | ✅ |
| Recursion | ✅ | ✅ | ✅ (within numeric subset) | ✅ |
| `print` | ✅ | ⚠️ `Null` spelling (AUD-003) | ⚠️ Boolean spelling and Windows integer truncation (AUD-002/003) | ⚠️ `Null` spelling (AUD-003) |
| Short-circuit boolean evaluation | ✅ | ⚠️ Eager RHS evaluation (AUD-004) | ❌ Rejected during lowering (AUD-004) | ⚠️ Eager RHS evaluation (AUD-004) |

## Data structures and advanced language features

| Feature | Interpreter | Native VM (`--native-backend`) | Native LLVM pipeline (`--emit-llvm`, `--emit-exe`) | C backend (`tinyc_cli`) |
| --- | --- | --- | --- | --- |
| Heap (`new`, `heap_get`, `heap_set`, `delete`) | ✅ | ✅ | ⚠️ Basic operations execute; error records, `len` and file-context builtins fail (AUD-005/007/008) | ❌ |
| Array literals (`new[ a, b, c ]`) | ✅ | ✅ | ✅ | ❌ |
| Classes / methods | ✅ | ✅ | ✅ | ❌ |
| Operator overloading | ✅ | ✅ | ⚠️ User-class overload rejected during lowering (AUD-006) | ❌ |
| Pattern matching + ADTs | ✅ | ✅ | ✅ | ❌ |
| Collections (`Map`, `Set`, `Deque`) | ✅ | ✅ | ✅ | ❌ |
| Concurrency (`spawn`, `join`, tokens) | ✅ | ✅ | ⚠️ Synchronous worker result and token state verified; parallel scheduling/cancellation equivalence unqualified | ❌ |

## Interop and tooling

| Feature | Interpreter | Native VM (`--native-backend`) | Native LLVM pipeline (`--emit-llvm`, `--emit-exe`) | C backend (`tinyc_cli`) |
| --- | --- | --- | --- | --- |
| Module imports (`import`, namespaces) | ✅ | ✅ | ⚠️ Static function import executes; file-context builtin qualification fails (AUD-008) | ❌ |
| Python interop (`Python.import_module`, `Python.call`) | ✅ | ✅ | ⚠️ IR emits external calls, but standalone linking lacks Python bridge symbols (AUD-009) | ❌ |
| Formatter / lints | ✅ | ✅ (shared frontend) | ✅ (shared frontend) | ✅ (shared frontend) |

## Notes

- The native VM and LLVM prototype intentionally target the tutorial-style subset. Unsupported constructs raise `NotImplementedError` so gaps remain visible.
- The LLVM pipeline lowers the native IR; if a feature is not in the native VM subset, it is also unavailable in the LLVM output.
- The `tinyc_cli` C backend is separate from the native LLVM pipeline and intentionally limited to the minimal subset described in `docs/c_backend.md`.
- For the most up-to-date subset details, see `docs/native_compiler.md`, `docs/c_backend.md`, and the code generator headers in `src/tiny_language_codegen_native.py`, `src/tiny_language_codegen_llvm.py`, and `src/tiny_language_codegen_c.py`.

## Open backend work items (by feature)

These task lists capture the remaining feature gaps for the non-interpreter backends so they can be tracked and tackled incrementally.

### Native VM (`--native-backend`)

### Open tasks

See [AUD-003/004](independent_correctness_audit.md#bounded-follow-up-work):
literal rendering and short-circuit evaluation remain open.

### Closed tasks

- [x] Concurrency (`spawn`, `join`, tokens)
  - [x] Define a VM scheduling model for concurrent tasks.
  - [x] Implement token synchronization primitives in the native runtime.

- [x] Pattern matching + ADTs
  - [x] Encode ADT constructors in native IR and allocate tagged values in the runtime.
  - [x] Implement match dispatch on tags with destructuring.

- [x] Operator overloading
  - [x] Extend native IR to carry operator overload resolution results.
  - [x] Map overloaded operators to runtime method calls in the VM.

- [x] Classes and methods
  - [x] Define object layout metadata for class instances in the native runtime.
  - [x] Lower method dispatch to vtable lookups or direct offsets in native IR.
  - [x] Support `this` binding and field access in the VM execution loop.

- [x] Heap operations
  - [x] Implement `new`, `heap_get`, `heap_set`, and `delete` in the native VM runtime.
  - [x] Add runtime safety checks for double-free and out-of-bounds access.
  - [x] Extend native IR lowering to emit heap operations with typed offsets.

- [x] Array literals
  - [x] Represent array literals in native IR and lower them in the VM interpreter loop.
  - [x] Add bounds checking and length metadata in the runtime heap model.
  - [x] Wire array operations into standard library helpers (where applicable).

- [x] Module imports
  - [x] Add module loader support for native VM execution.
  - [x] Cache and reuse module initialization across runs.

- [x] Collections (`Map`, `Set`, `Deque`)
  - [x] Port collection runtime implementations into the native VM.
  - [x] Expose collection constructors and methods through the VM call interface.

- [x] Python interop
  - [x] Define native VM bridges for `Python.import_module` and `Python.call`.
  - [x] Validate argument/return marshalling in the VM runtime.
### Native LLVM pipeline (`--emit-llvm`, `--emit-exe`)

### Open tasks

See [AUD-001 through AUD-010](independent_correctness_audit.md#bounded-follow-up-work).
The historical completed implementation entries below are not execution acceptance.

### Closed tasks

- [x] Module imports
  - [x] Generate per-module initialization functions in LLVM IR.
  - [x] Emit a module loader in the runtime and link it into executables.

- [x] Cancellation tokens (`Async.token`, `Async.cancel`, `Async.is_cancelled`, `Async.reason`, `Async.link`)

- [x] Concurrency (`spawn`, `join`) (synchronous, no tokens)
  - [x] Define C runtime entry points for task scheduling.
  - [x] Lower spawn/join operations to runtime calls.

- [x] Collections (`Map`, `Set`, `Deque`)
  - [x] Port collection runtime to C/LLVM helpers.
  - [x] Generate bindings for collection methods in the LLVM IR.

- [x] Pattern matching + ADTs
  - [x] Represent ADTs with tagged unions in LLVM.
  - [x] Lower `match` into tag dispatch + payload extraction.

- [x] Classes and methods
  - [x] Define class layouts in the LLVM runtime and generate constructors.
  - [x] Emit method dispatch (vtable or direct) in the LLVM IR.

- [x] Operator overloading
  - [x] Emit overloaded operator calls in the LLVM IR.
  - [x] Ensure overloaded operators link against runtime helpers.

- [x] Array literals
  - [x] Introduce array allocation helpers in the LLVM runtime ABI.
  - [x] Lower array literals to runtime calls and wire bounds checks.

- [x] Python interop
  - [x] Define a C/LLVM FFI bridge for Python interop APIs.
  - [x] Stabilize argument conversion and reference lifetime management.

- [x] Full literal and type coverage
  - [x] Add `null` lowering and a runtime sentinel representation.
  - [x] Support non-numeric variables and assignments beyond the numeric subset.

- [x] Heap operations
  - [x] Port heap op lowering from the native IR into LLVM IR.
  - [x] Implement runtime safety checks and error reporting in the C/LLVM runtime helpers.
