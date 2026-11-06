# Parity fixture layout

This directory hosts TinyLanguage fixtures that should run across multiple
backends (interpreter, native VM, LLVM JIT, and C backend). Each fixture is a
`.tiny` file; optional metadata can be supplied via a matching
`<fixture>.meta.json` file.

## Metadata keys (optional)

- `backends`: explicit list of backends to run (`interpreter`, `native`, `llvm`,
  `c`). If omitted, the parity runner defaults to all supported backends.
- `skip_backends`: list of backends to skip for this fixture.
- `expected_exit_code`: 0 (default), or 1 for a deliberate error case.
- `error_contains`: required diagnostic substring when the expected exit is 1.

Metadata narrows the requested backend list; it cannot add unrequested backends.
An unexpected common failure and an entirely unexecuted run both fail. Optional
`.stdout`/`.stderr` sidecars are compared exactly, before broad parity output
normalization. The bundled positive snapshots have independent arithmetic and
control-flow derivations in [the audit](../../docs/independent_correctness_audit.md).
The separate correctness audit supplies staged C/LLVM executable evidence and
raw contract oracles; ordinary backend agreement does not replace that evidence.

The parity runner lives in `tools/parity_runner.py` and defaults to this folder
when fixtures are present.
