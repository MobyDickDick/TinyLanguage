# Installed workflow acceptance — 2026-10-29

Work package 2 has local acceptance evidence for its installed CLI/editor
contract. This record covers a working-tree wheel and isolated extension payload,
not a signed release candidate. Packages 1 and 3 retain release qualification
and supported-platform coverage.

## Implementation

- `tiny project` and `tiny c` dispatch to the installed project/C-backend tools;
  existing standalone commands and `python -m tinyc_cli` remain available.
- Project scaffolding selects its Python executable and leaves the editor
  runtime override empty, so projects do not embed a checkout/runtime directory.
- The extension discovers `tiny_language` and its CLI through the configured
  Python, with bounded discovery probes. Explicit development paths remain
  supported. Helpers and the debug adapter use that runtime's module directory;
  application `src/` directories are not injected into Python's search path.
- Run/native/REPL terminals receive executable and argument arrays. Saving a
  modified file finishes before execution, and a failed save cancels the run.
- Imports inherit the caller's output mode and preserve earlier buffered
  output. Debugger output from a multi-file program stays in DAP output events.
- The extension waits for the adapter's TCP listening signal before handing
  VS Code the connection descriptor. Startup errors/timeouts reject the launch
  and stop the child process.
- The installed quickstart and scaffolding docs distinguish implemented project
  creation from future package-template proposals. Artifact CI runs the installed
  workflow verifier on its target matrix and the editor job runs Node regressions.

## Retained local evidence

[`windows-installed-workflows.json`](../artifacts/packaging/windows-installed-workflows.json)
identifies the tested wheel by SHA-256. Python 3.12.14 installs that wheel into
a fresh temporary environment without external runtime dependencies. Checks run
outside the repository with `PYTHONPATH`, `PYTHONHOME` and `TINYPATH` removed:

- Every command in the marked installed quickstart block executes verbatim,
  substituting only absolute executable paths for the fresh environment. The
  report retains each command and its output hash.
- A project under `Pröjekt with spaces` runs from an unrelated directory,
  imports a neighboring module and bundled `stdlib.math`, and passes typecheck.
- Package initialization/resolution writes a lockfile. Interpreter, Python,
  native VM and native Python bytecode entry points execute the arithmetic
  subset. Both the C module entry point and `tiny c` emit matching C source.
- Installed LSP and copied extension helpers format source and report malformed
  source diagnostics. The copied payload has no adjacent repository `src/`.
- A separate Python process runs the actual debug adapter handlers against the
  wheel: breakpoint at line 3, stack inspection, continue, output and termination.
- Actual VS Code 1.141.2 runs the copied extension payload in an isolated test
  profile. Activation, formatting, diagnostics, run/native command registration
  and invocation, and a complete TCP DAP breakpoint/stack/output/continue cycle
  pass. Run checks verify terminal executable/argument arrays and execute those
  exact arrays independently to assert output. They do not scrape terminal text.

Temporary environments and editor profiles are removed after verification. Their
paths in the report are evidence identifiers, not persistent installations.

## Regression checks and limits

Selected Python regression checks cover CLI, public wrappers, project creation,
module imports, nested import output, LSP, stdlib, executable specification,
semantics, debugger, REPL, self-host CLI and package builds: 104 cases pass.
Four C/LLVM toolchain tests skip because no C compiler/clang is installed; C emission is
checked independently by the installed verifier. Eight Node tests pass, covering installed discovery,
overrides, per-launch Python selection, Unicode/space argument boundaries,
cancelled saves, readiness framing and adapter startup failure. Formatter/lint
and whitespace checks pass.

The first sandboxed test run could not create pytest temporary directories;
using an explicit workspace basetemp resolved that. The fresh-install verifier
needed unsandboxed temporary-directory access. One package-build regression
initially lacked setuptools in the existing Python 3.14 test environment and was
rerun with the bundled Python/build tools. These environment failures are not
counted as successful checks.

This is Windows evidence. It does not establish cross-platform installation,
full backend language coverage, C compilation/linking, registry-backed package
publication, VSIX signature/install qualification, or candidate reproducibility.
The real editor test loads a copied extension payload in development-host mode;
isolated VSIX installation belongs to package 1. Repeat against a tagged
candidate and retain supported-platform results before release sign-off.
