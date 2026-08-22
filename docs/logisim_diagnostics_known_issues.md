# Prüfung der Logisim-Diagnose-Schaltungen

Die Projekte unter `hardware/logisim/diagnostics/` werden mit
`tiny_cpu_circuit.py --split-output` direkt aus der integrierten Schaltung
`hardware/logisim/TinyCPU.circ` erzeugt. Damit gelten für die einzelnen Blätter
dieselben Bauteile, Bitbreiten und Verbindungen wie für die Referenzschaltung.

## Ergebnis der Prüfung

Die frühere, manuell abweichende `TinyCPU-FetchDecode.circ` verband
1-Bit-Steuersignale mit einem 16-Bit-Datenpfad. Insbesondere waren
`JUMP_NOT_ZERO` und `HALT_ERROR` nicht mit ihren vorgesehenen Decoder-Lanes
verbunden. Diese Fassung wurde durch die beiden aktuellen Referenzblätter
`TinyCPU-FetchDecode.circ` und `TinyCPU-FetchDecodeControls.circ` ersetzt. Der
PC-/ROM-Pfad und die Steuersignaldecodierung bleiben dadurch elektrisch
getrennt und lassen sich unabhängig untersuchen.

Alle sechs Diagnoseprojekte bestehen aus genau einem eigenständig ladbaren
Blatt und bestehen die strukturelle Verbindungsprüfung. Ein automatischer Test
vergleicht sie bytegenau mit neu aus `TinyCPU.circ` erzeugten Dateien, damit
künftige Änderungen der Referenzschaltung nicht unbemerkt von den
Diagnoseprojekten abweichen.

## Reproduzierbare Prüfung

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --split-output hardware/logisim/diagnostics \
  hardware/logisim/TinyCPU.circ

for project in hardware/logisim/diagnostics/*.circ; do
  PYTHONPATH=src python src/tiny_cpu_circuit.py "$project"
done
```

Diese Prüfung bewertet Struktur, Anschlussbelegung und Busbreiten. Die
elektrische Laufzeitsimulation der Logisim-Bauteilbibliothek bleibt weiterhin
Aufgabe von Logisim-evolution.

## Ursachenanalyse der wiederholten Rücksetzung

Die fehlerhafte Fassung wurde nicht von Logisim selbst wiederhergestellt. Die
Git-Historie zeigt vielmehr, dass auf die ausdrücklich wiederhergestellte
Benutzerfassung (`ac06b29` beziehungsweise später `5f4d2ab`) jeweils erneut ein
älterer, automatisiert erzeugter Reparaturstand (`3e9ea7a`, `c5b8cd2` und
`de63af2`) angewendet und anschließend über einen Pull Request zusammengeführt
wurde. Damit wurde bei der Reparatur die falsche Baseline gewählt: statt den
jeweils neuesten Benutzer-Commit zu korrigieren, dienten frühere
Agenten-Commits als vermeintlich bekannte, „funktionierende“ Referenz.

Begünstigt wurde das durch Regressionstests, die konkrete Koordinaten und
Bauteilpositionen der älteren Zeichnung festschrieben. Eine elektrisch anders
angeordnete Benutzerlösung schlug daher selbst dann fehl, wenn ihr Aufbau
inhaltlich gleichwertig war. Der scheinbar einfachste Weg zu grünen Tests war
so das Zurückkopieren der alten Zeichnung – genau das hat die Benutzeränderung
wiederholt verdrängt.

Für die aktuelle Reparatur gilt deshalb ausdrücklich Commit `28d49cb` als
Baseline. Bauteile und Layout dieser Fassung bleiben erhalten; korrigiert wurden
nur fehlerhafte Netze, Busabgriffe und die dazugehörigen Diagnose-Fixtures.
Die Tests ermitteln verschobene Bauteile nun anhand ihrer Labels oder ihrer
aktuellen Schnittstelle, statt die alte Zeichnung durch historische
Koordinaten indirekt wiederherzustellen. Die aus dem Hauptprojekt erzeugten
Diagnoseblätter bleiben bytegenau reproduzierbar.
