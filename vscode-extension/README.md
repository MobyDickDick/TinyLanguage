# TinyLanguage VS Code extension

This extension adds TinyLanguage editing support to Visual Studio Code:

- Syntax highlighting powered by a TextMate grammar.
- Formatting via the built-in TinyLanguage formatter.
- Hover and completion suggestions sourced from the TinyLanguage language server helpers.
- REPL and run commands backed by `tiny_language.py`.
- On-the-fly diagnostics based on the TinyLanguage linters.

## Getting started

1. **Install the runtime**: Install the candidate `tinylanguage` wheel in a Python 3.11+ environment.
2. **Create an application**: Run `tiny project init my_app --vscode` in any directory and open `my_app` in VS Code.
3. **Install the packaged extension**: `code --install-extension tinylanguage-vscode-1.0.0.vsix`. For development builds, run `npm ci` and `npx vsce package` in `vscode-extension`.
4. **Select Python**: Scaffolding selects its own Python executable. For existing projects, set `tinylanguage.pythonPath` to the Python environment containing TinyLanguage.
5. **Discover the runtime**: Leave `tinylanguage.runtimePath` and `tinylanguage.cliPath` empty to find installed modules. Explicit paths, including `${workspaceFolder}` substitutions, remain available for development. Reload VS Code after replacing an active extension.
6. **Enable the TinyLanguage icons**: The extension now defaults the file icon theme to **TinyLanguage File Icons** on install. If you switch themes later, you can re-enable it via **File → Preferences → File Icon Theme**.

## Commands

- **TinyLanguage: Start REPL** (`tinylanguage.startRepl`): Opens an integrated terminal using the selected Python and discovered runtime with `--repl`.
- **TinyLanguage: Run Active File** (`tinylanguage.runFile`): Saves and executes the current `.tiny` document with the discovered runtime.
- **TinyLanguage: Run Active File (Native Backend)** (`tinylanguage.runFileNative`): Saves and executes the current `.tiny` document with the discovered CLI's `--backend native` option.
- **TinyLanguage: Format Document** (`tinylanguage.formatDocument`): Uses the TinyLanguage formatter to rewrite the buffer.
- **TinyLanguage: Refresh Diagnostics** (`tinylanguage.refreshDiagnostics`): Manually recomputes diagnostics for the active file.

Diagnostics and formatting use the helper script in `python/vscode_helpers.py` and the same installed runtime as execution/debugging. The application workspace needs no Python runtime sources. See the [installed CLI/editor quickstart](../docs/installed_workflows.md).

## License

The TinyLanguage VS Code extension is distributed under the [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](LICENSE.md). Commercial redistribution of the extension or derivative works is not permitted under this license.

### Debugging with the provided launch config

1. Open **Run and Debug** in VS Code.
2. Click **create a launch.json file** (or the gear icon) and choose **TinyLanguage: Launch active file (prototype)** from the dropdown. This writes a `launch.json` that uses the `tinylanguage` debugger with `${file}` as the target.
3. Start debugging via **Run and Debug → TinyLanguage: Launch active file (prototype)**. If the configuration list is empty, ensure the extension shows as enabled in **Extensions** and reload the window so VS Code picks up the `tinylanguage` debugger contribution.
4. If VS Code reports `Couldn't find a debug adapter descriptor` for `tinylanguage`, update to version `0.1.2` (or newer) and reload the window so the debugger activation events are registered.

If you need to verify that the debug adapter wiring works at all, the **TinyLanguage: Launch active Python file (debug adapter test)** configuration runs the same adapter in a Python stepping mode. Point it at a `.py` file, set breakpoints, and the adapter will pause using Python's debugger hooks instead of the TinyLanguage runtime.

> TinyLanguage sessions use a custom adapter (`vscode-extension/python/tiny_debug_adapter.py`) to drive the interpreter. When you point a `tinylanguage` launch configuration at a **Python** file, the extension now delegates to the official VS Code Python extension (debugpy) by default so you get the full Python debugging experience. Disable this behavior with `"tinylanguage.preferPythonExtensionDebugger": false` or a per-launch `"usePythonExtension": false` override if you want to exercise the built-in adapter instead.

#### Launch configuration reference

The default launch entry should look like this (comments are allowed because VS Code treats `launch.json` as JSON with comments):

```jsonc
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "TinyLanguage: Launch active file (prototype)",
      "type": "tinylanguage",
      "request": "launch",
      "program": "${file}", // the active .tiny file
      "python": "${config:tinylanguage.pythonPath}" // Python with TinyLanguage installed
    }
  ]
}
```

`python` selects the Python executable. The optional `runtime` field selects a `tiny_language.py` source file; omit it for installed discovery. When a launch fails, inspect **Output → TinyLanguage** for adapter startup details.

If you need a detailed trace of every Debug Adapter Protocol (DAP) message exchanged with VS Code, use **TinyLanguage › Debug Log Path**. By default the extension writes adapter traces to `${workspaceFolder}/.tinylanguage/debug-adapter.log` and mirrors the same content to **Output → TinyLanguage** so you can see the log even if file writes fail. You can point the setting elsewhere or clear it to disable file logging. The extension now creates the parent directory for the log automatically and emits a warning to the TinyLanguage output channel if the directory cannot be created (for example due to permissions). The adapter records inbound and outbound DAP payloads, breakpoint updates, and stepping commands to the configured file/output.

For stepping problems inside the interpreter itself, the extension now also seeds **TinyLanguage › Trace Log Path** (default `${workspaceFolder}/.tinylanguage/runtime-trace.log`) and forwards it as `TINYLANG_TRACE_LOG` to the runtime. Each statement the interpreter evaluates is logged with the namespace, position, call stack, and visible identifiers so you can see whether breakpoints and steps are being hit.

To override the log destination or mirror it to the TinyLanguage output pane for easier inspection, add an `env` block to your `launch.json` entry and set `TINYLANGUAGE_DAP_LOG` or `TINYLANGUAGE_DAP_STDERR`:

```jsonc
{
  "name": "TinyLanguage: Launch active file (prototype)",
  "type": "tinylanguage",
  "request": "launch",
  "program": "${file}",
  "env": {
    "TINYLANGUAGE_DAP_LOG": "${workspaceFolder}/.tinylanguage/debug-adapter.log", // optional custom path
    "TINYLANGUAGE_DAP_STDERR": true // also stream the log to Output → TinyLanguage
  }
}
```

Enable `tinylanguage.showDebugTerminal` to open a **TinyLanguage Debug Log** terminal showing the target program, Python executable, runtime, and working directory.

VS Code now accepts the `env` block on TinyLanguage launch configurations, so you will no longer see `Property env is not allowed` when adding these environment variables.

#### Interpreting the adapter self-test log

Every TinyLanguage debug session performs a quick self-test before launching. The JSON payload printed to **Output → TinyLanguage** (and stored in your adapter log) confirms which Python executable is used and where the adapter loaded `tiny_language.py` from. Typical fields include:

- `src_root` / `src_root_exists`: The adapter's best guess at a development source tree. An installed distribution normally has `src_root_exists=false`; runtime discovery uses the selected Python environment instead.
- `tiny_language_module`: Implementation path for the loaded runtime, normally under the selected environment's `site-packages`. The synthesized `tiny_language_stitched.py` traceback path does not require a generated file. Explicit development overrides may point at a checkout.
- `sys_path_sample`: The first few entries of `sys.path`, which helps verify whether your workspace or virtual environment is being searched.

If the self-test fails or shows the wrong runtime, ensure TinyLanguage is installed in the configured Python environment and restart the debug session.

#### Troubleshooting a stuck debug session

If the TinyLanguage debug session seems to “hang” (no breakpoints hit, VS Code status bar shows “running” forever), try the following steps to pinpoint the failure:

- Open **Output → TinyLanguage** and inspect the self-test JSON printed when the adapter starts. Confirm `tiny_language_module` belongs to the intended installed environment or explicit development checkout. Set **TinyLanguage › Python Path** to the correct Python executable; leave **TinyLanguage › Runtime Path** empty for installed discovery, then restart VS Code.
- Enable a verbose adapter trace via **TinyLanguage › Debug Log Path** (or set `"TINYLANGUAGE_DAP_LOG": "${workspaceFolder}/.tinylanguage/debug-adapter.log"` in `launch.json`) and reproduce the issue. The resulting log shows every Debug Adapter Protocol request/response so you can see whether VS Code ever sent `configurationDone`, set any breakpoints, or issued a `continue` after the initial `stopped` event.
- Verify the target file actually exists on disk after variable substitution. The adapter will refuse to launch if `program` cannot be resolved; the **Output → TinyLanguage** pane echoes the final absolute path so you can cross-check it.
- On Windows, prefer launching the adapter with the same Python interpreter you use for running tests (for example from a virtual environment). You can override the executable in `launch.json` by adding `"python": "C:/path/to/venv/Scripts/python.exe"` so the adapter does not rely on the `python3` shim.
- If you want to compare behavior with a known-good reference, the official VS Code [Mock Debug](https://github.com/microsoft/vscode-mock-debug) sample extension mirrors the same Debug Adapter Protocol lifecycle (initialize → setBreakpoints → launch → configurationDone → continue). You can run it in an Extension Development Host to see the expected requests and responses.

These checks usually reveal why the runtime never starts or why execution pauses indefinitely while waiting for client commands.

## Roadmap / TODO

This section gathers upcoming tasks for TinyLanguage.
Roughly grouped into frontend/language, type discipline, runtime, and tooling.
The “nativeCompiler” work is tracked separately.

### 1. Frontend / language

- [x] **Improve error positions and messages**
  - Tokens and AST nodes should consistently carry line and column information.
  - Unified error type with an optional `SourceSpan` that highlights the affected line when displayed.
  - Parser and linter should use this error type.

- [x] **Refine the linter**
  - “must use” rule across control flow: a variable counts as used only when referenced on all relevant paths.
  - Unreachable-code warnings (e.g., statements after `return`).

### 2. Type discipline

- [x] **No implicit type changes**
  - After `def i = 5;`, assigning `i = 0.5;` should be an error (or explicitly allowed via another mechanism).
  - Apply type rules uniformly across expressions, functions, and heap operations.
- [x] (Optional) Simple type inference
  - Example: `def x = 0;` ⇒ `x` is of type `number` without an explicit annotation.

### 3. Runtime

- [x] **Harden the heap API**
  - More precise errors for invalid pointers, out-of-bounds, double `delete`, etc.
  - Simple leak tracking (e.g., for tests).
- [x] **Expand the test suite**
  - Edge cases: nested arrays, many `new/delete` pairs, deep recursion, heap-API error scenarios.

### 4. Tooling

- [x] **CLI wrapper**
  - A small command-line tool that compiles/runs TinyLanguage files (for example `python src/tiny_language_cli.py demo.tiny` or `python src/tiny_language_cli.py --source "print(1+2);"`).
- [x] **Document the language**
  - Short, stable language specification (syntax, type rules, “must use” rules) to keep behavior clear. See [`LANGUAGE_SPEC.md`](LANGUAGE_SPEC.md) for the stable reference used by the VS Code extension and other tooling.

### 5. Native Compiler

### 6. Codegen / interop

- [x] **Tiny → C → LLVM pipeline**
  - Add a CLI flag that emits LLVM IR by translating TinyLanguage to C and invoking clang.
  - Include a small regression test that validates the emitted `.ll` output exists. See [`README.md`](../README.md#compile-to-a-native-executable-c-backend).
- [x] **Python library imports**
  - Provide a TinyLanguage-facing API (or syntax) that maps to `importlib` for loading Python modules.
  - Add examples/tests demonstrating Python library usage. See [`docs/python_interop.md`](../docs/python_interop.md#common-interop-scenarios).
- [x] **Backend feature matrix**
  - Document which language features are supported by the interpreter, C backend, and LLVM backend. See [`docs/backend_feature_matrix.md`](../docs/backend_feature_matrix.md).

The native compiler is developed in its own branch (`nativeCompiler`).

- [x] Define a custom native IR (stack- or register-based).
- [x] Small VM that executes this IR (prototype interpreter in Python mirroring the Julia sketch).
- [x] Lowering: AST → Native IR for expressions, statements, functions, heap API.
- [x] Optional: Backend targeting LLVM or “plain Julia” without a runtime wrapper to produce native code.
