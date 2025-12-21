# Native compiler prototype

This draft outlines the target architecture for an alternative backend that executes TinyLanguage programs without the AST interpreter. The emphasis is on a fast feedback loop: small, inspectable building blocks that can be checked against the existing interpreter tests.

## Goals

- **Emit bytecode/IR from the existing AST**: We do not want to maintain a second parser pipeline. The generator should operate directly on the nodes from `tiny_language_ast.py`.
- **Simple VM layer**: A compact, stack-based VM with jump/call instructions is sufficient for the first experiments. It must be deterministic and easy to test.
- **Feature flag in the CLI**: The alternative path should sit alongside the interpreter and Python backend (`--native-backend`) so functional comparisons stay straightforward.

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
- **Regression tests**: `python -m pytest tests/test_native_codegen.py -q` compares interpreter and native-backend output and ensures unsupported constructs remain visible as `NotImplementedError`.

## Current CLI workflow and VM boundaries

- **Plan for A/B comparisons**: Every run with `--native-backend` should be repeated once without the flag to surface divergences from the interpreter immediately.
- **Limited language surface**: Heap operations, classes, pattern matching, or deques are not covered yet and deliberately raise `NotImplementedError`. Use the interpreter path for those features.
- **Consistent invocation shapes**: Both the CLI (`src/tiny_language.py`) and `tiny_lang_cli` accept `--native-backend` before `-e` or the file path. The VM only works on files or inline snippets; the REPL and formatter remain interpreter-backed.
- **Output comparison**: The VM buffers `print` output line by line; that keeps comparisons with the interpreter simple, but multi-delimiters or structured logs are not implemented yet.

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
  PYTHONPATH=src python src/tiny_language.py --native-backend -e 'define i = 0; define out = 0; while (i < 3) { if (i == 1) { out = out + 10; } else { out = out + i; } i = i + 1; } print(out);'
  # Expected output
  11
  ```

- **Make unsupported features visible** (heap operations):

  ```bash
  PYTHONPATH=src python src/tiny_language.py --native-backend -e 'define p = new(1);'
  # Expected output
  # NotImplementedError: Call to new not supported in native backend
  ```

Typical CLI responses:

- Successful runs exit with code `0` and print the VM stack output.
- Unsupported language constructs raise `NotImplementedError` and serve as markers for missing lowerings.
- Runtime errors (e.g., division by zero) appear as `RuntimeError` from the VM with stack frames (see troubleshooting below).

## Limitations and known gaps

- Not all constructs are covered yet; heap operations, classes, and pattern matching are intentionally marked as `NotImplementedError`.
- The VM expects simple numeric/Boolean expressions. Type annotations are accepted, but complex type checks still happen in the interpreter.
- `print` collects output inside the VM but currently does not support formatting or multi-delimiters like the interpreter.
- Backend flags apply per invocation: the REPL and formatter still use the interpreter path; only `--native-backend` in `tiny_language.py` or `tiny_lang_cli` enables the VM.
- No heap or object model: pointers, arrays, and classes are not yet represented in bytecode. Tests needing those features should run against the interpreter for now.

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
