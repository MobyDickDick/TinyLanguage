# Release compatibility matrix

This document captures the compatibility commitments for major TinyLanguage
releases. It is intentionally lightweight and should be updated alongside
`VERSION` and `CHANGELOG.md` whenever a new major release is tagged.

## 1.0.0 (current)

| Capability | Status | Notes |
| --- | --- | --- |
| Interpreter backend | **Supported** | Full-language reference implementation; baseline for correctness tests. |
| Native VM backend (`--native-backend`) | **Experimental** | Feature coverage is intentionally limited; unsupported constructs raise `NotImplementedError`. Use the interpreter for complete coverage. |
| LLVM pipeline (`--emit-llvm`, `--emit-exe`) | **Experimental** | Shares the same experimental constraints as the native VM; only a subset of language features is supported. |
| Native Python bytecode backend (`--native-python-bytecode`) | **Experimental** | Alternate lowering path for the native IR; use for comparisons only. |

### Tested platforms (1.0.0)

TinyLanguage is distributed as a Python project, so the baseline compatibility
promise is tied to the Python runtime + toolchain available on the host.
Documented backend expectations are:

- **Interpreter**: Pure Python (no external toolchain dependencies).
- **Native VM + native Python bytecode**: Pure Python, but still experimental.
- **LLVM pipeline**: Requires `llvmlite` plus a working LLVM/Clang toolchain
  when emitting executables.

For authoritative backend constraints and the experimental status of the native
VM + LLVM paths, see `docs/native_compiler.md`.

## Update checklist for future major releases

When a new major version is released:

1. Add a new section to this file with the release number.
2. Update the table to reflect which backends are considered **Supported** vs.
   **Experimental** for that release.
3. Update the tested-platforms list with any changes to required toolchains.
4. Link to the matching migration guide entry in
   `docs/release_migration_guides.md`.
