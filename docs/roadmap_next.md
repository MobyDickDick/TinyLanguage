# TinyLanguage roadmap (proposed)

This document captures a forward-looking roadmap for maturing TinyLanguage into
an end-to-end programming language with a stable toolchain and ecosystem. The
phases below build on each other but can progress in parallel where practical.

## Roadmap by area (execution-oriented)

To make the roadmap actionable, the work is grouped by the major program areas
tracked in `docs/open_tasks.md`.

### Language core

- Finalize evaluation-order, scoping, error-handling, and concurrency rules in
  the language specification.
- Define compatibility commitments and deprecation policies for core semantics.
- Align diagnostics with a shared error schema across interpreter and tooling.

### Type system

- Introduce optional type annotations and a gradual-typing strategy. (See
  `docs/gradual_typing.md`.)
- Add a minimal type-checking pass that can run in lints/CI.
- Decide if effect or mutability annotations are needed for stricter safety
  profiles.

### Runtime and performance

- Document optimization stages and performance targets for interpreter, C, and
  LLVM backends.
- Establish profiling + benchmarking workflows for regressions.
- Track backend parity gaps with targeted tests and close them.

### Tooling and developer experience

- Expand LSP capabilities (rename, references, code actions, formatting hooks).
- Improve debugging workflows (breakpoints, watch expressions, variable views).
- Provide project scaffolding, templates, and versioned CLI ergonomics.

### Ecosystem maturity

- Prioritize stdlib modules (I/O, data formats, filesystem, networking, math,
  collections) and document APIs.
- Specify module resolution rules (local vs. stdlib vs. external packages).
- Define a package manager plan (lockfiles, registry layout, semantic
  versioning).
- Track package/module milestones and deliverables in
  `docs/package_module_roadmap.md`.
- Maintain conformance and cross-backend parity test suites.
- Publish compatibility matrices and migration guides for major releases.

## Phase 1: Language core stability

**Goals**: Lock down semantics, reduce surprises, and define compatibility rules.

- Publish a definitive language specification that covers evaluation order,
  scoping, error handling, concurrency semantics, and numeric conversion rules.
- Add explicit versioning/deprecation policies for language features and runtime
  behavior changes.
- Strengthen diagnostics with structured error metadata and consistent
  formatting across interpreter and toolchain.

## Phase 2: Type discipline and safety

**Goals**: Provide optional static checks without blocking dynamic workflows.

- Introduce optional type annotations with a gradual-typing strategy. (See
  `docs/gradual_typing.md`.)
- Define a minimal type-checking pass that can run as a linter or CI gate.
- Plan for effect or mutability annotations if needed for stricter safety
  profiles.

## Phase 3: Standard library and modules

**Goals**: Offer essential APIs and a clear module/package story.

- Prioritize stdlib modules (I/O, data formats, filesystem, networking, math,
  collections) and document their APIs.
- Specify module resolution rules (local vs. stdlib vs. external packages).
- Define a package manager plan (lockfiles, registry layout, semantic
  versioning).
- Track package/module milestones and deliverables in
  `docs/package_module_roadmap.md`.

## Phase 4: Runtime and performance

**Goals**: Deliver predictable performance and multiple backends with parity.

- Document optimization stages and performance targets for interpreter, C, and
  LLVM backends.
- Establish profiling and benchmarking workflows for regressions.
- Track backend feature parity and close gaps with targeted tests.

## Phase 5: Tooling and developer experience

**Goals**: Make TinyLanguage productive to develop and debug.

- Expand LSP capabilities (rename, references, code actions, formatting hooks).
- Improve debugging workflows (breakpoints, watch expressions, variable views).
- Provide project scaffolding, templates, and versioned CLI ergonomics.

## Phase 6: Testing, compliance, and ecosystem

**Goals**: Ensure correctness and long-term maintainability.

- Maintain a conformance test suite linked to language spec requirements.
- Run cross-backend parity tests to guarantee consistent behavior.
- Publish compatibility matrices and migration guides for major releases.

## Milestone tracking

Milestones should be tracked in `docs/open_tasks.md` so that the roadmap stays
anchored to concrete, testable work items.
