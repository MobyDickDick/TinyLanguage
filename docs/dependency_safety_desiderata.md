# Desiderata: safer function dependencies

**Status:** Possible development direction, recorded on 2026-10-29. This is a
design discussion, not a description of implemented features or a scheduled
delivery commitment. It applies to both functions and methods.

## Motivation

Consider a call graph in which `a` calls `b`, `b` calls `c` and `d`, and `d`
calls `e`. A small change to `e` can make `a` behave unexpectedly even when
every function still accepts and returns the same types.

Defining helpers locally can improve encapsulation, but lexical locality alone
does not preserve their behavior. Copying the complete dependency tree into
each caller would isolate subsequent edits, at the cost of substantial code
duplication and independently maintained copies that can miss bug fixes.

The desired outcome is to retain reuse while making behavioral assumptions
explicit and detecting incompatible changes as early as practical.

## Desired capabilities

### Explicit, checkable function contracts

A contract should describe the properties callers may rely on beyond parameter
and return types: accepted values, preconditions, postconditions, ordering,
mutation, observable side effects, and error behavior. For example, a helper
might promise to return values in ascending order without changing its input.

Explore contracts attached to function definitions, with runtime checks and,
where feasible, static checks. The syntax and enforcement model remain open;
this document introduces no new TinyLanguage syntax.

### Visible direct and transitive dependencies

Explore tooling that shows which functions a changed helper may affect. For a
change to `e` in the example, it should identify `d`, `b`, and `a` as potentially
affected callers and explain the call paths. Such a report identifies review
and testing scope; it does not establish that those callers are broken.

Dynamic calls, callbacks, and foreign code can make the graph incomplete.
Tooling should expose uncertainty rather than report an apparently complete
list when some targets cannot be resolved.

### Tests across abstraction levels

Combine contract tests for individual helpers with integration and regression
tests for the behavior of their callers. Tests for `e` alone cannot establish
that `a` still meets its own requirements.

Explore running relevant caller tests automatically when a dependency changes.
If dependency analysis is incomplete, retain a broader test fallback. Passing
selected tests must not be presented as proof of behavioral compatibility.

### Fewer hidden dependencies

Favor pure functions where practical: results depend on explicit inputs and
calls do not change external state. Make mutation, IO, time, randomness, and
other effects visible, including effects introduced through helper calls. This
connects to the proposed
[strict-by-default safety profile](strict_by_default_safety_profile.md).

Purity reduces hidden coupling; changing a pure function's result can still
break a caller's assumptions.

### Deliberate evolution of contracts

Distinguish implementation changes that preserve a contract from changes to
the promised behavior. For incompatible behavior, consider a separately named
API or an explicitly versioned interface and migrate callers deliberately.
For language and standard-library releases, follow the existing
[versioning and deprecation policy](versioning_deprecation_policy.md).

Version pinning can make dependencies reproducible, but cannot by itself
establish that their behavior is correct.

## Possible incremental exploration

1. Document behavioral contracts for a small set of shared helpers and add
   tests for both those contracts and a representative caller chain.
2. Prototype a report of affected callers for directly resolvable calls, with
   explicit indications of unresolved dependencies.
3. Evaluate how the report could select relevant tests while retaining broader
   checks when coverage or dependency information is uncertain.
4. Use those experiments to decide whether language-level contracts and effect
   annotations justify their syntax, runtime cost, and tooling complexity.

## Open questions and limits

- Which properties belong in executable contracts, and which remain prose?
- Should checks be optional, enabled in development, or part of a safety profile?
- How should failures be reported consistently across execution backends?
- How can tooling associate caller tests with functions without excessive
  annotation or false confidence?

Contracts can omit assumptions, tests cover only selected cases, and dependency
graphs can be incomplete. The aim is effective risk reduction and earlier
feedback, not a guarantee that changes to shared code can never break callers.
