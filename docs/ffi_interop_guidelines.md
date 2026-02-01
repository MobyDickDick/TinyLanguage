# Interoperability + FFI guidelines

This document defines the interoperability rules and FFI expectations for
TinyLanguage. The goal is to keep cross-language boundaries predictable,
portable, and safe while allowing embedding TinyLanguage into host
applications and calling out to C/Python when needed.

## Scope

These guidelines cover:

- Embedding the TinyLanguage runtime in a host application.
- Calling C APIs from TinyLanguage.
- Calling Python APIs from TinyLanguage (CPython-first).
- Data marshaling, ownership rules, and error propagation across the boundary.

They intentionally avoid prescribing a concrete implementation API. Instead,
this document specifies *behavioral* and *ABI* expectations so tooling and
libraries can interoperate consistently.

## Design principles

1. **Explicit boundaries**: FFI calls are opt-in and visible in code; no hidden
   conversions or implicit dynamic dispatch.
2. **Stable ABI surface**: C-facing boundaries use a strict C ABI with pinned
   layouts for exported structs.
3. **Clear ownership**: Every cross-boundary allocation has a single owner and
   a documented free path.
4. **Predictable errors**: Cross-language errors map to a structured
   `Result`/exception strategy with explicit fallbacks.
5. **Versioned contracts**: FFI-facing APIs and marshaling rules are versioned
   and tracked in release notes.

## Embedding TinyLanguage in a host application

### Runtime lifecycle

Hosts must adhere to a simple lifecycle:

1. **Initialize** a runtime instance (with explicit configuration for stdlib
   paths, module search paths, and debug flags).
2. **Load/compile** modules or snippets (with a defined policy for caching
   compiled artifacts).
3. **Invoke** exported entry points with typed arguments.
4. **Finalize** and release runtime resources.

Each runtime instance is isolated: globals, heap objects, and module caches must
not leak across instances unless the host explicitly shares them.

### Embedding guidelines

- Prefer **one runtime instance per isolation boundary** (process, plugin, or
  untrusted workload).
- Provide **explicit host hooks** for stdout/stderr capture, logging, and
  tracing.
- Support **cancellation hooks** so hosts can stop long-running TinyLanguage
  execution.
- Expose **deterministic teardown** to avoid heap leaks at process shutdown.

## Calling C from TinyLanguage

### ABI expectations

- The default ABI is **C ABI** (`extern "C"`).
- Functions must be declared with **fixed-size primitives** or opaque pointer
  handles.
- Structs passed by value must be **layout-stable** (explicit field order, no
  padding assumptions). If layout stability is unclear, pass pointers instead.

### Data types and marshaling

| TinyLanguage type | C type / rule | Notes |
| --- | --- | --- |
| `number` | `double` | Uses IEEE 754; be explicit about NaN handling. |
| `int` (if used) | `int64_t` | Signed 64-bit; use `uint64_t` for unsigned. |
| `bool` | `uint8_t` | `0` = false, non-zero = true. |
| `string` | `const char*` + length | UTF-8. Always pass length to avoid NUL issues. |
| `array` | pointer + length | Elements must be contiguous and well-typed. |
| `map` / `set` | opaque handle | Accessed via helper APIs rather than raw layout. |
| `null` | `NULL` pointer or optional wrapper | Use explicit optional fields. |

### Ownership and lifetime

- **Caller owns allocations** unless explicitly documented.
- If TinyLanguage passes a pointer to C, it must either:
  - Remain valid for the duration of the call, **or**
  - Be accompanied by a `retain/release` protocol if ownership is transferred.
- C code must never hold a pointer to TinyLanguage-managed memory beyond the
  documented lifetime.

### Errors and results

- C functions that can fail should return a **result struct**:
  `typedef struct { int32_t code; const char* message; } TinyError;`
  and/or a `Result`-style wrapper with `ok` + `err` fields.
- TinyLanguage converts C error codes into `Result` values or thrown errors
  depending on the call site.

## Calling Python from TinyLanguage

### Interop modes

Two modes are supported:

1. **FFI-style bindings** (direct CPython calls via a stable shim layer).
2. **Adapter libraries** (TinyLanguage modules that expose curated Python APIs).

### Marshaling rules (CPython-first)

- `number` ↔ `float` (or `int` where explicitly requested).
- `string` ↔ `str` (UTF-8).
- `array` ↔ `list` (preserve order).
- `map` ↔ `dict` (string keys by default; non-string keys require explicit
  encoding).
- `null` ↔ `None`.

### Ownership and reference management

- The binding layer manages **reference counting**. Callers should not manually
  `Py_INCREF`/`Py_DECREF` unless the API explicitly exposes borrowed/owned
  references.
- Ensure **GIL ownership** is explicit: cross-language calls must acquire the
  GIL before invoking CPython and release it immediately afterward.

### Errors and exceptions

- Python exceptions propagate into TinyLanguage as structured errors with
  `type`, `message`, and optional `traceback` fields.
- A failed Python call must never crash the TinyLanguage runtime; it should
  raise a TinyLanguage error or return an explicit `Result`.

## Tooling and documentation expectations

When introducing new FFI surfaces or bindings, ensure:

- A **schema** or manifest describes the exposed functions and types.
- Examples show **round-trip marshaling** with explicit error handling.
- Tests cover **error paths** (bad types, nulls, boundary conditions).
- Performance notes document **allocation costs** and conversion overhead.

## Versioning and stability

- FFI rules are versioned alongside TinyLanguage releases.
- Breaking changes must be called out in release notes and include migration
  guidance.
- If an ABI surface is experimental, it must be labeled as such.

## Security considerations

- Treat FFI as **unsafe** by default; only trusted modules should use it.
- Validate all input sizes and pointer handles at the boundary.
- Avoid exposing raw pointers unless a strict capability model is in place.

## Open questions

Future revisions should clarify:

- Whether to support a WASM-based sandboxed FFI layer.
- How to standardize async callbacks across FFI boundaries.
- The minimal set of native modules required for interoperability testing.
