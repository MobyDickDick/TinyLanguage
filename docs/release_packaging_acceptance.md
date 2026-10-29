# Release packaging acceptance checkpoint — 2026-10-29

This is a working-tree implementation checkpoint for open work package 1. It is
not a signed release qualification record for a tagged candidate commit.

## Implemented

- `pyproject.toml` and `setup.py` build the `tinylanguage` wheel and installable
  sdist for Python 3.11+. The interpreter has no mandatory third-party runtime
  dependency; optional backend/formatting integrations remain optional.
- Installed commands: `tiny`, `tiny-project`, `tiny-pkg`, `tinyc`, `tiny-lsp`.
  `tiny --version` identifies the installed or frozen runtime release.
  Existing public modules, including `python -m tiny_language` and
  `python -m tinyc_cli`, remain available.
- Wheels contain the Python source segments, Tiny standard library, and
  `src_tiny` sources, including the parser bootstrap. Module lookup uses bundled
  assets without a checkout. Imports keep synthesized traceback source in memory
  and do not write `tiny_language_stitched.py` in the installation directory.
- The PEP 517 backend normalizes sdist ordering, ownership, modes, timestamps and
  gzip headers. Wheel timestamps use `SOURCE_DATE_EPOCH`.
- The release helper builds from an archived commit, validates versions, builds
  selected Python/native/editor artifacts twice, and fails on hash differences.
  It records artifact hashes, build dependency inventory, source identity and
  source epoch. SPDX and checksum metadata have deterministic timestamps and
  line endings. `--sign` creates and verifies detached GPG signatures.
- The frozen spec bundles the same runtime assets. VSIX builds use `npm ci` and
  normalize ZIP metadata. Extension and lockfile versions match `VERSION`.
- `.github/workflows/release-artifacts.yml` builds on Windows x86_64, Linux
  x86_64, macOS x86_64 and macOS arm64, checks rebuild hashes, installs wheels
  and wheels rebuilt from sdists in fresh environments, and executes frozen
  interpreters outside the checkout. A separate job builds the VSIX twice.
  These jobs retain artifacts and acceptance reports; they do not publish.

## Local evidence

The Windows wheel was built with Python 3.12.14, setuptools 84.1.0 and wheel
0.48.0. `tools/release/verify_python_package.py` created a fresh environment
outside the checkout, installed the wheel with `--no-index --no-deps`, executed
a program importing `stdlib.math`, and checked the public module command,
console entry points, bootstrap assets, and absence of generated source writes.
The retained machine-readable report is
[`artifacts/packaging/windows-wheel.json`](../artifacts/packaging/windows-wheel.json).
Its artifact hash identifies the tested wheel. The temporary installation path
identifies the test environment, which is removed after verification.

Additional retained evidence:

- [`windows-rebuild.json`](../artifacts/packaging/windows-rebuild.json): matching
  hashes for wheel, sdist and Windows executable built in distinct source/build
  directories with the same epoch and build tools.
- [`windows-sdist.json`](../artifacts/packaging/windows-sdist.json): a fresh
  installation of the wheel rebuilt from the sdist. The pip frontend rebuild
  was also checked; its wheel hash matched the direct wheel build. A sandboxed
  pip build hung and was interrupted; the unrestricted local-file rebuild
  succeeded. This environment limitation is separate from package correctness.
- [`windows-standalone.json`](../artifacts/packaging/windows-standalone.json): the
  frozen executable imports the bundled stdlib and runs from outside the checkout.
- [`vsix-rebuild.json`](../artifacts/packaging/vsix-rebuild.json): normalized VSIX
  hashes match across two builds (local Node 24.22.1, npm 10.9.2). The VSIX was
  installed in an isolated VS Code profile/extension directory; listing extensions
  confirmed `tinylanguage.tinylanguage-vscode@1.0.0`. The CLI reported a sandbox
  `chdir` warning but installation and version listing succeeded. This verifies
  installation, not editor activation or debugging.

The Python/sdist/executable artifacts use the same working-tree snapshot and
epoch within each comparison. They are not evidence for a tagged candidate or
an independent machine. CI's Node 22.14.0 builder is a separate qualification run.

Focused regression tests in `tests/test_release_packaging.py` cover source
archive/checksum reproducibility, VSIX ZIP normalization, dependency inventory,
the real wheel/sdist build hooks, CLI version reporting, and a minimal installed
layout without generated source. The selected 202 tests pass, covering the
interpreter, CLI, module import, native-codegen, language-server, debugger,
stdlib, specification, semantics and
wrapper checks pass. REPL tests keep history in temporary directories instead of
writing to the real user profile. Formatter/lint and whitespace checks pass.

## Outstanding qualification

Keep work package 1 unchecked until all of these have retained evidence:

1. Run the committed artifact workflow on every target and retain the successful
   reports for the candidate commit, including frozen binary and VSIX rebuilds.
2. Repeat the isolated editor installation for the actual candidate artifact.
   Installed-runtime discovery and full run/debug/format workflows belong to
   dependent work package 2.
3. Use immutable builder images/snapshots and retain their identifiers. Exact
   Python/build dependencies and `npm ci` are configured, but hosted runner labels
   are mutable. `BUILDER_IMAGE_DIGEST` records an operator-supplied image identity;
   absence is recorded as null, not as proof of pinned host inputs.
4. Sign the complete artifact set with the actual release key and independently
   verify signatures/checksums. No release key is created or substituted by these
   checks. Retain all platform provenance when assembling the final release.
5. Compare hashes across independent builders with the same pinned inputs.
   Two builds on one host detect local nondeterminism but do not prove independent
   cross-builder reproducibility. Signing timestamps and host-specific provenance
   are separate from reproducible unsigned payload hashes.
6. Audit the frozen bundle's embedded Python/Tcl and platform runtime inventory.
   The current SPDX inventory identifies payloads and installed Python/npm build
   distributions; it is not a complete file-level inventory of native libraries
   embedded by PyInstaller.

The complete application/editor/platform qualification in packages 2–3 remains
separate; the packaging workflow is not a claim that those packages are done.
