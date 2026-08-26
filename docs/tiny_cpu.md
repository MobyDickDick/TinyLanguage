# TinyCPU: Mikrocomputer, Assemblersprache und Simulator

TinyCPU ist eine bewusst kleine, vollständige Lehrmaschine für TinyLanguage. Sie
ist standardmäßig eine **16-Bit-Akkumulatormaschine** mit einem 12-Bit-Adressbus
und 4096 Speicherzellen. Daten- und Adressbreite sind unabhängig konfigurierbar.
Die Maschine besitzt Adressregister, Programmzähler, Ein-/Ausgabe, bedingte
Sprünge und eine strikte Fehlersemantik. Der Simulator liegt in
`src/tiny_cpu_vm.py`, der
Assembler in `src/tiny_cpu_assembler.py` und die ISA in `src/tiny_cpu_isa.py`.

## Empfehlung für die Schaltungssimulation

Für den Nachbau der TinyCPU wird **[Logisim-evolution](https://github.com/logisim-evolution/logisim-evolution)**
empfohlen. Es ist plattformübergreifend, für Lehrschaltungen gut nachvollziehbar
und bietet die für TinyCPU benötigten Register-, RAM/ROM-, ALU-, Splitter- und
Taktbausteine. Vor allem lässt sich der Prozessor hierarchisch in Datenpfad,
Steuerwerk und Ein-/Ausgabe zerlegen. Die mitgelieferte Python-VM bleibt dabei
die Referenz: Ein Logisim-Test gilt als korrekt, wenn Register, Speicher,
Ausgaben und Fehlerflags nach jedem Takt mit `src/tiny_cpu_vm.py` übereinstimmen.

Als Alternative eignet sich **[Digital](https://github.com/hneemann/Digital)**,
insbesondere wenn automatische Schaltungstests und eine kompakte
Java-Anwendung wichtiger sind. Für gemeinsames Arbeiten und eine leicht
zugängliche Dokumentation wird Logisim-evolution bevorzugt. Browserbasierte
Werkzeuge sind für eine Demonstration brauchbar, erschweren aber die genaue
Abbildung der unten beschriebenen Invalid-Bits und Sticky-Fehlerflags.

Das Maschinenformat ist inzwischen versioniert: Ein Instruktionswort umfasst
22 Bit aus einem 6-Bit-Opcode und einem 16-Bit-Operanden. `assemble()` liefert
weiterhin ein `Program` aus symbolischen `Instruction`-Objekten; anschließend
erzeugt `src/tiny_cpu_machine.py` daraus die Maschinenwörter, ein von
Logisim-evolution lesbares ROM-Image und eine menschenlesbare Listing-Datei.
Die Opcode-Tabelle liegt in `hardware/logisim/tinycpu-machine-v1.json`. Das
AP-5-Programm, sein ROM-Abbild und sein Listing dienen als reproduzierbare
Referenzartefakte für den Encoder und das eingebettete Logisim-ROM.

### Hardwarevertrag für den Nachbau

Die kleinste kompatible Schaltung besteht aus folgenden Zuständen und Signalen:

| Teil | Erforderlicher Zustand / Verhalten |
|---|---|
| Programmsteuerung | vorzeichenloser `address_bits` breiter PC; vor der Ausführung auf die Folgeinstruktion erhöhen |
| Datenpfad | `data_bits` breiter Akkumulator im Zweierkomplement sowie Zero- und Negative-Status |
| Adressierung | `address_bits` breites Adressregister mit eigenem Valid-Bit |
| Datenspeicher | je Zelle ein `data_bits` breiter Wert **und ein Valid-Bit** |
| Fehlerregister | sticky Bits `OVF`, `DIV0`, `ADDR`, `INV`, `ILL`, `INPUT`; deren OR ist `ERR` |
| Ein-/Ausgabe | Eingabewarteschlange zum Akkumulator; `PRINT` schreibt einen gültigen Wert auf den Ausgabekanal |
| Halt | getrennte Zustände für normal angehalten und mit Fehler angehalten |

Das Valid-Bit ist kein optionales Debugsignal: Ohne ein Valid-Bit für
Akkumulator, Adressregister und jede Speicherzelle kann die festgelegte
Fehlerfortpflanzung nicht implementiert werden. `CLEAR_ERROR()` löscht nur das
Fehlerregister, niemals Valid-Bits. Zero ist genau dann gesetzt, wenn der im
Akkumulator gespeicherte Wert null ist; bedingte Zero-/Not-Zero-Sprünge werden
jedoch nur bei gültigem Akkumulator genommen. Negative ist nur für einen
gültigen negativen Akkumulator gesetzt.

Für eine taktsynchrone Implementierung ist folgende Reihenfolge beobachtbar:

1. Instruktion an `PC` lesen; eine ungültige Instruktionsadresse setzt `ADDR`
   und hält mit Fehler an.
2. `PC` auf die Folgeinstruktion erhöhen.
3. Operanden lesen, Operation und Gültigkeitsprüfung ausführen.
4. Ergebnis, Flags, Speicher oder Sprungziel gemeinsam an der Taktflanke
   übernehmen.

Sprungziele sind **Instruktionsindizes**, keine Byteadressen. Ein genommener
Sprung außerhalb des geladenen Programms setzt `ADDR`; ein nicht genommener
Sprung validiert sein Ziel nicht. Division ganzer Zahlen schneidet gegen null
ab. `AND`, `OR` und `NOT` arbeiten bitweise auf der gewählten
Zweierkomplementbreite. Arithmetische Ergebnisse außerhalb des signierten
Datenbereichs setzen `OVF` und schreiben `0 INVALID` in den Akkumulator.

### TinyCPU.circ testen

Eine kurze deutschsprachige Schritt-für-Schritt-Anleitung für den vollständigen
elektrischen Test, den Test mit einer bereits vorhandenen Logisim-JAR und die
visuelle Fehlersuche steht in
[`docs/tiny_cpu_test_guide.md`](tiny_cpu_test_guide.md). Der verbindliche
Kompletttest wird aus dem Repository-Hauptverzeichnis mit
`scripts/test-logisim.sh` gestartet.

### Abgenommener Aufbau in Logisim-evolution

Das in Logisim-evolution 4.1.x ausführbare Projekt liegt unter
[`hardware/logisim/TinyCPU.circ`](../hardware/logisim/TinyCPU.circ). Es legt das
16/12-Bit-Profil, die Subcircuits und die zwingenden Valid-/Fehlerzustände an.
Architektur und elektrische AP-12-Abnahme sind in
[`hardware/logisim/README.md`](../hardware/logisim/README.md) festgehalten.
Die folgende Liste beschreibt die bereits ausgeführte Aufbau- und
Abnahmereihenfolge, nicht fehlende Verdrahtung: Der Inspector meldet
`TinyCPUMain: connected`, und die elektrische AP-11-Matrix deckt alle 50
Opcodes des versionierten Maschinenformats einschließlich ihrer Positiv- und
Fehlerfälle ab. Damit sind sowohl sämtliche Top-Level-Pins als auch der
dokumentierte Befehlssatz umgesetzt; sichtbare Leitungskreuzungen ohne
Abzweigpunkt sind in Logisim bewusst keine elektrischen Verbindungen.

Mit `PYTHONPATH=src python src/tiny_cpu_circuit.py
hardware/logisim/TinyCPU.circ` lässt sich das Projekt ohne Logisim zunächst
strukturell prüfen. Der Prüfer liest das `.circ`-XML, meldet fehlende Leitungen
und endet bei Vertragsverletzungen mit Status 1. Er simuliert bewusst
nicht die gesamte Logisim-Bauteilbibliothek; für elektrische Simulation bleibt
Logisim-evolution zuständig, während `tiny_cpu_vm.py` die CPU-Sollsemantik
liefert. Ein erfolgreicher Strukturcheck ersetzt deshalb nicht den oben
verlinkten elektrischen Kompletttest.

Bei ungewöhnlich hoher CPU- oder Speichernutzung können die fünf eigenständigen
Projekte unter [`hardware/logisim/diagnostics/`](../hardware/logisim/diagnostics/)
einzeln geladen werden. So lassen sich Fetch/Decode, Datenpfad, Adresspfad,
Speicher und Fehlerflags untersuchen, ohne zugleich alle anderen Schaltungsblätter
zu laden. Erzeugung, Größenvergleich und eine empfohlene Testreihenfolge sind im
Hardware-[README](../hardware/logisim/README.md#ressourcenverbrauch-eingrenzen)
dokumentiert.

1. Das Zielprofil wurde auf **16 Datenbits, 12 Adressbits und 4096
   Speicherzellen** festgelegt.
2. Datenpfad (Akkumulator, ALU, Status), Adresspfad (Adressregister,
   Offset-Addierer), Speicher und Steuerwerk wurden als getrennte Subcircuits
   gebaut.
3. Das Valid-RAM liegt parallel zum Daten-RAM; beide verwenden dieselbe Adresse
   und denselben Write-Enable.
4. Die Fehlerflags sind set-dominante Register; `CLEAR_ERROR` bildet die einzige
   gemeinsame Clear-Leitung.
5. `LOAD_CONST`, `STORE_ADDRESS`, `ADD_ADDRESS`, `JUMP_NOT_ZERO`, `PRINT` und
   `HALT` wurden zuerst mit dem Schleifenbeispiel abgenommen.
6. Anschließend wurden die übrigen Adressierungsarten und gezielten Fehlerfälle
   ergänzt und in der vollständigen elektrischen Matrix abgenommen.

Für reproduzierbare Vergleiche sollte jeder Schaltungstest neben dem
Logisim-Projekt auch die `.tcpu`-Quelldatei, das verwendete Zielprofil, die
Eingabefolge sowie erwartete Ausgaben und Fehlerflags enthalten.

## Leitprinzip: Fehler sind keine Modulo-Arithmetik

Jedes Register und jede Speicherzelle besteht logisch aus `(value, valid)`. Eine
Operation erzeugt nur dann einen gültigen Wert, wenn alle Eingaben gültig sind,
die Operation erlaubt ist und das Ergebnis im vorzeichenbehafteten Wertebereich
des konfigurierten Datenbusses liegt (bei 16 Bit: -32768 bis 32767).
Andernfalls wird das Ziel zu `0 INVALID` und ein spezifisches Fehlerflag gesetzt.
Invalidität pflanzt sich bei weiterer Verwendung fort.

## Skaleninvariante Breiten

Die ISA und Assemblersprache enthalten absichtlich keine fest codierte
Operandenbreite: Zahlen, Adressen, Offsets und Sprungziele werden symbolisch als
Ganzzahlen dargestellt. Erst eine konkrete `TinyCPU`-Instanz legt mit
`data_bits` und `address_bits` die Hardwaregrenzen fest. Dadurch bleibt dasselbe
Assemblerprogramm beispielsweise auf einer 8/8-, 16/12- oder 32/20-Maschine
verwendbar, sofern seine Werte und Adressen in die gewählten Bereiche passen.

Der Datenbus verwendet Zweierkomplement und bestimmt Akkumulator,
Speicherzellen, Ein-/Ausgabewerte und arithmetischen Überlauf. Der Adressbus ist
vorzeichenlos und bestimmt unabhängig davon Adressregister, effektive Adressen,
Programmzähler und die maximal adressierbare Speichergröße. `memory_size` darf
kleiner als der Adressraum sein (teilbestückter Speicher), aber nie größer.

```python
TinyCPU(data_bits=8, address_bits=8, memory_size=256)
TinyCPU(data_bits=32, address_bits=20, memory_size=65536)
```

Diese Parametrisierung ist semantisch skaleninvariant; ein späteres binäres
Instruktionsformat muss seine Kodierungsbreite ebenfalls aus dem Zielprofil
ableiten und darf sie nicht in Opcodes festschreiben.

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

Die Operationen `LOAD`, `ADD`, `SUB`, `MUL`, `DIV`, `AND`, `OR` und `XOR`
besitzen je vier explizite Quellen:

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

Ausführbare Beispielprogramme liegen unter [`examples/tiny_cpu/`](../examples/tiny_cpu/).
Für jede der unten aufgeführten Operationen gibt es ein eigenes Programm; bei
Operationen mit mehreren Adressierungsarten führt dieses alle Varianten aus.
Zu jeder `.tcpu`-Datei gehört eine gleichnamige `.stdout`-Datei mit der
vollständigen erwarteten Ausgabe. Optional liefern `.args` die CLI-Argumente
und `.exit` den erwarteten, von null abweichenden Exit-Status. Der Test
`tests/detailtests/test_tiny_cpu_examples.py` findet alle diese Programme
automatisch, führt sie über die öffentliche CLI aus und vergleicht Ausgabe,
Fehlerausgabe und Exit-Status. Ein neues Ausgabebeispiel benötigt daher nur
die Quelldatei und ihren Output-Snapshot. Ein zusätzlicher Abdeckungstest stellt
sicher, dass keine Operation oder Adressierungsart fehlt. Die Beispielsuite
lässt sich gezielt so starten:

```bash
python -m pytest tests/detailtests/test_tiny_cpu_examples.py
```

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
python src/tiny_cpu_cli.py --data-bits 8 --address-bits 9 --memory-size 512 program.tcpu
```

Mit `--data-bits` und `--address-bits` wird das Zielprofil auch beim CLI-Aufruf
festgelegt. `--memory-size` darf den durch den Adressbus bestimmten Adressraum
nicht überschreiten; die Standardwerte sind 16, 12 und 4096.

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
