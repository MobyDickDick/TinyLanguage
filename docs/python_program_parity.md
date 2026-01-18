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
| `src/tiny_language_stitched.py` | `src_tiny/tiny_language_stitched.tiny` | Tiny wrapper delegates to the stitched Python runtime. |
| `src/tiny_project_cli.py` | `src_tiny/tiny_project_cli.tiny` | Tiny wrapper delegates to the project scaffolding CLI. |
| `src/tinyc_cli.py` | `src_tiny/tinyc_cli.tiny` | Tiny C compiler CLI available. |
| `src/transpile_rosetta.py` | `src_tiny/transpile_rosetta.tiny` | Tiny transpiler entrypoint available. |
| `tiny_language.py` | `src_tiny/tiny_language.tiny` | Tiny top-level entrypoint available. |
| `tools/generate_doc_reference.py` | `src_tiny/generate_doc_reference.tiny` | Tiny wrapper delegates to the doc reference generator. |
| `tools_unused_scan.py` | `src_tiny/tools_unused_scan.tiny` | Tiny wrapper delegates to the unused symbol scan tool. |
| `vscode-extension/python/tiny_debug_adapter.py` | `src_tiny/tiny_debug_adapter.tiny` | Tiny wrapper loads the adapter from the repo root. |
| `vscode-extension/python/vscode_helpers.py` | `src_tiny/vscode_helpers.tiny` | Tiny wrapper loads the helper module from the repo root. |
