# Platform verification checkpoint — 2026-10-30

This records implementation and local acceptance for open work package 3. It is
not cross-platform release sign-off. The sixteen CI qualification runs have
been configured but have not been executed from this working-tree session.

## Implemented qualification

`.github/workflows/ci.yml` tests CPython 3.11–3.14 on Linux x86_64, Windows
x86_64, macOS Intel and macOS arm64. Each job checks the actual CPU architecture,
installs Clang and a native linker/SDK, and runs the entire pytest suite with
`--require-backend-toolchains`. Missing Clang aborts qualification; skips in
required C/LLVM checks become failures. LLVM compilation/linking failures also
fail ordinary smoke runs rather than being treated as unavailable tools.

Each job builds a wheel from the current source and installs it in a separate
fresh environment outside the checkout. The installed workflow helper checks:

- documented quickstart commands, project creation and package resolution;
- multi-file and bundled standard-library imports from an unrelated directory;
- Unicode and space-containing paths, literal apostrophes, ampersands and
  parentheses in program arguments, and both LF and CRLF source files;
- interpreter, Python, native VM and native Python bytecode arithmetic execution;
- installed C and direct LLVM compilation **and execution**, with mandatory
  `--require-compiler`;
- LSP formatting/diagnostics and copied extension helpers plus DAP
  breakpoint/stack/continue/termination behavior.

JUnit results and installed-workflow JSON are uploaded per OS/Python job even
when a check fails. Optional JIT checks may still skip, and source-port execution
is Linux-only under the documented
[platform contract](release_compatibility_matrix.md#source-program-service-platform-contract).
Full VS Code extension-host qualification remains separate from helper/DAP
checks; package 2 retains its Windows acceptance record. The four-target
standalone artifact workflow remains part of package 1 release qualification.

## Portability defects corrected

- The source-port sandbox imports on all hosts and explicitly refuses execution
  on unsupported systems before creating output or starting a child. Its
  portable rejection/integrity tests still execute on Windows/macOS.
- Quarantine/scan/port temporary files use `mkstemp`'s POSIX owner-only mode
  without unavailable Windows `fchmod` calls that also leaked open descriptors.
  POSIX permission assertions remain active on POSIX; Windows ACL limitations
  and symlink-privilege skips are explicit.
- The quoted-path TOML test serializes resolved POSIX metadata without creating
  a Windows-invalid filename. Real dependency resolution remains covered by
  other filesystem fixtures. Lockfile output uses LF on every host.
- C compiler invocations omit `-lm` on Windows, whose native C runtime supplies
  math functions. Backend tests use explicit `.exe` output names on Windows.
- Compiler CLI output writes logical newlines instead of double-translating
  `os.linesep` on Windows; the Python/Tiny compiler snapshots pass unchanged.
- POSIX path-contract tests use Python's independent `posixpath` oracle rather
  than host-dependent `os.path`. The YAML file fixture uses an escaped-safe
  forward-slash path. Output normalization accepts native and POSIX root paths.
- Installed acceptance subprocesses receive valid standard-input handles and
  use explicit UTF-8 decoding.

## Retained Windows evidence

The complete suite passes with native Windows CPython **3.12.14**:
**819 passed, 14 skipped** (833 collected). Test dependencies are the pure
Python pytest 8.4.2 installation from the repository development environment;
the interpreter and packaging tools are the bundled CPython runtime. Tests use
a writable temporary directory and a valid standard-input handle. The compact
[test record](../artifacts/platform/windows-python312.json) identifies the base
commit, modified implementation hashes, tool versions, counts and skip reasons.

The fourteen skips are ten compiler-dependent checks (no local C/LLVM compiler),
one optional llvmlite JIT check, two Linux-only sandbox execution checks, and one
Windows symlink-privilege check. They are **not** successful backend/security
qualification. The strict compiler gate was exercised separately and correctly
aborts with exit 4 when Clang is absent.

The final working-tree wheel is separately identified by SHA-256 in the
[installed workflow report](../artifacts/packaging/windows-platform-workflows.json).
It passes all ten quickstart commands plus external multi-file, LF/CRLF,
argument-path, package, backend dispatch, LSP and DAP checks. Local installed
acceptance omits `--require-compiler`, so this report establishes C emission
only, not compiled C/LLVM execution. No actual editor host was launched in this
platform run.

Formatter/lint, workflow YAML parsing and `git diff --check` pass. All eight
Node extension-runtime tests pass. An initial native Windows full-suite run
found seventeen failures; the corrected cases pass in the final complete run.
The earlier MinGW Python 3.14 run established collection only and is not
CPython 3.14 qualification evidence.

## Outstanding acceptance

Keep work package 3 unchecked until the committed candidate has successful
retained reports for all sixteen jobs, including required compiled backend
execution, and package 1 release-artifact qualification is complete. Link the
candidate commit and CI run/artifact identifiers here when available. Runner
configuration alone does not prove a successful Linux/macOS run or any of the
other Python versions. Optional/missing-tool skips must remain separate from
passing checks. This local checkpoint neither publishes artifacts nor changes
the release qualification status.
