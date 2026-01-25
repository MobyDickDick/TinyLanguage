# Parity fixture layout

This directory hosts TinyLanguage fixtures that should run across multiple
backends (interpreter, native VM, LLVM JIT, and C backend). Each fixture is a
`.tiny` file; optional metadata can be supplied via a matching
`<fixture>.meta.json` file.

## Metadata keys (optional)

- `backends`: explicit list of backends to run (`interpreter`, `native`, `llvm`,
  `c`). If omitted, the parity runner defaults to all supported backends.
- `skip_backends`: list of backends to skip for this fixture.

The parity runner lives in `tools/parity_runner.py` and defaults to this folder
when fixtures are present.
