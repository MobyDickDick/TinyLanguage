# TinyLanguage debugger workflows (VS Code)

The VS Code extension ships a prototype Debug Adapter Protocol (DAP) server that
connects to the TinyLanguage interpreter. It exposes standard launch
configurations plus a handful of adapter-specific behaviors so you can pause at
breakpoints, inspect scopes, and step through TinyLanguage code directly from VS
Code.

## Launching the debugger
1. Install the local VS Code extension contained in `vscode-extension/` (either
   with `code --install-extension` while pointing at the packaged `.vsix` or by
   running the extension in a dev window).
2. Open a TinyLanguage workspace and create a `launch.json` entry with the
   "TinyLanguage: Launch active file (prototype)" configuration. The extension's
   configuration provider auto-fills the `type`, `request`, `program` (defaults
   to the active editor file), and `runtime` (defaults to
   `${workspaceFolder}/src/tiny_language.py`).
3. Hit **Run and Debug → TinyLanguage: Launch active file (prototype)**. The
   extension starts the Python-based debug adapter via the
   `tinylanguage.getDebugAdapterExecutable` command and wires breakpoints into
   the interpreter before execution begins.

## Supported controls
- **Breakpoints**: Any line breakpoint in a TinyLanguage source file will pause
  execution. Breakpoints are forwarded through the adapter and installed on the
  interpreter-side debugger before the program starts.
- **Stepping**: Continue, step over, step into, and step out map to the
  interpreter's synchronous stepping hooks. The adapter sends `stopped` events
  whenever the runtime pauses and responds to the corresponding DAP step
  requests by resuming execution.
- **Scopes and variables**: When paused, the adapter surfaces the current scopes
  and variables reported by the interpreter. Variable values are rendered with
  `repr` to stay faithful to the runtime objects.
- **Call stacks**: The stack trace view includes TinyLanguage function frames and
  the current location in the active source file. Namespaces are resolved from
  the file path to keep module names stable across workspaces.

## Troubleshooting
- The adapter reports file read errors and runtime exceptions through `output`
  events in the Debug Console. Check for messages prefixed with
  `Failed to read program:` or `Runtime error:` if execution ends early.
- If a session appears stuck at a breakpoint, verify that stepping/continue
  commands are being issued; the adapter waits briefly for a command
  (continue/step over/step in/step out) whenever the interpreter pauses and
  then auto-continues so executions do not stall indefinitely.
- Ensure the configured Python executable can import the repository's `src`
  directory; the default launcher prepends it to `sys.path` via the adapter
  script, but custom launchers should replicate that behavior.
- When debugging the adapter itself, look for the startup handshake in the
  DAP log. A healthy session starts with `initialize` → `initialized` events
  (as in `Debug adapter started ... initialize ... initialized`). If the log
  stops there, the VS Code client likely never sent a `launch` request—common
  causes are a missing extension install, an unregistered `tinylanguage` debug
  type, or an invalid `launch.json` entry. Reinstall the extension from
  `vscode-extension/` and trigger a TinyLanguage launch configuration to ensure
  the adapter receives `launch` followed by `configurationDone`.
