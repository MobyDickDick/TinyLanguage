# TinyCPU: Mikrocomputer, Assemblersprache und Simulator

TinyCPU ist eine bewusst kleine, vollständige Lehrmaschine für TinyLanguage. Sie
ist eine **16-Bit-Akkumulatormaschine** mit 4096 Speicherzellen (konfigurierbar),
Adressregister, Programmzähler, Ein-/Ausgabe, bedingten Sprüngen und einer
strikten Fehlersemantik. Der Simulator liegt in `src/tiny_cpu_vm.py`, der
Assembler in `src/tiny_cpu_assembler.py` und die ISA in `src/tiny_cpu_isa.py`.

## Leitprinzip: Fehler sind keine Modulo-Arithmetik

Jedes Register und jede Speicherzelle besteht logisch aus `(value, valid)`. Eine
Operation erzeugt nur dann einen gültigen Wert, wenn alle Eingaben gültig sind,
die Operation erlaubt ist und das Ergebnis zwischen -32768 und 32767 liegt.
Andernfalls wird das Ziel zu `0 INVALID` und ein spezifisches Fehlerflag gesetzt.
Invalidität pflanzt sich bei weiterer Verwendung fort.

Fehlerflags sind **sticky**. `CLEAR_ERROR()` löscht sie, repariert aber keine
invaliden Werte. Beispielsweise macht erst `LOAD_CONST(5)` den Akkumulator wieder
gültig. Unterstützte Flags sind `OVF`, `DIV0`, `ADDR`, `INV`, `ILL` und `INPUT`;
`ERR` entspricht „mindestens ein Fehlerflag ist gesetzt“.

## Syntax

Jede Instruktion verwendet Funktionsschreibweise. Kommentare beginnen mit `;`
oder `//`. Direkte Operanden sind zwingend; deshalb ist `ADD_ADDRESS()` ein
Assemblerfehler, während `ADD_ADDRESS_REGISTER()` korrekt ist.

```text
sum := 100
ADC := ADD_CONST

LOAD_CONST(7)
STORE_ADDRESS(sum)
LOAD_CONST(5)
ADC(3)
ADD_ADDRESS(sum)
PRINT()
HALT()
```

`name := 100` definiert einen Wertalias, `ADC := ADD_CONST` einen
Instruktionsalias. Sprungziele werden mit `name:` definiert. Häufige Kurzformen
(`LDC`, `LDA`, `STA`, `ADC`, `ADA`, `JMP`, `JZ`, `JNZ`, `JNEG`, `JER`, `CER`,
`HLT`) sind eingebaut; kanonische Namen bleiben die dokumentierte Schnittstelle.

## Befehlssatz

Die Operationen `LOAD`, `ADD`, `SUB`, `MUL`, `DIV`, `AND` und `OR` besitzen je
vier explizite Quellen:

```text
OP_CONST(value)
OP_ADDRESS(address)
OP_ADDRESS_REGISTER()
OP_ADDRESS_REGISTER_PLUS_OFFSET(offset)
```

`STORE` besitzt die drei beschreibbaren Zielvarianten (kein `STORE_CONST`). Das
Adressregister wird durch `LOAD_ADDRESS_REGISTER_CONST(value)` oder
`LOAD_ADDRESS_REGISTER_ADDRESS(address)` geladen. Hinzu kommen:

| Gruppe | Instruktionen |
|---|---|
| Logik | `NOT()` |
| Sprünge | `JUMP_ADDRESS`, `JUMP_ZERO`, `JUMP_NOT_ZERO`, `JUMP_NEGATIVE`, `JUMP_ERROR`, `JUMP_NOT_ERROR` |
| Fehler | `CLEAR_ERROR()`, `HALT_ERROR()` |
| I/O | `INPUT()`, `PRINT()`, `PRINT_ADDRESS(address)` |
| Ablauf | `HALT()` |

Sprunginstruktionen erwarten ein Label oder eine numerische Instruktionsadresse.
`INPUT()` liest die nächste mit `--input` übergebene Zahl. Eine fehlende oder
ungültige Eingabe setzt `INPUT` und invalidiert den Akkumulator.

## Beispiel und Aufruf

```text
counter := 20
LOAD_CONST(3)
STORE_ADDRESS(counter)

loop:
LOAD_ADDRESS(counter)
PRINT()
SUB_CONST(1)
STORE_ADDRESS(counter)
JUMP_NOT_ZERO(loop)
HALT()
```

```bash
python src/tiny_cpu_cli.py program.tcpu
python src/tiny_cpu_cli.py --disassemble program.tcpu
python src/tiny_cpu_cli.py --input 41 input_program.tcpu
```

Der Prozess endet mit Status 1, wenn `HALT_ERROR()` ausgeführt wird oder bei
`HALT()` noch ein Fehlerflag gesetzt ist. Eine Schrittgrenze schützt vor
unbeabsichtigten Endlosschleifen.

## Crosscompiler-Richtung

Die stabile Grenze für ein künftiges Backend ist das kanonische
`Instruction`/`Program`-Modell. Vorgesehen ist:

```text
TinyLanguage-Subset -> Native IR -> TinyCPU Program
TinyCPU Program -> Kontrollflussanalyse -> kanonisches TinyLanguage-Subset
```

Die Rückrichtung ist ein Decompiler und kann ursprüngliche Namen oder
Kontrollstrukturen nicht allgemein rekonstruieren. Daher wird sie bewusst auf
eine kanonische Teilmenge (Zahlen, Variablen, Arithmetik, `if`, `while`, einfache
I/O) begrenzt; Simulator und Assembler funktionieren unabhängig davon bereits
als vollständiger kleiner Mikrocomputer.
