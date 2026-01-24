# Stdlib consolidation decision tasks

Use this task list to evaluate whether the TinyLanguage stdlib should remain
split between `stdlib/` (Tiny `.tiny` sources) and `src/stdlib/` (native
registrations + curated Tiny sources), or be consolidated into a single root.

## Tasks

### 1) Capture the current state
- [ ] Document how `tiny_language_runtime.py` resolves the stdlib search root.
- [ ] Summarize what lives in `stdlib/` vs. `src/stdlib/` (include any overlap).
- [ ] Note any packaging/distribution assumptions about both directories.

### 2) Evaluate option A: keep the split
- [ ] Confirm that existing Tiny programs import from `stdlib/` implicitly.
- [ ] Identify maintenance cost or confusion caused by two roots.
- [ ] Record any advantages of keeping native registration separate.

### 3) Evaluate option B: consolidate into a single root
- [ ] Choose a target root (`src/stdlib/` or `stdlib/`) and justify why.
- [ ] Identify import-path changes required for existing programs.
- [ ] Assess how native registration can coexist with Tiny sources in one root.
- [ ] List tooling/tests/docs that would need updates.

### 4) Decide and record
- [ ] Select the preferred option.
- [ ] Record rationale, decision owner, and decision date.

### 5) Plan migration (if consolidating)
- [ ] Update runtime search logic for a single stdlib root.
- [ ] Move Tiny `.tiny` modules into the chosen root.
- [ ] Update docs and tests to use the new import paths.
- [ ] Provide deprecation notes and a compatibility shim (if needed).
- [ ] Remove legacy root references after the grace period.

## Decision log

- **Chosen option**: _TBD_
- **Rationale**: _TBD_
- **Decision owner**: _TBD_
- **Date**: _TBD_
