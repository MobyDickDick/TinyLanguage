# Native IR (stackbasiert)

Diese Kurzreferenz beschreibt das interne Bytecode-Format des Native-Backends. Es ist bewusst klein gehalten, damit Codegen und VM eng aufeinander abgestimmt bleiben und Tests die ausgegebenen Instruktionen leicht prüfen können.

## Opcode-Übersicht

| Opcode | Operanden | Beschreibung |
| --- | --- | --- |
| `PUSH_CONST` | Wert | Konstante auf den Stack legen. |
| `LOAD` | Name | Lokale oder globale Variable laden. |
| `STORE` | Name | Stack-Top in Variable speichern. |
| `BINARY` | Operator (`+`, `-`, `*`, `/`, `%`, `^`, Vergleichsoperatoren, `&&`, `||`) | Zwei Werte vom Stack holen, Operator anwenden, Ergebnis zurück auf den Stack. |
| `PRINT` | Anzahl | Angegebene Zahl von Stack-Werten nehmen, formatieren und mit Zeilenumbruch ausgeben. |
| `JUMP` | Zielindex | Unbedingter Sprung innerhalb des aktuellen Frames. |
| `JUMP_IF_FALSE` | Zielindex | Bedingter Sprung, wenn der Stack-Top falsy ist. |
| `CALL` | `(Funktionsname, Arg-Anzahl)` | Argumente vom Stack sammeln und Funktion aufrufen. |
| `POP` | – | Obersten Stack-Eintrag verwerfen (z. B. für Bare-Calls). |
| `RETURN` | – | Funktion beenden; optional den obersten Stack-Wert als Ergebnis zurückgeben. |

## Container-Strukturen

`src/native_ir.py` bündelt die zugehörigen Dataklassen:

- `Instruction`: Einzelne Opcode/Operand-Kombination.
- `FunctionIR`: Bytecode und Parameterliste einer Funktion.
- `ProgramIR`: Entry-Block und Funktions-Tabelle für das Programm.

Ein Helfer `format_program(program)` gibt eine menschenlesbare Ansicht der Instruktionen aus und erleichtert Snapshot-Tests.

## Beispiel

```text
entry[00]: PUSH_CONST 1
entry[01]: STORE a
entry[02]: PUSH_CONST 2
entry[03]: STORE b
entry[04]: LOAD a
entry[05]: LOAD b
entry[06]: BINARY +
entry[07]: PRINT 1
entry[08]: RETURN
function add(x, y)
  add[00]: LOAD x
  add[01]: LOAD y
  add[02]: BINARY +
  add[03]: RETURN
```

Der Ausschnitt oben entsteht z. B. für `print(add(1, 2));` und zeigt den Entry-Block sowie die kompilierten Instruktionen der Funktion `add`.
