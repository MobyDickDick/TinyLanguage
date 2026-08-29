# Task list: documentation review of all source files

Each task asks: **Is the source file documented in English as completely as practical (line by line and with broader context)?**

Total number of files: **136**

## Generation (terminal commands used)

The file list was generated with a Python scan:

```bash
python - <<'PY'
import os
exts={'.py','.rs','.c','.cc','.cpp','.h','.hpp','.js','.ts','.jsx','.tsx','.java','.go','.rb','.php','.cs','.swift','.kt','.m','.mm','.scala','.sh','.bat','.ps1','.lua','.pl','.r','.jl','.dart'}
files=[]
for root, dirs, filenames in os.walk('.'):
    for fn in filenames:
        path=os.path.join(root,fn)
        _,ext=os.path.splitext(fn)
        if ext.lower() in exts:
            files.append(path)
files=sorted(files)
output_path='documentation_tasks.md'
with open(output_path,'w',encoding='utf-8') as f:
    f.write('# Task list: documentation review of all source files\n\n')
    f.write('Each task asks: **Is the source file documented in English as completely as practical (line by line and with broader context)?**\n\n')
    f.write(f'Total number of files: **{len(files)}**\n\n')
    for path in files:
        f.write(f'- [x] {path}: Is the source file documented in English as completely as practical (line by line and with broader context)?\n')
print(output_path)
PY
```

- [x] ./.vscode/import_code.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./benchmarks/microbenchmarks.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/copy_rosetta_samples.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/factorial/factorial.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/fibonacci/fibonacci.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/fizzbuzz/fizzbuzz.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/hello_world/hello_world.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/python/factorial.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/python/fibonacci.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/python/fizzbuzz.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/python/hello_world.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/python/sorting.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./examples/rosetta/sorting/sorting.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./run_all.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/console_sum.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/formatter.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/language_server.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/language_server_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/native_ir.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/native_python_bytecode.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/native_vm.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/run_all.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/simpelst_Python_program.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/stdlib/__init__.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/stdlib_datetime.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_errors.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_lang_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_api.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_ast.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_codegen_c.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_codegen_llvm.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_codegen_native.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_codegen_py.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_compiler_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_eval.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_highlighting.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_lexer.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_linter.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_parser.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_preamble.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_runtime.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_stitched.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_language_transpilers.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tiny_project_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/tinyc_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./src/transpile_rosetta.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/__init__.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/conftest.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_async_structured.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_async_tokens.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_benchmark_and_fuzz.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_c_codegen.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_cli_smoke.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_concurrency.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_copy_on_call.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_copy_rosetta_samples.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_debug_adapter_flow.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_debugger_hooks.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_error_formatting.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_error_messages.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_errors.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_experimental_math_formula.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_experimental_math_tuples.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_formatter.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_heap_api_errors.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_heap_lints.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_heap_pointer_demo.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_hello_world.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_inheritance.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_language_server.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_language_server_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_llvm_codegen.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_modules.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_namespaces.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_native_backend_errors.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_native_codegen.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_native_ir.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_native_python_bytecode_backend.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_native_vm.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_null.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_number_class.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_number_intervall.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_number_overflow.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_objects.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_operator_overloading.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_pattern_matching.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_python_codegen.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_python_interop_demos.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_readme_concurrency_demo_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_readme_hello_world_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_repl.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_repl_highlighting.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_result_type.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_rosetta_transpile.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_runtime_expansion.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_semantics_suite.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_span_consistency.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_spans.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_src_tiny_regressions.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_stdlib.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_stdlib_sources.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_style_lints.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_tiny_language_cli_self_host.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_tiny_language_compiler_cli_self_host.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_tiny_language_server_cli_self_host.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_tiny_native_backend.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_tiny_project_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_tiny_transpilers.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_transpilers.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_try_catch.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/test_typing.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/detailtests/utils.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_c_backend.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_language_spec_grammar.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_linter_parity.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_llvm_jit.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_src_tiny_regressions.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_standalone_tiny_regressions.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_stdlib_compatibility.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_tiny_language.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_tiny_language_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_tiny_language_compiler_cli.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_tiny_language_preamble.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_tiny_lexer_self_host.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_tiny_parser_self_host.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/test_tiny_wrapper_imports.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tests/utils.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tiny_language.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tools/check_format_lint.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tools/generate_doc_reference.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./tools_unused_scan.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./vscode-extension/extension.js: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./vscode-extension/python/tiny_debug_adapter.py: Is the source file documented in English as completely as practical (line by line and with broader context)?
- [x] ./vscode-extension/python/vscode_helpers.py: Is the source file documented in English as completely as practical (line by line and with broader context)?

## Additional documentation task

- [x] Are there redundancies in Tiny Language? (see `docs/redundancy_review.md`)

## Additional task list (project requirements)

- [x] Every Python file in the project is ultimately translated into an equivalent Tiny file, and the evidence (mapping/table) is documented. (see `docs/python_to_tiny_mapping.md`)
- [x] Every source file is documented in as much useful detail as possible (including context and rationale for broader relationships).
- [x] Large source files are divided into manageable, logically separated smaller files (including a new module structure and updated import paths where necessary).

## Redundancy-reduction tasks (from `docs/redundancy_review.md`)

- [x] Consolidate entry-point shims: define a migration plan specifying which wrappers (`run_all.py`, `tiny_language`, `tiny_language.py`, `src/tiny_lang_cli.py`) are removed or renamed, including a deprecation period and compatible transition commands.
- [x] Update tooling/docs: update documentation and internal tools to reference the canonical entry points (e.g., `src/run_all.py`, `src/tiny_language.py`, `src/tiny_language_cli.py`) and no longer rely on the old paths.
- [x] Update tests/CI: identify tests or scripts that invoke the wrappers directly and migrate them to the new entry points; add regression tests that validate the migration plan.
- [x] Unify the stdlib structure: prepare a decision document about whether `stdlib/` and `src/stdlib/` can be merged (including effects on import paths, runtime lookup, and API registration).
- [x] Refactor runtime search paths: if a merge is approved, adjust the runtime logic (`tiny_language_runtime.py`) so that only one stdlib root is supported.
- [x] Define a stdlib transition strategy: provide deprecation notes and, if appropriate, migration tools that move existing Tiny programs to the new import paths.
