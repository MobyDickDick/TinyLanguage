# TL-Stdlib: Compatibility Goals & Structure

## 1) API compatibility target
For the initial milestone, the TL stdlib aligns with these Python modules:

- `math` (numeric core functions)
- `random` (randomness)
- `string` (string utilities, e.g. split/join)
- `datetime` (Python interop-backed subset in `stdlib/datetime.tiny`)
- `gui` (Tkinter-backed mini framework in `stdlib/gui.tiny` for desktop windows)

**Current status:** The core namespaces `Math`, `Random`, and `String` are implemented natively. Additionally, `Collections`, `Map`, `Set`, `Deque`, `File`, `JSON`, `Async`, and `Result` are available. Wrapper modules for `math`, `random`, `string`, `datetime`, and `gui` live in `stdlib/` (`datetime` and `gui` delegate through the Python interop layer).

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

## 4) First modules: `stdlib.math`, `stdlib.random`, `stdlib.string`, `stdlib.datetime`
The first TinyLanguage modules are **`stdlib.math`**, **`stdlib.random`**, **`stdlib.string`**, and **`stdlib.datetime`**, each with a Python-like API subset.

Import and usage:

```tiny
import stdlib.math;
import stdlib.random;
import stdlib.string;
import stdlib.datetime;
print(math.sqrt(9));
print(math.round_digits(math.pi, 3));
print(random.randint(1, 6));
print(string.upper("hello"));
print(datetime.datetime_isoformat(2024, 1, 2, 3, 4, 5));
```

## 5) API deviations from Python
- `math.round_digits(value, digits)` replaces the optional `round(x, ndigits)`.
- Functions are limited to the math operations available in TL.
- `string` utilities are also exposed via the `String` namespace (with the `stdlib.string` module wrapping it).
- `datetime` is provided via Python interop-backed helpers that return ISO strings and total-seconds values.

Further extensions will arrive in the stdlib once the corresponding runtime functions exist.

## 6) API stability guarantees + module maturity tiers
TinyLanguage follows the versioning and deprecation policy in
`docs/versioning_deprecation_policy.md`. That policy applies to the stdlib, with
the following maturity tiers used to communicate API stability expectations.

### Maturity tier definitions
- **Stable**: Covered by the formal deprecation policy. Backward-incompatible
  changes require a major version and documented upgrade notes.
- **Beta**: API surface is expected to converge, but small breaking changes may
  land in minor releases when needed. Breaking changes must still be documented,
  but may ship faster than Stable.
- **Experimental**: APIs can change at any time. Expect churn across minor
  releases and prioritize testing against the current version.
- **Deprecated**: Use is discouraged and removal is scheduled per the
  deprecation policy.

### Current stdlib module tiers
| Module | Tier | Notes |
| --- | --- | --- |
| `stdlib.math` | Stable | Core numeric helpers with parity tests. |
| `stdlib.random` | Stable | Deterministic RNG helpers with parity tests. |
| `stdlib.string` | Stable | String utilities with parity tests and `String` namespace parity. |
| `stdlib.datetime` | Beta | Python-interop backed; may expand as native support grows. |
| `stdlib.collections` | Stable | Map/Set/Deque wrappers over core namespaces. |
| `stdlib.io` | Stable | File primitives used across demos and tooling. |
| `stdlib.json` | Stable | Wrapper over runtime `JSON` namespace. |
| `stdlib.fs` | Beta | Core file-system helpers wrapping `File` + `OS` namespaces. |
| `stdlib.os` | Beta | OS/environment utilities; may grow with package tooling. |
| `stdlib.path` | Beta | Path helpers; behavior tuned as cross-platform needs evolve. |
| `stdlib.pathlib` | Beta | Higher-level path objects built on `stdlib.path`. |
| `stdlib.time` | Beta | Time helpers; expected to grow with monotonic support. |
| `stdlib.csv` | Beta | Minimal CSV parse/serialize; format options may expand. |
| `stdlib.logging` | Beta | Structured logging helpers; may evolve with sinks/formatters. |
| `stdlib.statistics` | Beta | Initial statistics helpers; further aggregates may be added. |
| `stdlib.regex` | Experimental | Minimal regex slice; syntax and APIs can change. |
| `stdlib.http` | Experimental | Capability-gated networking; scope may shift. |
| `stdlib.process` | Experimental | Capability-gated process spawning; API may adjust. |
| `stdlib.fswatch` | Experimental | File watch API, likely to evolve with backend support. |
| `stdlib.yaml` | Experimental | JSON-compatible YAML subset (`key: value` mappings + JSON literals for scalars/sequences/maps); broader YAML features remain out of scope for now. |
| `stdlib.argparse` | Beta | CLI parsing helpers; expected to expand with package tooling. |
| `stdlib.gui` | Experimental | Tkinter-backed helpers for tiny standalone desktop windows; intended for simple demos/tools. |

When a module changes tiers, the docs and release notes must explicitly call out
the new status, along with any migration guidance.
