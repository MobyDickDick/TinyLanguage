# Gradual typing and optional annotations

TinyLanguage supports **optional type annotations** that can be layered onto
otherwise dynamic code. The goal is to provide early correctness signals (while
preserving the runtime behavior of untyped programs) and to let teams migrate
progressively without a hard “all-typed” switch.

This guide summarizes the syntax, compatibility rules, and a practical migration
strategy that matches the current runtime enforcement behavior and the typing
track plan in `docs/typing_track_plan.md`.

## Design goals

- **Opt-in safety**: Annotations are optional and do not change execution for
  unannotated code.
- **Gradual adoption**: Mixed typed/untyped code is supported. Teams can type
  only the modules that benefit most.
- **Predictable runtime behavior**: Annotated values are still checked at
  runtime so behavior is consistent across backends.

## Syntax recap

Annotations can appear on:

- **Bindings**: `def count: number = 0;`
- **Parameters**: `fn add(x: number, y: number) -> number { ... }`
- **Return types**: `fn name(...) -> string { ... }`
- **Type/class fields**: `type Point { x: number; y: number; }`

### Optional and dynamic escape hatches

- `T?` marks an optional type. It accepts `Null` and any value compatible with
  `T`.
- `any` disables type-change checks for a binding, but still participates in
  parameter/return validation when a stricter annotation is present.

## Compatibility rules

TinyLanguage uses a lightweight compatibility model (designed to mirror runtime
checks) rather than a heavy structural type system:

- `number` accepts both integer and floating-point literals.
- `string`, `bool`, and `Null` are strict (only exact values match).
- `T?` accepts `Null` and any value compatible with `T`.
- `any` accepts any value but should be reserved for interoperability or staged
  migrations.

## Type stability in bindings

The first assignment to a `def` binding establishes its type unless an
annotation is present. Reassignments must stay compatible with the established
(or annotated) type. If you need to change to an unrelated type, introduce a new
binding instead of reassigning the old one.

## Runtime enforcement

Annotations are enforced at runtime in the interpreter and backend runtimes.
This keeps behavior consistent even if static checks are not enabled. Runtime
errors use standard diagnostics (e.g. `E009`, `E014`) and align with the
diagnostics planned for the lint-based static pass.

## Lint/CI integration

Use the typing lint profile to enable static checks for annotated code paths:

- **CLI example**: `python src/language_server_cli.py --lint-profile typing ...`
- **Expected behavior**: annotated parameter, return, and assignment mismatches
  are reported early without requiring whole-program typing.

(See `docs/typing_track_plan.md` for the implementation roadmap and the planned
Phase 1 static checks.)

## Migration strategy (recommended)

1. **Start with high-value modules**: annotate public APIs and “core” utility
   modules first.
2. **Add return annotations early**: this prevents inconsistent returns in
   functions that are widely called.
3. **Use `T?` for partial coverage**: optional types let you preserve `Null`
   semantics while still constraining the non-null path.
4. **Use `any` sparingly**: treat it as a temporary escape hatch and document
   why it is required.
5. **Enforce via CI**: once a module is annotated, add the typing lint profile
   to CI to keep regressions from slipping in.

## Example

```tiny
fn greet(name: string?) -> string {
  if name == Null {
    return "hello";
  }
  return "hello " + name;
}

fn add(x: number, y: number) -> number {
  return x + y;
}

def label: any = "name"; // escape hatch, but prefer a real type
```

## Related documentation

- `docs/language_spec.md` (type stability and annotation rules)
- `docs/typing_track_plan.md` (implementation plan for static checks)
