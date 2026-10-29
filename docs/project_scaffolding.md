# Project scaffolding and CLI ergonomics

`tiny project init` creates a runnable project independently of the source
checkout. `tiny-project init` and `python -m tiny_project_cli init` are equivalent.

```bash
tiny project init my_app --vscode
tiny my_app/src/main.tiny
```

The generated layout is:

```text
my_app/
  module.json
  src/main.tiny
  .vscode/launch.json       # with --vscode
  .vscode/settings.json     # with --vscode
```

`module.json` records the project name, entry path and dependency list.
`src/main.tiny` prints a greeting. `--name` overrides the directory-derived name;
`--force` permits overwriting generated files. The scaffolder otherwise refuses
to overwrite an existing file.

The editor settings record the scaffolding Python's `sys.executable`, with an
empty runtime override for installed discovery. `--python` selects a different
Python executable; `--runtime` supplies an explicit development runtime path.
The launch configuration references these settings instead of embedding a
checkout or installation directory.

`tiny pkg init my_app` creates `tiny.toml` separately. It creates a package
manifest only; it does not create application sources or VS Code settings.
See the [installed quickstart](installed_workflows.md) for a complete workflow.

## Future templates

The files under `docs/project_template_v1/` describe proposed versioned templates.
`--template`, `--bin`, `--lib`, `--with-tests`, `--with-ci`, workspace templates
and `tiny pkg upgrade-template` are design proposals, not implemented flags.
