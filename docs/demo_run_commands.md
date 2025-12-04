# Befehlsliste für Demos und Schnelltests

Diese Liste bündelt häufige CLI-Aufrufe, um die wichtigsten Beispiele und Backends in einem Lauf zu verifizieren. Führe die Befehle aus dem Repository-Root aus; setze `PYTHONPATH=src` für die Python-Helferskripte.

## Interpreter-Demos
```bash
python src/tiny_language.py src_tiny/demo.tiny
python src/tiny_language.py src_tiny/all_features.tiny
python src/tiny_language.py src_tiny/class_demo.tiny
python src/tiny_language.py src_tiny/namespace_demo.tiny
python src/tiny_language.py src_tiny/match_demo.tiny
python src/tiny_language.py src_tiny/operator_overloading_demo.tiny
python src/tiny_language.py src_tiny/heap_pointer_demo.tiny
python src/tiny_language.py src_tiny/stdlib_io_random_demo.tiny
python src/tiny_language.py src_tiny/stdlib_collections_demo.tiny
```

## Concurrency- und Pipeline-Beispiele
```bash
python src/tiny_language.py src_tiny/concurrency_demo.tiny
python src/tiny_language.py src_tiny/concurrency_pipeline.tiny
python src/tiny_language.py src_tiny/parallel_map.tiny
```

## Python-Interop
```bash
PYTHONPATH=src python src/tiny_language.py src_tiny/python_math_demo.tiny
PYTHONPATH=src python src/tiny_language.py src_tiny/python_json_demo.tiny
PYTHONPATH=src python src/tiny_language.py src_tiny/python_namespace_typed_demo.tiny
```

## Native Backend im Vergleich
```bash
python src/tiny_language.py --native-backend src_tiny/all_features.tiny
python src/tiny_language.py --native-backend src_tiny/match_demo.tiny
python -m pytest tests/test_native_codegen.py -q
```

## Language-Server-Helfer
```bash
PYTHONPATH=src python src/language_server_cli.py --file src_tiny/class_demo.tiny hover --symbol Greeter
PYTHONPATH=src python src/language_server_cli.py --file src_tiny/namespace_demo.tiny completions --prefix To
PYTHONPATH=src python src/language_server_cli.py --file src_tiny/stdlib_io_random_demo.tiny diagnostics
```

## Module-Workflows
```bash
# Lokalen Modulbaum mit relativem Import prüfen
python -m tiny_lang_cli --file my_pkg/main.tiny --backend interpreter

# Mit optionalem Suchpfad und Native-Backend gegentesten
TINYPATH=../deps python -m tiny_lang_cli --file my_pkg/main.tiny --backend native
```

## Alles auf einmal
Das Skript `run_all.py` führt eine repräsentative Auswahl der obigen Demos plus die Pytest-Suite aus:

```bash
python run_all.py
```

Fehlschläge führen zu einem non-zero Exitcode; so kann das Skript als schneller Regressionstest in CI oder Editor-Launchern dienen.
