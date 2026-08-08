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
