# Runtime module boundaries

Work package 10 replaces import-time source concatenation with ordinary Python
modules. `src/tiny_language.py` is a compatibility facade with explicit named
re-exports. It does not read or execute implementation source, synthesize a
filename, or generate a file in the installation directory.

## Dependency direction and interfaces

| Layer | Modules | Interface |
| --- | --- | --- |
| Data and diagnostics | `tiny_errors`, `tiny_language_ast` | Shared node, position, span and error classes |
| Parsing | `tiny_language_lexer`, `tiny_language_parser` | `Lexer`, `Token`, `Parser.parse()` returning canonical AST instances |
| Analysis | `tiny_language_linter` | Explicit AST imports and independent lint/summary functions |
| Code generation | `tiny_language_codegen_py`, `tiny_language_codegen_native`, `tiny_language_codegen_c`, `tiny_language_codegen_llvm` | AST-to-Python or AST/native-IR-to-backend generators with their own dependencies |
| Runtime components | `tiny_language_runtime_environment`, `tiny_language_runtime_modules`, `tiny_language_runtime_debugger` | Environments, namespace references, module lookup and debugging |
| Evaluation | `tiny_language_eval` | `Evaluator.eval_block`, `eval_stmt`, `eval_expr`; return/cancellation control-flow signals |
| Stateful runtime | `tiny_language_runtime` | `Runtime(Evaluator)` supplies calls, heap operations, diagnostics and task state |
| Orchestration | `tiny_language_api` | Parsing/linting, stdlib registration, execution, backend dispatch and REPL |
| Compatibility | `tiny_language` | Named re-exports for existing Python and Tiny wrappers |

The evaluator never imports the concrete runtime. `Runtime` inherits evaluator
methods at class definition time, so importing the runtime directly is enough
to use it; there is no subsequent class patching. Both layers share the same
return/cancellation signal classes. The resolver invokes compilation only when
an import is executed. The runtime's legacy `compile_and_run` proxy imports
`tiny_language_api.compile_and_run` at call time, avoiding an initialization
cycle. Analysis and generators do not need the facade to supply their globals.

Previously concatenation also changed which same-named private helpers a
function resolved. Each function now resolves its own module's definitions.
The facade preserves the historical last-definition choice for overlapping
private helper exports, without feeding those aliases back into other modules.

## Compatibility and migration

The public `tiny_language_api.__all__` list, named facade imports, repository-root
shim, installed commands, direct source entry point and Tiny wrappers remain
available. `tiny_language.Fn` and `tiny_language_ast.Fn` are now the same class;
there is one canonical `Runtime`, parser and set of AST classes per process.
Tracebacks and `inspect.getsourcefile()` identify the maintained implementation
files. Object `__module__` values consequently identify those modules too.

`tiny_language_stitched.py` was a generated implementation artifact and has
been removed. Replace Python imports of it with `tiny_language`. The legacy
Tiny entry point `src_tiny/tiny_language_stitched.tiny` now calls the canonical
facade. `TINYLANG_STITCH_DEBUG` and loader-only `hashlib`, `tokenize`, `linecache`
and `TYPE_CHECKING` facade attributes have no compatibility contract. Patching
facade globals to change implementation behavior is unsupported; integrations
that patch an implementation helper must patch its owning module. Serialized
objects from historical generated modules require application-level migration.

Wheels contain ordinary Python modules and the same Tiny stdlib/bootstrap
assets. The PyInstaller spec imports Python modules from its PYZ archive; it
bundles only non-Python runtime assets as data. No loose source segments are
required for the frozen loader.

## Reproduce acceptance

Run the complete suite, including the focused module and packaging checks:

```sh
python -m pytest --require-backend-toolchains -ra
python tools/check_format_lint.py
python -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist/module-boundaries
python tools/release/verify_python_package.py dist/module-boundaries/tinylanguage-1.0.0-py3-none-any.whl --report artifacts/runtime-modules/installed-wheel.json
```

`tests/test_runtime_module_boundaries.py` starts isolated fresh interpreters in
nine import orders. It executes parsed AST directly through the runtime and
uses both AST generators before importing the facade, then verifies canonical
identities and API aliases. Packaging tests build wheel/sdist twice and compare
hashes, then execute the wheel outside the checkout.

The installed-wheel verifier creates a fresh environment, installs with
`--no-index --no-deps`, and exercises commands and stdlib imports. It then
protects the disposable installed directory with an inheritable Windows ACL
or POSIX modes. Four simultaneous fresh processes prove the OS rejects both
source rewrites and new-file creation, execute interpreter/native/Python paths,
check real traceback filenames, and compare every installed file's hash before
and after. Permission changes are restored in a `finally` block. Python runs
with `-I -B`; no inherited checkout path or bytecode write is needed. A
privileged POSIX process that bypasses the mode protection fails the write probe
and cannot be presented as read-only acceptance.

Retained commands, source identities, results and artifact hashes are in
[`artifacts/runtime-modules/checkpoint.json`](../artifacts/runtime-modules/checkpoint.json).
This evidence covers the local Windows implementation checkpoint. Supported
platform and signed release qualification remain in work packages 1, 3 and 5;
known backend semantic gaps remain in the package 9 audit follow-up.

## Acceptance checkpoint — 2026-11-08

- Windows x86_64, CPython 3.12.14: the complete run has 1,059 passes, eight
  sandbox-blocked loopback HTTP failures and seven explicit skips. All eight
  HTTP cases pass on a targeted rerun outside the network sandbox, yielding
  1,067 passing cases overall. Skips cover unavailable symlink privileges,
  optional llvmlite JIT, POSIX permission bits and Linux resource limits.
- The focused module/wrapper/generator/packaging run has 90 passes and two
  POSIX skips. It includes nine fresh import orders, OS-protected concurrent
  execution and actual reproducible wheel/sdist build checks. Formatter/lint
  and `git diff --check` pass. Fresh imports also exposed an implicit
  `importlib.util` dependency in stdlib, now explicitly imported there.
- The wheel is installed in a fresh environment outside the checkout under
  the separate validation workspace. All ten quickstart commands, Unicode and
  quoted paths, LF/CRLF multi-file imports, package tooling, four execution
  entry points, installed C/LLVM compilation/execution, formatting/diagnostics
  and a debug-adapter breakpoint/stack/output/continue cycle pass. Four fresh
  processes pass the Windows ACL write-denial probes and leave all 1,063
  installed files unchanged. No actual VS Code extension-host run is claimed
  for this checkpoint.
- The current PyInstaller spec builds a Windows executable with no loose
  `.py` data in its archive. Outside the checkout it passes version, stdlib,
  native and Python execution, and Tiny-parser bootstrap checks. This is a
  functional build check, not a reproducible or signed binary qualification.
- The independent execution audit retains 65 passing backend/case pairs,
  the same 15 documented package 9 failures, no missing toolchains and 16
  non-applicable combinations. The strict audit still fails for those known
  semantic gaps; module extraction does not assert that they are repaired.
