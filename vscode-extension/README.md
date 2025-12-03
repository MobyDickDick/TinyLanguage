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

## Roadmap / TODO

Dieser Abschnitt sammelt anstehende Aufgaben für TinyLanguage.  
Grob unterteilt in: Frontend/Sprache, Typdisziplin, Runtime und Tooling.  
Der „nativeCompiler“ wird separat geführt.

### 1. Frontend / Sprache

- [ ] **Fehlerpositionen und Fehlermeldungen verbessern**
  - Tokens und AST-Knoten sollen konsistent Zeilen- und Spalteninformation tragen.
  - Einheitlicher Fehlertyp mit optionalem `SourceSpan`, der bei Ausgabe die betroffene Zeile und eine Unterstreichung zeigt.
  - Parser und Linter sollen diesen Fehlertyp verwenden.

- [ ] **Linter verfeinern**
  - „must use“-Regel über Kontrollfluss: eine Variable gilt nur als benutzt, wenn sie auf allen relevanten Pfaden verwendet wird.
  - Unreachable-Code-Warnungen (z.B. Code nach `return`).

### 2. Typdisziplin

- [ ] **Keine impliziten Typänderungen**
  - Nach `define i = 5;` darf `i = 0.5;` ein Fehler sein (oder explizit über einen anderen Weg erzwungen werden).
  - Typregeln einheitlich in Ausdrücken, Funktionen und Heap-Operationen anwenden.
- [x] (Optional) Einfache Typinferenz
  - Z.B. `define x = 0;` ⇒ `x` ist vom Typ `number`, ohne explizite Annotation.

### 3. Runtime

- [ ] **Heap-API robuster machen**
  - Präzisere Fehlermeldungen für ungültige Pointer, Out-of-Bounds, doppelte `delete` usw.
  - Einfaches Leak-Tracking (z.B. für Tests).
- [ ] **Test-Suite erweitern**
  - Randfälle: verschachtelte Arrays, viele `new/delete`, tiefe Rekursion, Fehlerfälle der Heap-API.

### 4. Tooling

- [ ] **CLI-Wrapper**
  - Ein kleines Kommandozeilentool, das TinyLanguage-Dateien kompiliert/ausführt (z.B. `julia --project=. tiny_cli.jl source.tiny`).
- [ ] **Sprache dokumentieren**
  - Kurze, stabile Sprachspezifikation (Syntax, Typregeln, „must use“-Regeln), damit das Verhalten klar bleibt.

### 5. Native Compiler

Der native Compiler wird in einem eigenen Branch (`nativeCompiler`) entwickelt.

- [ ] Eigenes Native-IR definieren (stack-/registerbasiert).
- [ ] Kleine VM, die dieses IR ausführt (Interpreter in Julia).
- [ ] Lowering: AST → Native-IR für Ausdrücke, Statements, Funktionen, Heap-API.
- [ ] Optional: Backend auf LLVM oder „Plain Julia“ ohne Runtime-Wrapper zur Erzeugung nativen Codes.
