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
- Vergleichs-CLI: `tools/compare_tiny_sources.py`
- Test: `tests/test_tiny_program_repository_db_adapter.py`

## Neue Konverter

Der Adapter enthält jetzt zwei direkte Konverter:

- `source_to_db(program_name, source_text) -> int`
  - Nimmt Tiny-Source entgegen.
  - Parsed den Source in unterstützte Statement-Typen (`label`, `print`, `set`, `goto`, `if_goto`).
  - Speichert das Programm inkl. normalisierter Statements in der Datenbank.
  - Liefert `program_id` zurück.

- `db_to_source(program_id) -> str`
  - Lädt die normalisierten Statements eines Programms aus der Datenbank.
  - Baut daraus den Tiny-Source wieder auf.
  - Liefert den rekonstruierten Sourcecode zurück.

### Unterstützte Tiny-Zeilenformate

- `<label>:`
- `print <expr>`
- `set <var> = <expr>`
- `goto <label>`
- `if <expr> goto <label>`

Leere Zeilen und Zeilen mit `#` am Anfang werden ignoriert.

## Vergleichsprogramm

Es gibt zusätzlich ein CLI-Programm:

```bash
python tools/compare_tiny_sources.py <datei_a.tiny> <datei_b.tiny>
```

Verhalten:

- Gibt `EQUIVALENT` aus und endet mit Exit-Code `0`, wenn beide Source-Dateien nach Normalisierung das gleiche Tiny-Programm darstellen.
- Gibt `DIFFERENT` aus und endet mit Exit-Code `1`, wenn sich die Programme unterscheiden.

## Kurzer Ablauf

1. Tiny-Programm ausführen, um Schema + Seed zu generieren:
   - `python src/tiny_language_cli.py --file src_tiny/tiny_program_repository_db.tiny`
2. Adapter nutzen, um Datenbank anzulegen und Programme zu registrieren.
3. Konverter `source_to_db(...)` / `db_to_source(...)` für Import/Export einsetzen.
4. Mit `step(...)` schrittweise ausführen.
5. Mit `find_unreachable_pcs(...)` tote Programmteile erkennen.
6. Mit `tools/compare_tiny_sources.py` zwei Tiny-Quellen vergleichen.
