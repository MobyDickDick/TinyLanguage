# Expansion Roadmap

This roadmap collects the high-level work packages that will extend TinyLanguage
towards compiler, library, and transpiler capabilities. The items are phrased so
they can be tackled incrementally.

## 1) Native compiler (executables)

- **LLVM-based pipeline**: TinyLanguage → Native IR → LLVM IR → binary.
- **CLI support**: `--emit-llvm` (dump LLVM IR) and `--emit-exe` (build binary).
- **First target scope**: arithmetic expressions, variables, `print`, simple control flow.
- **Toolchain**: `clang`/`llc` for the first end-to-end flow.
- **Task list (statusable, current prototype)**:
  - [x] Map straight-line code (arithmetic expressions, variables, `print`).
  - [x] Add control flow (`if`/`while`) to the LLVM emitter.
  - [x] Support functions and calls in the LLVM prototype.
  - [x] Sketch heap/strings (e.g. `new`, `heap_get`/`heap_set`, string print) in the LLVM path.
  - [x] Refine error messages when an IR opcode is not supported.

## 2) Port the Python standard library

- **Prioritised modules**: `math`, `random`, `string`, `datetime` (incrementally).
- **Goal**: Provide TL stdlib modules with a similar API to Python.
- **Tests**: Small comparison tests against Python results (where sensible).

## 3) Rosetta Code tasks

- **Consistent task layout** ✅: `examples/rosetta/<task>/`.
- **First wave**: Beginner tasks (e.g. Hello World, Fibonacci, sorting).
- **Transpiler checks**: Verify which language features TL still needs.

## 4) Port a Julia subset

- **Keep scope small**: e.g. `Statistics` or simple linear algebra.
- **PoC modules**: First functions (e.g. `mean`, `std`) with tests.
- **API notes**: Document differences to Julia.

## 5) Debugging & IDEs

- **LLVM-first VS Code debugging**: Enable a direct debugging workflow in VS Code for LLVM-native executables produced by the LLVM pipeline.
