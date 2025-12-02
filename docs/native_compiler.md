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

## Nutzung
- **CLI-Schalter**: `python src/tiny_language.py --native-backend -e "print(1 + 2);"` führt ein Snippet ohne den AST-Interpreter aus.
- **Datei-Ausführung**: `python src/tiny_language.py --native-backend path/to/program.tiny` lädt ein Programm und nutzt denselben Codegen/VM-Pfad.
- **Regression-Tests**: `python -m pytest tests/test_native_codegen.py -q` vergleicht Interpreter- und Native-Backend-Ausgaben und stellt sicher, dass nicht unterstützte Konstrukte weiterhin als `NotImplementedError` sichtbar bleiben.

## CLI-Workflow auf einen Blick

1. **Smoke-Run mit Beispielprogramm**: `PYTHONPATH=src python src/tiny_language.py --native-backend src_tiny/demo.tiny` – prüft, ob Parser, Codegen und VM zusammenarbeiten.
2. **Schneller Feature-Vergleich**: Führe denselben Befehl ohne `--native-backend` aus und vergleiche die Ausgabe, um Divergenzen einzukreisen.
3. **Gezielte Funktionstests**: `python -m pytest tests/test_native_codegen.py -k while -q` zum Fokussieren auf einzelne Konstrukte wie `while`-Schleifen oder Funktionsaufrufe.

## Grenzen und bekannte Lücken

- Nicht alle Konstrukte sind bislang abgedeckt; Heap-Operationen, Klassen und Pattern Matching werden absichtlich als `NotImplementedError` gekennzeichnet.
- Die VM erwartet einfache numerische/Boolean-Ausdrücke. Typannotationen werden akzeptiert, aber komplexe Typprüfungen erfolgen weiterhin im Interpreter.
- `print` sammelt Ausgaben in der VM, unterstützt aber aktuell keine Formatierung oder Mehrfach-Delimiter wie der Interpreter.

## Troubleshooting

- **`NotImplementedError` beim Codegen**: Der Generator nennt meist den betroffenen AST-Knoten. Beispiel: `NotImplementedError: Call to Map.set not supported in native backend` – reduziere den Testfall auf einfache Arithmetik oder deaktiviere `--native-backend`.
- **Stacktrace aus der VM**: Fehler werden mit Frame-Informationen ausgegeben, z. B.:
  ```
  Traceback (most recent call last):
    at NativeVM.run_function(<main>)
    at NativeVM._binary()
  RuntimeError: division by zero
  ```
  Die Frames spiegeln die Bytecode-Ausführung wider und helfen, fehlerhafte Instruktionen zu lokalisieren.
- **CLI-Parsing klappt nicht**: Stelle sicher, dass `--native-backend` vor `-e` oder dem Dateipfad steht; andernfalls interpretiert `argparse` das Flag als Programmargument.
- **Ungültige Instruktion im Bytecode**: Falls die VM `RuntimeError: unknown opcode` meldet, ist der Bytecode vermutlich aus einer älteren Generator-Version. Lege den Bytecode neu an, indem du das Quellprogramm erneut mit `--native-backend` ausführst und alte Artefakte löschst.
- **Interpreter/Nativ divergieren**: Nutze den A/B-Vergleich aus dem Workflow oben: einmal mit und einmal ohne `--native-backend` laufen lassen. Unterschiedliche Ausgaben deuten auf fehlende Lowerings hin und sollten als Regression dokumentiert werden.
- **Timeouts in Test-Suites**: Lange Läufe können die VM blockieren. Begrenze Schleifen in `.tiny`-Fixtures oder verwende gezielte Test-Filter (`-k while`) und `-q`, um die Logmenge klein zu halten.
