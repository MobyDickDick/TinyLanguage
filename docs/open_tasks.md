# Open tasks

This file tracks active work items for TinyLanguage. Completed language work is
archived in [open_tasks_archive.md](open_tasks_archive.md). The work packages
below were opened after the repository review on 2026-10-21 and are ordered by
implementation priority. Keep a package unchecked until its acceptance evidence
is available; a design document or prototype alone does not close the package.

## Current tasks

### 1. Installation and release artifacts

- [ ] **Ship installable and reproducible TinyLanguage releases**
  (Owner: Release/Packaging; priority: P1)
  - Scope: add Python package metadata and installed command entry points;
    package the runtime source segments, standard library, and required assets.
    Extend the release pipeline to build wheels, source distributions,
    standalone executables, and the VS Code extension for the supported targets.
  - Acceptance: install each artifact in a clean environment without the source
    checkout and execute a program that imports the bundled standard library.
    Verify release versions, checksums, signatures, dependency inventory, and
    provenance. Rebuild with pinned inputs and compare the reproducible artifact
    hashes; resolve timestamp and path nondeterminism before sign-off.
  - References: [release_artifacts_pipeline.md](release_artifacts_pipeline.md),
    [building_executables.md](building_executables.md),
    `tools/release/build_release_artifacts.py`.

### 2. Installed CLI and editor workflow

- [ ] **Make the CLI and editor work independently of the source checkout**
  (Owner: Tooling/Developer Experience; priority: P1; depends on package 1)
  - Scope: expose a consistent installed `tiny` command for the supported run,
    project, package, and backend workflows. Resolve runtime and standard-library
    locations independently of the working directory. Let the VS Code extension
    find the installed runtime without requiring `${workspaceFolder}/src/`.
  - Acceptance: create a project outside this repository, run and debug it from
    another working directory, and exercise formatting, diagnostics, and module
    imports. Execute every quickstart command verbatim in the documented clean
    environment, including the C-backend entry point currently shown as
    `python -m tinyc_cli`.
  - References: [cli_workflows.md](cli_workflows.md),
    [project_scaffolding.md](project_scaffolding.md), `vscode-extension/`.

### 3. Supported-platform verification

- [ ] **Verify installation and development workflows across supported platforms**
  (Owner: Testing/CI; priority: P1; depends on packages 1 and 2)
  - Scope: declare supported Python versions and add Windows, Linux, and macOS
    CI coverage for installation, interpreter execution, package tooling, LSP,
    and the supported backend subsets. Include the promised CPU architectures
    in the artifact test matrix and install required backend toolchains.
  - Acceptance: fresh-environment installation and a separate multi-file sample
    project pass on every promised target. Required checks cannot silently skip
    because a toolchain is missing. Include path, Unicode, argument-escaping,
    file-system, and line-ending cases.
  - Known regression: `test_write_lockfile_escapes_path_as_valid_toml` creates
    `deps/quoted"library`, which is not a valid Windows file name. Preserve TOML
    escaping coverage with a portable fixture or an explicitly POSIX-only case.
  - Additional platform gap: the full suite cannot collect on Windows because
    `src/tiny_program_source_sandbox.py` imports the POSIX-only `resource`
    module unconditionally. Define the supported sandbox behavior per platform
    and make its implementation and test collection follow that contract.
  - References: `.github/workflows/ci.yml`,
    [release_compatibility_matrix.md](release_compatibility_matrix.md),
    `tests/detailtests/test_pkg_lockfile_reproducibility.py`.

### 4. Complete package workflow

- [ ] **Complete registry-backed package installation and publication**
  (Owner: Ecosystem/Package Tooling; priority: P2)
  - Scope: connect registry metadata lookup, dependency resolution, locked
    downloads, vendoring, and authenticated publication into the package CLI.
    The current publish helper supports dry-run staging only; retain that
    reviewable mode while implementing the actual registry transaction.
  - Acceptance: use a controlled test registry to publish, resolve, install,
    cache, and reproduce a multi-package project in a clean environment. Cover
    transitive dependencies, incompatible constraints, immutable published
    versions, offline use, authentication failures, interrupted downloads, and
    checksum mismatches without exposing credentials in diagnostics.
  - References: [package_manager_plan.md](package_manager_plan.md),
    `src/tiny_pkg_cli.py`, `src/tiny_pkg_resolution.py`,
    `tools/tiny_pkg_publish.py`.

### 5. Stable scope and evidence-based release status

- [ ] **Reconcile release promises and verify the stable interpreter scope**
  (Owner: Language/Release/Documentation; priority: P1)
  - Scope: define the stable interpreter, CLI, and standard-library contract;
    freeze its supported language semantics and explicitly label experimental
    native/LLVM features. Reconcile `VERSION`, `CHANGELOG.md`, backend matrices,
    readiness checklists, and release documentation with demonstrated behavior.
  - Acceptance: every release claim links to a passing check or retained manual
    acceptance record for the candidate commit. Extend executable specification
    and backend-parity coverage to the promised feature subsets and error cases.
    The release checklist gate must verify evidence rather than merely checked
    Markdown boxes. Mark delivery work complete only after packages 1-3 pass.
  - References: [full_language_readiness.md](full_language_readiness.md),
    [release_v1_dod.md](release_v1_dod.md),
    [backend_feature_matrix.md](backend_feature_matrix.md),
    `tools/release/check_release_candidate_checklist.py`.

### 6. Package hardening and real-project acceptance

- [ ] **Harden external package handling and qualify complete applications**
  (Owner: Runtime/Package Tooling/Testing; priority: P1)
  - Scope: require integrity verification for remote packages, bound network
    operations with explicit timeouts and resource limits, and validate archive
    extraction using path-component containment and safe link handling. Exercise
    the documented filesystem, network, process, and Python-interop boundaries.
  - Acceptance: missing or incorrect checksums, malformed archives, traversal
    attempts, escaping links, and stalled downloads fail predictably without
    leaving partially accepted packages. Run complete application acceptance
    cases covering installation, dependencies, file/JSON processing, CLI errors,
    concurrency/resource cleanup, and upgrades between release versions.
  - References: `src/tiny_pkg_cli.py`,
    [python_interop.md](python_interop.md),
    [strict_by_default_safety_profile.md](strict_by_default_safety_profile.md).

## First release milestone

A fresh machine can install TinyLanguage and run a separate example project,
including standard-library imports and editor support, on every supported
Windows, Linux, and macOS target. The installed interpreter is the stable
reference path; experimental backend completeness and self-hosting are separate
future milestones.
