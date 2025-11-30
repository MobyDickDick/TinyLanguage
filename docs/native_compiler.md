# Native-Compiler-Prototyp

Dieser Entwurf steckt die Zielarchitektur für ein alternatives Backend ab, das TinyLanguage-Programme ohne den AST-Interpreter ausführt. Der Fokus liegt auf einem schnellen Feedback-Zyklus: kleine, nachvollziehbare Bausteine, die mit den bestehenden Interpreter-Tests gegengeprüft werden können.

## Ziele
- **Bytecode- oder IR-Emission aus dem vorhandenen AST**: Wir wollen keine zweite Parser-Pipeline pflegen. Der Generator soll direkt auf den bestehenden Knoten aus `tiny_language_ast.py` arbeiten.
- **Einfache VM-Schicht**: Eine kompakte, stapelbasierte VM mit Jump-/Call-Instruktionen reicht für die ersten Experimente. Sie muss deterministisch und gut testbar sein.
- **Feature-Flag im CLI**: Der alternative Pfad soll neben dem Interpreter und dem Python-Backend auswählbar sein (`--native-backend`). So bleiben Funktionsvergleiche einfach.

## Grobe Architektur
1. **Codegen-Pass** (`NativeCodeGenerator`): Traversiert das AST und erzeugt linearen Bytecode pro Funktion sowie eine Entry-Sequence für Top-Level-Statements. Nicht unterstützte Konstrukte werfen `NotImplementedError`.
2. **VM** (`NativeVM`): Führt den Bytecode über Frames mit einfachem Local/Global-Lookup aus und sammelt Ausgaben in `output`. Kerninstruktionen sind u. a. `PUSH_CONST`, `LOAD`, `STORE`, `BINARY`, `PRINT`, `JUMP`, `JUMP_IF_FALSE`, `CALL`, `RETURN`.
3. **API/CLI-Hooks**: `tiny_language_api.py` stellt `run_with_native_backend` bereit; `tiny_language.py` lädt den Generator als Modulsegment; das CLI akzeptiert `--native-backend` für `--eval` und Datei-Ausführung (REPL bleibt vorerst beim Interpreter).

## Minimale Abdeckung der ersten Iteration
- Literale (`Num`, `Str`, `Bool`, `Null`)
- Variablenbindung und -zuweisung (`Let`, `Assign`)
- Arithmetik und Vergleichsoperatoren über `Bin`
- Kontrollfluss: `If`, `While`
- Funktionen mit `return` und Funktionsaufruf (`Fn`, `Call`)
- Ausgabe via `print`-Statement (mehrere Argumente, Leerzeichen-getrennt)

## Nachweise und Tests
- **Smoke-Tests** vergleichen Interpreter- und Native-Backend-Ausgabe für Arithmetik, Branching und Funktionen.
- Die VM bleibt absichtlich klein, um spätere Erweiterungen (z. B. Arrays, Objekte, Pattern Matching) messbar zu halten.
