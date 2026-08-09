# Arbeitsplan: TinyCPU-Hardware

Dieser Plan führt die vorhandene symbolische ISA schrittweise zu einer in
Logisim-evolution ausführbaren TinyCPU. Die Python-VM bleibt während des
gesamten Aufbaus das Referenzmodell. Jeder Schritt muss einzeln prüfbar sein;
ein Maschinenformat wird erst festgelegt, wenn Datenpfad und Steuerwerk stabil
sind.

## Ziel und Definition of Done

Das erste Zielsystem verwendet 16 Datenbits, 12 Adressbits und 4096
Speicherzellen. Fertig ist die TinyCPU, wenn ein Logisim-Testlauf das
Kernprogramm aus Arbeitspaket 5 taktweise mit der VM vergleichen kann und
Ausgabe, Haltzustand, Register, Speicher-Validität und Fehlerflags
übereinstimmen.

## Arbeitspakete

| AP | Inhalt | Ergebnis und Abnahme |
|---|---|---|
| **1. Hardwarevertrag einfrieren** | Zielprofil, benötigte Subcircuits, Register, RAM-Breiten und Fehlerbits maschinenlesbar festlegen. | Versioniertes Profil; der Inspector bestätigt, dass `TinyCPU.circ` den Vertrag erfüllt. |
| **2. Daten- und Adresspfad** | Akkumulator und Adressregister samt Valid-Bits verdrahten; Zero und Negative ableiten; Offset-Addition ergänzen. | Register lassen sich taktsynchron laden; Statusausgänge entsprechen der VM für Grenzwerte. |
| **3. Speicher und Fehlerregister** | Daten- und Valid-RAM an gemeinsame Adresse und Write-Enable legen; sechs set-dominante Sticky-Flags und `CLEAR_ERROR` bauen. | Lesen, Schreiben, Invaliditätsfortpflanzung und Set-vor-Clear-Priorität sind getestet. |
| **4. Fetch und Decode** | PC, Instruktions-ROM und Steuerwerk für `LOAD_CONST`, `STORE_ADDRESS`, `ADD_ADDRESS`, `JUMP_NOT_ZERO`, `PRINT` und `HALT` aufbauen. | Jede Kerninstruktion besitzt einen dokumentierten Taktablauf; ungültiger PC setzt `ADDR` und hält fehlerhaft. |
| **5. Kernprogramm integrieren** | Zählschleife als reproduzierbare Fixture ausführen und Zustände nach jedem Takt gegen die VM vergleichen. | Identische Trace, Ausgabe und Haltstatus in VM und Logisim. |
| **6. ISA vervollständigen** | Weitere Adressierungsarten, Arithmetik, Logik, Sprünge und I/O ergänzen. | Parametrisierte Positiv- und Fehlertests decken jede Instruktion ab. |
| **7. Maschinenformat und Tooling** | Versionierte Opcode-Tabelle und Wortlayout definieren; Encoder, ROM-Image und Listing erzeugen. | Roundtrip-Tests und ein durch den Encoder geladenes Logisim-Programm bestehen. |
| **8. Abschluss und Dokumentation** | Bedienung, Schaltplanarchitektur und automatisierte Regressionstests vervollständigen. | Ein frischer Checkout kann die dokumentierten Prüfungen reproduzieren. |

## Abhängigkeiten und Reihenfolge

AP 1 ist die gemeinsame Schnittstelle aller folgenden Pakete. AP 2 und AP 3
können danach getrennt entwickelt werden; AP 4 benötigt beide. AP 5 friert den
Kern als Integrationsbasis ein, bevor AP 6 den Befehlssatz verbreitert. Das
binäre Format in AP 7 kommt bewusst spät, damit frühe Schaltungsänderungen
keine dauerhaft inkompatiblen Opcodes erzeugen.

## Stand

- [x] **AP 1:** `hardware/logisim/tinycpu-16-12.json` beschreibt den Vertrag;
  `tiny_cpu_circuit.py --profile … --contract-only` prüft ihn unabhängig von
  der noch fehlenden Verdrahtung.
- [x] **AP 2:** Daten- und Adresspfad; `Datapath` lädt Akkumulator und
  Valid-Bit an derselben Taktflanke und leitet `ZERO`/`NEGATIVE` über einen
  vorzeichenbehafteten Vergleicher ab. `AddressPath` lädt Adressregister und
  Valid-Bit synchron und stellt die 12-Bit-Offset-Summe samt Carry bereit. Das
  Hardwareprofil und die Netlist-Tests frieren diese Schnittstellen ein.
- [x] **AP 3:** Speicher und Fehlerregister; Daten- und Valid-RAM teilen sich
  Adresse, Write-Enable und Takt. Sechs set-dominante Sticky-Flags implementieren
  `SET OR (Q AND NOT CLEAR_ERROR)` und exportieren ihren Zustand.
- [x] **AP 4:** Fetch und Decode; ein 12-Bit-PC adressiert das interne ROM,
  `CORE_DECODER` erzeugt die Steuersignale des Kernbefehlssatzes und
  `PC_RANGE` setzt bei einem PC außerhalb `PROGRAM_LIMIT` gleichzeitig `ADDR`
  und `HALT_ERROR`. Die Taktabläufe und das vorläufige interne ROM-Wort sind
  in `hardware/logisim/README.md` dokumentiert und im Hardwareprofil fixiert.
- [x] **AP 5:** Kernprogramm integrieren; die ROM-Zählschleife und ihr
  versionierter 17-Takt-Trace liegen unter `hardware/logisim/`. Der
  Trace-Comparator prüft PC, Akkumulator, Status, Speicherzellen, Ausgabe,
  Fehlerflags und Haltzustand an jeder Taktflanke gegen die Python-VM.
- [x] **AP 6:** ISA vervollständigen; `FetchDecode` exportiert die vollständige
  symbolische ISA-Steuerfläche für alle Adressierungsarten, ALU-Operationen,
  Sprünge und I/O. Profil und parametrisierte Strukturtests gleichen jeden
  Befehl sowie alle Bedingungs- und Fehlerpfade mit der Python-ISA ab.
- [x] **AP 7:** Maschinenformat und Tooling; die versionierte Opcode-Tabelle
  definiert ein 22-Bit-Wort aus 6-Bit-Opcode und 16-Bit-Operand. Der Encoder
  erzeugt ROM-Image und Listing der Zählschleife, das Logisim-ROM lädt exakt
  dieses Image, und Roundtrip- sowie Negativtests sichern das Format ab.
- [x] **AP 8:** Abschluss und Dokumentation; die Bedienungs- und
  Architekturhinweise beschreiben den Schaltplan sowie die Simulatorgrenze.
  `tiny_cpu_verify.py` prüft aus einem frischen Checkout Vertrag, Verdrahtung,
  generierte Artefakte, eingebettetes ROM und den 17-Takt-Referenztrace mit
  einem einzigen reproduzierbaren Kommando.

## Baseline-Pflege

Nach Abschluss der acht Arbeitspakete ist das Abnahmekommando als eigener
Schritt im Haupt-CI-Job verankert. Dadurch schlagen Änderungen an Vertrag,
Schaltung, Maschinenformat, generierten ROM-/Listing-Artefakten oder
Referenztrace bereits vor der allgemeinen Testsuite mit einer gezielten
TinyCPU-Diagnose fehl. Ein Regressionstest schützt sowohl den Namen des Gates
als auch das dokumentierte Kommando vor unbeabsichtigtem Entfernen.

## Folgeschritt: elektrische Top-Level-Integration

Die abgeschlossene AP-1-bis-AP-8-Baseline beschreibt und prüft die einzelnen
Blöcke, während das Top-Level weiterhin eine Integrationsgrenze ist. Die
Übersichtsseite `TinyCPU` in `hardware/logisim/TinyCPU.circ` wird manuell
weitergebaut und gilt in ihrer eingecheckten Anordnung und Verdrahtung als
maßgeblich. Automatisch erzeugte Diagnoseblätter dienen nur der isolierten
Prüfung; sie dürfen die Übersichtsseite weder ersetzen noch deren Bauteile
verschieben.

Der aktuelle Stand verteilt den gemeinsamen Takt an Fetch/Decode, Datenpfad,
Adresspfad, Speicher und Fehlerflags. Ein unabhängiger `RESET`-Eingang setzt
ausschließlich Fetch/Decode und damit den Programmzähler zurück. Alle weiteren
Netze werden anhand der
[Top-Level-Vorlage](tiny_cpu_top_level_template.md) einzeln ergänzt. Dabei wird
jede Leitung rechtwinklig in einem freien Korridor um Bauteile herumgeführt;
eine Leitung durch ein Symbol oder über einen fremden Anschluss ist auch dann
unzulässig, wenn die XML-Strukturprüfung sie akzeptieren würde. Als Nächstes
werden Steuernetze, Datenpfade und zuletzt Halt-/Fehlerausgänge jeweils getrennt
verdrahtet und abgenommen.

Als erstes Decode-Netz führt die Übersichtsseite nun den 22-Bit-Ausgang
`FetchDecode.OPCODE` zum gleichnamigen Eingang des separat platzierten
`FetchDecodeControls`-Blocks. Die Route bleibt von `CLK` und `RESET` isoliert
und nutzt den freien linken Außenkorridor. Das erste einbittige Decodesignal
`CLEAR_ERROR` ist ebenfalls über den freien rechten Außenkorridor mit dem
gleichnamigen Eingang der Fehlerflags verbunden und bleibt von Takt, Reset und
Opcode-Bus getrennt. `SET_OVF`, das erste der sechs
Sticky-Fehler-Setzsignale, nutzt daneben eine eigene äußere Leitung und bleibt
von den vorhandenen Netzen isoliert. `SET_DIV0` folgt in einer weiteren
äußeren Leitung und ist ebenfalls ausschließlich mit dem gleichnamigen
Fehlerflag-Eingang verbunden. Auch `SET_ADDR`, `SET_INV`, `SET_ILL` und
`SET_INPUT` erreichen den jeweils gleichnamigen Fehlerflag-Eingang über eigene,
voneinander isolierte äußere Leitungen. Damit sind alle Sticky-Fehler-Setznetze
der Decode-Steuerung angeschlossen; als nächstes folgen die Datenpfad-Steuernetze.
Die nachträgliche visuelle Korrektur ist strukturell nachvollzogen: Der
Opcode-Splitter reicht nur die sechs höchstwertigen Bits weiter, `RESET`
erreicht wieder ausschließlich Fetch/Decode, und die Tests verwenden die
tatsächlichen Anschlüsse der neu platzierten Steuer- und Fehlerblöcke. Mit
`LOAD_CONST` nach `Datapath.ACC_LOAD` ist außerdem das erste
Datenpfad-Steuernetz ergänzt; weitere Ladeursachen benötigen vor dem Anschluss
eine explizite Zusammenfassung, damit Decoder-Ausgänge nicht gegeneinander
treiben. Diese Zusammenfassung beginnt nun mit dem benannten ODER-Gatter
`ACC_LOAD_REQUEST`: Es führt `LOAD_CONST` und `LOAD_ADDRESS` auf
`Datapath.ACC_LOAD`, hält aber beide Decoder-Ausgänge auf getrennten Netzen.
Auch `LOAD_ADDRESS_REGISTER` und `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` sind nun
als getrennte Eingänge angeschlossen. Damit deckt das ausdrücklich vierfach
ausgelegte Gatter die gesamte `LOAD_*`-Familie ab, ohne den benachbarten
`DATA_IN`-Eingang anzusteuern. Die vier `ADD_*`-Steuersignale belegen ebenfalls
je einen eigenen Eingang. Das nun ausdrücklich mit sechzehn Eingängen ausgelegte Gatter deckt die
vollständigen `LOAD_*`-, `ADD_*`-, `SUB_*`- und `MUL_*`-Familien ab, ohne ihre
Decoder-Ausgänge elektrisch zu koppeln. Als nächste Akkumulator-schreibende
Befehlsgruppe folgen die vier `DIV_*`-Steuersignale.
