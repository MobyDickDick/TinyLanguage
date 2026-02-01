# TinyLanguage debug adapter integration guide

This guide explains how to wire up the TinyLanguage VS Code debug adapter,
covers every supported launch mode, and provides targeted troubleshooting
steps for each path. It complements `docs/debugger_workflows.md` by focusing on
integration details, configuration knobs, and adapter-specific failure modes.

## Prerequisites

- Install the TinyLanguage VS Code extension from `vscode-extension/` (packaged
  `.vsix` or Extension Development Host).
- Ensure the configured Python executable can import the repository `src/`
  directory (the adapter launches `src/tiny_language.py` by default).
- Open your TinyLanguage workspace so `${workspaceFolder}` and `${file}` resolve
  correctly in `launch.json`.

## Launch modes (supported)

### 1) TinyLanguage source debugging (prototype adapter)

**When to use:** You are debugging a `.tiny` file with the custom adapter.

**Launch configuration:**

```jsonc
{
  "name": "TinyLanguage: Launch active file (prototype)",
  "type": "tinylanguage",
  "request": "launch",
  "program": "${file}",
  "runtime": "${workspaceFolder}/src/tiny_language.py",
  "python": "${config:tinylanguage.pythonPath}",
  "stopOnEntry": false
}
```

**What happens:** VS Code calls the TinyLanguage debug adapter, which performs
its self-test, injects the workspace `src/` directory into `sys.path`, then
launches the interpreter with your program.

**Troubleshooting:**

- If the adapter never receives a `launch` request, ensure the configuration
  uses `"type": "tinylanguage"` and that the extension is installed/enabled.
- If the adapter reports `Launch request is missing required 'program' path`,
  confirm `${file}` resolves to an existing `.tiny` file and your editor is
  focused on the correct buffer.
- If breakpoints never hit, enable a debug log (`TINYLANGUAGE_DAP_LOG`) and
  verify that VS Code sends `setBreakpoints` and `configurationDone` after
  `launch`.

### 2) Python file debugging via the Python extension (default delegation)

**When to use:** You point a `tinylanguage` launch config at a `.py` file and
want the richer `debugpy` experience.

**Behavior:** The TinyLanguage extension detects Python targets and delegates
to the official VS Code Python extension by default. This bypasses the
TinyLanguage adapter and uses `debugpy` instead.

**Troubleshooting:**

- If you expected the TinyLanguage adapter, set
  `"tinylanguage.preferPythonExtensionDebugger": false` globally or add
  `"usePythonExtension": false` in the launch entry to force the built-in
  adapter.
- If no Python debugger starts, verify the VS Code Python extension is
  installed and that your `python` setting points to a valid interpreter.

### 3) Python file debugging with the TinyLanguage adapter (self-test mode)

**When to use:** You want to validate the adapter itself on a `.py` file or
reproduce adapter issues without running TinyLanguage code.

**Launch configuration:**

```jsonc
{
  "name": "TinyLanguage: Launch active Python file (debug adapter test)",
  "type": "tinylanguage",
  "request": "launch",
  "program": "${file}",
  "usePythonExtension": false
}
```

**Troubleshooting:**

- If the adapter still delegates to Python, double-check
  `"usePythonExtension": false` is set on the specific launch entry.
- If the adapter self-test fails, open **Output → TinyLanguage** and inspect
  the JSON payload for `tiny_language_loaded: false` or missing `src_root`.

## Diagnostics and logging knobs

- `TINYLANGUAGE_DAP_LOG`: write the full DAP transcript to a file.
- `TINYLANGUAGE_DAP_STDERR`: mirror the DAP log to **Output → TinyLanguage**.
- `TINYLANG_TRACE_LOG`: enable runtime-level tracing to confirm statement
  execution when breakpoints or stepping appear stuck.

## Known failure patterns and fixes

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Couldn't find a debug adapter descriptor` | Extension not activated or outdated | Reinstall/upgrade the extension and reload VS Code. |
| `Launch request is missing required 'program' path` | `program` resolved empty | Ensure `${file}` points to an open file. |
| Adapter starts but no `launch` request | Wrong `type` in `launch.json` | Use `"type": "tinylanguage"`. |
| Breakpoints ignored | Missing `configurationDone` | Enable `TINYLANGUAGE_DAP_LOG` and verify request flow. |

## Next steps

For deeper workflow examples (scaffolding, logging locations, stepping
limitations), see `docs/debugger_workflows.md`.
