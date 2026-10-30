# Tiny Program Repository DB (SQLite)

This design represents Tiny programs **atomically** in SQLite:

- `programs`: program metadata and source code.
- `statements`: a linear program counter (PC) sequence.
- A separate table for each statement type:
  - `labels`
  - `print_statements`
  - `set_statements`
  - `goto_statements`
  - `if_goto_statements`

This supports three goals:

1. **Repository**: store programs in a form that supports versioning.
2. **Workbench / stepping**: an interpreter can execute individual steps using `pc`.
3. **Quality analysis**: graph analysis of jump edges can identify unreachable code, for example.

<a id="dateien"></a>
## Files

- Tiny generator (writes SQL files): `src_tiny/tiny_program_repository_db.tiny`
- SQLite adapter (Python): `src/tiny_program_repository_db_adapter.py`
- Comparison CLI: `tools/compare_tiny_sources.py`
- Test: `tests/test_tiny_program_repository_db_adapter.py`

<a id="neue-konverter"></a>
## New converters

The adapter now includes two direct converters:

- `source_to_db(program_name, source_text) -> int`
  - Accepts Tiny source.
  - Parses the source into supported statement types (`label`, `print`, `set`, `goto`, `if_goto`).
  - Stores the program, including normalized statements, in the database.
  - Returns `program_id`.

- `db_to_source(program_id) -> str`
  - Loads a program's normalized statements from the database.
  - Rebuilds the Tiny source from those statements.
  - Returns the reconstructed source code.

<a id="unterstützte-tiny-zeilenformate"></a>
### Supported Tiny line formats

- `<label>:`
- `print <expr>`
- `set <var> = <expr>`
- `goto <label>`
- `if <expr> goto <label>`

Blank lines and lines starting with `#` are ignored.

<a id="vergleichsprogramm"></a>
## Comparison program

A CLI program is also available:

```bash
python tools/compare_tiny_sources.py <datei_a.tiny> <datei_b.tiny>
```

Behavior:

- Prints `EQUIVALENT` and exits with code `0` when both source files represent the same Tiny program after normalization.
- Prints `DIFFERENT` and exits with code `1` when the programs differ.

<a id="kurzer-ablauf"></a>
## Quick workflow

1. Run the Tiny program to generate the schema and seed data:
   - `python src/tiny_language_cli.py --file src_tiny/tiny_program_repository_db.tiny`
2. Use the adapter to create the database and register programs.
3. Use the `source_to_db(...)` / `db_to_source(...)` converters for import/export.
4. Execute one step at a time with `step(...)`.
5. Detect unreachable code with `find_unreachable_pcs(...)`.
6. Compare two Tiny source files with `tools/compare_tiny_sources.py`.
