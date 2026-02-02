# Native compiler prototype

This draft outlines the target architecture for an alternative backend that executes TinyLanguage programs without the AST interpreter. The emphasis is on a fast feedback loop: small, inspectable building blocks that can be checked against the existing interpreter tests.

> **Status:** The native VM and LLVM pipeline are experimental and explicitly
> non-blocking for v1.0. Expect missing features and `NotImplementedError` for
> unsupported constructs; use the interpreter backend for full language
> coverage.

## Goals

- **Emit bytecode/IR from the existing AST**: We do not want to maintain a second parser pipeline. The generator should operate directly on the nodes from `tiny_language_ast.py`.
- **Simple VM layer**: A compact, stack-based VM with jump/call instructions is sufficient for the first experiments. It must be deterministic and easy to test.
- **Feature flag in the CLI**: The alternative path should sit alongside the interpreter and Python backend (`--native-backend`) so functional comparisons stay straightforward.
- **Executable compiler path**: Emit LLVM IR from the native IR and feed it into a system compiler (`clang`) to produce a binary for supported constructs.

## High-level architecture

1. **Codegen pass (`NativeCodeGenerator`)**: Traverses the AST and emits linear bytecode per function plus an entry sequence for top-level statements. Unsupported constructs raise `NotImplementedError`.
2. **VM (`NativeVM`)**: Executes the bytecode via frames with simple local/global lookups and collects output in `output`. Core instructions include `PUSH_CONST`, `LOAD`, `STORE`, `BINARY`, `PRINT`, `JUMP`, `JUMP_IF_FALSE`, `CALL`, and `RETURN`.
3. **API/CLI hooks**: `tiny_language_api.py` exposes `run_with_native_backend`; `tiny_language.py` loads the generator as a module segment; the CLI accepts `--native-backend` for `--eval` and file execution (the REPL currently stays interpreter-driven).

## Minimum coverage for the first iteration

- Literals (`Num`, `Str`, `Bool`, `Null`)
- Variable binding and assignment (`Let`, `Assign`)
- Arithmetic and comparison operators via `Bin`
- Control flow: `If`, `While`
- Functions with `return` and function calls (`Fn`, `Call`)
- Output via `print` statements (multiple arguments separated by spaces)

## Proof points and tests

- **Smoke tests** compare interpreter and native-backend output for arithmetic, branching, and functions.
- The VM is intentionally small so later expansions (arrays, objects, pattern matching) remain measurable.

## Usage

- **CLI switch**: `python src/tiny_language.py --native-backend -e "print(1 + 2);"` runs a snippet without the AST interpreter.
- **Alternative bytecode emission**: `python src/tiny_language.py --native-python-bytecode -e "print(1 + 2);"` builds the same native IR and compiles it to pure Python bytecode.
- **File execution**: `python src/tiny_language.py --native-backend path/to/program.tiny` loads a program and uses the same codegen/VM path.
- **Emit LLVM IR**: `python src/tiny_language.py --emit-llvm out.ll path/to/program.tiny` writes the LLVM IR for the native backend subset. Use `--llvm-opt-level 2` to enable a stronger optimization profile in the emitted IR.
- **Build executable**: `python src/tiny_language.py --emit-exe out path/to/program.tiny` compiles a native binary via `clang` (only the LLVM-prototype subset is supported). Use `--opt-level 2` for release-style compiler optimizations.
- **Diagnostics**: Add `--native-diagnostics` to emit compiler/LLVM configuration details (opt levels, target info, and compiler resolution) to stderr.
- **Regression tests**: `python -m pytest tests/test_native_codegen.py -q` compares interpreter and native-backend output and ensures unsupported constructs remain visible as `NotImplementedError`.

## Minimal LLVM toolchain setup (reproducible)

The LLVM pipeline expects a working `clang` + `llc` toolchain and (optionally)
`llvmlite` for the JIT runner. Keep the LLVM pieces on the same major version.

### Recommended versions

- **LLVM/clang/llc**: 15.x or 16.x (same major version across tools).
- **llvmlite** (optional): build against the same major LLVM version as above.

If your distro packages a newer LLVM (e.g. 17+), it can still work as long as
all LLVM tools (`clang`, `llc`, `llvm-config`) match on the major version.

### Baseline commands

```bash
clang --version
llc --version
llvm-config --version
```

Check that the major versions match (for example, all report `15.x` or `16.x`).

### Minimal end-to-end workflow

```bash
# 1) Emit LLVM IR from TinyLanguage.
PYTHONPATH=src python src/tiny_language.py --emit-llvm out.ll path/to/program.tiny

# 2) Build a native executable with clang.
clang -O0 -g -o out out.ll

# 3) Run the binary.
./out
```

If you want a release-style build, use `-O2` (or `-O3`) in the `clang` step, or
pass `--opt-level 2` to `--emit-exe` so TinyLanguage drives the optimization.

### Common flags and when to use them

- **TinyLanguage flags**:
  - `--emit-llvm out.ll`: emit human-readable LLVM IR.
  - `--emit-exe out`: compile to a native binary using `clang`.
  - `--llvm-opt-level 0|1|2|3`: set LLVM IR optimization level.
  - `--opt-level 0|1|2|3`: set `clang` optimization level for executables.
  - `--compiler /path/to/clang`: override the compiler resolution.
- **clang flags** (manual builds):
  - `-O0/-O2/-O3`: optimization level.
  - `-g`: include debug symbols (useful for LLDB/GDB).
  - `-fno-omit-frame-pointer`: optional; keeps call stacks clearer for profiling.

### Common failure modes and fixes

| Symptom | Typical error | Fix |
| --- | --- | --- |
| `clang` not found | `FileNotFoundError: [Errno 2] No such file or directory: 'clang'` | Install clang or point to it with `--compiler /path/to/clang`. |
| `llc` not found | `RuntimeError: llc not found on PATH` | Install LLVM tools and ensure `llc` is on `PATH`. |
| Mixed LLVM versions | `LLVM ERROR: mismatch in LLVM version` or `llvmlite: incompatible LLVM` | Align versions: make sure `clang`, `llc`, and `llvm-config` share the same major version; rebuild `llvmlite` against that version. |
| Unsupported target triple | `error: unknown target triple` | Pass a known target triple via the CLI (see `--native-diagnostics`) or install the matching LLVM target backend. |
| IR verification failures | `LLVM ERROR: Broken module found` | Lower optimization levels (`--llvm-opt-level 0`), then bisect the input to isolate unsupported constructs. |

## LLVM optimization checklist (with benchmark metrics)

Use this checklist when you change LLVM lowering or tweak optimization flags.
The goal is to gather **before/after** numbers for both compile time and
runtime using the microbenchmarks in `benchmarks/microbenchmarks.py`.

### 1) Record the baseline (no extra LLVM optimizations)

1. **Compile time (IR → executable)**

   ```bash
   /usr/bin/time -p PYTHONPATH=src python src/tiny_language.py --emit-exe /tmp/tiny-bench \
     --llvm-opt-level 0 --opt-level 0 benchmarks/microbenchmarks.tiny
   ```

   Capture `real` time in seconds.

2. **Runtime**

   ```bash
   /usr/bin/time -p /tmp/tiny-bench
   ```

   Capture `real` time in seconds.

3. **Benchmark output**

   ```bash
   PYTHONPATH=src python benchmarks/microbenchmarks.py
   ```

   Copy the printed benchmark table for reference.

### 2) Record the optimized run

Repeat the same commands, but enable optimizations:

```bash
/usr/bin/time -p PYTHONPATH=src python src/tiny_language.py --emit-exe /tmp/tiny-bench-opt \
  --llvm-opt-level 2 --opt-level 2 benchmarks/microbenchmarks.tiny
/usr/bin/time -p /tmp/tiny-bench-opt
PYTHONPATH=src python benchmarks/microbenchmarks.py
```

### 3) Fill in the before/after table

| Metric | Baseline (`--llvm-opt-level 0`, `--opt-level 0`) | Optimized (`--llvm-opt-level 2`, `--opt-level 2`) | Delta |
| --- | --- | --- | --- |
| Compile time (`/usr/bin/time`) | | | |
| Runtime (`/usr/bin/time`) | | | |
| Benchmark highlights | | | |

### 4) Notes and next actions

- If compile time regresses >10% with minimal runtime gain, prefer a lower
  optimization level or reduce the LLVM pass list.
- If runtime improves but compile time balloons, document it in the PR so we
  can decide whether the new default should stay optional.
- Keep the benchmark output snippet in the PR body or commit message for
  traceability.

## Current CLI workflow and VM boundaries

- **Plan for A/B comparisons**: Every run with `--native-backend` should be repeated once without the flag to surface divergences from the interpreter immediately.
- **Limited language surface**: Heap operations, classes, pattern matching, or deques are not covered yet and deliberately raise `NotImplementedError`. Use the interpreter path for those features.
- **Consistent invocation shapes**: Both the CLI (`src/tiny_language.py`) and `src/tiny_language_cli.py` accept `--native-backend` before `-e` or the file path. The VM only works on files or inline snippets; the REPL and formatter remain interpreter-backed.
- **Output comparison**: The VM buffers `print` output line by line; that keeps comparisons with the interpreter simple, but multi-delimiters or structured logs are not implemented yet.
- **LLVM executable scope**: The LLVM backend is intentionally narrow (numeric values, basic control flow, simple functions, and `print`). Expect `NotImplementedError` for anything outside that subset. Use `--llvm-opt-level` and `--opt-level` to tune LLVM/clang optimization profiles.
  For a concise list of open gaps and next steps in the LLVM emitter, see the checklist under **LLVM-basierte Pipeline** in [`docs/expansion_roadmap.md`](expansion_roadmap.md).

### Module import constraints (native + LLVM)

The native VM and LLVM pipeline share the same module resolver, but the LLVM
code generator needs import targets to be statically known so it can wire the
module init functions into the emitted IR. That means:

- **Import paths must be literal module paths**: the module string must be known
  at compile time and is parsed from identifiers/dots (not runtime expressions).
  `import math.trig;` works, while building a module name at runtime is not
  supported in the native/LLVM pipeline.
- **Relative imports remain supported** inside modules (leading dots are resolved
  against the caller namespace), but the path still needs to be literal.
- **Python interop imports require string literals**: `Python.import_module`
  and the internal `__import` call only accept literal module names in the LLVM
  pipeline; dynamic expressions raise `NotImplementedError`.

Allowed module literals include:

- `import math.trig;`
- `import stdlib.collections as collections;`
- `import .helpers;`
- `import ..shared.math as math;`
- `def json = Python.import_module("json");`

If you need dynamic module selection (e.g., building a name string at runtime),
run the interpreter backend instead of `--native-backend`/`--emit-llvm`.

## CLI workflow at a glance

1. **Smoke run with an example program**: `PYTHONPATH=src python src/tiny_language.py --native-backend src_tiny/demo.tiny` checks whether parser, codegen, and VM cooperate.
2. **Quick feature comparison**: Run the same command without `--native-backend` and compare the output to pinpoint divergences.
3. **Targeted function tests**: `python -m pytest tests/test_native_codegen.py -k while -q` focuses on specific constructs like `while` loops or function calls.
4. **Keep the fallback path visible**: If a program is not supported yet, the same call without `--native-backend` should still work. Use the A/B comparison to catch interpreter regressions early.

### Mini playbook with expected output

These commands exercise exactly the constructs implemented today (literals, arithmetic, `if`/`while`, function calls, `print`). Anything beyond that should deliberately raise `NotImplementedError`:

- **Arithmetic and function call inline** (should mirror the interpreter):

  ```bash
  PYTHONPATH=src python src/tiny_language.py --native-backend -e 'fn add(x, y) { return x + y; } print(add(2, 3));'
  # Expected output
  5
  ```

- **While/if path coverage**:

  ```bash
  PYTHONPATH=src python src/tiny_language.py --native-backend -e 'def i = 0; def out = 0; while (i < 3) { if (i == 1) { out = out + 10; } else { out = out + i; } i = i + 1; } print(out);'
  # Expected output
  11
  ```

- **Heap operations now supported**:

  ```bash
  PYTHONPATH=src python src/tiny_language.py --native-backend -e 'def p = new(1); def _unused1 = heap_set(p, 0, 42); print(heap_get(p, 0));'
  # Expected output
  42
  ```

Typical CLI responses:

- Successful runs exit with code `0` and print the VM stack output.
- Unsupported language constructs raise `NotImplementedError` and serve as markers for missing lowerings.
- Runtime errors (e.g., division by zero) appear as `RuntimeError` from the VM with stack frames (see troubleshooting below).

## Limitations and known gaps

- Not all constructs are covered yet; classes and pattern matching are intentionally marked as `NotImplementedError`.
- The VM expects simple numeric/Boolean expressions. Type annotations are accepted, but complex type checks still happen in the interpreter.
- `print` collects output inside the VM but currently does not support formatting or multi-delimiters like the interpreter.
- Backend flags apply per invocation: the REPL and formatter still use the interpreter path; only `--native-backend` in `src/tiny_language.py` or `src/tiny_language_cli.py` enables the VM.
- No object model yet: classes are not yet represented in bytecode. Tests needing those features should run against the interpreter for now.

## Troubleshooting

Common error signatures at a glance:

| Symptom | Typical output | Fix |
| --- | --- | --- |
| Missing lowering | `NotImplementedError: Call to Map.set not supported in native backend` | Use the interpreter path or simplify the test to core constructs. |
| VM runtime error | `RuntimeError: division by zero` plus a stack trace with `NativeVM.*` frames | Check inputs/division; the stack trace points to the bytecode operation. |
| Misplaced flag | `SystemExit 2` with an argparse hint | Place `--native-backend` before `-e` or the file path. |

- **`NotImplementedError` during codegen**: The generator usually names the affected AST node. Example: `NotImplementedError: Call to Map.set not supported in native backend`—reduce the test to basic arithmetic or drop `--native-backend`.
- **Stack trace from the VM**: Errors are emitted with frame information, e.g.:

  ``` (Python)
  Traceback (most recent call last):
    at NativeVM.run_function(<main>)
    at NativeVM._binary()
  RuntimeError: division by zero
  ```

  The frames mirror bytecode execution and help locate faulty instructions.
- **CLI parsing fails**: Ensure `--native-backend` appears before `-e` or the file path; otherwise `argparse` treats the flag as a program argument.
- **Invalid instruction in bytecode**: If the VM reports `RuntimeError: unknown opcode`, the bytecode is likely from an older generator version. Regenerate it by rerunning the source with `--native-backend` and deleting old artifacts.
- **Interpreter/native divergence**: Use the A/B comparison from the workflow above—run once with and once without `--native-backend`. Differences signal missing lowerings and should be tracked as regressions.
- **Timeouts in test suites**: Long runs can block the VM. Limit loops in `.tiny` fixtures or use targeted test filters (`-k while`) and `-q` to keep log volume small.
- **Error codes at a glance**:
  - `NotImplementedError`: Feature missing in codegen/VM (e.g., heap, classes, pattern matching).
  - `RuntimeError: division by zero` (or similar): Runtime error during bytecode execution; the stack trace shows `NativeVM.*` frames.
  - `SystemExit 2`: `argparse` error caused by a misplaced `--native-backend` flag.
