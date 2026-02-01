# Full-language readiness checklist

This checklist centralizes the remaining work needed to evolve TinyLanguage into
an end-to-end, production-ready programming language. It focuses on language
completeness, ecosystem maturity, and delivery requirements beyond the current
interpreter and tooling footprint.

## Checklist (prioritized)

### 1) Core language + semantics
- [x] Specify a formal versioning + deprecation policy for language changes.
- [x] Lock down evaluation order, scoping, and error-handling rules with
  testable examples in `docs/language_spec.md`.
- [x] Publish a conformance test suite for the spec (lexer, parser, runtime
  semantics) and gate it in CI.

### 2) Modules + packages (MVP)
- [x] Define the minimal package manager UX (init, add/remove deps, lockfile).
- [x] Implement a module-resolution algorithm that is shared across interpreter
  and native backends.
- [x] Ship a reference project layout template with tooling defaults.

### 3) Standard library coverage
- [x] Prioritize missing core modules (`json`, `pathlib`, `os`, `fs` primitives)
  with parity tests against Python behavior.
- [x] Document stdlib API stability guarantees and module maturity tiers (see
  `docs/stdlib_compatibility.md`).

### 4) Tooling + developer experience
- [x] Expand LSP coverage (rename, references, code actions) and publish a
  feature matrix (see `docs/language_server_workflows.md`).
- [x] Provide a debug adapter integration guide with troubleshooting steps for
  all supported launch modes (see `docs/debug_adapter_integration.md`).

### 5) Distribution + releases
- [ ] Publish official release artifacts (versioned binaries, pip/npm packages
  as needed) and a reproducible build pipeline.
- [ ] Provide upgrade guides and compatibility matrices for each release.

### 6) Ecosystem maturity
- [ ] Define interoperability/FFI guidelines (embedding, calling C/Python, data
  marshaling rules).
- [ ] Establish performance budgets and profiling baselines for each backend.

## Completed (this update)

- [x] Centralize the “full-language readiness” task list in
  `docs/full_language_readiness.md` and link it from `docs/open_tasks.md`.
- [x] Prioritize missing core modules (`json`, `pathlib`, `os`, `fs` primitives)
  with explicit parity-test expectations in `docs/stdlib_expansion_plan.md`.
- [x] Define and publish the formal versioning + deprecation policy for language
  changes.
- [x] Define the minimal package manager UX (init, add/remove deps, lockfile).
- [x] Gate spec conformance fixtures in the test suite to verify canonical
  stdout/stderr snapshots for spec examples.
- [x] Ship a reference project layout template with tooling defaults (see
  `docs/project_template_v1/`).
