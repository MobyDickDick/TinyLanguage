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
- [ ] Define the minimal package manager UX (init, add/remove deps, lockfile).
- [ ] Implement a module-resolution algorithm that is shared across interpreter
  and native backends.
- [ ] Ship a reference project layout template with tooling defaults.

### 3) Standard library coverage
- [ ] Prioritize missing core modules (`json`, `pathlib`, `os`, `fs` primitives)
  with parity tests against Python behavior.
- [ ] Document stdlib API stability guarantees and module maturity tiers.

### 4) Tooling + developer experience
- [ ] Expand LSP coverage (rename, references, code actions) and publish a
  feature matrix.
- [ ] Provide a debug adapter integration guide with troubleshooting steps for
  all supported launch modes.

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
- [x] Define and publish the formal versioning + deprecation policy for language
  changes.
- [x] Gate spec conformance fixtures in the test suite to verify canonical
  stdout/stderr snapshots for spec examples.
