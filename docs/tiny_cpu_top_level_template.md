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
| 4 | Akkumulator-Steuerung | passender `FetchDecode`-Ausgang | passender `Datapath`-Eingang | 1 je Netz | Akkumulator ändert sich nur bei aktivem Ladesignal an der Taktflanke. |
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

## Korrektur der bereits gezeichneten Decode-Leitungen

Die automatische Logisim-Symboldarstellung verwendet den `loc`-Punkt einer
Subcircuit-Instanz als rechten Ausgangsanker. Die zuvor verwendeten Punkte
`x=430` an `FetchDecodeControls` und `x=1610` an `ErrorFlags` liegen deshalb
neben den sichtbaren Pins. Die betreffenden Netze müssen vollständig gelöscht
und mit diesen Endpunkten neu gezeichnet werden (Zwischenpunkte dürfen in
freien Korridoren liegen):

| Netz | von | nach |
|---|---:|---:|
| `OPCODE` | `FetchDecode.OPCODE (330,110)` | `FetchDecodeControls.OPCODE (130,910)` |
| `CLK` | bestehendes CLK-Netz, z. B. Abzweig `(1290,10)` | `ErrorFlags.CLK (1330,90)` |
| `CLEAR_ERROR` | `FetchDecodeControls.CLEAR_ERROR (330,790)` | `ErrorFlags.CLEAR_ERROR (1330,80)` |
| `SET_OVF` | `FetchDecodeControls.SET_OVF (330,850)` | `ErrorFlags.SET_OVF (1330,100)` |
| `SET_DIV0` | `FetchDecodeControls.SET_DIV0 (330,860)` | `ErrorFlags.SET_DIV0 (1330,110)` |
| `SET_ADDR` | `FetchDecodeControls.SET_ADDR (330,870)` | `ErrorFlags.SET_ADDR (1330,120)` |
| `SET_INV` | `FetchDecodeControls.SET_INV (330,880)` | `ErrorFlags.SET_INV (1330,130)` |
| `SET_ILL` | `FetchDecodeControls.SET_ILL (330,890)` | `ErrorFlags.SET_ILL (1330,140)` |
| `SET_INPUT` | `FetchDecodeControls.SET_INPUT (330,900)` | `ErrorFlags.SET_INPUT (1330,150)` |

Die vorhandenen falschen Endpunkte dürfen nicht nur mit kurzen Stücken zu den
richtigen Pins verlängert werden: Dadurch blieben irreführende Stummel und
unnötige Wege erhalten. Jedes Netz einzeln ersetzen und anschließend mit dem
Poke-Werkzeug am Quell- und Zielpin prüfen.

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
