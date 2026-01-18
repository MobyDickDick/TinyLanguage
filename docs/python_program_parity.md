# Python program parity inventory

This inventory tracks Python entrypoint scripts (files that contain
`if __name__ == "__main__"`) and their TinyLanguage equivalents. It captures
which programs already have Tiny translations and highlights remaining gaps for
future conversion work.

## Entrypoint parity

| Python entrypoint | Tiny equivalent | Notes |
| --- | --- | --- |
| `benchmarks/microbenchmarks.py` | `src_tiny/microbenchmarks.tiny` | Tiny runner mirrors the benchmark harness with Tiny + Python interop. |
| `examples/rosetta/copy_rosetta_samples.py` | `src_tiny/copy_rosetta_samples.tiny` | Shared Rosetta sample copier. |
| `run_all.py` | `src_tiny/run_all.tiny` | Tiny version mirrors the main runner in `src/run_all.py`. |
| `src/language_server_cli.py` | `src_tiny/language_server_cli.tiny` | CLI entrypoint already mirrored. |
| `src/run_all.py` | `src_tiny/run_all.tiny` | Tiny runner is available. |
| `src/tiny_lang_cli.py` | `src_tiny/tiny_lang_cli.tiny` | Tiny CLI available. |
| `src/tiny_language_api.py` | `src_tiny/tiny_language_api.tiny` | Tiny API wrapper available. |
| `src/tiny_language_cli.py` | `src_tiny/tiny_language_cli.tiny` | Tiny CLI available. |
| `src/tiny_language_compiler_cli.py` | `src_tiny/tiny_language_compiler_cli.tiny` | Tiny compiler CLI available. |
| `src/tiny_language_stitched.py` | _missing_ | Generated stitched file has no Tiny counterpart yet. |
| `src/tiny_project_cli.py` | _missing_ | Project scaffolding CLI not yet mirrored. |
| `src/tinyc_cli.py` | `src_tiny/tinyc_cli.tiny` | Tiny C compiler CLI available. |
| `src/transpile_rosetta.py` | `src_tiny/transpile_rosetta.tiny` | Tiny transpiler entrypoint available. |
| `tiny_language.py` | `src_tiny/tiny_language.tiny` | Tiny top-level entrypoint available. |
| `tools/generate_doc_reference.py` | _missing_ | Doc tooling not yet mirrored. |
| `tools_unused_scan.py` | _missing_ | Maintenance tool not yet mirrored. |
| `vscode-extension/python/tiny_debug_adapter.py` | _missing_ | VS Code debug adapter not yet mirrored. |
| `vscode-extension/python/vscode_helpers.py` | _missing_ | VS Code helper script not yet mirrored. |
