# C backend guide

This guide documents the TinyLanguage C backend, which emits a self-contained C
source file containing the native bytecode plus a tiny VM. The output can be
compiled with a system compiler (`cc`, `clang`, or `gcc`) for quick native
executables, and it also supports LLVM IR/bitcode emission by invoking `clang`
under the hood.

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

## Supported subset

The C backend targets the same bytecode subset as the tutorial-focused native
VM, but its runtime currently implements only the following constructs:

- Literals: `number`, `string`, `bool`, `null`
- Variables: `def`, assignment
- Arithmetic and comparisons: `+`, `-`, `*`, `/`, `%`, `^`, `==`, `!=`, `<`, `<=`,
  `>`, `>=`
- Boolean operators: `and`, `or`, `&&`, `||`
- Control flow: `if`/`else`, `while`
- Functions and `return` (including recursion)
- Output: `print` (space-separated arguments) and `flush`
- String concatenation with `+`

Unsupported language features will surface as `NotImplementedError` during
code generation (for example, classes/methods, pattern matching, modules, heap
operations, collections, concurrency, and Python interop). Use the interpreter
or native VM for those features.

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
