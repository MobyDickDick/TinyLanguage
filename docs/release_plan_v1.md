# TinyLanguage 1.0 Release Plan

This document proposes concrete steps to plan a **1.0 release** of TinyLanguage. It focuses on scope, readiness criteria, and a lightweight execution checklist so the release can be scoped and delivered predictably.

---

## 1) Define 1.0 scope and non-goals

**Goal:** lock a stable interpreter experience with core language features + docs + tests.

**In scope (candidate 1.0):**
- Interpreter backend (default) is stable.
- Language syntax and semantics documented in [docs/language_spec.md](language_spec.md).
- Standard library baseline in [stdlib/](../stdlib/) documented in [docs/stdlib_compatibility.md](stdlib_compatibility.md).
- CLI usage documented in [README.md](../README.md) and [docs/tutorial.md](tutorial.md).
- Tests cover critical runtime features (parsing, control flow, heap, functions, classes).

**Explicit non-goals for 1.0 (defer):**
- LLVM and native compiler backends beyond the current experimental state.
- Performance guarantees or optimization targets.
- A formal package distribution beyond source checkout.

**Action:** decide and record the official 1.0 scope, then freeze it.

**Scope decision (frozen):**
- **Release scope:** interpreter + core language only.
- **Out of scope:** LLVM backend, native/C compiler backend, performance guarantees,
  and packaging/distribution beyond source checkout.
- **Status:** frozen for 1.0 to prioritize interpreter stability, docs, and tests.

---

## 2) Release criteria (exit checklist)

Create an explicit **release checklist** and treat it as the definition of done.

### Feature readiness
- [ ] All “must-have” features in the scope are implemented and documented.
- [ ] Language spec updated and consistent with current behavior.
- [ ] Known “major” bugs are either fixed or documented in a “Known issues” list.

### Testing readiness
- [ ] `python -m pytest` passes locally.
- [ ] `python run_all.py` passes locally.
- [ ] At least one round of regression tests added for recent fixes.

### Docs readiness
- [ ] README quickstart matches current CLI usage.
- [ ] Tutorial runs as-is and outputs match.
- [ ] Demo commands list is up-to-date (see [docs/demo_run_commands.md](demo_run_commands.md)).

### Release artifact readiness
- [ ] Version set to `1.0.0` in all relevant files (if versioning exists).
- [x] `CHANGELOG.md` created or updated with “1.0.0” notes.
- [ ] Tag + GitHub release notes prepared.

---

## 3) Work breakdown and milestones

Break the release into **short, verifiable milestones**. Example:

### Milestone A — Scope + documentation freeze
- Freeze the scope (list of must-have features).
- Audit language spec vs. behavior; patch mismatches.
- Lock the tutorial and quickstart content.

### Milestone B — Test hardening
- Expand tests for interpreter edge cases (heap, control flow, recursion).
- Add regression tests for known tricky behavior.
- Ensure `run_all.py` and `pytest` are green.

### Milestone C — Release packaging
- Add or update version info.
- Create or update `CHANGELOG.md`.
- Prepare release notes and “known issues” list.

---

## 4) Release readiness review

Perform a **release candidate (RC)** pass:
1. Branch off `release/1.0.0-rc`.
2. Run the full test suite.
3. Validate docs by running tutorial and demo commands end-to-end.
4. Verify expected output for key demos in `src_tiny/`.
5. Reconfirm that the language spec matches behavior.

Only merge the RC when all checklist items are satisfied.

---

## 5) Versioning + changelog policy

- Adopt **SemVer** for release tags (`1.0.0`, `1.0.1`, etc.).
- Maintain a `CHANGELOG.md` with:
  - Added/Changed/Fixed sections.
  - A “Known issues” list for limitations or experimental features.

---

## 6) Communication plan

- Write short release notes describing:
  - Key language features.
  - What is *stable* vs. *experimental*.
  - How to get started (quickstart steps).
- Pin a “1.0 release” note to the README (optional).

---

## 7) Open items to decide now

Make a decision (and record it in this plan or a roadmap entry):
- ✅ 1.0 includes only the interpreter (C/LLVM remain experimental).
- Define guarantees implied by “1.0” (API stability, no breaking changes).
- Define the minimal docs and tests required to ship.

---

## 8) Suggested next steps (actionable)

1. Add a short **1.0 scope** checklist to `docs/open_tasks.md` or a dedicated release checklist.
2. Audit the language spec + tutorial against the current interpreter behavior.
3. Create/expand regression tests for recent fixes and high-risk features.
4. Introduce a `CHANGELOG.md` and decide versioning location.
5. Schedule a release candidate window and perform a full doc + demo run-through.

---

## 9) Quick checklist (copy/paste)

```
[x] Scope frozen (interpreter + core language only)
[ ] Language spec audited and updated
[ ] Tutorial audited and demo commands verified
[ ] pytest passes
[ ] run_all.py passes
[ ] Regression tests added
[x] CHANGELOG.md updated
[ ] Version set to 1.0.0
[ ] Release notes written
[ ] Tag created and release published
```
