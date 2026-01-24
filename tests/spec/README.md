# Spec fixture layout (draft)

This directory is the initial skeleton for spec conformance fixtures. Each
fixture should include the Tiny program plus snapshot files for stdout/stderr
so that tooling can diff actual backend output against the canonical results.

## Naming convention

For a fixture named `hello_world`:

- `hello_world.tiny` — the Tiny program under test, including a header comment
  that references the relevant spec section(s).
- `hello_world.stdout` — expected standard output (exact text).
- `hello_world.stderr` — expected standard error (exact text; empty file for
  no stderr output).
- `hello_world.meta.json` (optional) — metadata describing the scope, backend
  support, stability tier, and expected outcome.

The sample fixture below mirrors this layout and serves as an example for new
spec tests.
