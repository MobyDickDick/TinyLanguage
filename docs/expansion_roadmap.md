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
### Open tasks

  - [x] Document a minimal, reproducible LLVM toolchain setup (versions + flags) in
        `docs/native_compiler.md`, including common failure modes and fixes.

  - [x] Add an LLVM optimization checklist with measurable before/after metrics (compile time,
        runtime) using the microbenchmarks in `benchmarks/microbenchmarks.py`.

### Closed tasks

  - [x] Extend the LLVM emitter to cover remaining runtime built-ins needed by the interpreter
        (confirm gap list by diffing `tiny_language_runtime.py` built-ins against LLVM lowering).

  - [x] Add an LLVM conformance smoke suite that compiles a representative set of Tiny programs
        (arithmetic, control flow, functions, heap ops, string ops) via `--emit-llvm`, then executes
        them with `clang`/`llc` and asserts on stdout/stderr snapshots.

  - [x] Map straight-line code (arithmetic expressions, variables, `print`).

  - [x] Add control flow (`if`/`while`) to the LLVM emitter.

  - [x] Support functions and calls in the LLVM prototype.

  - [x] Sketch heap/strings (e.g. `new`, `heap_get`/`heap_set`, string print) in the LLVM path.

  - [x] Refine error messages when an IR opcode is not supported.
- **LLVM integration tasks (Julia-style, incremental)**:
### Open tasks

  - [x] Add a `math` module parity map: list Python APIs to mirror, then implement TL equivalents in
        `stdlib/math.tiny` with cross-check tests against Python results.

  - [x] Add a `random` module parity map: define minimal API surface (seed, randint, choice,
        shuffle) and introduce deterministic tests using fixed seeds.

  - [x] Add a `string` module parity map: extend beyond current string helpers with utilities like
        `split`, `join`, `strip`, `replace`, and document any deviations.

  - [x] Add a `datetime` module parity map: document supported types and format helpers, then build
        a TL subset with snapshot tests for parsing/formatting.

### Closed tasks

  - [x] Allow `tiny_language_cli.py --emit-llvm [FILE|-]` to write LLVM IR to a file or stdout.

  - [x] Add an optional `llvmlite` JIT runner to execute the LLVM prototype without invoking `clang`.

  - [x] Thread target triple/data layout through the LLVM emitter and expose CLI flags to override them.

  - [x] Add basic optimization passes (mem2reg, instcombine) behind a `--llvm-opt` flag.

  - [x] Extend the LLVM runtime ABI with heap/string helpers so non-numeric types can be lowered.
## 2) Port the Python standard library

- **Prioritised modules**: `math`, `random`, `string`, `datetime` (incrementally).
- **Goal**: Provide TL stdlib modules with a similar API to Python.
- **Tests**: Small comparison tests against Python results (where sensible).

## 3) Rosetta Code tasks

- **Consistent task layout** ✅: `examples/rosetta/<task>/`.
- **First wave**: Beginner tasks (e.g. Hello World, Fibonacci, sorting).
- **First wave checklist**:
### Open tasks

_None_

### Closed tasks

  - [x] Hello World.

  - [x] Fibonacci.

  - [x] FizzBuzz.

  - [x] Factorial.

  - [x] Sorting.
- **Transpiler checks**: Verify which language features TL still needs.

## 4) Port a Julia subset

- **Keep scope small**: e.g. `Statistics` or simple linear algebra.
- **PoC modules**: First functions (e.g. `mean`, `std`) with tests.
- **API notes**: Document differences to Julia.
### Open tasks

  - [x] Define the target Julia subset (e.g. `Statistics`) and list the specific functions to
        implement in `docs/julia_subset.md` with signatures and examples.

  - [x] Implement `mean` and `std` in a new TL module (e.g. `stdlib/statistics.tiny`) and add tests
        that compare TL output against Python/NumPy reference values where feasible.

  - [ ] Add a short compatibility table that flags precision or edge-case differences compared to
        Julia (NaN handling, empty collections, integer promotion).

### Closed tasks

- [x] Implement `mean` and `std` in a new TL module (e.g. `stdlib/statistics.tiny`) and add tests
      that compare TL output against Python/NumPy reference values where feasible.

## 5) Debugging & IDEs

### Open tasks

_None_

### Closed tasks

- [x] **LLVM-first VS Code debugging**: Enable a direct debugging workflow in VS Code for LLVM-native executables produced by the LLVM pipeline (see `docs/debugger_workflows.md`).

## 6) Stdlib string ergonomics

- **Goal**: Round out everyday string helpers so TL scripts mirror common Python-style workflows.
- **Task list (statusable)**:
### Open tasks

_None_

### Closed tasks

  - [x] Add `String.is_digit(text)` to validate numeric-only strings (document in `stdlib/string.tiny`).

  - [x] Add `String.starts_with(text, prefix)` + `String.ends_with(text, suffix)` with tests in `tests/detailtests/test_stdlib.py`.

  - [x] Add `String.replace(text, old, new)` with coverage in `tests/detailtests/test_stdlib.py`.

## 7) Self-hosting parity verification

- **Goal**: Keep Tiny self-hosting modules aligned with Python behavior and error messages.
- **Scope**: Lexer/parser, runtime/eval, linter, transpilers, CLI, and native backend parity.
### Open tasks

  - [ ] Add parity snapshots for CLI and LSP flows by running both Python and Tiny CLIs on the
        same inputs and asserting identical diagnostics and exit codes.

  - [ ] Expand parity tests to cover error formatting and span consistency between Python and Tiny
        (including multi-line errors and nested spans).

  - [ ] Introduce a regression matrix for self-hosting modules that records last-verified
        interpreter/hash versions and known deviations.

### Closed tasks

_None_
