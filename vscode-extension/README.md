# TinyLanguage VS Code extension

This extension adds TinyLanguage editing support to Visual Studio Code:

- Syntax highlighting powered by a TextMate grammar.
- Formatting via the built-in TinyLanguage formatter.
- REPL and run commands backed by `tiny_language.py`.
- On-the-fly diagnostics based on the TinyLanguage linters.

## Getting started

1. **Install dependencies**: Make sure `python` is on your PATH and can import the TinyLanguage sources in `src/`.
2. **Open the folder**: Launch VS Code in the repository root (`code .`).
3. **Install locally**: From the `vscode-extension` directory run `npm install` (not required for pure JS) and `vsce package` to build a `.vsix`, or use the built-in `F5` launch to run the extension host.
4. **Install the packaged extension**: `code --install-extension tinylanguage-vscode-0.1.0.vsix`.
5. **Enable the TinyLanguage icons**: The extension now defaults the file icon theme to **TinyLanguage File Icons** on install. If you switch themes later, you can re-enable it via **File → Preferences → File Icon Theme**.

## Commands

- **TinyLanguage: Start REPL** (`tinylanguage.startRepl`): Opens an integrated terminal and starts `python src/tiny_language.py --repl`.
- **TinyLanguage: Run Active File** (`tinylanguage.runFile`): Executes the current `.tiny` document with `python src/tiny_language.py <file>`.
- **TinyLanguage: Format Document** (`tinylanguage.formatDocument`): Uses the TinyLanguage formatter to rewrite the buffer.
- **TinyLanguage: Refresh Diagnostics** (`tinylanguage.refreshDiagnostics`): Manually recomputes diagnostics for the active file.

Diagnostics and formatting rely on the helper script in `vscode-extension/python/vscode_helpers.py`, which imports `formatter.py` and `language_server.py`. If the sources live outside the workspace folder, adjust the `TinyLanguage › Python Path` and `TinyLanguage › Runtime Path` settings accordingly.
