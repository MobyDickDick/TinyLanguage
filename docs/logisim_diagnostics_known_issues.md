# Bekannte Fehler der Logisim-Diagnose-Schaltung

Diese Notiz dokumentiert die noch vorhandenen Fehler der aktuellen
Diagnose-Lösung. Die Schaltungen `hardware/logisim/diagnostics/TinyCPU-FetchDecode.circ`
und `hardware/logisim/diagnostics/TinyCPU.circ` werden hier bewusst nicht
korrigiert.

## Betroffene Stelle

Die sichtbare Fehlstelle liegt im Diagnose-Schaltbild für Fetch/Decode an den
Ausgängen des Decoders. Dort werden die aus dem Decoder kommenden Leitungen mit
Status- beziehungsweise Hilfssignalen verbunden, obwohl ihre Bitbreiten nicht
zueinander passen.

## Noch vorhandene Fehler

- **Breiteninkompatible Verbindung an `NOT_ZERO`:** Das Steuersignal
  `JUMP_NOT_ZERO` ist ein 1-Bit-Ausgang. In der gezeigten Lösung wird es über
  eine Leitung mit einem Signalpfad verbunden, der in Logisim als 16-Bit-Pfad
  markiert ist. Dadurch entsteht die angezeigte Fehlermeldung
  `Breiten nicht kompatibel (2)`.
- **Breiteninkompatible Verbindung an `ERROR_HALT`:** Auch der Haltpfad für
  Fehlerfälle ist als 1-Bit-Steuerinformation gedacht, wird aber im Schaltbild
  an einen breiteren Bus geführt. Das erzeugt dieselbe Klasse von
  Breitenkonflikten und verhindert eine saubere Simulation.
- **Vermischung von Datenbus und Steuerleitungen:** Die orange markierte
  Verdrahtung zeigt, dass ein 16-Bit-Datenpfad beziehungsweise ein daraus
  abgeleiteter Bus direkt mit booleschen Decoder-Ausgängen verschaltet wurde.
  Diese Netze müssen logisch getrennt bleiben; ein Bus darf nicht als Ersatz
  für einzelne Steuersignale verwendet werden.
- **Decoder-Ausgänge sind deshalb nicht belastbar prüfbar:** Solange die
  Breitenfehler bestehen, kann nicht zuverlässig bewertet werden, ob die
  Decoder-Ausgänge für Sprung- und Fehler-Halt-Befehle funktional korrekt sind,
  weil die Simulation bereits an der Netlist-Struktur scheitert.

## Erwartete Konsequenz

Die Diagnose-Schaltung bleibt in diesem Zustand absichtlich fehlerhaft
dokumentiert. Eine spätere Korrektur muss in den Schaltungsdateien selbst
ansetzen und die betroffenen 1-Bit-Steuerleitungen von 16-Bit-Datenbussen
trennen, ohne die Opcode-Ausgänge erneut mit Busbreiten zu vermischen.
