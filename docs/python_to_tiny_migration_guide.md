# Python-to-Tiny migration guide

This guide outlines the current migration gaps between Python and TinyLanguage,
recommended refactors, and opportunities for tooling automation. It is meant to
be a practical checklist for porting existing Python programs into Tiny while
keeping behavior aligned.

## Quick checklist

- Inventory module usage and map Python imports to Tiny stdlib modules.
- Replace dynamic typing patterns with explicit, stable types.
- Remove implicit mutation or aliasing assumptions (especially for heap-backed
  data structures).
- Swap Python-specific runtime conveniences (exceptions, context managers,
  reflection) for Tiny equivalents or explicit helper functions.
- Add parity tests that compare Python output to Tiny output.

## Known gaps and differences

### Runtime model

- **Memory management**: Tiny exposes manual heap operations; Python relies on
  automatic memory management. Prefer stack or fixed-size arrays where possible,
  and use `new`/`delete` consistently for heap-backed structures.
- **Type stability**: Tiny disallows implicit type changes; Python allows values
  to change type freely. If a Python variable is re-assigned with a different
  type, split it into two Tiny variables or add explicit conversions.
- **Exceptions**: Tiny has narrower exception support; prefer explicit error
  returns (`Result`-style patterns) and guard checks instead of catching broad
  exceptions.

### Syntax and control flow

- **Comprehensions**: Replace list/set/dict comprehensions with explicit loops
  and append operations.
- **Generators**: Python generators and `yield` are not available; build
  iterators manually or return arrays.
- **Context managers**: Replace `with` blocks using explicit open/close calls or
  helper functions that ensure cleanup.

### Standard library gaps

- **Filesystem/path APIs**: Some Python `pathlib` or `os` conveniences are not
  available in Tiny. Prefer the Tiny stdlib `io` module and wrapper helpers.
- **Datetime**: Tiny has a smaller datetime surface area; convert to primitive
  numeric timestamps when possible.
- **JSON**: Tiny supports JSON in the stdlib, but be mindful of heap-backed
  collections and ensure round-tripping tests exist for complex data.

## Recommended refactors

- **Introduce explicit data models**: Turn ad-hoc dictionaries into typed
  structs or explicit tuples.
- **Separate parsing from computation**: Keep input parsing in small helpers so
  computational logic is easier to port.
- **Replace globals with parameters**: Tiny modules favor explicit parameter
  passing over global mutation.
- **Prefer deterministic iteration**: Replace unordered set/dict iteration with
  ordered arrays when output order matters.

## Tooling automation opportunities

- **Static analysis for type changes**: detect Python variables that change
  type and recommend explicit conversion or new identifiers.
- **Loop expansion helpers**: convert comprehensions to explicit loops.
- **Import mapping**: produce a report that maps Python imports to Tiny stdlib
  equivalents or suggests custom shims.
- **Parity snapshots**: generate output snapshots for Python and Tiny versions
  to detect behavior drift.

## Example migration pattern

### Python

```python
values = [v for v in source if v > 0]
values.sort()
print(sum(values))
```

### Tiny

```tiny
let values = []
for v in source:
    if v > 0:
        values.append(v)
values.sort()
print(sum(values))
```

## Parity testing workflow

1. Capture expected output from the Python program.
2. Port the program to Tiny and run the Tiny equivalent.
3. Compare outputs in a lightweight snapshot test.
4. Repeat after refactors or stdlib changes.

## When to rewrite instead of port

- The Python program relies heavily on metaprogramming, reflection, or dynamic
  import behavior.
- The data model assumes mutable shared state across threads without explicit
  synchronization.
- The code depends on third-party libraries that are not targeted for Tiny
  compatibility.

