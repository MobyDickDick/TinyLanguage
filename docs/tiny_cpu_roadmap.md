# Arbeitsplan: TinyCPU-Hardware

Dieser Plan führt die vorhandene symbolische ISA schrittweise zu einer in
Logisim-evolution ausführbaren TinyCPU. Die Python-VM bleibt während des
gesamten Aufbaus das Referenzmodell. Jeder Schritt muss einzeln prüfbar sein;
ein Maschinenformat wird erst festgelegt, wenn Datenpfad und Steuerwerk stabil
sind.

## Ziel und Definition of Done

Das erste Zielsystem verwendet 16 Datenbits, 12 Adressbits und 4096
Speicherzellen. Die AP-1-bis-AP-8-Baseline stellt Schaltung, Maschinenformat
und ein VM-basiertes Referenzmodell bereit, ist aber noch kein Nachweis einer
elektrisch ausgeführten CPU. Fertig ist die TinyCPU erst, wenn ein gepinnter
Logisim-evolution-Testlauf das Kernprogramm aus Arbeitspaket 5 taktweise mit
der VM vergleicht, die gesamte ISA in Positiv- und Fehlerfällen elektrisch
abdeckt und Ausgabe, Haltzustand, Register, Speicher-Validität und Fehlerflags
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
| **9. Reale Simulator-Basis** | Logisim-evolution und Java für lokale sowie CI-Läufe pinnen; `TinyCPU.circ` headless laden. | Ein frischer Checkout startet die festgelegte Simulatorversion, protokolliert sie und bricht bei Lade- oder Schaltungsfehlern ab. |
| **10. Elektrischen Kerntrace abnehmen** | Das AP-5-ROM im echten Simulator takten und die festgelegten Integrationspins per Tabellenlogger exportieren. | Der unveränderte CSV-/TSV-Export besteht `tiny_cpu_trace.py --integration --check-logisim-table`; das CI-Artefakt belegt die elektrische Ausführung. |
| **11. Elektrische ISA-Matrix** | Jede Instruktionsfamilie sowie Invalidität, Adress-, Overflow-, Div0-, Illegal- und Input-Fehler mit kleinen ROM-Fixtures ausführen. | Parametrisierte Logisim/VM-Vergleiche decken jeden Opcode und jedes Sticky-Fehlerbit ab; Abdeckungsmetadaten verhindern ungetestete Opcodes. |
| **12. Hardware-Abschluss** | Reset-/Wiederanlauf-, Mehrzyklus- und reproduzierbare Release-Abnahme dokumentieren und alle elektrischen Gates verpflichtend machen. | Das Abschlusskommando erzeugt die Nachweisartefakte aus einem frischen Checkout; kein Simulator-Test ist mehr optional und die Definition of Done ist erfüllt. |
| **13. 1.0-Releasevertrag einfrieren** | Öffentliche Hardware-, ISA-, Maschinenformat-, CLI- und Nachweisgrenzen versionieren. | Ein maschinenlesbarer Releasevertrag wird gegen vorhandene Profile, Tool-Versionen und CLI-Oberflächen geprüft. |
| **14. Reproduzierbare Distribution bauen** | Quell- und Simulator-Bundle mit kanonischem Inventar, Digests, Dokumentation und AP-12-Nachweisen erzeugen. | Zwei saubere Builds liefern identische Payloads; das extrahierte Bundle lässt sich offline verifizieren. |
| **15. TinyCPU 1.0 qualifizieren und veröffentlichen** | Den exakten Release Candidate elektrisch abnehmen, im Clean Room testen und mit Release Notes sowie authentifizierten Prüfsummen veröffentlichen. | Alle Nachweise referenzieren denselben Commit und dieselben Digests; erst danach gilt TinyCPU 1.0 als veröffentlicht. |

## Abhängigkeiten und Reihenfolge

AP 1 ist die gemeinsame Schnittstelle aller folgenden Pakete. AP 2 und AP 3
können danach getrennt entwickelt werden; AP 4 benötigt beide. AP 5 friert den
Kern als Integrationsbasis ein, bevor AP 6 den Befehlssatz verbreitert. Das
binäre Format in AP 7 kommt bewusst spät, damit frühe Schaltungsänderungen
keine dauerhaft inkompatiblen Opcodes erzeugen. AP 9 ist die Voraussetzung für
alle elektrischen Abnahmen. AP 10 hält die erste reale Simulation bewusst auf
das bereits eingefrorene Kernprogramm begrenzt; erst danach verbreitert AP 11
die Abdeckung auf die ISA. AP 12 darf erst geschlossen werden, wenn diese Gates
in einem frischen Checkout verpflichtend laufen.
AP 13 friert anschließend die Produktgrenze ein, bevor AP 14 daraus
Distributionsartefakte erzeugt. AP 15 qualifiziert exakt diese Artefakte; es darf
weder einen anderen Commit noch nachträglich veränderte Bundles veröffentlichen.

## Stand

### Funktionsstatus und weitere Planung

TinyCPU ist im eingefrorenen 1.0-Zielprofil **voll funktionsfähig**: Die
16-Bit-Daten-/12-Bit-Adress-Schaltung implementiert alle 50 Opcodes, wird im
realen, gepinnten Logisim-evolution elektrisch gegen die Python-VM geprüft und
besitzt eine reproduzierbar qualifizierte Distribution. „Voll funktionsfähig“
bezieht sich dabei auf den veröffentlichten 1.0-Vertrag, nicht auf jede denkbare
Erweiterung einer Lehr-CPU. Insbesondere verspricht die Hardware keine anderen
Busbreiten, keine Drittanbieter-Schaltungsvarianten und keine Stabilität der als
intern gekennzeichneten Diagnoseartefakte.

Damit gibt es aktuell **kein notwendiges nächstes Arbeitspaket**, um TinyCPU
betriebsfähig zu machen. Sinnvolle neue Pakete wären Produktentscheidungen für
eine spätere Version und keine Restarbeiten an 1.0. Bevor dafür
Implementierungsarbeit beginnt, soll ein eigener Vorschlag genau eine der
folgenden Entwicklungsrichtungen auswählen, Kompatibilitätsfolgen benennen und
messbare Abnahmekriterien festlegen:

1. **Weitere Hardwareprofile:** Encoder, Schaltung und elektrische Matrix für
   mindestens ein zusätzliches Daten-/Adressbreitenprofil qualifizieren.
2. **Entwicklungswerkzeuge:** symbolisches Debugging, Breakpoints und
   Zustandsinspektion auf dem versionierten Maschinenformat aufbauen.
3. **Peripherie und Integration:** ein versioniertes Bus-/Interrupt-Modell und
   klar abgegrenzte Geräte ergänzen, ohne die 1.x-Schnittstellen stillschweigend
   zu verändern.

Diese Richtungen sind bewusst **Kandidaten und keine offenen Checklistenpunkte**.
Priorität, Versionsziel und Ressourcen sind noch nicht beschlossen; die
abgeschlossenen AP 1 bis AP 15 werden dadurch nicht wieder geöffnet.

- [x] **AP 1: Hardwarevertrag einfrieren:** Das Profil
  `hardware/logisim/tinycpu-16-12.json` beschreibt den Vertrag;
  `tiny_cpu_circuit.py --profile … --contract-only` prüft ihn unabhängig von
  der Verdrahtung. Der vollständige Inspector-Lauf meldet die inzwischen
  abgenommene Schaltung `TinyCPUMain: connected`.
- [x] **AP 2: Daten- und Adresspfad:** `Datapath` lädt Akkumulator und
  Valid-Bit an derselben Taktflanke und leitet `ZERO`/`NEGATIVE` über einen
  vorzeichenbehafteten Vergleicher ab. `AddressPath` lädt Adressregister und
  Valid-Bit synchron und stellt die 12-Bit-Offset-Summe samt Carry bereit. Das
  Hardwareprofil und die Netlist-Tests frieren diese Schnittstellen ein.
- [x] **AP 3: Speicher und Fehlerregister:** Daten- und Valid-RAM teilen sich
  Adresse, Write-Enable und Takt. Sechs set-dominante Sticky-Flags implementieren
  `SET OR (Q AND NOT CLEAR_ERROR)` und exportieren ihren Zustand.
- [x] **AP 4: Fetch und Decode:** ein 12-Bit-PC adressiert das interne ROM,
  `CORE_DECODER` erzeugt die Steuersignale des Kernbefehlssatzes und
  `PC_RANGE` setzt bei einem PC außerhalb `PROGRAM_LIMIT` gleichzeitig `ADDR`
  und `HALT_ERROR`. Die Taktabläufe und das vorläufige interne ROM-Wort sind
  in `hardware/logisim/README.md` dokumentiert und im Hardwareprofil fixiert.
- [x] **AP 5: Kernprogramm integrieren:** die ROM-Zählschleife und ihr
  versionierter 17-Takt-Trace liegen unter `hardware/logisim/`. Der
  Trace-Comparator prüft PC, Akkumulator, Status, Speicherzellen, Ausgabe,
  Fehlerflags und Haltzustand an jeder Taktflanke gegen die Python-VM.
- [x] **AP 6: ISA vervollständigen:** `FetchDecode` exportiert die vollständige
  symbolische ISA-Steuerfläche für alle Adressierungsarten, ALU-Operationen,
  Sprünge und I/O. Profil und parametrisierte Strukturtests gleichen jeden
  Befehl sowie alle Bedingungs- und Fehlerpfade mit der Python-ISA ab.
- [x] **AP 7: Maschinenformat und Tooling:** die versionierte Opcode-Tabelle
  definiert ein 22-Bit-Wort aus 6-Bit-Opcode und 16-Bit-Operand. Der Encoder
  erzeugt ROM-Image und Listing der Zählschleife, das Logisim-ROM lädt exakt
  dieses Image, und Roundtrip- sowie Negativtests sichern das Format ab.
- [x] **AP 8: Abschluss und Dokumentation:** die Bedienungs- und
  Architekturhinweise beschreiben den Schaltplan sowie die Simulatorgrenze.
  `tiny_cpu_verify.py` prüft aus einem frischen Checkout Vertrag, Verdrahtung,
  generierte Artefakte, eingebettetes ROM und den 17-Takt-Referenztrace mit
  einem einzigen reproduzierbaren Kommando.
- [x] **AP 9: Reale Simulator-Basis:** Logisim-evolution 4.1.0 und Temurin
  21.0.8+9.0.LTS sind in CI und im Launcher festgelegt. Der nicht-interaktive
  Tabellenlauf protokolliert beide Versionen und lädt `TinyCPUMain`; Fehler beim
  Download, Start, Versionsabgleich oder Projektladen brechen das Gate ab.
- [x] **AP 10: Elektrischen Kerntrace abnehmen:** Der Launcher taktet eine
  temporäre Kopie von `TinyCPUMain`
  direkt im gepinnten Simulator, normalisiert dessen änderungsgetriebene
  Tabellenausgabe und vergleicht alle 17 Flanken mit dem VM-Vertrag. CI bewahrt
  den unveränderten Simulator-Export als Artefakt auf.
- [x] **AP 11: Elektrische ISA-Matrix:** Die elektrische Positiv- und
  Fehlermatrix tauscht das ROM je Fixture aus, bewahrt jede Roh-Tabelle auf und
  vergleicht alle Flanken mit der VM.
- [x] **AP 12: Hardware-Abschluss:** Das verpflichtende Release-Gate startet die
  reale Schaltung
  zweimal am Reset-Zustand, vergleicht die normalisierten 17-Flanken-Traces,
  führt anschließend die vollständige elektrische ISA-Matrix aus und bewahrt
  Rohdaten, normalisierte Traces und ein versioniertes Abnahmeprotokoll auf.
- [x] **AP 13: 1.0-Releasevertrag einfrieren:** Der maschinenlesbare Vertrag
  gleicht Hardwareprofil, Maschinenformat, Laufzeitversionen, AP-12-Schema und
  öffentliche CLI-Hilfe mit ihren Quellen ab. Die 1.x-Richtlinie trennt diese
  stabilen Grenzen von internen Diagnoseartefakten.
- [x] **AP 14: Reproduzierbare Distribution bauen:** Ein deterministischer
  Builder erzeugt Quell- und Simulatorarchive mit kanonischen Inventaren,
  eingebetteter Offline-Prüfung und validierten AP-12-Nachweisen.
- [x] **AP 15: TinyCPU 1.0 qualifizieren und veröffentlichen:** Die signierte
  Qualifikation prüft exakt diese Archive offline, führt den Countdown im Clean
  Room aus und friert Commit, Digests und unveränderte Veröffentlichungsbytes
  für den Tag `tinycpu-v1.0.0` ein.

## Abgeschlossenes Arbeitspaket: AP 12 – Hardware-Abschluss

AP 12 macht die elektrische Matrix zur verbindlichen Abschlussabnahme. Das
CI-Gate ruft nur noch das gemeinsame Abnahmekommando auf; ein fehlgeschlagener
Simulator-, Reset-/Wiederanlauf-, Mehrzyklus- oder Matrixvergleich bricht den
Job ab. Die Bedienung und die erzeugten Nachweise sind im Logisim-Handbuch
dokumentiert.

## Abgeschlossene Release-Arbeitspaketgrenze

Die elektrische Hardware ist nach AP 12 abgenommen. AP 13 hat die
Release-Grenze eingefroren, AP 14 die reproduzierbare Distribution gebaut und
AP 15 deren signierte Clean-Room-Qualifikation und unveränderte Veröffentlichung
abgeschlossen. Der Umfang und die Abnahmekriterien sind im
[TinyCPU-1.0-Releaseplan](tiny_cpu_1_0_release_plan.md) festgelegt; ein weiteres
Release-Arbeitspaket ist derzeit nicht dokumentiert. Die
abgeschlossenen Pflegeeinträge in `docs/open_tasks.md` öffnen AP 1 bis AP 12
nicht erneut.

## Abgeschlossene Baseline-Pflege

Nach Abschluss der acht Arbeitspakete ist das Abnahmekommando als eigener
Schritt im Haupt-CI-Job verankert. Dadurch schlagen Änderungen an Vertrag,
Schaltung, Maschinenformat, generierten ROM-/Listing-Artefakten oder
Referenztrace bereits vor der allgemeinen Testsuite mit einer gezielten
TinyCPU-Diagnose fehl. Ein Regressionstest schützt sowohl den Namen des Gates
als auch das dokumentierte Kommando vor unbeabsichtigtem Entfernen.

## Abgeschlossener Folgeschritt: elektrische Top-Level-Integration

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
Netze wurden anhand der
[Top-Level-Vorlage](tiny_cpu_top_level_template.md) einzeln ergänzt. Dabei wird
jede Leitung rechtwinklig in einem freien Korridor um Bauteile herumgeführt;
eine Leitung durch ein Symbol oder über einen fremden Anschluss ist auch dann
unzulässig, wenn die XML-Strukturprüfung sie akzeptieren würde. Die damals
nächsten Steuernetze, Datenpfade und Halt-/Fehlerausgänge sind inzwischen
getrennt verdrahtet und durch die abgeschlossene elektrische Abnahme geschützt.

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
der Decode-Steuerung angeschlossen. Die damals folgenden
Datenpfad-Steuernetze sind inzwischen über die zusammengefasste
`DecodeSignals.ACC_WRITE_REQUEST`-Grenze angeschlossen und abgenommen.
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
je einen eigenen Eingang. Das nun ausdrücklich mit zweiunddreißig Eingängen
ausgelegte Gatter deckt die vollständigen `LOAD_*`-, `ADD_*`-, `SUB_*`-, `MUL_*`-, `DIV_*`-, `AND_*`-,
`OR_*`- und `XOR_*`-Familien ab, ohne ihre Decoder-Ausgänge elektrisch zu
koppeln. Die Strukturtests berücksichtigen dabei auch Abzweige, die in Logisim
entstehen, wenn ein Leitungsende auf eine andere Leitung trifft, und verhindern
so insbesondere wired-ORs. `NOT` was then routed separately as the next accumulator-writing instruction
into the second-stage `ACC_WRITE_AGGREGATOR` OR gate together with the 32-input
family aggregator. `INPUT` now occupies a third,
independent input of that second stage; only the gate output drives
`Datapath.ACC_LOAD`. This preserves isolated decoder outputs without exceeding
Logisim's per-gate input limit. The explicit accumulator data-source selection
required by these write-enable controls is also complete.
The instruction splitter's 16-bit operand output now reaches
`Datapath.DATA_IN` on an isolated route, while the adjacent opcode and
one-bit control nets remain separate. This establishes the constant operand as
the first accumulator data source. The labelled 16-bit `ACC_DATA_SELECT`
multiplexer now keeps that operand on its default input and
`Memory.MEMORY_DATA` on an independent second input. `LOAD_ADDRESS` drives the
selector through the labelled `ACC_MEMORY_SELECT` gate, whose second independent
input is now `LOAD_ADDRESS_REGISTER`. Either addressing mode therefore selects
the memory source without directly joining decoder outputs or data-bus drivers.
`LOAD_ADDRESS_REGISTER_PLUS_OFFSET` is now a third independent cause in that
selection logic. A labelled 16-bit `ACC_NOT_VALUE` inverter derives the unary
result from the accumulator, and the second-stage `ACC_NOT_SELECT` multiplexer
selects it only for `NOT` while passing the existing operand-or-memory result
through by default. A final labelled 16-bit `ACC_INPUT_SELECT` multiplexer now
passes that result through normally and selects the external top-level
`INPUT_VALUE` only for `INPUT`. The selected result reaches
`Datapath.DATA_IN`; the accumulator-validity control required by `INPUT` is
also integrated. The independent top-level `INPUT_VALID` pin now
reaches `Datapath.VALID_IN` through the labelled one-bit
`ACC_INPUT_VALID_SELECT` multiplexer only while `INPUT` is active. Before that
final override, `ACC_MEMORY_VALID_SELECT` mirrors the accumulator data
selection: immediate operands supply a valid constant, while all three
memory-backed load modes propagate `Memory.MEMORY_VALID`. A following
`ACC_NOT_VALID_SELECT` stage propagates `Datapath.ACC_VALID_OUT` for `NOT`,
because the unary result is valid exactly when its accumulator input is valid;
the independent `INPUT` stage retains final priority. The four `ADD_*` modes
select immediate or memory operand validity and combine it with
`Datapath.ACC_VALID_OUT`; only two valid operands produce a valid addition
result. The four `SUB_*` modes now additionally select the matching 16-bit
operand, subtract it from the current accumulator, and apply the same two-valid-
operand rule in the next staged data and validity selectors. `INPUT` remains
both final overrides. `MUL_*` now follows the same operand and validity
contract inside its extracted operation box and participates in the combined
result, overflow, validity, and invalid-operand paths. `DIV_*` follows the same
operand selection and validity contract, exports a dedicated divide-by-zero
signal, and participates in the consolidated result and validity OR gates.
Integer division deliberately has no overflow output; apart from invalid
operands, only a zero divisor invalidates its result. The manually compacted
four-mode routes have been checked against the current `Operations` pin order
and corrected without restoring the superseded drawing. `AND_*`, `OR_*`, and
`XOR_*` are now extracted and integrated behind the same operand and validity
boundary; their bitwise results are neutral while inactive and deliberately
export no overflow status. XOR extends the compact seven-way summaries through
an explicit second OR stage. The accompanying top-level audit also separated
the accidentally joined error/OR controls and restored the interrupted
`LOAD_ADDRESS_REGISTER_PLUS_OFFSET` route. The non-binary data paths have also
been integrated. Nach der erneuten manuellen Korrektur gelten die
verschobenen Symbole und direkten Leitungen der eingecheckten Übersichtsseite
als neue Referenz. Die Strukturtests leiten die Eingangsseite der automatisch
erzeugten Symbole entsprechend ab und verlangen nicht länger die Tunnel und
Koordinaten der überholten Zeichnung; die drei Akkumulator-Multiplexer behalten
lediglich eindeutige, nicht-elektrische Bezeichner.

Die vier funktionalen Kästen `AddSubCircuit`, `SubSubCircuit`, `MulSubCircuit`
und `NotCircuit` sind nun auf dem eigenen Blatt `Operations` gekapselt.
`TinyCPUMain` enthält
genau eine Instanz dieses Blatts. Gemeinsam verwendete Befehls-, Speicher-,
Akkumulator- und Validitätswerte überschreiten die Grenze jeweils nur einmal;
`Operations` führt `RESULT`, `RESULT_VALID` und `OVERFLOW` lokal zusammen und
exportiert je ein gemeinsames Signal.

Der gemeinsame Ergebnis- und Validitätsbus erreicht nun zusammen mit
`DecodeSignals.ACC_WRITE_REQUEST` alle drei Ladeeingänge des Akkumulators.
Damit schreibt insbesondere der bereits isoliert ausgewählte `NOT`-Zweig sein
invertiertes Ergebnis samt Eingangsvalidität an der nächsten Taktflanke zurück.
`PRINT` und `PRINT_ADDRESS` sind nun als getrennte Top-Level-Ausgabekanäle
angebunden. Jeder Kanal exportiert sein eigenes Enable-Signal sowie den Wert und
das Validitätsbit seiner Quelle: `PRINT` verwendet den Akkumulator,
`PRINT_ADDRESS` den ausgewählten Speicherwert. Dadurch muss ein Verbraucher nur
bei aktivem Enable und gesetzter Validität ausgeben, ohne die beiden
Befehlsursachen elektrisch zusammenzuschalten. `HALT` und `HALT_ERROR` sind
ebenfalls als getrennte Ereignisnetze `HALT_ENABLE` und `HALT_ERROR_ENABLE`
integriert. Der nächste Abnahmeschritt ist als End-to-End-Grenztrace umgesetzt:
Die drei Szenarien in `hardware/logisim/tinycpu_integration_trace.json`
beobachten Normalhalt, Fehlerhalt und ungültige Ausgabevalidität an jeder
Taktflanke. Der Checkout-Verifier spielt diese Referenz ohne Simulator
reproduzierbar gegen die VM ab. Eine spätere CI-Installation von
Logisim-evolution soll dieselben Pins direkt exportieren; der Referenzvergleich
allein wird ausdrücklich nicht als elektrische Simulation bezeichnet.

Die manuelle Fetch/Decode-Anpassung wird ebenfalls als maßgeblich behandelt:
Die Überlaufprüfung des Programmzählers ist nach dessen Hochzählen angeordnet.
Regressionstests verfolgen diese Stufen anhand ihrer relativen Topologie und
dürfen weder die früheren absoluten Koordinaten noch die alte Anordnung
wiederherstellen.

Der funktionslose L-förmige Leitungsrest im oberen linken Außenkorridor von
`TinyCPUMain` ist entfernt. Er endete ohne Verbraucher und gehörte weder zum
Takt noch zu einem Decode-Netz; ein gezielter Strukturtest verhindert seine
erneute Einfügung. Der damals nächste externe Abnahmeschritt, der direkte Export
des Integrations-Grenztraces aus Logisim-evolution, ist inzwischen Bestandteil
der abgeschlossenen AP-10- und AP-12-Abnahme.

Die Vergleichsseite dieses Abnahmeschritts ist inzwischen ausführbar:
`tiny_cpu_trace.py --integration --check` erzeugt aus dem jeweiligen
Assemblerprogramm den erwarteten Grenztrace und vergleicht ihn feldweise mit
dem aus Logisim exportierten JSON. Der elektrische Export ist
simulatorabhängig und wird in der AP-12-Abnahme tatsächlich mit dem gepinnten
Logisim-evolution ausgeführt; der VM-Vergleich ersetzt ihn nicht.

Als vorbereitendes Folgepaket akzeptiert der Comparator nun außerdem den
flachen CSV-/TSV-Export des Logisim-Tabellenloggers direkt. Die festgelegten
Pin-Spalten werden in das versionierte Grenztrace-Schema überführt;
undefinierte Bits, fehlende Spalten und eine vom Programm abweichende
Taktanzahl brechen die Abnahme eindeutig ab. Damit ist nach der späteren
Simulatorinstallation keine manuelle Umschreibung in verschachteltes JSON
mehr nötig.

Für alle weiteren Arbeitspakete gilt: Eine sichtbare rechtwinklige Leitung hat
Vorrang vor einem benannten Tunnel. Vor dem Einsatz eines Tunnels sind Symbole
zu verschieben und freie Leitungskorridore zu prüfen. Nur wenn beides keine
lesbare und elektrisch getrennte Route ermöglicht, darf ein Tunnel als
dokumentierte Ausnahme verbleiben; diese Ausnahme ist in einem späteren Redraw
erneut zu prüfen. Lokal begrenzte Netze und neu hinzukommende Verbindungen
werden immer direkt gezeichnet. Als erster konsequenter Redraw wurden alle
sechs `ErrorFlags`-Rückkopplungen ohne Tunnel ausgeführt.

## Abgeschlossenes Folgepaket: Abgleich der manuell angepassten Übersichtsseite

Die aktuelle, manuell angepasste Anordnung von `TinyCPUMain` bleibt die
verbindliche Ausgangsbasis. Das Abgleichpaket stellt keine frühere Zeichnung
wieder her: Es ergänzt ausschließlich die beim Redraw verlorene senkrechte
Akkumulator-Busstrecke, stellt die elektrischen Attribute von Fetch/Decode und
der Ergebniswahl wieder her und richtet die Trace-Abgriffe sowie Strukturtests
auf die tatsächlich eingecheckten Anschlüsse aus. Der direkte, tunnelfreie
JNZ-Statuspfad und alle verschobenen Symbole bleiben unverändert erhalten.

Der Abgleich ist abgeschlossen und wird durch die fokussierten Struktur-,
Topologie- und Verdrahtungstests dauerhaft abgesichert. Weitere Änderungen an
der Übersichtsseite benötigen deshalb ein neu abgegrenztes Arbeitspaket; aus
diesem historischen Abschnitt darf kein impliziter Folgeauftrag abgeleitet
werden.
