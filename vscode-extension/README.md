# TinyLanguage VS Code extension

This extension adds TinyLanguage editing support to Visual Studio Code:

- Syntax highlighting powered by a TextMate grammar.
- Formatting via the built-in TinyLanguage formatter.
- Hover and completion suggestions sourced from the TinyLanguage language server helpers.
- REPL and run commands backed by `tiny_language.py`.
- On-the-fly diagnostics based on the TinyLanguage linters.

## Getting started

1. **Install dependencies**: Make sure `python` is on your PATH and can import the TinyLanguage sources in `src/`.
2. **Open the folder**: Launch VS Code in the repository root (`code .`).
3. **Install locally**: From the `vscode-extension` directory run `npm install` (not required for pure JS) and `vsce package` to build a `.vsix`, or use the built-in `F5` launch to run the extension host.
4. **Install the packaged extension**: `code --install-extension tinylanguage-vscode-0.1.2.vsix`.
5. **Verify the new version is active**: Open the **Extensions** view, search for *TinyLanguage*, and confirm the version shows `0.1.2` with a green checkmark. If VS Code still shows an older version, run **Developer: Reload Window** after the installation command.
6. **Enable the TinyLanguage icons**: The extension now defaults the file icon theme to **TinyLanguage File Icons** on install. If you switch themes later, you can re-enable it via **File → Preferences → File Icon Theme**.

## Commands

- **TinyLanguage: Start REPL** (`tinylanguage.startRepl`): Opens an integrated terminal and starts `python src/tiny_language.py --repl`.
- **TinyLanguage: Run Active File** (`tinylanguage.runFile`): Executes the current `.tiny` document with `python src/tiny_language.py <file>`.
- **TinyLanguage: Format Document** (`tinylanguage.formatDocument`): Uses the TinyLanguage formatter to rewrite the buffer.
- **TinyLanguage: Refresh Diagnostics** (`tinylanguage.refreshDiagnostics`): Manually recomputes diagnostics for the active file.

Diagnostics and formatting rely on the helper script in `vscode-extension/python/vscode_helpers.py`, which imports `formatter.py` and `language_server.py`. If the sources live outside the workspace folder, adjust the `TinyLanguage › Python Path` and `TinyLanguage › Runtime Path` settings accordingly.

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
      "runtime": "${workspaceFolder}/src/tiny_language.py" // Python interpreter path
    }
  ]
}
```

The adapter starts the Python runtime shown in `runtime`. If the interpreter is not on your PATH or lives elsewhere, point `runtime` to the correct executable or virtual environment. When a launch fails, the extension writes activation issues to **Output → Log (Extension Host)** and adapter startup messages to **Output → TinyLanguage**, which helps pinpoint whether activation or runtime resolution failed.

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

When you start a debug session, the extension also opens a **TinyLanguage Debug Log** integrated terminal and echoes the target program, Python executable, runtime, and working directory. This provides a quick sanity check that terminal output is working in your environment and shows exactly what the adapter is about to launch.

VS Code now accepts the `env` block on TinyLanguage launch configurations, so you will no longer see `Property env is not allowed` when adding these environment variables.

#### Interpreting the adapter self-test log

Every TinyLanguage debug session performs a quick self-test before launching. The JSON payload printed to **Output → TinyLanguage** (and stored in your adapter log) confirms which Python executable is used and where the adapter loaded `tiny_language.py` from. Typical fields include:

- `src_root` / `src_root_exists`: The adapter’s best guess at the bundled source tree. When installed from the marketplace the `src_root_exists` flag may be `false` because the sources live in your workspace instead of inside the extension package. This is informational only.
- `tiny_language_module`: Absolute path to the loaded `tiny_language.py` module. This should point at your workspace copy (for example `${workspaceFolder}/src/tiny_language.py`). If it points somewhere unexpected, adjust **TinyLanguage › Python Path** or **TinyLanguage › Runtime Path**.
- `sys_path_sample`: The first few entries of `sys.path`, which helps verify whether your workspace or virtual environment is being searched.

If the self-test fails or shows the module being imported from the wrong location, ensure the configured Python interpreter can import your workspace’s `src/` directory and restart the debug session.

#### Troubleshooting a stuck debug session

If the TinyLanguage debug session seems to “hang” (no breakpoints hit, VS Code status bar shows “running” forever), try the following steps to pinpoint the failure:

- Open **Output → TinyLanguage** and inspect the self-test JSON printed when the adapter starts. Confirm the `tiny_language_module` points at your workspace copy (for example `${workspaceFolder}/src/tiny_language.py`) and that `sys_path_sample` includes your repository `src` folder. If not, set **TinyLanguage › Python Path** and **TinyLanguage › Runtime Path** to the interpreter/virtual environment that can import the sources, then restart VS Code.
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
  - After `define i = 5;`, assigning `i = 0.5;` should be an error (or explicitly allowed via another mechanism).
  - Apply type rules uniformly across expressions, functions, and heap operations.
- [x] (Optional) Simple type inference
  - Example: `define x = 0;` ⇒ `x` is of type `number` without an explicit annotation.

### 3. Runtime

- [x] **Harden the heap API**
  - More precise errors for invalid pointers, out-of-bounds, double `delete`, etc.
  - Simple leak tracking (e.g., for tests).
- [x] **Expand the test suite**
  - Edge cases: nested arrays, many `new/delete` pairs, deep recursion, heap-API error scenarios.

### 4. Tooling

- [x] **CLI wrapper**
  - A small command-line tool that compiles/runs TinyLanguage files (for example `python -m tiny_language_cli demo.tiny` or `python -m tiny_lang_cli --source "print(1+2);"`).
- [x] **Document the language**
  - Short, stable language specification (syntax, type rules, “must use” rules) to keep behavior clear. See [`LANGUAGE_SPEC.md`](LANGUAGE_SPEC.md) for the stable reference used by the VS Code extension and other tooling.

### 5. Native Compiler

### 6. Codegen / interop

- [x] **Tiny → C → LLVM pipeline**
  - Add a CLI flag that emits LLVM IR by translating TinyLanguage to C and invoking clang.
  - Include a small regression test that validates the emitted `.ll` output exists. See [`README.md`](../README.md#compile-to-a-native-executable-c-backend).
- [x] **Python library imports**
  - Provide a TinyLanguage-facing API (or syntax) that maps to `importlib` for loading Python modules.
  - Add examples/tests demonstrating Python library usage. See [`README.md`](../README.md#6-codegen--interop).
- [x] **Backend feature matrix**
  - Document which language features are supported by the interpreter, C backend, and LLVM backend. See [`docs/backend_feature_matrix.md`](../docs/backend_feature_matrix.md).

The native compiler is developed in its own branch (`nativeCompiler`).

- [x] Define a custom native IR (stack- or register-based).
- [x] Small VM that executes this IR (prototype interpreter in Python mirroring the Julia sketch).
- [x] Lowering: AST → Native IR for expressions, statements, functions, heap API.
- [x] Optional: Backend targeting LLVM or “plain Julia” without a runtime wrapper to produce native code.
