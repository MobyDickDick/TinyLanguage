# TinyLanguage debugger workflows (VS Code)

The VS Code extension ships a prototype Debug Adapter Protocol (DAP) server that
connects to the TinyLanguage interpreter. It exposes standard launch
configurations plus a handful of adapter-specific behaviors so you can pause at
breakpoints, inspect scopes, and step through TinyLanguage code directly from VS
Code. If you are unsure whether the adapter itself is healthy, start with the
quick self-test below before chasing down editor log noise.

## Quick adapter health check

- Run `python vscode-extension/python/tiny_debug_adapter.py --self-test` from the
  repository root. The final JSON block should report `"tiny_language_loaded":
  true` and list the Python executable the adapter is using.
- If that succeeds, the adapter can talk to the runtime; focus on the VS Code
  launch configuration next (for example, ensure `"type": "tinylanguage"` in
  `launch.json`). If it fails, fix the Python path or import errors surfaced in
  the output before retrying VS Code.

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

## Debugging LLVM-native executables in VS Code

TinyLanguage can also compile Tiny code to a native executable via the C/LLVM
pipeline. To debug those executables in VS Code, generate a build with debug
symbols and then use the C/C++ or CodeLLDB debugger to launch the resulting
binary.

1. Compile with debug symbols enabled:

   ```bash
   python -m tinyc_cli examples/c_backend/hello_world.tiny -o build/hello_world --debug
   ```

2. Create a `launch.json` entry that points at the compiled binary. The
   following example uses the C/C++ extension (`cppdbg`) with LLDB on macOS; use
   `gdb` on Linux or switch to the CodeLLDB extension if you prefer:

   ```jsonc
   {
     "name": "TinyLanguage: Debug LLVM executable",
     "type": "cppdbg",
     "request": "launch",
     "program": "${workspaceFolder}/build/hello_world",
     "args": [],
     "cwd": "${workspaceFolder}",
     "stopAtEntry": false,
     "MIMode": "lldb"
   }
   ```

   For CodeLLDB, swap the type to `lldb`:

   ```jsonc
   {
     "name": "TinyLanguage: Debug LLVM executable (CodeLLDB)",
     "type": "lldb",
     "request": "launch",
     "program": "${workspaceFolder}/build/hello_world",
     "args": [],
     "cwd": "${workspaceFolder}"
   }
   ```

3. Start debugging with the chosen configuration. You can set breakpoints in
   the generated C source (if you emitted it with `--emit-c`) or in the
   executable's symbolized functions as reported by your debugger.

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

### Reading the extension's debug logs

- The extension prints a short summary when it resolves your `launch.json`
  entry. Lines such as `Program: C:\\Users\\...\\src_tiny\\all_features.tiny` and
  `Runtime: ...\\src\\tiny_language.py` mean that `${workspaceFolder}`
  variables were expanded correctly and the adapter will invoke the TinyLanguage
  interpreter with your program file.
- The following block shows the Python executable the adapter will spawn. If the
  executable path is **unexpected** (for example, a Microsoft Store shim on
  Windows), set the `tinylanguage.pythonPath` setting or `python` field in the
  launch configuration to point to your desired interpreter.
- When `Debug adapter logging enabled` appears, the session is writing a full
  DAP transcript to the indicated file (for example, `/tmp/tiny_dap.log` on
  Linux). This is the best place to inspect protocol-level requests and
  responses if you need to compare a "good" and "bad" launch side by side.
- A self-test block follows and includes `tiny_language_loaded: true` when the
  adapter successfully imported the TinyLanguage runtime module. If
  `src_root_exists` is `false`, verify that the `vscode-extension/src`
  directory exists in your extension install; a stale or corrupted extension
  package can prevent the adapter from finding its helper modules.

### Are generic VS Code extension host logs useful?

- The `ExtensionService#_doActivateExtension ...` lines come from VS Code's
  extension host and document which extensions activated during startup (for
  example, `vscode.git` or `ms-python.python`). They are **informational** and
  not specific to TinyLanguage. Use them to confirm that
  `tinylanguage.tinylanguage-vscode` activated, but otherwise they do not affect
  adapter behavior.
- Activation warnings/errors unrelated to TinyLanguage (such as
  `chatParticipant must be declared in package.json`) do not block the
  TinyLanguage debugger. Investigate only if you see TinyLanguage-specific
  failures; otherwise treat them as noise from other extensions.
- If the extension host log shows `onDebugResolve:tinylanguage`, it means the
  TinyLanguage configuration provider ran and prepared a debug configuration.
  Combine this with the adapter's own debug log to trace a launch end to end:
  the extension host log confirms VS Code activated the provider, while the
  adapter log confirms the TinyLanguage runtime and debug adapter started
  successfully.
- Messages like `Persistent process ... was an orphan` are emitted by VS Code's
  terminal reconnection logic when it reattaches to an existing integrated
  terminal session after a window reload. They do **not** prevent the
  TinyLanguage debug adapter from starting. If you see these alongside
  `onDebugResolve:tinylanguage` but the TinyLanguage adapter never logs a
  `launch` request, focus on the adapter log (`Debug adapter logging enabled`)
  to confirm whether VS Code actually sent the `launch` and
  `configurationDone` requests; missing requests indicate a misconfigured
  `launch.json` entry or an uninstalled TinyLanguage extension rather than a
  terminal reconnection issue.
- Periodic `[AutoSync]` entries (for example, `Sync started.`, `No changes
  found during synchronizing settings.`) come from VS Code's Settings Sync
  service. They are unrelated to debugging and continue to run in the
  background even when TinyLanguage sessions succeed. If the debugger fails to
  start, ignore these and instead inspect whether the adapter log shows a
  `launch` request and whether the Debug Console prints TinyLanguage runtime
  output.

### Why Python debugging opens a `.venv` shell but TinyLanguage does not

- The built-in VS Code Python launcher activates the selected interpreter
  (e.g., `.venv/Scripts/Activate.ps1` on Windows) in an integrated terminal and
  then starts `debugpy`. That activation banner is expected and comes from the
  Python extension setting up your environment before attaching the debugger.
- The TinyLanguage debugger uses its own `tinylanguage` debug type, which
  starts the Python-based adapter directly from the extension rather than
  through the integrated terminal. You should not see an extra shell prompt
  because the adapter spawns the interpreter in the background and forwards all
  output to the Debug Console. If you want to see the adapter's terminal log for
  troubleshooting, enable `tinylanguage.showDebugTerminal` (off by default);
  otherwise the extension keeps the extra terminal hidden so Python environment
  auto-activation scripts do not steal focus during launch.

### Interpreting "Window" log warnings and errors

- The **Window** log (from the main VS Code process) often contains extension
  warnings unrelated to TinyLanguage. Examples include duplicate setting
  registrations (e.g., `twxs.cmake: Cannot register 'cmake.cmakePath'`),
  deprecation notices (`punycode`), or experimental feature warnings (SQLite).
  These are emitted by other extensions and do not block the TinyLanguage
  adapter.
- Errors such as `Failed to fetch MCP registry providers Server returned 404`
  or `chatParticipant must be declared in package.json: claude-code` likewise
  originate from other extensions. Treat them as background noise unless they
  mention the `tinylanguage` debug type or the adapter script directly.
- A `Scheme contains illegal characters` `UriError` typically arises when an
  extension constructs an invalid URI. Unless the stack trace references
  TinyLanguage files (for example, paths under `vscode-extension/` or
  `tiny_language.py`), it will not prevent the TinyLanguage debugger from
  launching. Continue to verify that the adapter log shows the `launch` and
  `configurationDone` requests arriving after VS Code resolves the
  `tinylanguage` configuration.
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
