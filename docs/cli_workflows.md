# CLI workflows

This guide summarizes the supported command-line flows for running TinyLanguage
programs. All commands are intended to run from the repository root; the
canonical entry points live under `src/`.

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

## 2. CLI wrapper with backend selection (`tiny_language_cli.py`)

The CLI wrapper mirrors the interpreter API but adds explicit backend selection
and consistent argument parsing:

```bash
python src/tiny_language_cli.py --file path/to/program.tiny
python src/tiny_language_cli.py --source "print(1 + 2);"
python src/tiny_language_cli.py --file - < path/to/program.tiny
```

Backends:

```bash
python src/tiny_language_cli.py --file path/to/program.tiny --backend interpreter
python src/tiny_language_cli.py --file path/to/program.tiny --backend python
python src/tiny_language_cli.py --file path/to/program.tiny --native-backend
```

Pass-through arguments are separated with `--` and arrive in `sys.argv` inside
Tiny programs:

```bash
python src/tiny_language_cli.py --file path/to/program.tiny -- --flag value
```

### End-to-end workflow: validate first, then run

For CI and pre-commit hooks, use a two-step flow: first run with `--typecheck`
(which validates before executing), then run again with the target backend for
explicit backend parity checks.

```bash
# Step 1: fail early on typing/lint errors.
python src/tiny_language_cli.py --file path/to/program.tiny --typecheck

# Step 2: run the same file with the selected backend.
python src/tiny_language_cli.py --file path/to/program.tiny --backend python
```

Regression coverage for this workflow lives in
`tests/detailtests/test_tiny_language_cli_self_host.py`
(`test_tiny_cli_typecheck_then_backend_run_workflow`).

### Opt-in CI typecheck baseline trial

The repository also provides a manually enabled GitHub Actions job for gradual
adoption reviews. Start the **Tests, benchmark & fuzz** workflow with the
`run_typecheck_gate` input enabled. The job runs the `typing` lint profile over
the curated manifest at `tests/fixtures/typecheck_ci/manifest.json` and uploads
`typecheck-baseline-report` even when the gate fails.

Run the same gate locally with:

```bash
python tools/typecheck_ci_gate.py
```

The command writes `artifacts/ci/typecheck-baseline.json`. Each fixture declares
its expected diagnostic codes. A new diagnostic or a missing positive-control
diagnostic marks the report as `review-required` and fails the command, so the
artifact can be reviewed before expectations are deliberately updated. Paths,
ordering, and JSON keys are normalized to keep reports deterministic across
runs.

## 3. LLVM emission (via `tiny_language_cli`)

The CLI wrapper can emit LLVM IR without running the program. The LLVM pipeline
is **experimental** and only supports a subset of the language; use the
interpreter backend when you need full feature coverage.

```bash
python src/tiny_language_cli.py --file path/to/program.tiny --emit-llvm -
python src/tiny_language_cli.py --file path/to/program.tiny --emit-llvm out.ll
python src/tiny_language_cli.py --file path/to/program.tiny --emit-llvm - --llvm-opt
```

Optional overrides:

```bash
python src/tiny_language_cli.py --file path/to/program.tiny \
  --emit-llvm out.ll \
  --llvm-target-triple x86_64-unknown-linux-gnu \
  --llvm-data-layout "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
```

## 4. Module workflows

For multi-file projects, combine the CLI wrapper with `TINYPATH` and module
manifests:

```bash
TINYPATH=../deps python src/tiny_language_cli.py --file my_pkg/main.tiny --backend interpreter
TINYPATH=../deps python src/tiny_language_cli.py --file my_pkg/main.tiny --native-backend
```

## 5. Related helpers

- `python -m tiny_project_cli init my_app --vscode` scaffolds a TinyLanguage
  project.
- `python -m tinyc_cli` and `python src/tiny_language_compiler_cli.py` provide
  the C backend compiler flows.
- `python src/language_server_cli.py` exposes LSP-style operations (hover,
  diagnostics, completions) from the terminal.
