# Release artifacts & reproducible build pipeline

This document defines the **official release artifacts** for TinyLanguage and
the **reproducible build pipeline** required to publish them. It is intended as
the single source of truth for release packaging, verification, and promotion.

## Goals

- Ship **versioned, verifiable artifacts** for each release.
- Ensure builds are **reproducible** across CI and local release engineering.
- Provide **traceability** from artifacts back to a tagged commit.

## Official release artifacts

Each tagged release (`vX.Y.Z`) must publish the following artifacts:

1. **Source archive**
   - `TinyLanguage-vX.Y.Z.tar.gz` generated from the git tag.
   - Must include `VERSION`, `CHANGELOG.md`, and all docs.
2. **Standalone binaries (interpreter)**
   - `tiny-language-linux-x86_64`
   - `tiny-language-macos-x86_64`
   - `tiny-language-macos-arm64`
   - `tiny-language-windows-x86_64.exe`
   - Built from the same tag and bundled with the stdlib runtime assets.
3. **Python package**
   - `tinylanguage` sdist (`.tar.gz`) + wheel (`.whl`).
4. **VS Code extension bundle**
   - `tiny-language-vscode.vsix` built from `vscode-extension/`.
5. **Checksums**
   - `SHA256SUMS` covering every artifact above.
6. **SBOMs**
   - `TinyLanguage-vX.Y.Z-sbom.spdx.json` describing every artifact in the
     release bundle.
7. **Signatures**
   - Detached ASCII signatures (`.asc`) for each artifact and `SHA256SUMS`.
8. **Provenance + metadata**
   - `build-info.json` recording:
     - Git tag/commit, build timestamp (UTC), builder image digest,
       tool versions, and artifact hashes.

> Note: If a release explicitly skips any artifact (e.g., unsupported platform),
> the release notes must call it out in **Known limitations**.

## Reproducible build pipeline

The release pipeline is designed to make the build deterministic and auditable.

### 1) Inputs and version sources

- **Git tag** is the release source of truth (`vX.Y.Z`).
- `VERSION` **must match** the tag.
- `CHANGELOG.md` **must include** the release entry.

### 2) Build environment

- Build inside a **pinned container image** (by digest) that contains:
  - Python (exact version)
  - LLVM/clang (if native artifacts are built)
  - Node.js (for VS Code extension)
  - `pip`, `build`, and packaging tools (pinned versions)
- Record the container digest in `build-info.json`.

### 3) Build steps (deterministic)

1. **Checkout tag**: `git checkout vX.Y.Z`.
2. **Validate version**: ensure `VERSION` matches the tag.
3. **Build source archive**:
   - `git archive --format=tar.gz -o TinyLanguage-vX.Y.Z.tar.gz vX.Y.Z`
4. **Build Python package**:
   - `python -m build` from repo root (sdist + wheel).
5. **Build standalone binaries**:
   - Use a consistent packager (e.g., PyInstaller) with a pinned spec file.
   - Embed the stdlib runtime assets into the bundle.
6. **Build VS Code extension**:
   - `npm ci` in `vscode-extension/`
   - `vsce package -o tiny-language-vscode.vsix`
7. **Generate checksums**:
   - `sha256sum * > SHA256SUMS`
8. **Generate SBOM**:
   - Produce `TinyLanguage-vX.Y.Z-sbom.spdx.json` for the artifact bundle.
9. **Sign artifacts**:
   - Use `gpg --armor --detach-sign` on each artifact and `SHA256SUMS`.
10. **Emit provenance**:
   - Create `build-info.json` with full metadata.
11. **Automation helper (recommended)**:
   - `python tools/release/build_release_artifacts.py --output-dir dist/release`
     generates the source archive, SBOM, checksums, signatures, and
     `build-info.json` deterministically.

### 4) Reproducibility checks

For each artifact:

- Re-run the build on a clean machine using the same container digest.
- Ensure the **SHA-256 hash** matches the original output.
- If hashes differ, the release is **blocked** until the source of
  nondeterminism is eliminated (timestamps, embed paths, build IDs, etc.).

### 5) Publication checklist

1. Tag pushed, and `VERSION` matches.
2. All artifacts generated successfully.
3. `SHA256SUMS`, SBOM, signatures, and `build-info.json` are present.
4. Reproducibility check completed (hashes match).
5. Release notes link to:
   - `docs/release_migration_guides.md`
   - `docs/release_compatibility_matrix.md`
6. Publish artifacts in the GitHub release page.

## Definition of done (for this task)

- This document defines the official artifacts and deterministic build pipeline.
- The full-language readiness checklist references this document as the
  canonical source.
