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

### `stdlib.csv` behavior notes (Phase 1)

The initial CSV helpers should stay deliberately small and deterministic so
tests can round-trip cleanly across backends.

- **Defaults**: delimiter `,`, quote `"`, newline `\n`, no header row unless
  requested.
- **Parsing**:
  - Accept input with `\n` or `\r\n` line endings; normalize to `\n`.
  - Treat a final trailing newline as optional (do not append an empty row for
    it).
  - Support quoted fields that may include delimiters, newlines, or escaped
    quotes. Escaped quotes use doubled quote characters (`""` → `"`).
  - When `has_header` is `true`, return rows as dictionaries keyed by header
    strings; missing fields map to `null`, extra fields are ignored beyond the
    header count.
  - When `has_header` is `false`, return rows as lists of strings.
- **Serialization**:
  - Accept rows as lists (no headers) or dictionaries (with headers provided).
  - Emit rows in the provided order; if a header list is supplied, serialize
    columns in that exact order.
  - Quote fields when they contain the delimiter, quote, or newline. Escape
    quotes by doubling them.
  - Emit `\n` line endings and do not add a trailing newline by default.
- **Determinism**: dictionary serialization must use the explicit header order
  to avoid hash-order variance; missing keys serialize as empty strings.
- **Errors**: invalid delimiter/quote inputs (empty strings or multi-character
  tokens) raise a `ValueError` with a clear diagnostic message.
- **Examples**:
  - Parse without headers:
    - Input: `name,score\nAda,10\nLinus,12`
    - Output: `[[\"name\", \"score\"], [\"Ada\", \"10\"], [\"Linus\", \"12\"]]`
  - Parse with headers:
    - Input: `name,score\nAda,10\nLinus,12`
    - Output: `[{\"name\": \"Ada\", \"score\": \"10\"}, {\"name\": \"Linus\", \"score\": \"12\"}]`
  - Serialize with headers:
    - Headers: `[\"name\", \"score\"]`
    - Rows: `[{\"name\": \"Ada\", \"score\": \"10\"}, {\"name\": \"Linus\", \"score\": \"12\"}]`
    - Output: `name,score\nAda,10\nLinus,12`

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

### YAML scope decision (Phase 2)

The initial `stdlib.yaml` scope is approved as an optional, JSON-compatible
subset of YAML. The module will focus on deterministic round trips for:

- Scalars: strings, numbers, booleans, and `null`.
- Collections: lists (`- item`) and maps (`key: value`) with string keys.
- Whitespace rules: spaces only (no tabs), with consistent indentation
  requirements to keep parsing deterministic across backends.

Non-goals for the first iteration include anchors/aliases, tags, complex keys,
and multi-document streams. The module will expose `parse`, `stringify`, `load`,
and `dump` wrappers once a backend implementation is available.

### Minimal regex syntax subset (Phase 2)

To keep regex behavior portable across interpreter, C, and LLVM backends, the
initial `stdlib.regex` module targets a small, deterministic syntax slice.

**Supported constructs**

- Literals: ordinary characters match themselves; escape metacharacters with
  `\` (e.g., `\.` matches a literal dot).
- Wildcard: `.` matches any character except newline.
- Anchors: `^` (start of string) and `$` (end of string).
- Character classes:
  - `[abc]` for explicit sets, `[a-z]` for ASCII ranges, `[^abc]` for negation.
  - Escapes inside classes: `\d` (digits), `\w` (ASCII word), `\s` (ASCII
    whitespace); literal `]` and `-` must be escaped.
- Alternation: `|` with left-to-right precedence.
- Grouping: `(...)` for capturing groups only (no non-capturing syntax).
- Quantifiers (greedy only): `?`, `*`, `+`, `{m}`, `{m,}`, `{m,n}` where `m`
  and `n` are non-negative integers with `m <= n`.

**Unsupported constructs (deferred)**

- Lookarounds: `(?=...)`, `(?!...)`, `(?<=...)`, `(?<!...)`.
- Backreferences: `\1`, `\k<name>`, or any numbered/name-based backref syntax.
- Named groups or group modifiers: `(?P<name>...)`, `(?<name>...)`, `(?:...)`.
- Inline flags or mode switches: `(?i)`, `(?m)`, `(?s)` and equivalents.
- Non-greedy quantifiers: `*?`, `+?`, `??`, `{m,n}?`.
- Unicode categories and properties: `\p{...}` / `\P{...}`.
- Word-boundary tokens: `\b`, `\B` (can be added once backend parity is proven).

**Determinism requirements**

- The engine should behave as ASCII-only for the supported escapes above.
- Errors must include the failing pattern and a short reason (e.g., "unsupported
  construct" vs. "unbalanced parentheses").

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
