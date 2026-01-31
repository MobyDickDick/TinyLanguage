# TinyLanguage project template (v1)

This folder is the **reference project layout template** for TinyLanguage.
It matches the `v1` scaffold described in
`docs/project_scaffolding.md` and includes the default tooling configuration
used by the TinyLanguage VS Code extension.

## What this template includes

- `tiny.toml` with the baseline package metadata.
- A `src/` tree with a `main.tiny` entry point and optional `__init__.tiny`.
- A `tests/` folder with a starter test that mirrors the entry-point behavior.
- `.vscode/` launch + settings files that wire up the TinyLanguage debug adapter.
- `.gitignore` tuned for TinyLanguage build artifacts.

## Using the template

1. Copy this directory to start a new project.
2. Update `tiny.toml` with your package name and metadata.
3. Set `tinylanguage.runtimePath` in `.vscode/settings.json` to the path of
   `tiny_language.py` (or the installed TinyLanguage runtime).
4. Open the folder in VS Code and run the **TinyLanguage: Launch main.tiny**
   debug configuration.

If you want to scaffold a new project via the CLI instead, use:

```bash
python -m tiny_project_cli init my_app --vscode
```

That command creates the same baseline layout with runtime settings inferred
from the TinyLanguage checkout.
