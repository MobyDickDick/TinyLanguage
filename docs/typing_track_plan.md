# Optional static typing track plan

This document outlines a lightweight, optional static typing track for
TinyLanguage. The goal is to provide early correctness wins (mis-typed
assignments, mismatched call signatures, and inconsistent returns) without
blocking dynamic workflows or introducing a heavy type system too early.

## Goals

- **Optional by default**: Programs should run without annotations. Opting into
  static checks should be explicit (CLI flag, project config, or lint profile).
- **Early wins**: Catch common mistakes at edit/lint time (parameter count/type
  mismatches, invalid reassignments, and inconsistent returns).
- **Gradual typing**: Allow `any` and `T?` to interoperate with stricter
  annotations without forcing all code to be fully typed.
- **Runtime parity**: Keep runtime checks in place for annotated paths so
  behavior stays consistent across backends.

## Current foundations to leverage

TinyLanguage already supports:

- Parameter and return annotations (`fn add(x: number) -> number { ... }`).
- First-assignment type inference for bindings.
- Runtime enforcement of annotated types and type-stability rules.

The static typing track should treat these as authoritative and add a
compile-/lint-time pass that mirrors the runtime checks.

## Proposed phases

### Phase 1: Annotation-aware linting (MVP)

Add a lightweight static checker that operates on the parsed AST and the
existing binding/type-stability rules.

**Capabilities**

- Enforce binding reassignments to remain compatible with the inferred or
  annotated type.
- Verify function call arity and annotated argument compatibility.
- Validate return statements against annotated return types.
- Track `any` and `T?` as explicit escape hatches that suppress strict errors
  while still reporting mismatches when stricter annotations are present.

**Out of scope (Phase 1)**

- Global type inference across files/modules.
- Flow-sensitive inference beyond first assignment.
- Exhaustive structural typing for complex containers.

### Phase 2: Module-level summaries

Introduce lightweight symbol summaries per module:

- Exported function signatures and type annotations.
- Public type definitions (`type`, `class`) with field annotations.

This allows cross-module validation without full whole-program inference.

### Phase 3: Optional enhancements

- Limited generic constraints for container helpers (e.g., `List[number]`).
- Flow-sensitive narrowing for `match` or `if` guards.
- IDE-friendly diagnostics with richer hints (e.g., suggested annotation fixes).

## Minimal type-checking passes (Phase 1 detail)

The MVP can be expressed as a sequence of passes over the AST:

1. **Signature collection**
   - Register function signatures (param annotations + return annotation).
   - Register type and class field annotations.
2. **Binding inference + stability**
   - Track inferred types for `def` on first assignment.
   - Validate reassignments against existing type (or `any`/`T?` rules).
3. **Call validation**
   - Check function arity.
   - Validate argument compatibility when the callee has annotated params.
4. **Return validation**
   - For annotated functions, ensure all return paths are compatible.
   - For unannotated functions, enforce existing type-stability rules
     (e.g., `E014` behavior).
5. **Diagnostics alignment**
   - Reuse existing error codes where possible (e.g., `E009`, `E014`).
   - Emit linter-style diagnostics with `SourceSpan` for editor integration.

## Runtime type-check inventory (inputs for Phase 1)

The runtime already enforces several type-related constraints that should be
mirrored by the static lint pass. The table below maps the enforcement points
to their diagnostic codes so the linter can reuse the same semantics.

| Runtime check | Where it happens | Error code | Notes for the linter |
| --- | --- | --- | --- |
| Variable type stability (reassignment) | `_check_assignment_type` in `Runtime` | `E014` | Mirrors `lint_assignment_types` in the linter to flag type changes on reassignments. |
| Annotation enforcement (params/returns/fields) | `_enforce_annotation` in `Runtime` | `E009` | Emit when annotated types do not match values; linter should mirror `_type_matches` semantics. |
| Inferred return stability | `_enforce_inferred_return` in `Runtime` | `E014` | Used when unannotated functions change inferred return type across branches/returns. |
| Heap cell type stability | `heap_set` in `Runtime` | `E014` | Treat heap cell types as stable; linter may eventually mirror for heap APIs. |

The shared matching rules (`_type_matches` and `_types_match`) already normalize
`number`, `string`, `bool`, optional `T?`, and `any`, so the static checks should
reuse the same equivalence behavior. 

### Tasks derived from the runtime inventory

- [x] Align `_types_match` in the linter with runtime `_type_matches` so both
  respect the same normalization rules (e.g. `number`, `string`, `bool`,
  optional `T?`, and `any`).
- [x] Add annotation enforcement checks to the linter pipeline so annotated
  params/returns/fields emit `E009` when values do not match.
- [x] Extend return validation to mirror `_enforce_inferred_return` and emit
  `E014` for inferred return type drift in unannotated functions.
- [x] Evaluate whether heap API type stability (e.g. `heap_set`) should be
  surfaced in linting and document the decision.

**Decision (heap type stability in linting):** Defer adding a static lint for
`heap_set` type stability in Phase 1. The runtime check depends on the dynamic
value flowing into each heap cell (including pointer tags), and a static pass
would need alias tracking plus flow-sensitive value typing to avoid false
positives. For now, keep the runtime `E014` guard as the source of truth and
revisit once Phase 2 module summaries or Phase 3 narrowing are in place.

## CLI and tooling integration

- Add a lint profile (e.g., `tinyc lint --profile typing`) that runs the static
  type pass.
- Allow opt-in via project config (`tiny.toml` or similar) so CI can gate on it.
- Provide a strict flag (`--typecheck`) that fails builds on typing errors.

## Compatibility and migration notes

- Existing dynamic code continues to run without annotations.
- Teams can opt into typing progressively by annotating new modules first.
- `any` and `T?` provide controlled escape hatches during migration.

## Open questions

- Should the static pass treat runtime `tag(...)` as a type assertion?
- How should external module imports be typed (stubs vs. inferred summaries)?
- How aggressively should diagnostics warn about implicit `any` usage?

## Deliverables checklist

- [x] Add a `typing` lint profile and CLI flag.
- [x] Implement the Phase 1 static pass in the linter pipeline.
- [x] Document configuration and migration strategy. (See
  `docs/gradual_typing.md`.)
- [x] Add regression tests for common typing errors.

## Task breakdown (work items)

The following tasks break the plan into actionable work items that can be
tracked independently. Each task is intentionally scoped so it can be picked
up without requiring the entire typing track to be complete.

### Phase 1: Annotation-aware linting (MVP)

- [x] Inventory existing runtime type checks and map them to linter diagnostics
  (reuse error codes where possible).
- [x] Add an AST pass that collects function signatures, return annotations, and
  type/class field annotations.
- [x] Add a binding inference + stability pass that mirrors runtime reassignment
  rules (`any` and `T?` are explicit escape hatches).
- [x] Add a call validation pass that checks arity and annotated argument
  compatibility.
- [x] Add a return validation pass that enforces annotated return types and
  preserves existing stability rules for unannotated functions.
- [x] Align diagnostics with existing `SourceSpan`-based reporting for editor
  and CLI outputs.
- [x] Expose a `typing` lint profile (e.g., `python src/language_server_cli.py --lint-profile typing ...`) that
  runs the new static checks.
- [x] Add a strict flag (e.g., `--typecheck`) that fails builds on typing
  errors.
- [x] Document configuration + migration guidance for gradual adoption. (See
  `docs/gradual_typing.md`.)
- [x] Add regression tests that cover common typing mistakes (reassignment,
  call mismatch, and inconsistent returns).

### Phase 2: Module-level summaries

- [ ] Define a lightweight module summary format (exported functions, types,
  and class fields).
- [ ] Emit summaries during parsing or linting for modules with annotations.
- [ ] Resolve imports against summaries to validate cross-module call sites.
- [ ] Add tests that validate cross-module signature mismatches.

### Phase 3: Optional enhancements

- [ ] Add limited generic constraints for container helpers (e.g.,
  `List[number]`) and document the supported syntax.
- [ ] Introduce flow-sensitive narrowing for `match`/`if` guards where safe.
- [ ] Add richer diagnostics for IDE integration (quick fixes, hints, and
  annotation suggestions).

### Open questions to resolve

- [ ] Decide whether runtime `tag(...)` should act as a static type assertion.
- [ ] Decide how external module imports are typed (stubs vs. inferred
  summaries).
- [ ] Decide how strongly to warn about implicit `any` usage in typed modules.
