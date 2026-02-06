# Python-to-Tiny Translation Mapping

This document tracks which Python sources have TinyLanguage equivalents and clarifies which files intentionally remain Python-only.

## Scope

- **Translated**: runnable source files and examples that have a TinyLanguage equivalent in `src_tiny/`.
- **Python-only**: tests, tooling, editor integrations, and host-facing helpers (e.g. stdlib shims or package/module resolution) that are expected to remain in Python.

## Translated Python sources

| Python source | Tiny equivalent |
| --- | --- |
| `benchmarks/microbenchmarks.py` | `src_tiny/microbenchmarks.tiny` |
| `examples/rosetta/copy_rosetta_samples.py` | `src_tiny/copy_rosetta_samples.tiny` |
| `examples/rosetta/factorial/factorial.py` | `src_tiny/factorial.tiny` |
| `examples/rosetta/fibonacci/fibonacci.py` | `src_tiny/fibonacci.tiny` |
| `examples/rosetta/fizzbuzz/fizzbuzz.py` | `src_tiny/fizzbuzz.tiny` |
| `examples/rosetta/hello_world/hello_world.py` | `src_tiny/hello_world.tiny` |
| `examples/rosetta/python/factorial.py` | `src_tiny/factorial.tiny` |
| `examples/rosetta/python/fibonacci.py` | `src_tiny/fibonacci.tiny` |
| `examples/rosetta/python/fizzbuzz.py` | `src_tiny/fizzbuzz.tiny` |
| `examples/rosetta/python/hello_world.py` | `src_tiny/hello_world.tiny` |
| `run_all.py` | `src_tiny/run_all.tiny` |
| `src/console_sum.py` | `src_tiny/console_sum.tiny` |
| `src/formatter.py` | `src_tiny/formatter.tiny` |
| `src/language_server.py` | `src_tiny/language_server.tiny` |
| `src/language_server_cli.py` | `src_tiny/language_server_cli.tiny` |
| `src/native_ir.py` | `src_tiny/native_ir.tiny` |
| `src/native_python_bytecode.py` | `src_tiny/native_python_bytecode.tiny` |
| `src/native_vm.py` | `src_tiny/native_vm.tiny` |
| `src/run_all.py` | `src_tiny/run_all.tiny` |
| `src/simpelst_Python_program.py` | `src_tiny/simpelst_Python_program.tiny` |
| `src/tiny_errors.py` | `src_tiny/tiny_errors.tiny` |
| `src/tiny_lang_cli.py` | `src_tiny/tiny_lang_cli.tiny` |
| `src/tiny_language.py` | `src_tiny/tiny_language.tiny` |
| `src/tiny_language_api.py` | `src_tiny/tiny_language_api.tiny` |
| `src/tiny_language_ast.py` | `src_tiny/tiny_language_ast.tiny` |
| `src/tiny_language_cli.py` | `src_tiny/tiny_language_cli.tiny` |
| `src/tiny_language_codegen_c.py` | `src_tiny/tiny_language_codegen_c.tiny` |
| `src/tiny_language_codegen_llvm.py` | `src_tiny/tiny_language_codegen_llvm.tiny` |
| `src/tiny_language_codegen_native.py` | `src_tiny/tiny_language_codegen_native.tiny` |
| `src/tiny_language_codegen_py.py` | `src_tiny/tiny_language_codegen_py.tiny` |
| `src/tiny_language_compiler_cli.py` | `src_tiny/tiny_language_compiler_cli.tiny` |
| `src/tiny_language_eval.py` | `src_tiny/tiny_language_eval.tiny` |
| `src/tiny_language_highlighting.py` | `src_tiny/tiny_language_highlighting.tiny` |
| `src/tiny_language_lexer.py` | `src_tiny/tiny_language_lexer.tiny` |
| `src/tiny_language_linter.py` | `src_tiny/tiny_language_linter.tiny` |
| `src/tiny_language_parser.py` | `src_tiny/tiny_language_parser.tiny` |
| `src/tiny_language_preamble.py` | `src_tiny/tiny_language_preamble.tiny` |
| `src/tiny_language_runtime.py` | `src_tiny/tiny_language_runtime.tiny` |
| `src/tiny_language_stitched.py` | `src_tiny/tiny_language_stitched.tiny` |
| `src/tiny_language_transpilers.py` | `src_tiny/tiny_language_transpilers.tiny` |
| `src/tiny_project_cli.py` | `src_tiny/tiny_project_cli.tiny` |
| `src/tinyc_cli.py` | `src_tiny/tinyc_cli.tiny` |
| `src/transpile_rosetta.py` | `src_tiny/transpile_rosetta.tiny` |
| `tiny_language.py` | `src_tiny/tiny_language.tiny` |
| `tools/generate_doc_reference.py` | `src_tiny/generate_doc_reference.tiny` |
| `tools_unused_scan.py` | `src_tiny/tools_unused_scan.tiny` |
| `vscode-extension/python/tiny_debug_adapter.py` | `src_tiny/tiny_debug_adapter.tiny` |
| `vscode-extension/python/vscode_helpers.py` | `src_tiny/vscode_helpers.tiny` |

## Python-only sources (intentionally not translated)

| Python source | Reason |
| --- | --- |
| `.vscode/import_code.py` | Editor workspace tooling |
| `examples/rosetta/python/sorting.py` | Reference Python baseline for Rosetta examples |
| `examples/rosetta/sorting/sorting.py` | Example harness or fixture |
| `src/stdlib/__init__.py` | Python-backed stdlib helper |
| `src/stdlib_csv.py` | Python-backed stdlib helper |
| `src/stdlib_datetime.py` | Python-backed stdlib helper |
| `src/tiny_language_module_resolution.py` | Host integration for module/package resolution |
| `src/tiny_pkg_cli.py` | Host integration for module/package resolution |
| `src/tiny_pkg_resolution.py` | Host integration for module/package resolution |
| `tests/__init__.py` | Test suite (Python-only) |
| `tests/conftest.py` | Test suite (Python-only) |
| `tests/detailtests/stdlib_helpers.py` | Test suite (Python-only) |
| `tests/detailtests/test_async_structured.py` | Test suite (Python-only) |
| `tests/detailtests/test_async_tokens.py` | Test suite (Python-only) |
| `tests/detailtests/test_benchmark_and_fuzz.py` | Test suite (Python-only) |
| `tests/detailtests/test_c_codegen.py` | Test suite (Python-only) |
| `tests/detailtests/test_cli_smoke.py` | Test suite (Python-only) |
| `tests/detailtests/test_concurrency.py` | Test suite (Python-only) |
| `tests/detailtests/test_copy_on_call.py` | Test suite (Python-only) |
| `tests/detailtests/test_copy_rosetta_samples.py` | Test suite (Python-only) |
| `tests/detailtests/test_debug_adapter_flow.py` | Test suite (Python-only) |
| `tests/detailtests/test_debugger_hooks.py` | Test suite (Python-only) |
| `tests/detailtests/test_error_formatting.py` | Test suite (Python-only) |
| `tests/detailtests/test_error_messages.py` | Test suite (Python-only) |
| `tests/detailtests/test_errors.py` | Test suite (Python-only) |
| `tests/detailtests/test_experimental_math_formula.py` | Test suite (Python-only) |
| `tests/detailtests/test_experimental_math_tuples.py` | Test suite (Python-only) |
| `tests/detailtests/test_formatter.py` | Test suite (Python-only) |
| `tests/detailtests/test_heap_api_errors.py` | Test suite (Python-only) |
| `tests/detailtests/test_heap_lints.py` | Test suite (Python-only) |
| `tests/detailtests/test_heap_pointer_demo.py` | Test suite (Python-only) |
| `tests/detailtests/test_hello_world.py` | Test suite (Python-only) |
| `tests/detailtests/test_inheritance.py` | Test suite (Python-only) |
| `tests/detailtests/test_language_server.py` | Test suite (Python-only) |
| `tests/detailtests/test_language_server_cli.py` | Test suite (Python-only) |
| `tests/detailtests/test_llvm_codegen.py` | Test suite (Python-only) |
| `tests/detailtests/test_llvm_conformance_smoke.py` | Test suite (Python-only) |
| `tests/detailtests/test_modules.py` | Test suite (Python-only) |
| `tests/detailtests/test_namespaces.py` | Test suite (Python-only) |
| `tests/detailtests/test_native_backend_errors.py` | Test suite (Python-only) |
| `tests/detailtests/test_native_codegen.py` | Test suite (Python-only) |
| `tests/detailtests/test_native_ir.py` | Test suite (Python-only) |
| `tests/detailtests/test_native_python_bytecode_backend.py` | Test suite (Python-only) |
| `tests/detailtests/test_native_vm.py` | Test suite (Python-only) |
| `tests/detailtests/test_null.py` | Test suite (Python-only) |
| `tests/detailtests/test_number_class.py` | Test suite (Python-only) |
| `tests/detailtests/test_number_intervall.py` | Test suite (Python-only) |
| `tests/detailtests/test_number_overflow.py` | Test suite (Python-only) |
| `tests/detailtests/test_objects.py` | Test suite (Python-only) |
| `tests/detailtests/test_operator_overloading.py` | Test suite (Python-only) |
| `tests/detailtests/test_pattern_matching.py` | Test suite (Python-only) |
| `tests/detailtests/test_python_codegen.py` | Test suite (Python-only) |
| `tests/detailtests/test_python_interop_demos.py` | Test suite (Python-only) |
| `tests/detailtests/test_readme_concurrency_demo_cli.py` | Test suite (Python-only) |
| `tests/detailtests/test_readme_hello_world_cli.py` | Test suite (Python-only) |
| `tests/detailtests/test_repl.py` | Test suite (Python-only) |
| `tests/detailtests/test_repl_highlighting.py` | Test suite (Python-only) |
| `tests/detailtests/test_result_type.py` | Test suite (Python-only) |
| `tests/detailtests/test_rosetta_transpile.py` | Test suite (Python-only) |
| `tests/detailtests/test_runtime_expansion.py` | Test suite (Python-only) |
| `tests/detailtests/test_semantics_suite.py` | Test suite (Python-only) |
| `tests/detailtests/test_span_consistency.py` | Test suite (Python-only) |
| `tests/detailtests/test_spans.py` | Test suite (Python-only) |
| `tests/detailtests/test_src_tiny_regressions.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_argparse.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_csv.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_doc_examples.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_fswatch.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_http.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_json.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_logging.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_os.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_parity.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_path.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_process.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_regex.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_sources.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_time.py` | Test suite (Python-only) |
| `tests/detailtests/test_stdlib_yaml.py` | Test suite (Python-only) |
| `tests/detailtests/test_style_lints.py` | Test suite (Python-only) |
| `tests/detailtests/test_tiny_language_cli_self_host.py` | Test suite (Python-only) |
| `tests/detailtests/test_tiny_language_compiler_cli_self_host.py` | Test suite (Python-only) |
| `tests/detailtests/test_tiny_language_server_cli_self_host.py` | Test suite (Python-only) |
| `tests/detailtests/test_tiny_native_backend.py` | Test suite (Python-only) |
| `tests/detailtests/test_tiny_project_cli.py` | Test suite (Python-only) |
| `tests/detailtests/test_tiny_transpilers.py` | Test suite (Python-only) |
| `tests/detailtests/test_transpilers.py` | Test suite (Python-only) |
| `tests/detailtests/test_try_catch.py` | Test suite (Python-only) |
| `tests/detailtests/test_typing.py` | Test suite (Python-only) |
| `tests/detailtests/utils.py` | Test suite (Python-only) |
| `tests/test_c_backend.py` | Test suite (Python-only) |
| `tests/test_language_spec_grammar.py` | Test suite (Python-only) |
| `tests/test_linter_parity.py` | Test suite (Python-only) |
| `tests/test_llvm_jit.py` | Test suite (Python-only) |
| `tests/test_output_normalization.py` | Test suite (Python-only) |
| `tests/test_parity_runner.py` | Test suite (Python-only) |
| `tests/test_smoke.py` | Test suite (Python-only) |
| `tests/test_spec_conformance.py` | Test suite (Python-only) |
| `tests/test_src_tiny_regressions.py` | Test suite (Python-only) |
| `tests/test_standalone_tiny_regressions.py` | Test suite (Python-only) |
| `tests/test_stdlib_compatibility.py` | Test suite (Python-only) |
| `tests/test_tiny_language.py` | Test suite (Python-only) |
| `tests/test_tiny_language_cli.py` | Test suite (Python-only) |
| `tests/test_tiny_language_compiler_cli.py` | Test suite (Python-only) |
| `tests/test_tiny_language_preamble.py` | Test suite (Python-only) |
| `tests/test_tiny_lexer_self_host.py` | Test suite (Python-only) |
| `tests/test_tiny_parser_self_host.py` | Test suite (Python-only) |
| `tests/test_tiny_wrapper_imports.py` | Test suite (Python-only) |
| `tests/utils.py` | Test suite (Python-only) |
| `tools/check_format_lint.py` | Developer tooling |
| `tools/output_normalization.py` | Developer tooling |
| `tools/parity_runner.py` | Developer tooling |
