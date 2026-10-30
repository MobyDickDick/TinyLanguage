# Release artifact tooling

This directory contains the artifact builder, frozen-interpreter spec, pinned
build requirements and clean-install acceptance helper. Qualification status is
tracked in [release packaging acceptance](../../docs/release_packaging_acceptance.md).

## Quick start

```bash
python tools/release/build_release_artifacts.py --output-dir dist/release
```

This compatibility command builds the committed source archive and metadata.
All builds use `git archive` from the selected tag or HEAD: uncommitted changes
are excluded. To build installable Python artifacts and the host's standalone
interpreter twice and compare their hashes:

```bash
python -m pip install -r tools/release/requirements.txt
python tools/release/build_release_artifacts.py --python --binary --verify-reproducible --output-dir dist/release
```

`--vsix` additionally runs `npm ci` and the locked local VSCE, checks extension
versions against `VERSION`, and normalizes VSIX ZIP metadata. Install Node/npm
before using this option. The platform workflow selects Python 3.12.14 and
Node 22.14.0. Supply `BUILDER_IMAGE_DIGEST` when using an immutable builder;
the helper records null when no image identifier was supplied.

Build native binaries separately on each promised OS/architecture. Use repeated
`--include-artifact PATH` options when assembling the complete release. Include
each platform's provenance under a distinct filename as well. Supplied artifacts
are checksummed and signed but are not rebuilt by this invocation; retain and
review their original build/reproducibility records.

Validate a wheel in a fresh environment outside the checkout:

```bash
python tools/release/verify_python_package.py dist/release/tinylanguage-1.0.0-py3-none-any.whl --report dist/wheel-acceptance.json
python -m pip wheel --no-deps --no-build-isolation dist/release/tinylanguage-1.0.0.tar.gz --wheel-dir dist/from-sdist
python tools/release/verify_python_package.py dist/from-sdist/tinylanguage-1.0.0-py3-none-any.whl --report dist/sdist-acceptance.json
```

The second command runs in the pinned builder environment and proves the sdist
contains the inputs needed to rebuild a wheel. Installation uses a separate,
fresh venv with no dependencies or checkout paths. Set `TEMP`/`TMP` (Windows)
or `TMPDIR` (POSIX) to an accessible directory outside the checkout if needed.

Platform qualification additionally runs the complete regression suite with
`python -m pytest --require-backend-toolchains -ra` and the fresh-install
workflow helper with mandatory C/LLVM compilation and execution:

```bash
python tools/release/verify_installed_workflows.py dist/release/tinylanguage-1.0.0-py3-none-any.whl --require-compiler --report dist/platform-acceptance.json
```

Install Clang and the native linker/SDK first. Missing tools or compilation
failures are errors; optional JIT checks still report their skips separately.
The installed workflow check also covers local/stdlib imports with LF and CRLF,
Unicode/space/quoted argument paths, project/package tooling, LSP and DAP helpers.
See [platform qualification status](../../docs/platform_verification_acceptance.md).

## Signing

To sign artifacts, ensure `gpg` is installed and the release key is available
locally, then run:

```bash
GPG_KEY_ID="you@example.com" \
  python tools/release/build_release_artifacts.py --output-dir dist/release --sign
```

The script writes detached ASCII signatures (`.asc`) for each artifact and the
`SHA256SUMS` and `build-info.json` files and verifies them with GPG. Signing uses the actual release key;
unsigned CI artifacts do not establish signature acceptance.

## Outputs

The helper emits:

- `TinyLanguage-vX.Y.Z.tar.gz` (git archive source bundle)
- `TinyLanguage-vX.Y.Z-sbom.spdx.json`
- `SHA256SUMS`
- `build-info.json`
- Optional `.asc` signatures

Selected build options also produce the wheel, sdist, a host-platform executable
(`tiny-language-OS-ARCH[.exe]`) and/or `tiny-language-vscode.vsix`. Every selected
or included payload appears in SHA256SUMS and the SPDX inventory. Python and npm
build dependency versions are retained separately from mandatory interpreter
runtime dependencies (none). `build-info.json` records host-specific provenance;
payload hash comparisons exclude provenance and signatures.

## Release-candidate checklist

CI enforces the release-candidate checklist in
`docs/release_candidate_checklist.md` via:

```bash
python tools/release/check_release_candidate_checklist.py
```
