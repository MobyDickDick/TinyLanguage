# Ausbau-Roadmap

Diese Roadmap sammelt die groben Aufgabenpakete, die TinyLanguage in Richtung
Compiler, Bibliotheken und Transpiler erweitern sollen. Die Punkte sind bewusst
so formuliert, dass sie nach und nach abgearbeitet werden können.

## 1) Native Compiler (ausführbare Dateien)

- **LLVM-basierte Pipeline**: TinyLanguage → Native IR → LLVM IR → Binärdatei.
- **CLI-Unterstützung**: `--emit-llvm` (LLVM-IR ausgeben) und `--emit-exe` (Binary bauen).
- **Erster Zielumfang**: arithmetische Ausdrücke, Variablen, `print`, einfache Kontrollflüsse.
- **Toolchain**: `clang`/`llc` für den ersten End-to-End-Flow.

## 2) Python-Standardbibliothek portieren

- **Priorisierte Module**: `math`, `random`, `string`, `datetime` (schrittweise).
- **Ziel**: TL-Stdlib-Module mit ähnlicher API wie Python bereitstellen.
- **Tests**: Kleine Vergleichstests gegen Python-Ergebnisse (wo sinnvoll).

## 3) Rosetta-Code-Aufgaben

- **Konsistentes Aufgabenlayout** ✅: `examples/rosetta/<task>/`.
- **Erste Welle**: Einsteiger-Aufgaben (z. B. Hello World, Fibonacci, Sortierung).
- **Transpiler-Checks**: Prüfen, welche Sprachfeatures TL noch braucht.

## 4) Julia-Subset übertragen

- **Scope klein halten**: z. B. `Statistics` oder einfache Lineare Algebra.
- **PoC-Module**: erste Funktionen (z. B. `mean`, `std`) mit Tests.
- **API-Notizen**: Unterschiede zu Julia dokumentieren.
