# Open tasks

This file tracks active work items for TinyLanguage. Completed language work is
archived in [open_tasks_archive.md](open_tasks_archive.md). The work packages
below were opened after the repository review on 2026-10-21. Packages 1-6 cover
delivery and operations; packages 7-11 cover language quality, architecture, and
evidence for the project's distinctive ideas. Priority labels govern scheduling;
the numbering groups related work rather than imposing a strict execution order.
Keep a package unchecked until its acceptance evidence is available; a design
document or prototype alone does not close the package.

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

## Language quality and design review follow-up (2026-10-21)

This review found working interpreter demos, native-VM recursion, and successful
LLVM text generation. Ten existing test functions were invoked directly and
passed, including the specification snapshot runner. The complete pytest suite
was not run because pytest was unavailable in the review environment. LLVM text
generation alone does not establish successful compilation or execution.
The observations below distinguish reproduced behavior from design questions;
they are not a claim that every feature or backend has been audited.

### 7. Predictable argument encapsulation

- [ ] **Define and validate the mutation contract for copy-on-call**
  (Owner: Language/Runtime; priority: P1)
  - Observed behavior: with `copy_on_call=True`, a function that executes
    `heap_set(buf, 0, 99)` without returning a value leaves the caller's
    `new[1]` buffer unchanged. Adding `return len(buf)` makes the caller's
    buffer contain `99`, even though the returned value is a scalar.
    `_collect_return_param_usage` treats parameter references anywhere in a
    return expression as escaping. This follows the current broad rule, but
    creates a surprising coupling between return expressions and mutation.
  - Scope: decide whether argument identity and mutation permission should be
    explicit or inferred. Distinguish returning an alias from computing a
    scalar from an argument, and specify how aliases, nested calls, methods,
    conditional returns, and unreachable returns affect the decision.
  - Acceptance: publish the chosen contract and executable examples. Add
    regression cases for the observed scalar-return behavior and actual alias
    returns, including mutation through another alias. Under the revised
    contract, merely computing a scalar return from a buffer must not silently
    grant permission to mutate caller-owned data. Document migration from the
    current rule and measure copying time and memory on shared/cyclic graphs.
  - References: [language_spec.md](language_spec.md#argument-kapselung),
    `src/tiny_language_parser.py`, `src/tiny_language_runtime.py`,
    `tests/detailtests/test_copy_on_call.py`.

### 8. Numerically sound interval operations

- [ ] **Specify interval meaning and restore the enclosure guarantee**
  (Owner: Numeric Semantics/Runtime; priority: P1)
  - Reproduced defect under ordinary set-based interval semantics:
    `NumberIntervall(-2, 3) / NumberIntervall(-5, 0.5)` produces `[6, -4]`.
    The existing `test_dividing_zero_spanning_intervals_yields_wrapped_interval`
    expects this result. For all nonzero denominator values, the set of
    possible quotients is the entire real line; an exterior interval excluding
    the gap between `-4` and `6` does not enclose it.
  - Reproduced rounding defect: adding the singleton intervals `[1, 1]` and
    `[2^-53, 2^-53]` returns bounds `[1, 1]`, excluding the exact sum
    `1 + 2^-53`. These operands are exactly representable in binary floating
    point, so input conversion does not explain the loss of enclosure.
  - Scope: define ordinary and wrapped intervals, empty and unbounded results,
    division across zero, and numeric error states. Implement outward rounding
    for the operations that promise enclosure, and audit neighboring-float
    calculations, overflow, subnormal values, and conversions from `Number`.
  - Acceptance: document the represented sets and rounding guarantees. Correct
    both reproduced cases and their tests using an independent mathematical
    oracle. Verify enclosure with exact rational operands and boundary cases
    for every supported arithmetic operation. If any operations intentionally
    provide approximations without enclosure, label them explicitly and exclude
    them from claims of guaranteed interval arithmetic.
  - References: `src_tiny/number_intervall.tiny`, `src_tiny/number_class.tiny`,
    `src/tiny_language_runtime.py`, `src/stdlib/__init__.py`,
    `tests/detailtests/test_number_intervall.py`,
    [stdlib_math_parity.md](stdlib_math_parity.md).

### 9. Independent correctness evidence

- [ ] **Audit test expectations and verify backend behavior by execution**
  (Owner: Testing/Language; priority: P1; supports package 5)
  - Motivation: the interval regression above demonstrates that a passing test
    can preserve an incorrect expected result. Agreement between backends that
    share implementation helpers is also insufficient as an independent oracle.
  - Scope: review numeric, aliasing, ownership, and error-handling expectations
    against explicit contracts. Add property tests and independent reference
    calculations where practical. Distinguish parser acceptance, code generation,
    compilation, execution, and observable semantic parity in backend reports.
  - Acceptance: retain an auditable basis for critical expected results, such
    as exact arithmetic or a documented semantic derivation. New checks must
    detect the interval defects in package 8. For each backend feature claimed
    as supported, retain compilation/execution evidence where applicable and
    compare outputs, errors, and relevant side effects against the contract.
    Report missing tools and skipped checks separately from successful checks.
  - References: `tests/test_spec_conformance.py`,
    `tests/detailtests/test_semantics_suite.py`, `tests/parity/`,
    [conformance_compatibility_test_strategy.md](conformance_compatibility_test_strategy.md),
    [backend_feature_matrix.md](backend_feature_matrix.md).

### 10. Maintainable runtime module boundaries

- [ ] **Replace import-time source stitching with explicit module dependencies**
  (Owner: Runtime/Architecture; priority: P2; coordinate with packages 1 and 2)
  - Observed architecture: importing `src/tiny_language.py` reads source
    segments, concatenates them, writes `tiny_language_stitched.py` beside the
    sources, and executes the result in a shared global namespace. This makes
    imports depend on writable source directories and hides module dependencies.
  - Scope: introduce explicit interfaces between AST, parser, analysis, runtime,
    evaluator, and backend modules. Preserve the public wrapper API while
    removing the runtime requirement to generate source files in the install
    directory. Coordinate asset handling with the packaging work.
  - Acceptance: existing API, semantic, CLI, and backend regression checks pass
    with ordinary module imports. Verify imports and execution from a read-only
    installed package and concurrent fresh processes without rewriting source
    files. Tracebacks identify the maintained implementation files, and the
    supported public imports remain compatible or have migration guidance.
  - References: `src/tiny_language.py`, `src/tiny_language_stitched.py`,
    `tiny_language.py`, `tests/test_tiny_wrapper_imports.py`.

### 11. Demonstrated value of a focused language experiment

- [ ] **Evaluate one distinctive idea against established alternatives**
  (Owner: Language Design/Documentation; priority: P2)
  - Review conclusion: the project contains implemented language experiments,
    but this review did not establish a fundamental novelty or a demonstrated
    practical advantage. This is an evidence gap, not proof that no novelty
    exists. Prioritize one experiment before expanding the feature surface.
  - Scope: select a concrete hypothesis, for example predictable argument
    encapsulation, and define its intended users and workload. Compare its
    semantics and tradeoffs with established approaches. Relevant starting
    points include [Swift value/reference semantics](https://www.swift.org/documentation/articles/value-and-reference-types.html),
    [Boost interval arithmetic](https://live.boost.org/doc/libs/1_68_0/libs/numeric/interval/doc/interval.htm),
    and [Trio task nurseries](https://trio.readthedocs.io/en/stable/tutorial.html).
    Separate an original combination or implementation from a claim of a new
    underlying concept.
  - Acceptance: publish one reproducible application or experiment with a
    working baseline in an established language. State the hypothesis and
    criteria in advance, compare correctness, clarity, runtime, and memory as
    relevant, and record limitations and counterexamples. Use the findings to
    justify continuing, revising, or retiring the idea; a negative result also
    completes this task. Update the README's positioning to match the evidence.
  - References: [math_syntax_exploration.md](math_syntax_exploration.md),
    [strict_by_default_safety_profile.md](strict_by_default_safety_profile.md),
    [runtime_performance_goals.md](runtime_performance_goals.md), `README.md`.

## First release milestone

A fresh machine can install TinyLanguage and run a separate example project,
including standard-library imports and editor support, on every supported
Windows, Linux, and macOS target. The installed interpreter is the stable
reference path; experimental backend completeness and self-hosting are separate
future milestones.
