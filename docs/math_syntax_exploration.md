# Math-Oriented Syntax Exploration

This document explores potential math-oriented syntax/notation for TinyLanguage.
It is intentionally conservative: each proposal is scoped to incremental trials
that can be evaluated without destabilizing existing readability, tooling, or
compiler/interpreter behavior.

## Goals

- Improve ergonomics for math-heavy code without harming general-purpose code.
- Keep parsing deterministic and maintain the current lexer/token model.
- Make each experiment opt-in or behind a feature flag until proven.
- Preserve clear error spans for the linter, formatter, and LSP.

## Non-goals

- Replacing existing expression syntax.
- Introducing implicit precedence rules that differ from current semantics.
- Shipping experimental syntax without a compatibility story.

## Candidate syntax families

### 1) Tuple-based block forms

**Idea**: Use tuple-like forms to represent math blocks or grouped expressions,
possibly with a small operator vocabulary that is already legal in Tiny.

**Example sketches** (illustrative only):

```
# Inline block with explicit operator tokens
(def result = (sum: [x, y, z]))
(def area = (mul: [pi, (pow: [r, 2])]))

# Multi-line block with labeled segments
(def stats = (
  mean: (div: [sum, count]),
  variance: (div: [sq_sum, count])
))
```

**Pros**:
- Reuses existing literal delimiters without inventing new tokens.
- Straightforward to parse as a variant of tuple/struct literal patterns.

**Cons**:
- Potential ambiguity with existing tuple/struct literal usage.
- Might be visually noisy for non-math code.

**Incremental trial**:
- Allow a **single** extra grammar rule: `(<name>: <expr>)` in expression
  position is lowered to a compiler intrinsic (e.g., `Math.<name>(<expr>)`).
- Gate behind a feature flag: `--experimental-math-tuples`.
- Update formatter to preserve a canonical layout for these forms.

### 2) Formula syntax (infix-friendly)

**Idea**: Provide a math-formula mode that preserves infix readability but keeps
explicit delimiters for safety.

**Example sketches**:

```
(def area = #[ pi * r^2 ])
(def coeff = #[ (a + b) / 2 ])
```

**Pros**:
- Clear opt-in delimiter (`#[ ... ]`) that is unlikely to conflict with current
  syntax.
- Allows a dedicated parser entry with math-specific precedence or tokens.

**Cons**:
- Introduces new delimiter pair and requires lexer update.
- Requires a translation step into existing AST nodes.

**Incremental trial**:
- Define a `#[ ... ]` delimited expression that is parsed with **current**
  precedence rules only (no new operators beyond existing ones).
- Use `^` as a candidate **only if** it already exists; otherwise map `pow(a,b)`
  in the translation layer.
- Gate behind `--experimental-math-formula` and add a lint that warns on mixing
  math-formula and normal syntax in the same expression tree.

### 3) Stack-edit / LaTeX-like constructs

**Idea**: Allow a limited set of LaTeX-like tokens for common math operations.

**Example sketches**:

```
(def area = \mul{pi}{\pow{r}{2}})
(def inv = \frac{1}{x})
```

**Pros**:
- Familiar to users coming from LaTeX or symbolic math environments.
- Structured tokens encourage explicit grouping.

**Cons**:
- Adds lexer complexity (escape sequences, identifiers starting with `\`).
- Harder to keep formatting consistent.

**Incremental trial**:
- Restrict to a **small whitelist** of macro-like calls that lower directly to
  builtin functions (`\frac` → `div`, `\pow` → `pow`).
- Only allow inside a delimited `#[ ... ]` block to keep the feature isolated.

## Evaluation criteria

Each experiment should be judged against:

- **Parse determinism**: No conflicts with existing grammar.
- **Error recovery**: Syntax errors should yield precise spans.
- **Formatter stability**: Formatting round-trips without losing intent.
- **Tooling impact**: LSP hover, completion, and diagnostics should remain
  accurate.
- **Compatibility**: Opt-in and feature-gated; no changes to default semantics.

## Recommended next steps

1. Prototype the tuple-based form as the lowest-risk experiment.
2. If successful, trial the formula delimiter (`#[ ... ]`) with existing
   precedence rules and minimal token additions.
3. Defer LaTeX-like constructs until the delimiter form proves stable.

## Open questions

- Should math-oriented syntax be confined to a `Math` module or be globally
  available?
- Do we need a separate operator table for formula mode, or can we reuse the
  existing one?
- How should the formatter serialize math blocks to keep diffs small?
