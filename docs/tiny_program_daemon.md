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

Beispiel:

```bash
python src/tiny_program_daemon.py --interval-seconds 60 --count 3 --idea nand-gate
```

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
