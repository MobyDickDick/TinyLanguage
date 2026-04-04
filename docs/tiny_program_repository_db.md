# Tiny Program Repository DB (SQLite)

Dieses Konzept bildet Tiny-Programme **atomar** in SQLite ab:

- `programs`: Programm-Metadaten und Quelltext.
- `statements`: lineare Program Counter (PC)-Folge.
- Pro Befehlsart eine eigene Tabelle:
  - `labels`
  - `print_statements`
  - `set_statements`
  - `goto_statements`
  - `if_goto_statements`

Damit lassen sich drei Ziele abdecken:

1. **Repository**: Programme versionierbar speichern.
2. **Werkbank / Schrittbetrieb**: Ein Interpreter kann über `pc` Einzelschritte ausführen.
3. **Qualitätsanalyse**: Graphanalyse über Sprungkanten findet z. B. nicht erreichbare Teile.

## Dateien

- Tiny-Generator (schreibt SQL-Dateien): `src_tiny/tiny_program_repository_db.tiny`
- SQLite-Adapter (Python): `src/tiny_program_repository_db_adapter.py`
- Test: `tests/test_tiny_program_repository_db_adapter.py`

## Kurzer Ablauf

1. Tiny-Programm ausführen, um Schema + Seed zu generieren:
   - `python src/tiny_language_cli.py --file src_tiny/tiny_program_repository_db.tiny`
2. Adapter nutzen, um Datenbank anzulegen und Programme zu registrieren.
3. Mit `step(...)` schrittweise ausführen.
4. Mit `find_unreachable_pcs(...)` tote Programmteile erkennen.
