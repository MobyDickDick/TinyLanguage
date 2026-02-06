# LSP smoke tests

This checklist provides lightweight sanity checks for the TinyLanguage language
server helper (`src/language_server.py`) and its CLI wrapper
(`src/language_server_cli.py`). Use these smoke tests to verify that formatting,
hover, completion, and diagnostics remain stable.

## CLI smoke checks

All examples assume `PYTHONPATH=src` so the language server imports resolve.
The sample fixture below is used by the self-hosted tests:
`tests/fixtures/language_server_entrypoint_sample.tiny`.

1. **Diagnostics** (lints + parse errors):

   ```bash
   PYTHONPATH=src python src/language_server_cli.py \
     --file tests/fixtures/language_server_entrypoint_sample.tiny \
     diagnostics
   ```

2. **Formatting** (full source):

   ```bash
   PYTHONPATH=src python src/language_server_cli.py \
     --file tests/fixtures/language_server_entrypoint_sample.tiny \
     format
   ```

3. **Formatting** (edits):

   ```bash
   PYTHONPATH=src python src/language_server_cli.py \
     --file tests/fixtures/language_server_entrypoint_sample.tiny \
     format-edits
   ```

4. **Hover**:

   ```bash
   PYTHONPATH=src python src/language_server_cli.py \
     --file tests/fixtures/language_server_entrypoint_sample.tiny \
     hover --symbol add
   ```

5. **Completions**:

   ```bash
   PYTHONPATH=src python src/language_server_cli.py \
     --file tests/fixtures/language_server_entrypoint_sample.tiny \
     completions --line 1 --character 1
   ```

## Pytest smoke checks

These tests cover both the Python and Tiny self-hosted language server CLIs and
are the primary regression suite for LSP behavior:

```bash
pytest tests/detailtests/test_language_server_cli.py \
  tests/detailtests/test_tiny_language_server_cli_self_host.py
```

## Related references

- `docs/language_server_workflows.md` for detailed request/response shapes.
- `docs/developer_tooling_workflows.md` for recommended sequencing and lint
  profiles.
