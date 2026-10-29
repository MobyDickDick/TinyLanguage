# Installed CLI and editor quickstart

Use Python 3.11 or newer. Install the candidate wheel into a fresh virtual
environment with `python -m pip install /path/to/tinylanguage-1.0.0-py3-none-any.whl`
and activate that environment. No runtime dependencies or source checkout are
required for the commands below. Start in an empty directory outside the checkout.

<!-- installed-quickstart -->
```bash
tiny --version
tiny project init my_app --vscode
tiny my_app/src/main.tiny
tiny --source "print(1 + 2);"
tiny --backend native --source "print(1 + 2);"
tiny pkg init my_app
tiny pkg resolve --manifest my_app/tiny.toml
python -m tinyc_cli my_app/src/main.tiny --emit-c
tiny-lsp --file my_app/src/main.tiny diagnostics
tiny-lsp --file my_app/src/main.tiny format
```

`tiny project init` creates a runnable project; `tiny pkg init` adds the package
manifest. `tiny project`, `tiny pkg` and `tiny c` also have standalone aliases
`tiny-project`, `tiny-pkg` and `tinyc`. `tiny c` exposes the same compiler options
as `python -m tinyc_cli`. C emission needs no C compiler; compiling the generated
source into an executable requires a separately installed C toolchain. Native,
Python and C/LLVM backends support subsets of the interpreter language; see the
[backend matrix](backend_feature_matrix.md).

Run a file from any working directory by supplying its absolute path. Local
Tiny imports resolve relative to that file, and bundled `stdlib.*` modules
resolve from the installed distribution. Use `TINYPATH` for additional module
roots; see [module resolution](module_resolution_algorithm.md).

## VS Code

Install the candidate TinyLanguage VSIX and open `my_app`. The generated
`.vscode/settings.json` selects the Python interpreter that ran scaffolding.
The extension discovers the installed runtime through that interpreter. Run,
native run, REPL, formatting, diagnostics, completion, hover and debugging use
the same installation. Run commands pass executable/file paths as separate
arguments, including paths with spaces and Unicode characters.

Open `src/main.tiny`, run **TinyLanguage: Run Active File**, format the document,
and use **TinyLanguage: Refresh Diagnostics**. Set a breakpoint and select
**TinyLanguage: Launch main.tiny** in Run and Debug. Inspect the stack, continue
and check the Debug Console output.

For an existing project, set `tinylanguage.pythonPath` to the environment's
Python executable. Leave `tinylanguage.runtimePath` and `tinylanguage.cliPath`
empty for installed discovery. Set them explicitly for a development checkout;
`${workspaceFolder}` remains supported. Existing settings that point at
`${workspaceFolder}/src/tiny_language.py` must be cleared when that workspace
only contains application sources. `python` in a debug launch selects the
Python executable; `runtime` is an optional path to `tiny_language.py`.

## Reproduce acceptance

From a development checkout:

```bash
python tools/release/verify_installed_workflows.py dist/release/tinylanguage-1.0.0-py3-none-any.whl --report artifacts/packaging/installed-workflows.json
node --test tests/vscode_runtime.test.cjs
```

The verifier installs the wheel in a fresh temporary environment, copies only
the extension payload, runs the quickstart block verbatim, and checks a separate
multi-file project from an unrelated directory. It checks all execution backend
entry points on their arithmetic subset, C emission, LSP/editor helpers and a
debug breakpoint/stack/output/continue cycle. Add `--editor /path/to/Code` for
actual VS Code extension-host acceptance using an isolated profile. Linux GUI
runners need a display (for example `xvfb-run`). Temporary profiles are removed
after the run. No extension is installed into the user's normal profile.

The local evidence and its limitations are recorded in
[installed workflow acceptance](installed_workflows_acceptance.md). Release
artifact qualification and supported-platform checks remain separate gates.
