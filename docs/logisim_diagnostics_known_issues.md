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
