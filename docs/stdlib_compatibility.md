# TL-Stdlib: Compatibility Goals & Structure

## 1) API compatibility target
For the initial milestone, the TL stdlib aligns with these Python modules:

- `math` (numeric core functions)
- `random` (randomness)
- `string` (string utilities, e.g. split/join)
- `datetime` (planned, not implemented yet)

**Current status:** The core namespaces `Math`, `Random`, and `String` are implemented natively. Additionally, `Collections`, `Map`, `Set`, `Deque`, `File`, `JSON`, `Async`, and `Result` are available.

## 2) FFI/runtime strategy
By default, TL stdlib functions are implemented **natively** in the runtime (see `src/stdlib/__init__.py`).

For special cases or extensions, the Python bridge can be used optionally:

- `Python.import_module("...")` loads a Python module (with an allowlist).
- `Python.call(...)` or `Python.fn(...)` invokes functions.

This keeps the standard library deterministic and controlled, while advanced features can be accessed via the bridge mechanism.

## 3) TL stdlib structure
The standard library consists of two layers:

- **Native runtime implementation:** `src/stdlib/__init__.py`
- **TinyLanguage modules:** `stdlib/` (TinyLanguage sources, available via `import`)

The `stdlib/` directory is the permanent home for TL modules that wrap the native API in a Python-like module shape.

## 4) First modules: `stdlib.math`, `stdlib.random`
The first TinyLanguage modules are **`stdlib.math`** and **`stdlib.random`**, each with a Python-like API subset.

Import and usage:

```tiny
import stdlib.math;
import stdlib.random;
print(math.sqrt(9));
print(math.round_digits(math.pi, 3));
print(random.randint(1, 6));
```

## 5) API deviations from Python
- `math.round_digits(value, digits)` replaces the optional `round(x, ndigits)`.
- Functions are limited to the math operations available in TL.
- `string` utilities live in the `String` namespace (not as a separate module).
- `datetime` is currently only a compatibility target.

Further extensions will arrive in the stdlib once the corresponding runtime functions exist.
