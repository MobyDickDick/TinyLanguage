# Release artifact tooling

This directory contains the release artifact helper used by the documented
release pipeline.

## Quick start

```bash
python tools/release/build_release_artifacts.py --output-dir dist/release
```

## Signing

To sign artifacts, ensure `gpg` is installed and the release key is available
locally, then run:

```bash
GPG_KEY_ID="you@example.com" \
  python tools/release/build_release_artifacts.py --output-dir dist/release --sign
```

The script writes detached ASCII signatures (`.asc`) for each artifact and the
`SHA256SUMS` file.

## Outputs

The helper emits:

- `TinyLanguage-vX.Y.Z.tar.gz` (git archive source bundle)
- `TinyLanguage-vX.Y.Z-sbom.spdx.json`
- `SHA256SUMS`
- `build-info.json`
- Optional `.asc` signatures

Integrate additional artifacts (binaries, wheels, VSIX) in the pipeline and add
those files to the `SHA256SUMS` and SBOM entries before publishing.
