# Standard library expansion plan

This plan defines the next standard-library modules to prioritize, the criteria
for expanding the runtime surface area, and the test coverage expected before a
module is considered stable.

## Goals

1. **Practical parity** with frequently used Python stdlib modules while keeping
   the runtime deterministic and portable.
2. **Incremental delivery**: each module lands with a minimal, well-tested API
   slice that can grow over time.
3. **Consistent Tiny-first API design**: new APIs should prefer existing
   namespaces (e.g., `String`, `File`, `JSON`) and only introduce new modules
   when a cohesive group of functionality exists.

## Prioritization rubric

Modules are ranked using the following criteria:

- **Frequency of use** in common scripts and demos.
- **Runtime feasibility** (does it require OS access, binary parsing, or large
  dependency surfaces?).
- **Testability** in CI (deterministic behavior, minimal network dependence).
- **Cross-backend support** (interpreter + C/LLVM backends should be able to
  share behavior and diagnostics).

## Phase 1 (short term): high-value, low-risk

Target modules that map directly to existing primitives or have clear,
small-scope implementations.

- **`stdlib.path`**: Path join/split, basename/dirname, extension helpers,
  normalization, `is_absolute`, and simple glob-like filtering based on
  directory listings.
- **`stdlib.os`**: Basic environment access (`getenv`, `setenv`, `cwd`),
  directory listing, and platform identifiers.
- **`stdlib.json`** (module wrapper): Mirror the runtime `JSON` namespace with
  `parse`, `stringify`, and `validate` helpers.
- **`stdlib.csv`** (minimal): CSV parse/serialize with configurable delimiter,
  quote, and header row handling.
- **`stdlib.time`**: Timestamps and sleeps that map to runtime-supported
  monotonic/epoch APIs.

**Expected tests**

- Unit tests for each module that cover successful usage and failure modes
  (invalid paths, malformed input, missing environment keys).
- Parity tests between module wrappers and runtime namespaces where applicable
  (e.g., `stdlib.json.parse` vs `JSON.parse`).
- Cross-backend smoke tests for deterministic APIs (no network/file system
  dependencies beyond temporary directories).

## Phase 2 (mid term): data interchange + text processing

- **`stdlib.regex`**: Regular expression match/search/replace with a limited
  syntax subset if the full engine is not feasible across backends.
- **`stdlib.yaml`** (optional): YAML parsing/serialization with a conservative
  schema (string/number/bool/list/map) and a focus on deterministic output.
- **`stdlib.logging`**: Structured logging helpers that emit JSON by default and
  integrate with the `File` API.
- **`stdlib.argparse`**: Minimal CLI argument parsing (flags, positional args,
  default values).

**Expected tests**

- Parser round-trip tests (serialize → parse) for JSON/YAML/CSV modules.
- Coverage for edge cases: escaping, unicode handling, empty inputs, and
  malformed syntax.
- CLI parsing tests that cover common flag patterns and error messaging.

## Phase 3 (long term): platform integration

These modules require clear portability rules or optional capability flags.

- **`stdlib.http`**: Deterministic HTTP client with configurable timeouts and
  explicit DNS/network permission checks.
- **`stdlib.fswatch`**: File-watcher helpers for build tooling.
- **`stdlib.process`**: Process spawning, environment isolation, and exit-code
  management.

**Expected tests**

- Capability-gated tests that skip when system features are unavailable.
- Error-path coverage for permission issues, timeouts, and invalid inputs.

## Test coverage expectations (all phases)

- **Module-level unit tests** live alongside other stdlib tests in
  `tests/detailtests/`.
- **Documentation examples** for each new module should be exercised in the
  test suite (keep them runnable and deterministic).
- **Parity checks** should confirm that module APIs match the underlying runtime
  namespaces where a wrapper exists.

## Release criteria

A module is considered stable when:

- The minimal API slice has 90%+ line coverage in the stdlib test suite.
- The module passes interpreter, C backend, and LLVM backend smoke tests.
- Documentation examples are verified via tests or CI scripts.

## Open questions to resolve before Phase 1

- Should `stdlib.path` be a thin wrapper over `File` or a dedicated namespace
  with its own path normalization rules?
- What cross-platform guarantees do we want for `stdlib.os` path separators,
  case sensitivity, and environment variable handling?
- Can `stdlib.time` expose both monotonic and wall-clock clocks in the runtime
  without platform-specific behavior divergences?
