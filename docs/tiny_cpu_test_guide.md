# TinyCPU.circ selbst testen

Diese Anleitung ist der kurze, empfohlene Weg für einen vollständigen Test der
eingecheckten Schaltung. Alle Befehle werden im Hauptverzeichnis des
TinyLanguage-Checkouts ausgeführt.

## Was du brauchst

- **Java 21 oder neuer** (`java -version`)
- **Python 3** (`python3 --version`)
- eine Internetverbindung für den ersten Lauf **oder** die Datei
  `logisim-evolution-4.1.0-all.jar`

Du brauchst Logisim nicht separat zu installieren. Das Testskript lädt genau
die unterstützte Logisim-evolution-Version 4.1.0 in den Benutzer-Cache. Die JAR
wird nicht in Git eingecheckt.

## Vollständiger automatischer Test

1. Öffne ein Terminal und wechsle in den Checkout:

   ```bash
   cd /pfad/zu/TinyLanguage
   ```

2. Prüfe Java:

   ```bash
   java -version
   ```

   Die Ausgabe muss Java 21 oder neuer nennen.

3. Starte den Test:

   ```bash
   scripts/test-logisim.sh
   ```

Das Skript lädt `hardware/logisim/TinyCPU.circ` im echten Simulator, führt den
17-Takt-Zähltest zweimal aus und prüft anschließend jeden Opcode in einem
isolierten Verhaltensfall sowie alle Fehlerflags. Bedingte Sprünge werden dabei
jeweils genommen und nicht genommen. Ein erfolgreicher Lauf endet mit Exitcode 0 und erzeugt den
Prüfbericht `artifacts/tinycpu-ap12-acceptance/acceptance.json`. Darin muss
`"status": "passed"` stehen.

### Wenn du die Logisim-JAR schon hast

Lege die exakt benannte Datei `logisim-evolution-4.1.0-all.jar` irgendwo unter
dem Checkout ab und führe aus:

```bash
scripts/test-logisim-local.sh
```

Liegt sie außerhalb des Checkouts oder gibt es mehrere Kopien, gib den Pfad
explizit an:

```bash
scripts/test-logisim-local.sh /pfad/zu/logisim-evolution-4.1.0-all.jar
```

## Ergebnis später ohne Simulator nachprüfen

Ein bereits erzeugtes Beweispaket lässt sich nur mit Python auf Vollständigkeit
und unveränderte Prüfsummen kontrollieren:

```bash
PYTHONPATH=src python3 src/tiny_cpu_logisim.py \
  --verify-acceptance artifacts/tinycpu-ap12-acceptance
```

Diese Prüfung simuliert die CPU nicht erneut. Sie bestätigt, dass das zuvor vom
echten Simulator erzeugte Paket vollständig und unverändert ist.

## Schaltung zusätzlich ansehen

Für die visuelle Kontrolle starte Logisim-evolution 4.1.0 und öffne
`hardware/logisim/TinyCPU.circ`. Wähle links das Blatt `TinyCPUMain`. Mit dem
Poke-Werkzeug kannst du Signale untersuchen; Änderungen an der Datei sind für
den automatischen Test nicht nötig.

Falls das große Projekt nicht lädt, öffne zuerst der Reihe nach
`hardware/logisim/smoke/PinPair-1bit.circ`, `PinPair-12bit.circ` und
`PinPair-16bit.circ`. Funktionieren diese, helfen die Einzelprojekte unter
`hardware/logisim/diagnostics/`, das betroffene Schaltungsblatt einzugrenzen.

## Häufige Probleme

| Meldung oder Symptom | Lösung |
|---|---|
| `Java 21 or newer is required` | Java 21+ installieren oder `JAVA=/pfad/zu/java scripts/test-logisim.sh` verwenden. |
| Download der JAR scheitert | JAR manuell herunterladen und `scripts/test-logisim-local.sh /pfad/zur/JAR` ausführen. |
| Mehrere JAR-Dateien gefunden | Den gewünschten vollständigen Pfad an `scripts/test-logisim-local.sh` übergeben. |
| Test schlägt fehl | Die erste Fehlermeldung sowie `artifacts/tinycpu-ap12-acceptance/acceptance.json` prüfen; ein abgebrochener Lauf gilt nicht als bestanden. |
