# Vorlage: TinyCPU-Übersichtsseite weiterbauen

Diese Vorlage ist als knapper Arbeitszettel für die manuelle Integration in
Logisim-evolution gedacht. Die bestehende Übersichtsseite **`TinyCPU` in
`hardware/logisim/TinyCPU.circ` bleibt erhalten**. Nicht aus einem
Diagnoseprojekt kopieren, nicht automatisch neu erzeugen und die vorhandenen
Bauteile nicht für eine vermeintlich günstigere Verdrahtung neu anordnen.

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

## Reihenfolge der Netze

Die Reihenfolge hält Takt, Reset, Steuerung und Daten voneinander getrennt.
`CLK` ist für alle fünf zustandsbehafteten Blöcke angelegt. Der Anschluss der
Fehlerflags wurde als eigener Schritt vor `RESET` ergänzt.

| Schritt | Netz | Quelle | Ziele | Breite | Abnahme |
|---:|---|---|---|---:|---|
| 0 | bestehendes `CLK` | Top-Level-Pin | `FetchDecode`, `Datapath`, `AddressPath`, `Memory` | 1 | Die vier vorhandenen Abzweige prüfen und nicht neu führen. |
| 1 | `CLK` ergänzt | bestehendes Taktnetz | `ErrorFlags.CLK` | 1 | Der Abzweig verläuft oberhalb der Symbole; alle fünf Blöcke reagieren auf dieselbe Flanke. |
| 2 | `RESET` | neuer Top-Level-Pin | nur `FetchDecode.RESET` | 1 | PC wird zurückgesetzt; RAM, Akkumulator und Fehlerflags werden nicht versehentlich gelöscht. |
| 3 | Decode-Steuerung | `FetchDecode.OPCODE`, danach benannte Ausgänge von `FetchDecodeControls` | zuerst `FetchDecodeControls.OPCODE`, danach gleichnamiger Eingang des Zielblocks gemäß Pinvertrag | 22 für `OPCODE`, danach 1 je Netz | Keine Verbindung mit Takt oder Reset; jedes Signal beim Einzelschritt beobachten. `OPCODE`, `CLEAR_ERROR` und alle sechs `SET_*`-Fehlernetze sind angeschlossen; als Nächstes folgen die Datenpfad-Steuernetze. |
| 4 | Akkumulator-Steuerung | passender `FetchDecodeControls`-Ausgang | passender `Datapath`-Eingang | 1 je Netz | Alle vier `LOAD_*`-, `ADD_*`-, `SUB_*`- und `MUL_*`-Adressierungsarten erreichen `ACC_LOAD` über getrennte Eingänge des benannten ODER-Gatters `ACC_LOAD_REQUEST`; als Nächstes folgt die `DIV_*`-Gruppe. Weitere Schreibursachen dürfen nicht durch direktes Zusammenschalten mehrerer Ausgänge entstehen. |
| 5 | Adress-Steuerung | benannte Fetch/Decode-Ausgänge | gleichnamige Eingänge von `AddressPath` | 1 je Netz | Jedes Signal einzeln zeichnen und prüfen. |
| 6 | Speicher-Steuerung | Fetch/Decode-Ausgänge | `Memory` | 1 je Netz | Lesen und Schreiben getrennt testen; Validitäts-RAM mitprüfen. |
| 7 | Adressbus | `AddressPath` | `Memory` und benötigte Rückwege | laut Pinvertrag | Splitter vermeiden, solange keine Breitenumsetzung erforderlich ist. |
| 8 | Datenbus | jeweils dokumentierter Treiber | `Datapath`/`Memory` | 16 | Niemals zwei Ausgänge direkt auf dasselbe Netz legen. |
| 9 | Status | `Datapath.ZERO`, `NEGATIVE` und Valid-Signale | `FetchDecode`/Fehlerlogik | 1 je Netz | Sprungbedingungen einzeln mit 0, negativem und positivem Wert prüfen. |
| 10 | Fehler | Fehler-Set-Signale und `CLEAR_ERROR` | `ErrorFlags` | 1 je Netz | Sticky-Verhalten sowie Set-vor-Clear-Priorität prüfen. |
| 11 | Halt | normale und fehlerhafte Haltquelle | Top-Level `HALTED` | 1 | Normalhalt und Fehlerhalt getrennt auslösen. |

Die exakten Namen und Richtungen vor jedem Schritt im maschinenlesbaren
Pinvertrag `hardware/logisim/tinycpu-16-12.json` nachsehen. Wenn Tabellenname
und sichtbarer Pin voneinander abweichen, **nicht raten**, sondern den Schritt
offenlassen und die Abweichung notieren.

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
| `ACC_LOAD_REQUEST` | `FetchDecodeControls.LOAD_CONST (650,370)`, `LOAD_ADDRESS (650,390)`, `LOAD_ADDRESS_REGISTER (650,410)`, `LOAD_ADDRESS_REGISTER_PLUS_OFFSET (650,430)`, `ADD_CONST (650,450)`, `ADD_ADDRESS (650,470)`, `ADD_ADDRESS_REGISTER (650,490)`, `ADD_ADDRESS_REGISTER_PLUS_OFFSET (650,510)`, `SUB_CONST (650,530)`, `SUB_ADDRESS (650,550)`, `SUB_ADDRESS_REGISTER (650,570)`, `SUB_ADDRESS_REGISTER_PLUS_OFFSET (650,590)`, `MUL_CONST (650,610)`, `MUL_ADDRESS (650,630)`, `MUL_ADDRESS_REGISTER (650,650)` und `MUL_ADDRESS_REGISTER_PLUS_OFFSET (650,670)` über getrennte ODER-Eingänge | `Datapath.ACC_LOAD (720,180)` |

Der Splitter führt ausschließlich die Opcode-Bits 21 bis 16 des 22-Bit-
Maschinenworts an den sechs Bit breiten Decoder. Der 16-Bit-Operand bleibt für
die späteren Datenbus-Schritte getrennt; ein direkter 22-auf-6-Bit-Anschluss
wäre ein Breitenfehler.

`tiny_cpu_verify.py` prüft den strukturellen Pinvertrag und reproduzierbare
Artefakte, aber keine elektrische Top-Level-Verbindung. Es meldet deshalb auch
nicht länger irreführend eine bestandene `connectivity`-Prüfung. Der Circuit-
Inspector meldet die Top-Level-Blöcke bei solchen danebenliegenden Endpunkten
als `INCOMPLETE`/`unconnected`; die bisherigen Detailtests hatten lediglich die
Erreichbarkeit zwischen denselben falsch angenommenen Koordinaten geprüft und
konnten den geometrischen Grundfehler daher nicht erkennen.

## Kopiervorlage für jeden Arbeitsschritt

Diesen Block kopieren und vor dem Zeichnen ausfüllen:

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

## Prüfung nach jedem Netz

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --profile hardware/logisim/tinycpu-16-12.json \
  hardware/logisim/TinyCPU.circ
```

Während des schrittweisen Aufbaus darf der Inspector `TinyCPU: INCOMPLETE`
melden, weil spätere Pins noch offen sind. Neu auftretende Meldungen zu
`routing conflicts`, diagonalen/überlappenden Leitungen, Mehrfachtreibern oder
Breitenfehlern müssen dagegen vor dem nächsten Netz behoben werden.

Diagnoseblätter nur bei Bedarf in ein **temporäres** Verzeichnis schreiben:

```bash
tmpdir="$(mktemp -d)"
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --split-output "$tmpdir" hardware/logisim/TinyCPU.circ
```

So kann kein Generatorlauf versehentlich die Übersichtsseite oder die
eingecheckten Diagnoseartefakte überschreiben.
