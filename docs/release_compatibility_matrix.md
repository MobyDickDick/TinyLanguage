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

### Platform qualification targets (1.0.0)

The qualification matrix in `.github/workflows/ci.yml` covers CPython 3.11,
3.12, 3.13, and 3.14 on these targets:

| Operating system | Architecture | CI runner |
| --- | --- | --- |
| Linux | x86_64 | `ubuntu-24.04` |
| Windows | x86_64 | `windows-2022` |
| macOS | x86_64 (Intel) | `macos-15-intel` |
| macOS | arm64 (Apple Silicon) | `macos-15` |

These are qualification targets, not a claim of successful platform runs. The
current evidence and remaining gates are recorded in
[platform verification acceptance](platform_verification_acceptance.md).
Other Python implementations, newer Python versions, Linux/Windows ARM, and
32-bit hosts are unqualified. Package metadata permits Python 3.11+; that
installation constraint does not establish qualification of future versions.
Standalone release artifacts use Python 3.12.14 on the same four OS/architecture
targets in `.github/workflows/release-artifacts.yml`.

Backend expectations are:

- **Interpreter**: Pure Python (no external toolchain dependencies).
- **Native VM + native Python bytecode**: Pure Python, but still experimental.
- **LLVM pipeline**: Requires a working LLVM/Clang toolchain when emitting
  executables; `llvmlite` is optional for JIT/optimization workflows.

The direct LLVM text emitter and Clang executable path do not require
`llvmlite`; that optional dependency is needed for JIT/optimization workflows.
Platform CI installs Clang and a native linker/SDK and requires C and direct
LLVM compilation/execution. JIT coverage remains optional and its skips are
reported separately. Backend qualification covers the existing experimental
subset, not full interpreter parity.

### Source-program service platform contract

Importing the source-program tools and performing static import/scan/port work
is portable. Executing a port via `tiny_program_source_sandbox` requires Linux
and the complete POSIX resource-limit API. Windows and macOS raise
`SandboxUnavailableError` (CLI exit 2) before launching a child or writing a
passing assessment. There is no timeout-only fallback that could promote a
program without the resource policy. Linux resource limits constrain CPU,
address space, files and processes; they do not isolate filesystem or network
access and are not a security boundary for arbitrary hostile code.

POSIX artifact permission checks remain enforced on Linux/macOS. Windows
`chmod` does not provide equivalent owner-only ACL guarantees: source-service
storage inherits the directory ACL, so use a private, access-controlled
directory. POSIX mode assertions are inapplicable there. Symlink rejection is
tested where links can be created; Windows tests report an explicit skip when
Developer Mode/symlink privileges are absent.

For authoritative backend constraints and the experimental status of the native
VM + LLVM paths, see `docs/native_compiler.md`.

### Upgrade guide

For users migrating from pre-1.0 development snapshots, follow the guidance in
`docs/release_migration_guides.md#100`.

## Update checklist for future major releases

When a new major version is released:

1. Add a new section to this file with the release number.
2. Update the table to reflect which backends are considered **Supported** vs.
   **Experimental** for that release.
3. Update the tested-platforms list with any changes to required toolchains.
4. Link to the matching migration guide entry in
   `docs/release_migration_guides.md`.
