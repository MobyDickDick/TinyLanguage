# TinyLanguage redundancy review

This note captures the intentional redundancies that appear in the TinyLanguage
repository so future contributors know which duplicates are deliberate and
which are candidates for consolidation.

## Entrypoint shims and wrappers (intentional)

TinyLanguage keeps several wrapper scripts so that tooling, docs, and user
muscle memory can keep using familiar commands even as the implementation moves
under `src/`:

- `run_all.py` in the repo root is a compatibility shim that forwards to the
  real runner in `src/run_all.py`. This lets tooling invoke the suite from the
  root without needing to know about the internal layout.【F:run_all.py†L1-L16】
- The executable `tiny_language` (shell script) is a launcher that executes the
  Python interpreter against `src/tiny_language.py` so `.tiny` programs can be
  run without typing `python` explicitly.【F:tiny_language†L1-L9】
- The root-level `tiny_language.py` is a Python module wrapper that provides the
  `python -m tiny_language` entrypoint while still delegating execution to
  `src/tiny_language.py`.【F:tiny_language.py†L1-L20】
- `src/tiny_lang_cli.py` is a thin module wrapper that forwards to
  `src/tiny_language_cli.py` so both `python -m tiny_lang_cli` and
  `python -m tiny_language_cli` remain valid CLI entrypoints.【F:src/tiny_lang_cli.py†L1-L19】

These files are “redundant” in the sense that they forward to the same
implementation, but they intentionally preserve backwards-compatible entry
points and are not expected to be removed without a migration plan.

### Migration plan (proposed)

Goal: consolidate user-facing entrypoints on the canonical `src/` modules while
keeping a safe deprecation window for tooling and docs that still rely on the
legacy shims.

**Canonical entrypoints (target)**

- Test/automation runner: `python src/run_all.py`
- Language CLI: `python src/tiny_language_cli.py`
- Interpreter runner: `python src/tiny_language.py`

**Deprecation timeline**

1. **Phase 1 (announce, 0–1 release):**
   - Keep all shims, but print a one-line warning on invocation:
     - `run_all.py` warns to use `python src/run_all.py`.
     - `tiny_language` / `tiny_language.py` warn to use `python src/tiny_language.py`
       (or the CLI module as appropriate).
     - `src/tiny_lang_cli.py` warns to use `python src/tiny_language_cli.py`.
   - Update docs and internal tooling to reference canonical entrypoints only.
2. **Phase 2 (grace period, 1–2 releases):**
   - Shims remain, warnings stay, but tests/CI no longer call shims.
   - Provide a short migration note in release notes.
3. **Phase 3 (removal, 2+ releases):**
   - Remove the root-level shims (`run_all.py`, `tiny_language`,
     `tiny_language.py`) and the `src/tiny_lang_cli.py` alias.
   - Keep a final changelog entry listing removed commands and replacements.

**Compatibility mappings**

- `run_all.py` → `python src/run_all.py`
- `tiny_language` → `python src/tiny_language.py`
- `python -m tiny_language` → `python src/tiny_language.py`
- `python -m tiny_lang_cli` → `python src/tiny_language_cli.py`

## Stdlib sources vs. native stdlib registration

There are two stdlib layers in the repo:

- `stdlib/` at the repository root contains Tiny `.tiny` modules intended for
  source-level imports in TinyLanguage programs.
- `src/stdlib/` contains a Python module (`__init__.py`) that registers built-in
  namespaces/types with the runtime.

The runtime explicitly resolves `stdlib.*` imports against the top-level
`stdlib/` directory, while native registration continues to live in
`src/stdlib/__init__.py`.【F:src/tiny_language_runtime.py†L188-L192】【F:src/stdlib/__init__.py†L2-L44】

This layout keeps Tiny-language sources in `stdlib/`, while
`src/stdlib/__init__.py` wires the native runtime APIs and avoids re-implementing
logic already covered by Tiny sources.【F:src/stdlib/__init__.py†L2-L44】

### Stdlib consolidation decision template

If the project decides to revisit the split stdlib layout, use the task list in
`docs/stdlib_consolidation_decision.md` to evaluate whether the stdlib roots
can be merged and what the downstream impact would be.

## Summary

The redundancy scan did not uncover any accidental duplicate implementations.
The overlapping files are intentional compatibility shims or separate layers of
stdlib support. If future refactors consolidate these, the removal should come
with updated tooling/docs and migration notes.
