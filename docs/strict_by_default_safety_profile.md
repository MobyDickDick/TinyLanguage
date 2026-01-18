# Strict-by-default safety profile

This document defines a **strict-by-default safety profile** for TinyLanguage.
The goal is to make risky behavior opt-in, surface potential side effects
explicitly, and keep programs predictable by default. The profile is designed
as a policy layer that can be enabled by a future `--strict` (or equivalent)
flag, and it can guide linting, diagnostics, and stdlib defaults.

## Goals

- Make side effects visible at the call site (via annotations or explicit
  wrappers).
- Reduce implicit behavior (mutability, type changes, and hidden IO).
- Provide safer stdlib defaults with opt-in escape hatches.
- Keep runtime error surfaces predictable and well-scoped.

## Core defaults

### Explicit mutability

- **Default to immutable bindings**; require an explicit marker for mutation.
- Disallow implicit rebinding of captured values inside nested scopes without
  marking the binding as mutable.
- Require explicit `mut` (or equivalent) on any field/collection that is
  mutated after construction.

### Explicit side effects

- **Mark effectful functions** (IO, randomness, time, concurrency) with a
  dedicated annotation such as `@effect(io)` or `@effect(random)`.
- Require effect annotations to be present on any function that performs
  effectful operations directly or indirectly.
- Propagate effect markers through calls unless an explicit boundary wrapper
  is used (see "Effect boundaries" below).

### Narrowed implicit conversions

- Disallow implicit numeric widening or narrowing in strict mode.
- Require explicit casts or helper functions when converting between numeric
  types or between numeric and string representations.

### Deterministic evaluation

- Require deterministic evaluation order in strict mode; disallow evaluation
  of expressions with observable side effects in unspecified order contexts.
- Emit diagnostics when side-effectful expressions appear in contexts with
  unclear ordering.

## Effect boundaries

Effect boundaries make side effects explicit and auditable.

- Introduce a standard boundary wrapper such as `Effect.run { ... }` (or a
  similar construct) that marks a block as intentionally effectful.
- Within a boundary, effect annotations are still required, but the boundary
  provides a clear audit point for reviewers and tooling.
- Enforce that effectful stdlib operations can only be called inside a boundary
  or from already-effectful functions.

## Stdlib defaults (strict mode)

### IO and filesystem

- Require explicit intent flags for destructive operations (e.g.
  `File.remove(path, allow_missing=false)` should error on missing paths unless
  explicitly overridden).
- Prefer APIs that return `Result`-like values rather than raising exceptions
  for common, recoverable errors.

### Randomness and time

- Require explicit `Random.seed(...)` or a `Random.with_seed(...)` scope to use
  randomness in strict mode.
- Require explicit access to time APIs via effect annotations.

### Heap and mutation

- Require explicit ownership for heap allocations (e.g. `new`-like operations
  return an owned handle that cannot be aliased without an explicit `share`
  operation).
- Favor fixed-size arrays/stack-friendly structures in strict mode when the
  size is known at compile time; fall back to heap collections only when
  explicitly requested.

## Tooling expectations

- **Formatter/linter**: enforce explicit mutability markers and effect
  annotations in strict mode.
- **Diagnostics**: provide actionable error messages suggesting `mut`, explicit
  casts, or effect boundaries as fixes.
- **Language server**: highlight effectful APIs and propagate effect markers in
  hover/completion details.

## Migration guidance

- Provide an auto-fix mode that inserts `mut` and effect annotations where
  missing.
- Offer a `--strict-warn` mode that emits warnings without failing the build to
  ease adoption.

## Non-goals

- Strict mode does not remove features; it only changes defaults and requires
  explicit intent.
- Strict mode is not a substitute for runtime safety checks in the interpreter
  or native backends.
