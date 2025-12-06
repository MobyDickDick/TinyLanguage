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
4. **Install the packaged extension**: `code --install-extension tinylanguage-vscode-0.1.1.vsix`.
5. **Verify the new version is active**: Open the **Extensions** view, search for *TinyLanguage*, and confirm the version shows `0.1.1` with a green checkmark. If VS Code still shows an older version, run **Developer: Reload Window** after the installation command.
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
4. If VS Code reports `Couldn't find a debug adapter descriptor` for `tinylanguage`, update to version `0.1.1` (or newer) and reload the window so the debugger activation events are registered.

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

If you need a detailed trace of every Debug Adapter Protocol (DAP) message exchanged with VS Code, use **TinyLanguage › Debug Log Path**. By default the extension writes adapter traces to `${workspaceFolder}/.tinylanguage/debug-adapter.log`; you can point the setting elsewhere or clear it to disable file logging. The adapter records inbound and outbound DAP payloads, breakpoint updates, and stepping commands to the configured file.

## Roadmap / TODO

This section gathers upcoming tasks for TinyLanguage.
Roughly grouped into frontend/language, type discipline, runtime, and tooling.
The “nativeCompiler” work is tracked separately.

### 1. Frontend / language

- [ ] **Improve error positions and messages**
  - Tokens and AST nodes should consistently carry line and column information.
  - Unified error type with an optional `SourceSpan` that highlights the affected line when displayed.
  - Parser and linter should use this error type.

- [ ] **Refine the linter**
  - “must use” rule across control flow: a variable counts as used only when referenced on all relevant paths.
  - Unreachable-code warnings (e.g., statements after `return`).

### 2. Type discipline

- [ ] **No implicit type changes**
  - After `define i = 5;`, assigning `i = 0.5;` should be an error (or explicitly allowed via another mechanism).
  - Apply type rules uniformly across expressions, functions, and heap operations.
- [x] (Optional) Simple type inference
  - Example: `define x = 0;` ⇒ `x` is of type `number` without an explicit annotation.

### 3. Runtime

- [ ] **Harden the heap API**
  - More precise errors for invalid pointers, out-of-bounds, double `delete`, etc.
  - Simple leak tracking (e.g., for tests).
- [ ] **Expand the test suite**
  - Edge cases: nested arrays, many `new/delete` pairs, deep recursion, heap-API error scenarios.

### 4. Tooling

- [ ] **CLI wrapper**
  - A small command-line tool that compiles/runs TinyLanguage files (e.g., `julia --project=. tiny_cli.jl source.tiny`).
- [x] **Document the language**
  - Short, stable language specification (syntax, type rules, “must use” rules) to keep behavior clear. See [`LANGUAGE_SPEC.md`](LANGUAGE_SPEC.md) for the stable reference used by the VS Code extension and other tooling.

### 5. Native Compiler

The native compiler is developed in its own branch (`nativeCompiler`).

- [ ] Define a custom native IR (stack- or register-based).
- [ ] Small VM that executes this IR (interpreter in Julia).
- [ ] Lowering: AST → Native IR for expressions, statements, functions, heap API.
- [ ] Optional: Backend targeting LLVM or “plain Julia” without a runtime wrapper to produce native code.
