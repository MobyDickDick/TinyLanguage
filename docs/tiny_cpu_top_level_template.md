# Referenz: TinyCPU-Top-Level-Integration

Diese Referenz dokumentiert die abgeschlossene manuelle Integration in
Logisim-evolution. Die folgende Reihenfolge ist die Abnahmehistorie der bereits
verdrahteten Netze und kein offener Bauplan. Die bestehende Übersichtsseite
**`TinyCPU` in `hardware/logisim/TinyCPU.circ` bleibt erhalten**. Künftige,
zuvor als begrenztes Arbeitspaket dokumentierte Wartungsänderungen dürfen
nicht aus einem Diagnoseprojekt kopiert oder automatisch erzeugt werden und
die vorhandenen Bauteile nicht für eine vermeintlich günstigere Verdrahtung
neu anordnen.

## Unveränderliche Regeln

1. Vor jeder Änderung eine Kopie der `.circ`-Datei anlegen oder einen eigenen
   Git-Commit beginnen.
2. Pro Arbeitsschritt genau **ein benanntes Netz** ergänzen.
3. Leitungen nur horizontal und vertikal und immer in freien Korridoren **um
   Bauteile herum** führen. Keine Leitung darf ein Symbol, einen Text oder einen
   unbeteiligten Anschluss durchqueren.
4. Abzweige nur auf einem bewusst gewählten freien Rasterpunkt setzen. Eine
   Kreuzung ist keine Verbindung; eine Verbindung wird mit einem Abzweigpunkt
   kontrolliert.
5. Busbreiten vor dem Zeichnen an Quelle und Ziel vergleichen (Steuersignal:
   1 Bit; Adress- und Datenbreite immer dem Pinvertrag entnehmen).
6. Nach jedem Netz speichern, neu öffnen, mit dem Poke-Werkzeug prüfen und erst
   dann committen. Bei einem Fehler nur diesen einen Schritt zurücknehmen.

## Abgeschlossene Reihenfolge der Netze

Die ausgeführte Reihenfolge hält Takt, Reset, Steuerung und Daten voneinander
getrennt. Alle Schritte 0 bis 11 sind abgeschlossen. `CLK` ist für alle fünf
zustandsbehafteten Blöcke angelegt. Der Anschluss der Fehlerflags wurde als
eigener Schritt vor `RESET` ergänzt.

| Schritt | Netz | Quelle | Ziele | Breite | Abnahme |
|---:|---|---|---|---:|---|
| 0 | bestehendes `CLK` | Top-Level-Pin | `FetchDecode`, `Datapath`, `AddressPath`, `Memory` | 1 | Die vier vorhandenen Abzweige prüfen und nicht neu führen. |
| 1 | `CLK` ergänzt | bestehendes Taktnetz | `ErrorFlags.CLK` | 1 | Der Abzweig verläuft oberhalb der Symbole; alle fünf Blöcke reagieren auf dieselbe Flanke. |
| 2 | `RESET` | neuer Top-Level-Pin | nur `FetchDecode.RESET` | 1 | PC wird zurückgesetzt; RAM, Akkumulator und Fehlerflags werden nicht versehentlich gelöscht. |
| 3 | Decode-Steuerung | `FetchDecode.OPCODE`, danach benannte Ausgänge von `FetchDecodeControls` | zuerst `FetchDecodeControls.OPCODE`, danach gleichnamiger Eingang des Zielblocks gemäß Pinvertrag | 22 für `OPCODE`, danach 1 je Netz | Keine Verbindung mit Takt oder Reset; jedes Signal beim Einzelschritt beobachten. `OPCODE`, `CLEAR_ERROR` und alle sechs `SET_*`-Fehlernetze sind angeschlossen. Die anschließend integrierten Datenpfad-Steuernetze erreichen den Akkumulator über `DecodeSignals.ACC_WRITE_REQUEST`. |
| 4 | Akkumulator-Steuerung | passender `FetchDecodeControls`-Ausgang | passender `Datapath`-Eingang | 1 je Netz | Alle vier `LOAD_*`-, `ADD_*`-, `SUB_*`-, `MUL_*`-, `DIV_*`-, `AND_*`-, `OR_*`- und `XOR_*`-Adressierungsarten sowie `NOT` und `INPUT` erreichen `ACC_LOAD` über getrennte Eingänge der benannten, zweistufigen Schreibanforderung. Weitere Schreibursachen dürfen nicht durch direktes Zusammenschalten mehrerer Ausgänge entstehen. |
| 5 | Adress-Steuerung | benannte Ausgänge von `DecodeSignals` und `AddressPath` | `EffectiveAddress` | 1 je Netz | Die einzeln geführten Modussignale wählen direkte Adresse, Adressregister oder Register-plus-Offset; nur ein aktiver Offsetmodus darf `OFFSET_CARRY` als Adressfehler werten. |
| 6 | Speicher-Steuerung | `DecodeSignals.ACC_MEMORY_REQUEST` und die drei zusammengefassten `STORE_*`-Steuerungen | `Memory` | 1 je Netz | Leseanforderung und akkumulatorgespeiste Schreibanforderung sind getrennt angeschlossen; Daten- und Validitäts-RAM verwenden dieselben aktiven Steuerungen. |
| 7 | Adressbus | `EffectiveAddress.EFFECTIVE_ADDRESS` | Daten- und Validitäts-RAM in `Memory` | 16 | Die zentral ausgewählte effektive Adresse erreicht beide RAMs über einen gemeinsamen Bus. Eine Breitenprüfung gegen `0xfff` erfolgt vor dem Zugriff, ohne einen zweiten Adresstreiber einzufügen. |
| 8 | Datenbus | Instruktionsoperand, `Memory.MEMORY_DATA` und `Datapath.ACC_OUT` | `Operations`, danach `Datapath.DATA_IN` | 16 | Die drei unabhängigen Quellen erreichen `Operations.IMMEDIATE_VALUE`, `MEMORY_VALUE` und `ACC_VALUE`. `Operations.RESULT_VALUE` führt den dort ausgewählten Lade- oder Operationwert als einzigen Treiber zu `Datapath.DATA_IN`; die Auswahl- und Rechenstufen bleiben innerhalb des extrahierten Blatts. |
| 9 | Status | `Operations`, `Datapath.ZERO`, `EffectiveAddress` und `AddressPath.OFFSET_CARRY` | `Datapath.VALID_IN`, `FetchDecode.NOT_ZERO` und die zuständigen `ErrorFlags.SET_*`-Eingänge | 1 je Netz | `Operations.RESULT_IS_VALID` ist der einzige Treiber der Ladevalidität. Der invertierte Nullstatus steuert unabhängig davon `FetchDecode.NOT_ZERO`. `OVERFLOW`, `DIVIDE_BY_ZERO` und `INVALID_OPERAND` erreichen getrennt `SET_OVF`, `SET_DIV0` und `SET_INV`; der aktivitätsabhängige Bereichsfehler und Offset-Übertrag werden erst vor `SET_ADDR` vereinigt. |
| 10 | Fehler | `FetchDecodeControls.CLEAR_ERROR`, die decodierten `SET_ILL`-/`SET_INPUT`-Signale und die vier abgeleiteten Ausführungsfehler aus Schritt 9 | `ErrorFlags.CLEAR_ERROR` und der jeweils zuständige `SET_*`-Eingang | 1 je Netz | Alle sechs Register sind set-dominant und sticky verdrahtet; `CLEAR_ERROR` löscht sie gemeinsam nur dann, wenn nicht an derselben Taktflanke erneut ihre jeweilige Fehlerursache anliegt. Die sechs Zustände bleiben getrennt als `OVF_OUT`, `DIV0_OUT`, `ADDR_OUT`, `INV_OUT`, `ILL_OUT` und `INPUT_OUT` beobachtbar. |
| 11 | Halt | `FetchDecodeControls.HALT` und `FetchDecodeControls.HALT_ERROR` | Top-Level `HALTED` und `HALTED_WITH_ERROR` (im Integrationstrace `HALT_ENABLE` und `HALT_ERROR_ENABLE`) | 1 je Netz | Beide decodierten Ereignisse sind direkt und getrennt exportiert. Es gibt weder ein gemeinsames Halt-ODER noch eine Verbindung zwischen Normal- und Fehlerhalt. |

Die exakten Namen und Richtungen vor jeder Wartungsänderung im
maschinenlesbaren Pinvertrag `hardware/logisim/tinycpu-16-12.json` nachsehen.
Wenn Tabellenname und sichtbarer Pin voneinander abweichen, **nicht raten**,
sondern die Änderung abbrechen und die Abweichung als neues, begrenztes
Arbeitspaket dokumentieren.

## Abgenommene Endpunkte der Decode-Leitungen

Nach der manuellen Korrektur der Übersichtsseite sind die sichtbaren Pins der
neu platzierten Symbole maßgeblich. Die XML-Tests verfolgen jede Leitung von
diesen Endpunkten und prüfen zusätzlich, dass Takt, Reset und benachbarte
Steuernetze nicht versehentlich verbunden sind:

| Netz | von | nach |
|---|---:|---:|
| `OPCODE` | `FetchDecode.OPCODE (330,160)` über Splitter-Ausgang `(390,370)` | `FetchDecodeControls.OPCODE (430,370)` |
| `CLK` | bestehendes CLK-Netz | `ErrorFlags.CLK (1350,100)` |
| `CLEAR_ERROR` | `FetchDecodeControls.CLEAR_ERROR (650,1150)` | `ErrorFlags.CLEAR_ERROR (1350,80)` |
| `SET_OVF` | `FetchDecodeControls.SET_OVF (650,1270)` | `ErrorFlags.SET_OVF (1350,120)` |
| `SET_DIV0` | `FetchDecodeControls.SET_DIV0 (650,1290)` | `ErrorFlags.SET_DIV0 (1350,140)` |
| `SET_ADDR` | `FetchDecodeControls.SET_ADDR (650,1310)` | `ErrorFlags.SET_ADDR (1350,160)` |
| `SET_INV` | `FetchDecodeControls.SET_INV (650,1330)` | `ErrorFlags.SET_INV (1350,180)` |
| `SET_ILL` | `FetchDecodeControls.SET_ILL (650,1350)` | `ErrorFlags.SET_ILL (1350,200)` |
| `SET_INPUT` | `FetchDecodeControls.SET_INPUT (650,1370)` | `ErrorFlags.SET_INPUT (1350,220)` |
| `ACC_WRITE_REQUEST` | `DecodeSignals.ACC_WRITE_REQUEST` | `Datapath.ACC_LOAD` | 1 |
| `IMMEDIATE_VALUE` | Instruktionssplitter-Ausgang für Bits 15..0 | `Operations.IMMEDIATE_VALUE` | 16 |
| `MEMORY_VALUE` | `Memory.MEMORY_DATA` | `Operations.MEMORY_VALUE` | 16 |
| `ACC_VALUE` | `Datapath.ACC_OUT` | `Operations.ACC_VALUE` | 16 |
| `RESULT_VALUE` | `Operations.RESULT_VALUE` | `Datapath.DATA_IN` | 16 |
| `RESULT_IS_VALID` | `Operations.RESULT_IS_VALID` | `Datapath.VALID_IN` | 1 |
| `NOT_ZERO` | invertierter `Datapath.ZERO`-Status | `FetchDecode.NOT_ZERO` | 1 |
| `OVERFLOW` | `Operations.OVERFLOW` | `ErrorFlags.SET_OVF` | 1 |
| `DIVIDE_BY_ZERO` | `Operations.DIVIDE_BY_ZERO` | `ErrorFlags.SET_DIV0` | 1 |
| `INVALID_OPERAND` | `Operations.INVALID_OPERAND` | `ErrorFlags.SET_INV` | 1 |
| `ADDRESS_ERROR` | `EffectiveAddress.ADDRESS_OUT_OF_RANGE` oder aktiver `AddressPath.OFFSET_CARRY` | `ErrorFlags.SET_ADDR` | 1 |
| `HALT` | `FetchDecodeControls.HALT` | Top-Level `HALTED`; Trace-Feld `HALT_ENABLE` | 1 |
| `HALT_ERROR` | `FetchDecodeControls.HALT_ERROR` | Top-Level `HALTED_WITH_ERROR`; Trace-Feld `HALT_ERROR_ENABLE` | 1 |

Der Splitter führt ausschließlich die Opcode-Bits 21 bis 16 des 22-Bit-
Maschinenworts an den sechs Bit breiten Decoder. Der getrennte 16-Bit-Ausgang
führt den Operanden zu `Operations.IMMEDIATE_VALUE`. Speicherwert und
Akkumulator erreichen das Blatt über eigene Eingänge; nur dessen gemeinsamer
`RESULT_VALUE`-Ausgang führt zurück zum Datenpfad. Ein direkter
22-auf-6-Bit-Anschluss oder das Zusammenschalten dieser Datentreiber wäre ein
Breiten- beziehungsweise Mehrfachtreiberfehler.

Auch die Statusgrenze besitzt jeweils genau einen zuständigen Verbraucher:
`RESULT_IS_VALID` begleitet `RESULT_VALUE` zum Datenpfad, während der aus
`ZERO` abgeleitete Sprungstatus ausschließlich Fetch/Decode erreicht. Die drei
Operationsfehler bleiben bis zu ihren jeweiligen Sticky-Flag-Eingängen
getrennt. Nur die beiden Adressfehlerursachen werden nach ihrer
Aktivitätsprüfung vor `SET_ADDR` zusammengeführt.

Die anschließende Fehlerregistergrenze ist ebenfalls vollständig. Der Decoder
liefert `CLEAR_ERROR` sowie die unmittelbar aus dem Opcode beziehungsweise der
Eingabe abgeleiteten Ursachen `SET_ILL` und `SET_INPUT`. Die übrigen vier
Set-Eingänge erhalten ausschließlich die in der Statusstufe gebildeten
Überlauf-, Divisions-, Operanden- und Adressfehler. `ErrorFlags` hält jede
Ursache in einem eigenen set-dominanten Sticky-Register; ein gleichzeitig
anliegendes Set gewinnt deshalb gegenüber dem gemeinsamen `CLEAR_ERROR`. Die
sechs unabhängigen Zustände verlassen das Blatt als `OVF_OUT`, `DIV0_OUT`,
`ADDR_OUT`, `INV_OUT`, `ILL_OUT` und `INPUT_OUT` und werden weder untereinander
noch zu einem unbenannten Sammelfehler zusammengeschaltet.

Auch die Haltgrenze ist abgeschlossen. `FetchDecodeControls.HALT` erreicht
direkt und ausschließlich den Top-Level-Ausgang `HALTED`, während
`FetchDecodeControls.HALT_ERROR` direkt und ausschließlich
`HALTED_WITH_ERROR` erreicht. Der Tabellenlogger bildet diese Ereignisnetze
für den Integrationsvergleich auf `HALT_ENABLE` beziehungsweise
`HALT_ERROR_ENABLE` ab. Die getrennten Ausgänge bewahren die Beendigungsart;
insbesondere gibt es kein zusätzliches `HALTED_STATE`-ODER, das Normal- und
Fehlerhalt elektrisch zusammenfassen würde.

**Ursache der korrigierten Fehlverdrahtung:** Die zuvor verwendeten Endpunkte
wurden aus den XML-Positionen des Splitters, der Top-Level-Instanz und des
`DATA_IN`-Pins im Unterblatt abgeleitet. Diese
`loc`-Werte beschreiben jedoch Bauteilanker beziehungsweise die Geometrie des
Unterblatts, nicht automatisch die Anschlüsse des daraus erzeugten Symbols.
Beim aktuellen Splitter liegt der sichtbare 16-Bit-Ausgang oberhalb seines
Ankers; auch `Datapath.DATA_IN` liegt am automatisch erzeugten Symbol an einer
anderen Stelle. Die zuletzt manuell korrigierten direkten Leitungen und
Bauteilpositionen in `TinyCPU.circ` sind deshalb die Referenz und werden durch
Regressionstests geschützt, welche die Verbindungen semantisch prüfen.

Für zukünftige Verdrahtungen gilt daher zusätzlich: Endpunkte am sichtbaren
Top-Level-Symbol in Logisim ablesen und mit dem Poke-Werkzeug prüfen. Weder den
`loc`-Wert einer Unterblattinstanz noch die Koordinate eines Pins innerhalb der
Unterblattdefinition in eine Top-Level-Koordinate umrechnen oder erraten. Nach
Änderungen an Pinreihenfolge, Symbolaussehen, Ausrichtung oder Splitter-Fanout
müssen die sichtbaren Anschlüsse erneut ermittelt und die Endpunkttabelle samt
Strukturtest im selben Arbeitsschritt angepasst werden.

`tiny_cpu_verify.py` prüft den strukturellen Pinvertrag und reproduzierbare
Artefakte, wirbt aber weiterhin bewusst nicht mit einer eigenständigen
`connectivity`-Prüfung. Der Circuit-Inspector meldet die gepflegte
Top-Level-Schaltung inzwischen als `TinyCPUMain: connected`; seine generische
Prüfung belegt jedoch nur, dass die Pins an Leitungen liegen, und ersetzt weder
die fokussierten elektrischen Topologietests noch die AP-12-Simulatorabnahme.
Ein künftiges `INCOMPLETE`/`unconnected` ist daher ein Wartungsfehler, während
`connected` allein noch kein vollständiger elektrischer Funktionsnachweis ist.

## Änderungsprotokoll für künftige Wartungspakete

Die abgeschlossene Schaltung benötigt keinen weiteren Arbeitsschritt. Nur für
ein zuvor in `docs/open_tasks.md` abgegrenztes Wartungspaket wird dieser Block
vor dem Zeichnen ausgefüllt und zusammen mit der Änderung geprüft:

```text
Netz:
Quelle (Bauteil.Pin):
Ziel(e) (Bauteil.Pin):
Breite:
Freier Leitungskorridor (Rasterpunkte):
Gekreuzte Netze (ohne Verbindung):
Gewollte Abzweigpunkte:
Poke-Test vor der Taktflanke:
Poke-Test nach der Taktflanke:
Inspector-Ergebnis:
Git-Commit:
```

## Prüfung nach einer abgegrenzten Wartungsänderung

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --profile hardware/logisim/tinycpu-16-12.json \
  hardware/logisim/TinyCPU.circ
```

Die abgenommene Schaltung darf weder `TinyCPU: INCOMPLETE` noch neue Meldungen
zu `routing conflicts`, diagonalen/überlappenden Leitungen, Mehrfachtreibern
oder Breitenfehlern erzeugen. Jede solche Meldung lässt das Wartungspaket
scheitern und muss vor dem Commit behoben werden.

Diagnoseblätter nur bei Bedarf in ein **temporäres** Verzeichnis schreiben:

```bash
tmpdir="$(mktemp -d)"
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --split-output "$tmpdir" hardware/logisim/TinyCPU.circ
```

So kann kein Generatorlauf versehentlich die Übersichtsseite oder die
eingecheckten Diagnoseartefakte überschreiben.
