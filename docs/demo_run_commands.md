# Command list for demos and quick checks

This list collects common CLI invocations to validate the most important examples and backends in a single pass. Run the commands from the repository root; set `PYTHONPATH=src` for the Python helper scripts.

## Interpreter-Demos

```bash
python src/tiny_language.py src_tiny/hello_world.tiny
python src/tiny_language.py src_tiny/demo.tiny
python src/tiny_language.py src_tiny/all_features.tiny
python src/tiny_language.py src_tiny/class_demo.tiny
python src/tiny_language.py src_tiny/namespace_demo.tiny
python src/tiny_language.py src_tiny/match_demo.tiny
python src/tiny_language.py src_tiny/operator_overloading_demo.tiny
python src/tiny_language.py src_tiny/heap_pointer_demo.tiny
python src/tiny_language.py src_tiny/try_catch_demo.tiny
python src/tiny_language.py src_tiny/copy_rosetta_samples.tiny
python src/tiny_language.py src_tiny/transpile_rosetta.tiny
python src/tiny_language.py src_tiny/stdlib_io_random_demo.tiny
python src/tiny_language.py src_tiny/stdlib_collections_demo.tiny
```

## Concurrency and pipeline examples

```bash
python src/tiny_language.py src_tiny/concurrency_demo.tiny
python src/tiny_language.py src_tiny/concurrency_pipeline.tiny
python src/tiny_language.py src_tiny/parallel_map.tiny
```

## Python-Interop

```bash
PYTHONPATH=src python src/tiny_language.py src_tiny/python_math_demo.tiny
PYTHONPATH=src python src/tiny_language.py src_tiny/python_json_demo.tiny
PYTHONPATH=src python src/tiny_language.py src_tiny/python_namespace_typed_demo.tiny
PYTHONPATH=src python src/tiny_language.py src_tiny/python_proxy_pipeline_demo.tiny
```

## Native backend for comparison

```bash
python src/tiny_language.py --native-backend src_tiny/all_features.tiny
python src/tiny_language.py --native-backend src_tiny/match_demo.tiny
python -m pytest tests/test_native_codegen.py -q
```

## Language-server helpers

```bash
PYTHONPATH=src python src/language_server_cli.py --file src_tiny/class_demo.tiny hover --symbol Greeter
PYTHONPATH=src python src/language_server_cli.py --file src_tiny/namespace_demo.tiny completions --prefix To
PYTHONPATH=src python src/language_server_cli.py --file src_tiny/stdlib_io_random_demo.tiny diagnostics
```

## Module workflows

```bash
# Check a local module tree with a relative import
python -m tiny_lang_cli --file my_pkg/main.tiny --backend interpreter

# Cross-check with an optional search path and the native backend
TINYPATH=../deps python -m tiny_lang_cli --file my_pkg/main.tiny --native-backend
```

## Everything at once

The script `run_all.py` runs a representative selection of the demos above plus the pytest suite:

```bash
python run_all.py
```

Failures return a non-zero exit code, so the script works as a quick regression test in CI or editor launchers.
