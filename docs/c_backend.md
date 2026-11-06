# C backend guide

This guide documents the TinyLanguage C backend used by `tinyc_cli`. It emits a
self-contained C source file containing native bytecode plus a tiny VM. The
output can be compiled with a system compiler (`cc`, `clang`, or `gcc`) for
quick native executables. When `clang` is available, the same backend can emit
LLVM IR (`--emit-llvm`) or LLVM bitcode (`--emit-bc`).

> Note: The C backend behind `tinyc_cli` is distinct from the LLVM pipeline in
> `src/tiny_language.py` (`--emit-llvm`/`--emit-exe`). See
> `docs/native_compiler.md` for the LLVM-native backend.

## Requirements

- A C compiler available on `PATH` (`cc`, `clang`, or `gcc`).
- Optional: `clang` if you want LLVM IR (`--emit-llvm`) or LLVM bitcode
  (`--emit-bc`) output.

You can override the compiler using `--compiler` or the `TINYLANG_C_COMPILER`
environment variable.

## Quick start

Compile a TinyLanguage program into a native executable:

```bash
python -m tinyc_cli examples/c_backend/hello_world.tiny -o build/hello_world
./build/hello_world
```

Emit the generated C source without compiling:

```bash
python -m tinyc_cli examples/c_backend/hello_world.tiny --emit-c > build/hello_world.c
```

Generate LLVM IR via `clang` (from the C backend):

```bash
python -m tinyc_cli examples/c_backend/hello_world.tiny --emit-llvm build/hello_world.ll
```

Generate LLVM bitcode via `clang` (from the C backend):

```bash
python -m tinyc_cli examples/c_backend/hello_world.tiny --emit-bc build/hello_world.bc
```

If you want debug symbols and no optimizations, add `--debug` (passes `-g -O0`
to the compiler).

## Stability status and guidance

The C backend is experimental and intended for quick native builds of the
TinyLanguage subset described below. The
[independent execution audit](independent_correctness_audit.md) records output,
short-circuit and zero-division deviations within that subset. Expect `NotImplementedError` for unsupported
features and runtime errors from the embedded VM if the bytecode hits a missing
opcode path.

Use this backend when you need:

- Fast, single-binary prototypes for the supported subset.
- A quick way to compare interpreter output with native output.
- A stepping stone to LLVM IR/bitcode emission via `clang`.

Use the interpreter when you need:

- Modules, classes, heap operations, collections, pattern matching, or
  concurrency.
- Precise diagnostic spans or advanced tooling integrations.

## Known limitations

- **Opcode coverage is intentionally small**: unsupported constructs fail fast
  during codegen with `NotImplementedError`.
- **Runtime diagnostics are VM-level**: they do not include rich source spans.
- **Platform dependencies**: the emitted C must be compiled with a local toolchain.
- **Semantic parity**: boolean RHS expressions are evaluated eagerly, division
  by zero can continue with infinity, and `Null` prints as `null`. These are
  recorded contract deviations (AUD-003/004/010), not harmless normalization.

## Supported subset

The C backend implements the following instructions. The independent audit
qualifies only its bounded examples and records the deviations above:

- Literals: `number`, `string`, `bool`, `null`
- Variables: `def`, assignment
- Arithmetic and comparisons: `+`, `-`, `*`, `/`, `%`, `^`, `==`, `!=`, `<`, `<=`,
  `>`, `>=`
- Boolean operators: `and`, `or`, `&&`, `||` (currently eager, without short-circuit semantics)
- Control flow: `if`/`else`, `while`
- Functions and `return` (including recursion)
- Output: `print` (space-separated arguments) and `flush`
- String concatenation with `+`

Unsupported language features surface as `NotImplementedError` during code
generation (for example, classes/methods, pattern matching, modules, heap
operations, collections, concurrency, and Python interop). Use the interpreter
for those features. The LLVM-native prototype has its own partial coverage and
known failures; consult the backend matrix before using it.

For a side-by-side view across backends, see
`docs/backend_feature_matrix.md`.

## Troubleshooting

- **Compiler not found**: If you see `compiler 'cc' not found`, install a C
  compiler or set `TINYLANG_C_COMPILER` to the right binary.
- **Unsupported opcodes**: The C backend reports the missing opcode and the
  supported opcode list. Simplify the source to the supported subset or switch
  to another backend.
- **Runtime errors**: Errors such as “unknown variable” or “unsupported
  operator” are reported by the embedded VM at runtime. Emit C source with
  `--emit-c` to inspect the generated code path.

## How it fits with other backends

- `tinyc_cli` and `--emit-c/--emit-llvm/--emit-bc` use the C backend described
  here.
- `src/tiny_language.py --emit-llvm/--emit-exe` uses the LLVM-native pipeline
  described in `docs/native_compiler.md`; it is **not** the same as `tinyc_cli`.

## Testing and stability checks

- `python -m pytest tests/test_c_backend.py -q` exercises the C backend when a
  compiler is available.
- `python -m pytest tests/test_tiny_language_compiler_cli.py -q` validates CLI
  behavior for the `--emit-c` path.
- Keep quick A/B checks handy: run once with the interpreter and once with
  `python -m tinyc_cli` to compare outputs for the same `.tiny` program.
