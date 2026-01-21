# CLI workflows

This guide summarizes the supported command-line flows for running TinyLanguage
programs. All commands are intended to run from the repository root. For module
entrypoints (`python -m tiny_lang_cli`), set `PYTHONPATH=src` so Python can find
TinyLanguage’s modules.

## 1. Interpreter entrypoint (`tiny_language.py`)

Use the interpreter directly for the simplest path:

```bash
python src/tiny_language.py path/to/program.tiny
python src/tiny_language.py -e "print(1 + 2);"
```

Run through the native backend instead of the interpreter by adding
`--native-backend` before the file path or `-e` source:

```bash
python src/tiny_language.py --native-backend path/to/program.tiny
python src/tiny_language.py --native-backend -e "print(1 + 2);"
```

## 2. CLI wrapper with backend selection (`tiny_language_cli` / `tiny_lang_cli`)

The CLI wrapper mirrors the interpreter API but adds explicit backend selection
and consistent argument parsing. The recommended entrypoint is the module-based
wrapper:

```bash
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny
PYTHONPATH=src python -m tiny_lang_cli --source "print(1 + 2);"
PYTHONPATH=src python -m tiny_lang_cli --file - < path/to/program.tiny
```

Backends:

```bash
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny --backend interpreter
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny --backend python
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny --native-backend
```

Pass-through arguments are separated with `--` and arrive in `sys.argv` inside
Tiny programs:

```bash
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny -- --flag value
```

## 3. LLVM emission (via `tiny_language_cli`)

The CLI wrapper can emit LLVM IR without running the program:

```bash
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny --emit-llvm -
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny --emit-llvm out.ll
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny --emit-llvm - --llvm-opt
```

Optional overrides:

```bash
PYTHONPATH=src python -m tiny_lang_cli --file path/to/program.tiny \
  --emit-llvm out.ll \
  --llvm-target-triple x86_64-unknown-linux-gnu \
  --llvm-data-layout "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
```

## 4. Module workflows

For multi-file projects, combine the CLI wrapper with `TINYPATH` and module
manifests:

```bash
PYTHONPATH=src TINYPATH=../deps python -m tiny_lang_cli --file my_pkg/main.tiny --backend interpreter
PYTHONPATH=src TINYPATH=../deps python -m tiny_lang_cli --file my_pkg/main.tiny --native-backend
```

## 5. Related helpers

- `python -m tiny_project_cli init my_app --vscode` scaffolds a TinyLanguage
  project.
- `python -m tinyc_cli` and `python src/tiny_language_compiler_cli.py` provide
  the C backend compiler flows.
- `python src/language_server_cli.py` exposes LSP-style operations (hover,
  diagnostics, completions) from the terminal.
