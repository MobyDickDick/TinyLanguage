# TinyCPU ALU-Skizze

Diese Skizze ist bewusst ein Marschhalt-Artefakt: Sie beschreibt die ALU als
separaten Block, ohne die aktuell problematische Fetch/Decode-Schaltung weiter
zu verändern.

## Zielbreiten

- Datenpfad: 16 Bit signed/unsigned Zweierkomplement.
- Opcode/Operation-Select: 8 Bit, damit mehr als 32 Operationen eindeutig
  adressierbar sind.
- Instruktionswort: 24 Bit als Logisim-freundliche Breite, aufgeteilt in
  `OPCODE[23:16]` und `OPERAND[15:0]`.

## Blockbild

```text
                 +------------------------------+
ACC[15:0] ------>|                              |
                 |                              |----> RESULT[15:0]
OPERAND[15:0] -->|           TinyCPU ALU         |----> ZERO
                 |                              |----> NEGATIVE
OP_SEL[7:0] ---->|                              |----> OVERFLOW
                 |                              |----> DIV_BY_ZERO
VALID_IN ------->|                              |----> INVALID
                 +------------------------------+
```

## Interne Funktionsgruppen

```text
ACC[15:0] --------------------+--------------------+-------------------+
                              |                    |                   |
OPERAND[15:0] ----------------|--------------------|-------------------|
                              v                    v                   v
                       +-------------+      +-------------+      +-------------+
OP_SEL[7:0] ---------->| Add/Sub/Cmp |      | Mul/Div     |      | Logic       |
                       |             |      |             |      | AND/OR/NOT  |
                       +------+------+      +------+------+      +------+------+
                              |                    |                    |
                              +---------+----------+----------+---------+
                                        |                     |
                                        v                     v
                                  +------------+        +------------+
OP_SEL[7:0] -------------------->| Result Mux |------->| Flag Logic |
                                  +------------+        +------------+
                                        |                     |
                                        v                     v
                                  RESULT[15:0]     ZERO/NEG/OVF/DIV0/INVALID
```

## Vorgeschlagene Logisim-Teile

| Gruppe | Bauteile | Breiten |
|---|---|---|
| Add/Sub | `Adder`, XOR-Inverter für Subtraktion, Carry-In-Auswahl | 16 Bit |
| Compare | `Comparator` gegen `0` und optional gegen Operand | 16 Bit |
| Logic | `AND Gate`, `OR Gate`, `NOT Gate` oder Bitwise-Gatter | 16 Bit |
| Mul/Div | zunächst Platzhalter/Subcircuit, später echte Implementierung | 16 Bit |
| Auswahl | Multiplexer, gesteuert durch dekodierte `OP_SEL`-Leitungen | 16 Bit |
| Flags | Comparator/Sign-Bit/Overflow- und Div0-Logik | 1 Bit je Flag |

## Minimale externe Schnittstelle

| Pin | Richtung | Breite | Bedeutung |
|---|---:|---:|---|
| `ACC` | Eingang | 16 | aktueller Akkumulatorwert |
| `OPERAND` | Eingang | 16 | unmittelbarer Wert oder gelesener Speicherwert |
| `OP_SEL` | Eingang | 8 | dekodierter ALU-Opcode |
| `VALID_IN` | Eingang | 1 | Operand/ACC gültig |
| `RESULT` | Ausgang | 16 | ALU-Ergebnis |
| `ZERO` | Ausgang | 1 | `RESULT == 0` |
| `NEGATIVE` | Ausgang | 1 | `RESULT[15] == 1` |
| `OVERFLOW` | Ausgang | 1 | arithmetischer Überlauf |
| `DIV_BY_ZERO` | Ausgang | 1 | Division durch 0 angefordert |
| `INVALID` | Ausgang | 1 | ungültiger Operand oder ungültige Operation |

## Nächster sinnvoller Schritt

1. Diese ALU als eigenes Logisim-Blatt `ALU` anlegen.
2. Nur `ACC`, `OPERAND`, `OP_SEL` und die Flag-Ausgänge verdrahten.
3. Erst danach Fetch/Decode wieder anfassen und dabei auf 24-Bit-Instruktionen
   und 8-Bit-Opcode umstellen.
