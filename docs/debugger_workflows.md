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

### Why Python debugging opens a `.venv` shell but TinyLanguage does not
- The built-in VS Code Python launcher activates the selected interpreter
  (e.g., `.venv/Scripts/Activate.ps1` on Windows) in an integrated terminal and
  then starts `debugpy`. That activation banner is expected and comes from the
  Python extension setting up your environment before attaching the debugger.
- The TinyLanguage debugger uses its own `tinylanguage` debug type, which
  starts the Python-based adapter directly from the extension rather than
  through the integrated terminal. You should not see an extra shell prompt
  because the adapter spawns the interpreter in the background and forwards all
  output to the Debug Console.
- If you see the Python-style activation while trying to debug TinyLanguage,
  double-check that your `launch.json` uses `"type": "tinylanguage"` instead of
  the built-in Python configuration. That ensures stepping and breakpoints go
  through the TinyLanguage adapter rather than `debugpy`.

### Using a virtual environment with the TinyLanguage adapter
- The adapter runs under whichever Python executable the extension is
  configured to use. Set `tinylanguage.pythonPath` in VS Code settings (for
  example, `"${workspaceFolder}/.venv/bin/python"` on POSIX or
  `"${workspaceFolder}\\.venv\\Scripts\\python.exe"` on Windows) to force the
  adapter and its helper tools to run inside your virtual environment.
- You can also set `"python"` and `"runtime"` directly in the `launch.json`
  entry for a specific configuration if you want one launch to use a particular
  interpreter or runtime script.
- If your workspace already selects a Python interpreter (status bar in VS
  Code), reusing the same path for `tinylanguage.pythonPath` keeps linting,
  formatter helpers, and the debug adapter aligned with the rest of your
  tooling.
