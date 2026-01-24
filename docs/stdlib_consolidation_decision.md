# Stdlib consolidation decision template

## Goal
Decide whether the TinyLanguage stdlib should remain split between:

- `stdlib/` (Tiny `.tiny` modules for source-level imports), and
- `src/stdlib/` (Python-side native registrations and curated Tiny sources)

or be consolidated into a single stdlib root.

## Current state summary

- `stdlib/` is searched as the module root at runtime for Tiny-level imports.
- `src/stdlib/__init__.py` registers native APIs/types and may bundle Tiny
  sources used by the interpreter runtime.
- The runtime currently assumes both layers exist.

## Decision options

### Option A: Keep the split (status quo)

**Summary**: Continue to store Tiny modules in `stdlib/` and native
registrations in `src/stdlib/`.

**Pros**
- No breaking changes to import paths.
- Keeps native registration logic separate from Tiny source modules.
- Minimal tooling impact.

**Cons**
- Two stdlib roots to understand and maintain.
- Runtime search logic remains more complex.

### Option B: Consolidate into a single stdlib root

**Summary**: Choose one root (likely `src/stdlib/`) and move Tiny `.tiny`
modules there, or move native registration into `stdlib/`.

**Pros**
- Single source of truth for stdlib modules.
- Simpler runtime search and documentation.

**Cons**
- Requires import-path migration for existing Tiny programs.
- May complicate packaging (native registration vs. Tiny sources).
- Requires updates to tooling/tests/docs.

## Impact analysis checklist

### Import paths
- Do existing Tiny programs import from `stdlib/` implicitly?
- Would module names or relative paths change if the root moves?

### Runtime search (`tiny_language_runtime.py`)
- Where is the stdlib root resolved today?
- What code needs to change to support a new root or a single root?

### Native API registration (`src/stdlib/__init__.py`)
- Can the registration layer live alongside Tiny sources without ambiguity?
- Does the registration layer rely on file locations or packaging assumptions?

### Tooling and tests
- Which scripts/tests refer to the current stdlib root paths?
- Do any docs mention `stdlib/` explicitly?

### Packaging and distribution
- Are both `stdlib/` and `src/stdlib/` included in distributions today?
- Would consolidation affect import resolution when packaged?

## Decision

- **Chosen option**: _TBD_
- **Rationale**: _TBD_
- **Date**: _TBD_
- **Decision owner**: _TBD_

## Migration plan (if Option B)

1. Choose the new stdlib root and update runtime search logic.
2. Move Tiny `.tiny` modules into the chosen root.
3. Update import path documentation and run a migration pass for tests/examples.
4. Provide deprecation notes and a compatibility shim (if needed).
5. Remove legacy root references after a grace period.

## Follow-ups

- Update `documentation_tasks.md` and `docs/redundancy_review.md` as the
  decision is finalized.
- Track any required release notes or migration tooling.
