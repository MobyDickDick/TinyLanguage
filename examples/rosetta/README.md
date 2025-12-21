# Rosetta helpers

Utilities for keeping Rosetta Code samples in sync and translating them to
TinyLanguage.

## Copy missing Python samples

`copy_rosetta_samples.py` pulls Python scripts from a source directory (default:
`examples/rosetta/python`) into a target folder. Typical invocations:

- Dry-run with a prefix filter:
  ```bash
  python examples/rosetta/copy_rosetta_samples.py /tmp/rosetta-mirror \
    --include fizz --include fib --limit 5 --dry-run
  ```
- Copy the next 3 missing files without waiting and trigger transpilation into
  a custom TinyLanguage output directory:
  ```bash
  python examples/rosetta/copy_rosetta_samples.py examples/rosetta/python \
    --limit 3 --delay 0 --transpile --transpile-dest examples/rosetta/expected
  ```

Flags:

- `--source`: where to read Python samples (defaults to `examples/rosetta/python`)
- `--include`: optional stem prefixes to restrict which missing files are copied
- `--limit`: maximum number of files to copy
- `--delay`: seconds to wait between copy operations
- `--dry-run`: print planned copies without writing files
- `--transpile/--no-transpile`: run the TinyLanguage transpiler after copying
- `--transpile-dest`: destination directory for transpiled TinyLanguage files

## Transpile Rosetta samples

`src/transpile_rosetta.py` translates all Rosetta Python samples into TinyLanguage.
You can override the source location if you maintain your own mirror:

```bash
python -m transpile_rosetta --source examples/rosetta/python --dest examples/rosetta/expected
```
