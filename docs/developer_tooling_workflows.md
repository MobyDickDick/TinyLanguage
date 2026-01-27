# Developer tooling workflows

This guide standardizes the day-to-day tooling flow for TinyLanguage: which
language-server entry points to use, how to apply lints consistently, and what
editor setup is recommended for contributors.

## LSP defaults

The TinyLanguage language server lives in `src/language_server.py`, and the
companion CLI wrapper (`src/language_server_cli.py`) mirrors common LSP
request/response flows for hover, completion, diagnostics, formatting, references,
rename, and code actions. Use
this CLI for quick checks or for wiring editor integrations that do not speak
JSON-RPC yet. For example:

```bash
PYTHONPATH=src python src/language_server_cli.py --file path/to/file.tiny diagnostics
```

**Default workflow:**

1. **Format first.** Run the formatter to normalize source before linting.
2. **Collect diagnostics.** Run the `diagnostics` request to collect lints in a
   machine-readable JSON payload.
   The payload adheres to the shared diagnostic schema in
   [`docs/diagnostic_error_schema.md`](diagnostic_error_schema.md).

The `language_server_cli.py` helper exposes both steps, so editors or scripts
can treat it as the default LSP entry point until a full JSON-RPC client is
needed.

## Lint profiles

TinyLanguage lints run as part of the language server diagnostics and the
formatter pipeline. The recommended lint profiles are:

- **Default (recommended):** Use all built-in lints, including heap lifetime
  checks. The interpreter enables heap lints by default.
- **Typing (opt-in):** Enable additional annotation-aware checks (assignment
  stability and annotation enforcement). Run diagnostics with
  `python src/language_server_cli.py --lint-profile typing --file path/to/file.tiny diagnostics`.
- **Relaxed heap mode:** If you need to temporarily suppress heap lifetime
  lints, set `TINY_LINT_HEAP=0` in your environment before running diagnostics
  or tests. All other lints remain active.

To keep CI and local workflows aligned, only use relaxed heap mode for targeted
experiments and capture the reason in your commit or PR notes.

## Formatter + lint checks in CI

TinyLanguage CI runs a lightweight formatter and lint gate to ensure the
recommended workflow stays healthy:

1. **Formatter stability**: `tools/check_format_lint.py` formats a curated set
   of fixtures and verifies the output is unchanged.
2. **Lint clean**: the same fixtures must return zero diagnostics with the
   default lint profile (heap lints enabled).

To mirror CI locally, run:

```bash
python tools/check_format_lint.py
```

## Recommended editor setup (VS Code)

TinyLanguage ships a VS Code extension and scaffolding helper to align settings
across contributors.

1. **Scaffold a workspace with defaults**:

   ```bash
   python -m tiny_project_cli init my_app --vscode
   ```

   This creates `src/main.tiny`, `module.json`, and `.vscode/launch.json` +
   `.vscode/settings.json` with the TinyLanguage debug adapter defaults.

2. **Install the local extension** from `vscode-extension/`, either by running
   it in a VS Code development window or by packaging/installing a `.vsix`.

3. **Align Python tooling paths**: set `tinylanguage.pythonPath` to the Python
   executable that should run the TinyLanguage tools (for example, the same
   interpreter your workspace uses). This keeps formatter helpers, lints, and
   the debug adapter in sync.

For detailed debugging workflows and troubleshooting, see
`docs/debugger_workflows.md`.
