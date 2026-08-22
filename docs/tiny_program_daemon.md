# Tiny Program Daemon (30-Minuten-Generator)

Dieses Dokument beschreibt einen ersten "Kunstprojekt"-Baustein: einen Daemon,
der regelmäßig TinyLanguage-Beispielprogramme erzeugt.

## Ziel

Der Daemon erzeugt per Intervall automatisch `.tiny`-Dateien. Standardmäßig:

- Intervall: **1800 Sekunden (30 Minuten)**
- Ausgabeordner: `generated_tiny_programs/`
- Ideenkatalog: lokal kuratierte Templates (Logik + Mathematik + Simulation)

Implementierung: `src/tiny_program_daemon.py`.

## Starten (einmalig)

```bash
python src/tiny_program_daemon.py --count 1
```

## Als laufender Dienst (Daemon)

```bash
python src/tiny_program_daemon.py
```

## Wichtige CLI-Optionen

- `--interval-seconds 1800`: Intervall einstellen
- `--count N`: endlich viele Programme erzeugen und beenden
- `--idea <slug>`: bestimmte Programmidee erzwingen
- `--seed <int>`: reproduzierbare Zufallsauswahl
- `--db-path <sqlite.db>`: speichert validierte Programme zusätzlich in SQLite

Beispiel:

```bash
python src/tiny_program_daemon.py --interval-seconds 60 --count 3 --idea nand-gate
```

## Qualitätskriterien für den Programmgenerator

Der Generator prüft neue Programme vor dem Schreiben/Speichern mit konservativen
Heuristiken:

1. **Keine Dead Stores**: Variablen dürfen nicht nur geschrieben, sondern müssen
   auch gelesen werden (außer explizit `_unused*`).
2. **Keine offensichtlichen Endlosschleifen**: `while (true)` und `while (1)`
   werden abgewiesen.
3. **Keine offensichtlichen unbehandelten Exceptions**: `throw` und
   offensichtliche `... / 0`-Muster werden abgewiesen.
4. **Keine Duplikate in der DB**: Beim Schreiben in SQLite wird eine
   normalisierte Signatur geprüft; semantisch identische Programme werden nicht
   mehrfach gespeichert.
5. **Einfache Deadlock-Warnung**: `spawn` ohne erkennbares `join(...)` führt zur
   Ablehnung.

### Weitere sinnvolle Kriterien (als nächste Aufgaben)

- **Kontrollfluss-Termination tiefer prüfen (erledigt 2026-08-21)**:
  Strukturierte `while`-Blöcke werden als zyklische Kontrollflussregionen
  vollständig erfasst. Der Validator akzeptiert nur Vergleichsschleifen, für
  deren Induktionsvariable im Schleifenrumpf ein Fortschritt nachweisbar ist;
  auch anders formatierte literale Endlosschleifen werden abgewiesen.
- **Typsicherheits-/Range-Checks (erledigt 2026-08-22)**: Divisionen werden nur
  akzeptiert, wenn ein numerisches Literal, eine lokale Literalzuweisung oder
  ein vorheriger Null-Check mit zwingendem `return` einen von Null verschiedenen
  Nenner nachweist. Eine spätere Zuweisung macht den Nachweis ungültig.
- **Ressourcenbegrenzung (erledigt 2026-08-22)**: Heap-Allokationen benötigen
  eine feste, nichtnegative Größe von höchstens 4096 Elementen. Vergleichs-
  schleifen benötigen einen lokal nachweisbaren ganzzahligen Startwert, eine
  konstante Schrittweite und eine Obergrenze von höchstens 10.000 Iterationen.
- **Determinismus-Profil**: optionales Verbot von Zeit-/Zufallsquellen.
- **Stil- und Lesbarkeitsregeln**: Mindestkommentare, Namenskonventionen,
  Programmlänge pro Kategorie.

## Systemd-Template

Eine Unit-Vorlage liegt unter:

- `tools/systemd/tiny-program-daemon.service`

Die Pfade (`WorkingDirectory`, `ExecStart`) bitte für dein Zielsystem anpassen.

## Sicherheits- und Projekt-Hinweise

Dieser erste Schritt nutzt absichtlich **nur lokale, vordefinierte Templates** und
führt keinen fremden Code aus.

Für die nächste Ausbaustufe (Crawler, Repo-Import, Virenscan, Portierung nach Tiny)
empfiehlt sich ein mehrstufiger Pipeline-Ansatz:

1. **Quelle holen** (z. B. RosettaCode / Git-Repos) in Quarantäne
2. **Sicherheitsprüfung** (Signaturen, statische Analyse, Allowlist)
3. **Automatische Portierung** nach TinyLanguage
4. **Sandbox-Testlauf** + Ergebnisbewertung
5. **Optional GUI-Wrapper** pro generiertem Programm

So bleibt der kreative Workflow erhalten, ohne den sicheren Standardbetrieb zu gefährden.
