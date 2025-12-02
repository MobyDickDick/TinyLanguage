# TinyLanguage Feature Cheat Sheet

Kurzreferenz zu zentralen Sprachfeatures mit Verweisen auf die vollständigen `.tiny`-Demos. Alle Befehle gehen davon aus, dass du aus dem Repository-Root arbeitest und `PYTHONPATH=src` gesetzt ist, falls du die Python-Interop nutzt.

## Schnellstart
- Programm ausführen: `python src/tiny_language.py <pfad_zur_datei.tiny>`
- Interpreter vs. Native-Backend vergleichen: füge `--native-backend` hinzu.
- Formatieren: `python src/tiny_language.py --format <pfad>`

## Fundamentale Bausteine
- **Variablen & Arithmetik**: `src_tiny/demo.tiny` zeigt `define`, einfache Operatoren und `print`.
- **Kontrollfluss**: `src_tiny/all_features.tiny` enthält `if`/`else`, `while`, `return`-Pflichten.
- **Funktionen**: `src_tiny/all_features.tiny` definiert freie Funktionen und demonstriert Positionsargumente.

## Typen und Signaturen
- **Annotierte Parameter & Rückgabewerte**: `src_tiny/typing_demo.tiny` prüft Gradual Typing und Exhaustiveness.
- **Optionale Rückgaben**: `src_tiny/result_demo.tiny` illustriert `Result`-ähnliche Rückgabemuster.

## Namespaces und Module
- **Namespaces**: `src_tiny/namespace_demo.tiny` gruppiert Utilities und ruft sie qualifiziert auf.
- **Importe & Stdlib**: `src_tiny/stdlib_io_random_demo.tiny` nutzt `import`, I/O und Zufallsfunktionen.

## Klassen und Operatoren
- **Klassen & Methoden**: `src_tiny/class_demo.tiny` definiert Felder, Konstruktor-Wrapper und Methoden.
- **Operator-Overloading**: `src_tiny/operator_overloading_demo.tiny` überschreibt `+` und `==` für `Point`.

## Pattern Matching und ADTs
- **Tagged Unions**: `src_tiny/match_demo.tiny` führt `type`-Definitionen ein und erzwingt Exhaustiveness in `match`.

## Heap, Arrays und Collections
- **Pointer/Heap**: `src_tiny/heap_pointer_demo.tiny` demonstriert `new`, `heap_get`/`heap_set` und `delete`.
- **Collections**: `src_tiny/stdlib_collections_demo.tiny` nutzt `Map`, `Set`, `Deque` und zeigt Mutationen.

## Nebenläufigkeit und Async
- **Tasks & Pipelines**: `src_tiny/concurrency_demo.tiny` und `src_tiny/concurrency_pipeline.tiny` decken `spawn`, `join` und Token-Abbruch ab.
- **Parallel Map**: `src_tiny/parallel_map.tiny` kombiniert Tasks mit Aggregation.

## Interop mit Python
- **FFI-Basics**: `src_tiny/python_math_demo.tiny` und `src_tiny/python_json_demo.tiny` zeigen `Python.import_module`/`Python.call` mit Allowlist.
- **Namespaces + Typing**: `src_tiny/python_namespace_typed_demo.tiny` kapselt Python-Aufrufe in `namespace PyInterop` mit annotierten Signaturen.

## Native Backend
- **Bytecode-Pfad ausprobieren**: Führe z. B. `python src/tiny_language.py --native-backend src_tiny/all_features.tiny` aus und vergleiche die Ausgabe mit dem Interpreterlauf ohne Flag.
- **Smoke-Tests**: `python -m pytest tests/test_native_codegen.py -q` prüft, welche AST-Knoten bereits unterstützt sind.

## Fehlerbilder und Lints
- **Unbenutzter Rückgabewert**: Ein Call ohne Zuweisung kann `[E011] function ... discards return value` auslösen (siehe `src_tiny/typing_demo.tiny`).
- **Nicht erreichte Returns**: Fehlende Rückgaben in getypten Funktionen führen zu `[E010] not all paths return a value`.

## Hilfreiche Kombos
- **Formatter + Diagnostics**: Erst formatieren (`--format`), dann `python src/language_server_cli.py --file <file> diagnostics` nutzen, um klare Lints zu erhalten.
- **Rosetta-Beispiele**: `src_tiny/rosetta_fibonacci.tiny` bietet ein kleines, selbständiges Programm zum Validieren von Recursion/Loops.
