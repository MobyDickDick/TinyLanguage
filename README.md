# TinyLanguage

TinyLanguage is a small Julia-inspired language with a Python interpreter. This README provides a StackEdit-style Markdown overview: syntax highlights, a compact tutorial, pointers to examples, common error messages, and the most important run/test commands.

For interoperability guidance, see the cross-language compatibility notes in [`docs/cross_language_compatibility.md`](docs/cross_language_compatibility.md). For concrete Rosetta Code–style ports from Python to TinyLanguage, walk through [`docs/rosetta_python_examples.md`](docs/rosetta_python_examples.md). A compact language reference with syntax, type rules, and operator overview lives in [`docs/language_spec.md`](docs/language_spec.md).

## Intended use
TinyLanguage is a learning- and transpiler-focused playground rather than a production-ready toolchain. It exists to showcase syntax ideas, cross-language IR conversions, and runtime experiments (e.g., gradual typing and structured cancellation). The runnable demos and tests (`python run_all.py` or `python -m pytest`) are best treated as teaching materials for language design or interoperability, not as a polished SDK.

## Transpiler roadmap (task list)
- [x] **Expand the shared IR**: Add new statement/expression types (e.g., control-flow nodes like `IfElse` and `While`) and update the helpers in [`tiny_language_transpilers.py`](tiny_language_transpilers.py) so future language extensions can build on them.
- [x] **Update language transpilers**: Bring the parsers/renderers for `PythonTranspiler`, `JuliaTranspiler`, `JavaScriptTranspiler`, and `CppTranspiler` up to date so the new IR nodes round-trip correctly.
- [x] **Add tests**: Extend the round-trip tests (source → IR → source) for every new language feature and add negative tests for unsupported constructs.

## Open tasks
- [x] **Document language-server workflows (started)**: Write a compact reference for `TinyLanguageServer`, capture example requests/responses, and document the new CLI demos (see [`docs/language_server_workflows.md`](docs/language_server_workflows.md)). Add tests for hover/completion/diagnostics so future changes stay protected.
- [x] **Expand Python interop demos**: Provide additional `.tiny` programs that walk through [`docs/python_interop.md`](docs/python_interop.md) step by step, including how-to-run notes and tests.
- [x] **Evaluate the native-compiler prototype**: Implement an alternative backend path that emits bytecode or native IR from the existing AST and runs through a small VM. Compare against the interpreter via smoke tests (arithmetic, branching, functions). See [`docs/native_compiler.md`](docs/native_compiler.md) for CLI calls, regression tests, and known limits.

## VS Code debugging roadmap
- [x] **Seed launch configuration scaffolding**: Register a TinyLanguage debug configuration type with default `launch.json` snippets and a prototype resolver that currently shells out to the interpreter via a terminal. This keeps the UX stable while the real Debug Adapter Protocol (DAP) handler is built.
- [x] **Add interpreter hooks for breakpoints/stepping**: Teach the Python runtime to pause at breakpoints, step through statements, and surface scopes/variables for the adapter.
- [x] **Implement a TinyLanguage debug adapter**: Wire a DAP server (Node or Python) that speaks to the instrumented interpreter, translating DAP requests into runtime actions.
- [x] **Document and test the debugger flow**: Add README/extension docs plus integration tests so launch/attach scenarios remain stable. See [`docs/debugger_workflows.md`](docs/debugger_workflows.md) for the VS Code launch/stepping guide and the debugger adapter integration tests.

### Runtime trace logging for stepping issues
- Set `TINYLANG_TRACE_LOG=/tmp/tiny_trace.log` (or any path) to emit a detailed execution trace while a program runs. The file includes the current namespace, line/column number, call stack, and visible names in the active scope.
- Use `TINYLANG_TRACE_HEARTBEAT_SECS=1.0` to control how often repeated locations are logged. Setting `TINYLANG_TRACE_EVERY_STATEMENT=1` forces a line-by-line dump even inside tight loops.
- Add `TINYLANG_TRACE_STDOUT=1` to mirror the trace log to the terminal while still writing the log file.
- Combine these flags with your debugger workflow to understand why stepping or breakpoints are skipped—the trace records every statement the interpreter evaluates.
- The VS Code extension now enables runtime tracing automatically during debug sessions, writing to `${workspaceFolder}/.tinylanguage/runtime-trace.log` unless you override `tinylanguage.traceLogPath` or `TINYLANG_TRACE_LOG` in `launch.json`.
- When diagnosing VS Code launch/attach issues, set `TINYLANGUAGE_DAP_LOG=/tmp/tiny_dap.log` to capture every Debug Adapter Protocol request/response and `TINYLANGUAGE_DAP_STDERR=1` to mirror the adapter log to stderr. Idle timeouts will also suggest these flags when no launch/configuration requests arrive so you can see what the client actually sent.
- The TinyLanguage VS Code extension now forwards the `env` block from your `launch.json` to the debug adapter itself. You can enable adapter logging by adding `"env": { "TINYLANGUAGE_DAP_LOG": "/tmp/tiny_dap.log", "TINYLANGUAGE_DAP_STDERR": "1" }` to your TinyLanguage configuration—no extra global shell exports required. `${workspaceFolder}` inside `TINYLANGUAGE_DAP_LOG` is resolved for you, and `TINYLANGUAGE_DAP_STDERR` accepts `"1"`, `1`, `true`, or `"true"`.

### Expected debugger experience in VS Code
- The TinyLanguage extension contributes its own debugger type (`tinylanguage`). You should see **TinyLanguage: Launch active file (prototype)** as the configuration name, not the built-in Python debugger. If VS Code starts a Python session instead, double-check that the `type` in `launch.json` is `tinylanguage` and that the extension is enabled.
- The adapter is a Python script (see `vscode-extension/python/tiny_debug_adapter.py`) that runs the TinyLanguage interpreter; it is not the Python debugger itself. All stepping and breakpoints go through this adapter.
- If no debug session starts after hitting **Run and Debug**, open **Output → TinyLanguage** to confirm the extension registered the configuration and launched the adapter. The adapter writes per-request logs to `TINYLANGUAGE_DAP_LOG` when set, and the `--self-test` mode (`python vscode-extension/python/tiny_debug_adapter.py --self-test`) verifies that Python can import the interpreter on your machine.

## Next practical steps
- [x] **Deepen/update documentation (starting point, done)**: Cross-check the existing guides in `docs/` and bring them up to date. Specifically:
  - In [`docs/language_server_workflows.md`](docs/language_server_workflows.md), list every available LSP method with example requests/responses and add short "how to test it" snippets for the demo calls from the README section "Syntax and Features."
  - In [`docs/python_interop.md`](docs/python_interop.md), add more end-to-end examples that jointly demonstrate modular imports, namespaces, and typed function signatures; link the relevant `.tiny` demos in `src_tiny/` and document their expected outputs.
  - In [`docs/native_compiler.md`](docs/native_compiler.md), highlight the current CLI workflow and VM boundaries and append a small troubleshooting list (common error codes, representative stack trace).

## New quick references
- **Beginner tutorial**: [`docs/tutorial.md`](docs/tutorial.md) walks through setup, runnable demos, and the core language constructs.
- **Feature Cheat Sheet**: [`docs/feature_cheat_sheet.md`](docs/feature_cheat_sheet.md) summarizes the core constructs with short notes on the corresponding `.tiny` demos.
- **Bundled run/test commands**: [`docs/demo_run_commands.md`](docs/demo_run_commands.md) lists interpreter runs, native-backend comparisons, Python interop demos, and language-server CLI checks. `python run_all.py` remains a good all-in-one run.
- **Fuzzing guide**: [`docs/fuzzing.md`](docs/fuzzing.md) shows how to enable the optional Hypothesis-based fuzz tests and re-run failing seeds locally.
- **Executable builds**: [`docs/building_executables.md`](docs/building_executables.md) explains how to bundle TinyLanguage into a standalone Windows `.exe` (and the POSIX variant) with PyInstaller, including the required `--add-data` flags.
- **Git conflict troubleshooting**: [`docs/git_conflict_troubleshooting.md`](docs/git_conflict_troubleshooting.md) explains VS Code's "has conflicts" badge and how to rebase/merge to clear it.

## Quick start: run a program and see its output

1. Activate your virtual environment (PowerShell example: `./.venv/Scripts/Activate.ps1`).
2. Run any `.tiny` file with the CLI entrypoint and pass the file path from the repository root:

   ```powershell
   python -m tiny_language src_tiny/class_demo.tiny
   ```

3. The interpreter writes the program output to the terminal. For the example above you should see:

   ```
   Hello, TinyLanguage!
   ```

If no text appears, verify that you are running the command from the repository root (so `src/tiny_language.py` is discoverable) and that you passed a `.tiny` file path. Invoking `python -m tiny_language` without a file exits immediately after showing the argument error message.

## Backlog: next possible tasks
- [x] **Prototype an LLVM backend**: Explore emitting LLVM IR (e.g., via `llvmlite`) for constants, variables, and arithmetic, with a CLI switch like `--emit-llvm` to generate IR or invoke `llc`/`clang`.
- [x] **Port project modules to TinyLanguage (self-hosting)**: Inventory interpreter/compiler modules, design Tiny-compatible library primitives, and port core components while keeping parallel Python/Tiny tests. See [`docs/self_hosting_port_plan.md`](docs/self_hosting_port_plan.md) for the current module inventory and migration plan.
- [x] **Import and transpile Rosetta Code samples**: Store selected Rosetta Code tasks (FizzBuzz, Fibonacci, sorting, etc.) under `examples/rosetta/`, then build a translation pass that converts the Python versions into TinyLanguage variants with snapshot tests.
- [x] **Write a beginner-friendly tutorial**: Create `docs/tutorial.md` with setup, syntax, control flow, functions, modules, and tooling, linking runnable snippets and referencing them from `README.md`.
- [x] **Add English documentation across source files**: Sweep public functions/classes for docstrings and module headers that describe purpose, parameters, return values, and error scenarios; wire docstring checks (e.g., `ruff pydocstyle`) into CI.
- [x] **Additional ideas**
  - [x] REPL with syntax highlighting
  - [x] Parser/evaluator fuzzing (Hypothesis) to stress feature parity, now including match/ADT generators
  - [x] LSP enhancements (autocomplete/hover for the VSCode extension) via the VS Code helper commands
  - [x] Extend performance microbenchmarks with interpreter/runtime map operations (see [`benchmarks/microbenchmarks.py`](benchmarks/microbenchmarks.py)).

## Offene Aufgaben (aus der letzten Diskussion)
- [x] **LLVM-Emitter weiter ausbauen** (gestartet): Der experimentelle Pfad in `tiny_language_codegen_llvm.py` soll mehr Native-IR-Operationen abdecken und über CLI/API wählbar bleiben. Erste Schritte aus diesem Run: POP-Unterstützung und ein zusätzlicher Test, der das Verhalten absichert.
- [x] **Python-Bridge für Feature-Durchreichung**: Ein TinyLanguage-Modul und Python-Hilfen sollen die FFI vereinfachen (Import/Calls/Allowlist/Timeouts) und bidirektionale Aufrufe kapseln. Demos und Tests würden typische Datentyp-Mappings und Sandbox-Grenzen prüfen.
- [x] **Rosetta-Code-Sync für lokale Pfade**: Das Skript `examples/rosetta/copy_rosetta_samples.py` bietet jetzt konfigurierbare Pfade/Filter/Delays, einen Dry-Run-Schalter und kann den Transpiler direkt anstoßen.

### Neu priorisierte Aufgaben
1. **LLVM-Emitter präzisieren** ✅: Vergleichs- und Modulo-Operationen in `tiny_language_codegen_llvm.py` abbilden, die CLI-Option `--emit-llvm` funktionsfähig halten und Regressionstests ergänzen, die den erweiterten IR-Pfad prüfen.
2. **Python↔TinyLanguage-Bridge entwerfen** ✅: Eine kleine FFI-Schicht (Allowlist/Timeouts) plus passende Tiny/Python-Demos erstellen, um häufige Datentyp-Mappings zu zeigen; Tests in `tests/` sollen beide Richtungen abdecken.
3. **Rosetta-Sync konfigurierbar machen** ✅: `examples/rosetta/copy_rosetta_samples.py` ist jetzt filterbar, bietet Dry-Run/Transpile-Optionen und dokumentierte Bedienung inkl. Regressionstest.

## Syntax and Features

### Mini tutorial: variables, control flow, and functions
```tiny
// Variables, arithmetic, printing
define a = 7 + 5 * 2;
print(a);                // -> 17

// Declare and call functions
fn add(x, y) {
    return x + y;
}

define sum = add(a, 3);
print(sum);

// If/while and mutation
define i = 0;
while (i < 3) {
    if (i == 1) { print("in the middle"); }
    i = i + 1;
}

// Namespaces
namespace Math {
    fn inc(x) { return add(x, 1); }
}
print(Math.inc(4));
```

### More building blocks
- **Comparisons and strings**: `>`, `>=`, `<`, `<=`, `==`, `!=` plus string concatenation with `+`. Scientific notation like `1.2e2` is not supported.
- **Exponentiation**: The `^` operator only accepts integer exponents; for fractional exponents use `power(base, exponent)`.
- **Heap and arrays**: `new(3)` creates a pointer with three slots, `new[1, 2, 3]` allocates an array on the heap. `heap_get`/`heap_set` read and write, `tag` adds type tags to pointers, `delete` removes them.
  - Note: Manual heap primitives are primarily for VM/interop demos; beginners can stick to arrays/structs. Host languages with garbage collectors already handle most memory lifecycles. See [`docs/cross_language_compatibility.md`](docs/cross_language_compatibility.md) for portable patterns.
- **Destructuring**: Functions can return structs: `fn bump(a) { a = a + 1; return { a: a, e: 0 }; }` can be bound with `{ a, e } = bump(1);`.
- **Classes and operators**: Classes have fields and methods and allow multiple inheritance. Operators can be overloaded, e.g. `operator + (a: Number, b: Number) -> Number { ... }`.
- **Concurrency**: `spawn f(1, 2)` starts a task, `join` waits and returns its result.
- **Cancellation tokens**: The `Async` namespace offers `token()`, `cancel(token, reason)`, `is_cancelled(token)`, `reason(token)`, and `link(token, handle)` so tasks can cooperate on structured cancellation. See [`docs/structured_concurrency.md`](docs/structured_concurrency.md) for the design sketch.

#### Portability pitfalls
- **Multiple inheritance and free operator overloading**: JavaScript/TypeScript lack multiple inheritance and C++ overload rules differ; prefer single inheritance plus composition and model overloads as named functions or protocol-style methods so all targets can express them (see [`docs/cross_language_compatibility.md`](docs/cross_language_compatibility.md)).
- **Algebraic data types and `match`**: Exhaustive pattern matching and tagged unions require helper libraries or verbose switches in JS/TS/C++; encode variants as structs/maps with a `tag`/`kind` field and replace `match` with a `switch`/`if` ladder that checks the tag and throws in the default branch.
- **Manual heap primitives**: `new`/`heap_get`/`heap_set`/`tag`/`delete` have no direct equivalents in GC languages; map heap arrays to native lists/vectors, store tags as explicit fields, and rely on host lifetimes or RAII wrappers instead of manual deletion.
- **Namespace semantics**: Namespace blocks do not map 1:1 to module systems; map them to module objects or static classes and ensure imports resolve to a single module instance, avoiding side effects on import by using explicit initialiser functions.

### Type hints and gradual typing
- **Syntax**: Annotate parameters and return values: `fn label(x: string, times: number) -> string { return x * times; }`. Methods follow the same syntax.
- **Gradual typing checks**: Annotated arguments and returns are validated at runtime. A call like `label(1, "x")` yields `[E009] type mismatch ... expected string/number ...`.
- **Basic exhaustiveness checks**: Annotated functions must return a value on all paths. Missing `return` statements trigger `[E010] not all paths ... return a value ...` with hints about missing branch returns.

#### What's unique
- **Runtime gradual typing with exhaustiveness**: Type annotations are enforced at runtime, and functions must return on every path, making control-flow coverage explicit. See `tests/test_tiny_language.py` for return-coverage failures and [`docs/language_spec.md`](docs/language_spec.md) for rules.
- **Structured cancellation tokens**: `Async.token`/`cancel`/`link` support cooperative cancellation across tasks as a teaching example for structured concurrency. Examples live in [`docs/structured_concurrency.md`](docs/structured_concurrency.md) and `src_tiny/concurrency_demo.tiny`.
- **Always-return discipline**: Missing returns are flagged even without static types, encouraging clear exits; contrast with many dynamic languages where execution can silently fall through.

### Classes
A minimal example with a constructor function and a method. The output was verified via `python tiny_language.py src_tiny/class_demo.tiny`.

```tiny
class Greeter {
    name: string;

    fn greeting(self) {
        return "Hello, " + self.name + "!";
    }
}

fn Greeter(name) { return new Greeter { name: name }; }

define greeter = Greeter("TinyLanguage");
print(greeter.greeting());
```

Expected output:

```
Hello, TinyLanguage!
```

See [`class_demo.tiny`](src_tiny/class_demo.tiny) for the full program.

### Operator overloading
A `Point` type overrides `+` and `==`. Verified via `python tiny_language.py src_tiny/operator_overloading_demo.tiny`.

```tiny
class Point {
    x: number; y: number;
    fn to_tuple(self) { return new[self.x, self.y]; }
}

fn Point(x, y) { return new Point { x: x; y: y }; }
operator + (a: Point, b: Point) -> Point { return Point(a.x + b.x, a.y + b.y); }
operator == (left: Point, right: Point) -> Bool { return left.x == right.x && left.y == right.y; }

define p = Point(1, 2);
define q = Point(3, 4);
define sum = p + q;
print(heap_get(sum.to_tuple(), 0));
print(heap_get(sum.to_tuple(), 1));
print(p == sum);
```

Expected output:

```
4
6
false
```

Full program: [`operator_overloading_demo.tiny`](src_tiny/operator_overloading_demo.tiny).

### Namespaces
Namespaces help group related functions. Run with `python tiny_language.py src_tiny/namespace_demo.tiny`.

```tiny
namespace Tools {
    fn double(x) { return x * 2; }
    fn label(x) { return "#" + x; }
}

define value = Tools.double(5);
print(value);
print(Tools.label("done"));
```

Expected output:

```
10
#done
```

More context in [`namespace_demo.tiny`](src_tiny/namespace_demo.tiny).

### Pattern matching and algebraic data types
Define tagged unions with `type` and handle variants via `match` with named bindings or wildcards. Constructors are available as
functions, so `Circle { radius: 2 }` builds a `Shape` value. Match expressions must be exhaustive: missing cases or unknown
variants raise descriptive errors. Example (see [`match_demo.tiny`](src_tiny/match_demo.tiny)):

```tiny
type Shape {
  Circle { radius: number };
  Rectangle { width: number, height: number };
}

fn area(shape) {
  return match shape {
    case Circle { radius: r }: 3.14 * r * r;
    case Rectangle { width: w, height: h }: w * h;
  };
}

print(area(Circle { radius: 2 }));
print(area(Rectangle { width: 3, height: 4 }));
```

Expected output:

```
12.56
12
```

### Importing modules
- **Syntax**: `import math.trig;` loads `math/trig.tiny` and binds it under the last path segment (`trig`). Optional aliasing works too: `import utils.helpers as helpers;` or relative imports from inside modules: `import .shared as shared;`.
- **Namespacing**: Every imported file is registered under its fully qualified module name (e.g. `pkg.core`), so functions and constants are accessible as namespace fields (`core.helper_fn()` or `core.value`).
- **Search path**: The resolver checks the caller directory, entries from `TINYPATH` (colon-separated), then the current working directory and the directory containing `tiny_language.py`. Missing modules or cyclic imports raise `E008`.
- **Caching**: Each module file executes only once per runtime; repeated imports return the same namespace reference and avoid duplicate side effects.

### Concurrency
`spawn` and `join` mix tasks and results. Output from `python tiny_language.py src_tiny/concurrency_demo.tiny`:

```tiny
fn label(prefix, word) { return prefix + "=" + word; }

define keywords = String.split("spawn,join,string,interop", ",");
define first = spawn label("first", heap_get(keywords, 0));
define second = spawn label("second", heap_get(keywords, 1));
define third = spawn label("third", heap_get(keywords, 2));
define fourth = spawn label("fourth", heap_get(keywords, 3));

print("labels");
print(String.join(new[join(first), join(second), join(third), join(fourth)], " | "));
```

Expected output:

```
labels
first=spawn | second=join | third=string | fourth=interop
```

The full version with another split/join lives in [`concurrency_demo.tiny`](src_tiny/concurrency_demo.tiny).

### Heap/pointer operations
`new[...]` allocates arrays, `heap_get`/`heap_set` read and write, `delete` cleans up. Output from `python tiny_language.py src_tiny/heap_pointer_demo.tiny`.

```tiny
define pointer = new[1, 2, 3];
print(heap_get(pointer, 1));
heap_set(pointer, 1, 5);
print(heap_get(pointer, 1));
delete(pointer);
```

Expected output:

```
2
5
```

See [`heap_pointer_demo.tiny`](src_tiny/heap_pointer_demo.tiny) for more examples and failure scenarios.

### Standard library
The interpreter registers the built-in stdlib before running any program. Namespaces include:

- **Math**: `Math.abs(x)`, `Math.pow(base, exp)`, `Math.sqrt(x)` for basics. New helpers `Math.max(a, b)`, `Math.min(a, b)`, and `Math.clamp(value, lower, upper)` make comparisons and clamping easier. Additional helpers: `Math.round(value, digits?)` rounds to decimal places, `Math.floor`/`Math.ceil` round down/up, and `Math.sign(x)` returns -1/0/1 based on the sign. Example: `print(Math.clamp(Math.max(-2, 10), 0, 5));` prints `5`.
- **String**: `String.split(text, sep)` returns a heap pointer to an array of substrings; `String.join(items, sep)` joins a list/pointer; `String.contains(text, needle)` checks for substrings. Extra helpers `String.upper(text)`, `String.lower(text)`, `String.trim(text)`, and `String.repeat(text, count)` handle casing, trimming, and repetition. Example: `print(String.upper(String.trim("  tiny "))); print(String.repeat("ha", 3));` prints `TINY` and `hahaha`.
- **Collections**: `Collections.len(x)` measures the length of heap pointers or Python lists, `Collections.push(target, value)` appends and returns the new length, and `Collections.pop(target)` removes the last element or raises on empty collections. New helpers `Collections.slice(target, start, end)` and `Collections.contains(target, value)` support slicing and lookups: `define mid = Collections.slice(new[1, 2, 3], 1, 3); print(Collections.contains(mid, 2));` prints `true`. There is also a dedicated `Map` API (`Map.new`, `Map.set`, `Map.get`, `Map.keys`, etc.), a `Set` namespace (`Set.add`, `Set.delete`, `Set.to_list`), and doubly linked queues via `Deque` (`Deque.push_left/right`, `Deque.pop_left/right`, `Deque.peek_left/right`).
- **Random**: Random helpers `Random.random()`, `Random.randint(lower, upper)`, `Random.choice(seq)`, and `Random.shuffle(seq)` for quick sampling.
- **File/JSON**: `File.read`/`File.write`/`File.exists`/`File.remove` handle UTF-8 files. `JSON.parse(text)` converts strings to lists/maps/numerics/null, and `JSON.stringify(value)` builds a JSON string from compatible structures.
Detailed notes live in [`docs/stdlib_extensions.md`](docs/stdlib_extensions.md), and ready-made snippets can be tried via [`stdlib_collections_demo.tiny`](src_tiny/stdlib_collections_demo.tiny) or [`stdlib_io_random_demo.tiny`](src_tiny/stdlib_io_random_demo.tiny).

## Example programs
- [`hello_world.tiny`](src_tiny/hello_world.tiny): Minimal program that prints a single greeting—useful for smoke testing the interpreter setup.
- [`demo.tiny`](src_tiny/demo.tiny): Small showcase for variables, loops, functions, classes, and heap operations. Runs sequentially and prints intermediate results.
- [`rosetta_fibonacci.tiny`](src_tiny/rosetta_fibonacci.tiny): Classic Fibonacci implementation demonstrating function declarations and simple loops. Prints the first 10 Fibonacci numbers.
- [`all_features.tiny`](src_tiny/all_features.tiny): Comprehensive feature tour with arrays, classes, and operator overloading—handy for exploring the language end-to-end.
- [`class_demo.tiny`](src_tiny/class_demo.tiny): Minimal constructor + method that prints a personalized greeting.
- [`operator_overloading_demo.tiny`](src_tiny/operator_overloading_demo.tiny): Lean point class that overrides `+` and `==` and prints intermediate results.
- [`number_class.tiny`](src_tiny/number_class.tiny): Demonstrates the `Number` class and the overloaded `+` operator; instantiates objects, calls methods, and prints the result.
- [`number_intervall.tiny`](src_tiny/number_intervall.tiny): Example for numeric interval calculations and bounds checking.
- [`namespace_demo.tiny`](src_tiny/namespace_demo.tiny): A small `Tools` namespace with `double` and `label` helpers.
- [`concurrency_demo.tiny`](src_tiny/concurrency_demo.tiny): Starts multiple tasks with `spawn`, collects them via `join`, and combines them with `String.split`/`String.join` into a single output.
- [`heap_pointer_demo.tiny`](src_tiny/heap_pointer_demo.tiny): Safe heap handling with `new`, `heap_get`/`heap_set`, and `delete`, plus typical error messages for out-of-bounds or field access mistakes.
- [`stdlib_collections_demo.tiny`](src_tiny/stdlib_collections_demo.tiny): Map/Set/Deque examples from the Collections API.
- [`stdlib_io_random_demo.tiny`](src_tiny/stdlib_io_random_demo.tiny): Random helpers plus JSON parsing and file I/O working together.

## Common errors
- **Unused bindings**: Unused local variables or parameters raise errors (e.g., "unused parameter(s) in function f: b", "unused local binding(s): t").
- **Mutated parameters not returned**: When parameters are mutated they must be included in the return value (e.g., "mutated parameter(s) in function bump must be returned: a").
- **Type changes**: Reassigning a variable to a different inferred type raises `[E014] type change for variable ... expected <type> but got <type>`. Use a new variable or an explicit cast when switching types.

## Formatter, lints, and language server
- **Formatter**: `python tiny_language.py --format file.tiny` enforces four-space indents, a single space around operators and after commas, and normalized import lines (`import path as alias;`). Comments are preserved.
- **Linter style rules**: Unused bindings can be intentionally suppressed with a leading `_`. Import statements must appear sorted before the rest of the code (`E012`). Function calls with return types must not be silently ignored (`E011`); either bind the result or explicitly discard it with `_ = fn();`).
- **Language server prototype**: The `language_server.py` module exposes a small API for hover, completions, and diagnostics—handy for experimenting with LSP ideas without writing a JSON-RPC server. See [`docs/language_server_workflows.md`](docs/language_server_workflows.md) for a quickstart with example CLI commands and structured JSON outputs.
- **Incomplete destructuring**: All fields of a returned struct must be bound ("destructuring call to f must include output for argument(s): a"), and every binding must be used.
- **Bare calls**: Function calls cannot stand alone as statements ("bare call statements are not allowed"); print or assign the result instead.
- **Arithmetic limits**: The `^` operator accepts only integer exponents ("exponent for ^ must be an integer"); use `power` for fractional exponents.
- **Heap/field access**: Out-of-bounds or missing fields raise runtime errors (e.g., "heap access error: index 5 out of range ...", "unknown field missing"). `errorMessage` stores the last runtime error.

## Running programs and tests
- **Run a program**: `./tiny_language <file.tiny>` executes a TinyLanguage program and exits with status 0 on success. Example: `./tiny_language src_tiny/demo.tiny`.
  - If you prefer per-file executability, add a shebang such as `#!/usr/bin/env -S ./tiny_language` to the top of your `.tiny` file, mark it executable (`chmod +x your_program.tiny`), and run it directly with `./your_program.tiny`.
- **Python CLI wrapper**: `python -m tiny_lang_cli path/to/program.tiny` uses the same interpreter but can also switch backends with `--backend interpreter|python|native`. Inline snippets remain available via `--source "print(1+2);"`. Add `--emit-llvm` to print a textual LLVM IR prototype for arithmetic-heavy snippets instead of executing them.
- **Test suite**: `python -m pytest` runs all tests. Target individual files with commands like `python -m pytest tests/test_tiny_language.py -k class`.
  - On PowerShell, avoid entering just `test` after activating the virtual environment; `test` is a shell built-in that immediately exits without running the project. Use the explicit `python -m pytest` invocation (or `python run_all.py` for a combined smoke test) from the repository root instead.

### Optional type hints
- **Syntax**: Parameters and return types can be annotated with a trailing `?` (for example, `fn greet(name: string?) -> string?`). The suffix allows `Null` values in addition to the annotated type.
- **Gradual checks**: Type hints remain optional, but when provided the runtime enforces them on call boundaries and returns. Non-optional annotations still require every control-flow path to return a value.
- **Diagnostics**: Type errors surface with code `E009` and mention that `?` can be used to permit `Null` when desired.

### CLI: module init and publish
- **Init**: Create a new module directory (`mkdir my_pkg && cd my_pkg`), add an entry point such as `main.tiny`, and optionally maintain a `module.json` with metadata:

  ```json
  {"name": "my_pkg", "version": "1.0.0", "entrypoint": "main.tiny", "dependencies": ["utils@^2.1.0"]}
  ```

  Keep your sources in the same folder and resolve imports via the module path. A minimal scaffold:

  ```
  my_pkg/
    module.json
    main.tiny
    helpers.tiny
  ```

  Validate locally with `python ../tiny_language.py main.tiny` or via the wrapper `python -m tiny_lang_cli --file main.tiny --backend interpreter`; relative imports like `import .helpers;` work thanks to the module resolver. To pin dependencies during local tests, set `TINYPATH=../deps` and place sibling modules in that folder.
- **Publish**: Package the module sources plus `module.json`, e.g., `tar -czf my_pkg-1.0.0.tgz module.json *.tiny`, and upload to your target repository or artifact registry. Document version pins (e.g., `lib@1.4.2` or `lib@~1.4`) in the manifest to keep builds reproducible.

  For a final smoke test before release, extract the tarball into a temp directory and run `python -m tiny_lang_cli --file main.tiny --backend native` to ensure both interpreter and native backends succeed without access to the original workspace.

Note: On platforms without `readline` (e.g., Windows) the REPL history tests are automatically skipped (`1 skipped`). Other tests still run; the skip simply notes the optional dependency.

### Interactive REPL
- Tab completion covers keywords, stdlib names, and bindings defined in the current session. Completion works even without the native `readline` library.
- History is kept in memory and can be replayed via arrow keys or a simple reverse search (`Ctrl + R`). On exit it is persisted to `~/.tiny_language_history` when possible.
- Syntax highlighting is available when [`pygments`](https://pygments.org/) is installed and the REPL is running on a TTY. Set `TINYL_REPL_HIGHLIGHT=0` to disable coloring for copy/paste workflows.

Additional examples and expected diagnostics live in `tests/test_tiny_language.py` and the programs above.

### Error handling
- **Try/catch blocks**: Wrap risky code in `try { ... } catch(err) { ... }` to intercept runtime failures. The `err`
  object carries a `code`, human-readable `message`, optional `hint`, and a `stack` array with the formatted call chain.
- **Result helpers**: The stdlib exposes a lightweight `Result` type with `Result.ok(value)` and `Result.err(error)` helpers
  plus `Result.is_ok`/`Result.is_err` and `Result.unwrap_or`. Use it to thread success/failure through pipelines without
  throwing.
- **Stack traces**: Unhandled runtime errors include stack traces in their messages by default, and caught errors preserve
  the same information for logging or conversion into `Result.Err` values.

## Ideas for future extensions
- [x] **Pattern matching and algebraic data types**
  - [x] Design syntax for sum/product types and match expressions
  - [x] Implement exhaustiveness checks in the parser/interpreter
  - [x] Add example programs and tests for missing/extra cases
- [x] **Modules/packages**
  - [x] Define module loading semantics (namespacing, relative imports, search path)
  - [x] Extend the interpreter with a module resolver and caching
  - [x] Describe CLI workflow for module init/publish (version pins optional)
- [x] **Optional type hints**
  - [x] Specify syntax for optional type annotations on functions, parameters, and return values
  - [x] Implement gradual typing checks and simple exhaustiveness checks
  - [x] Extend error messages and docs with type hints
- [x] **Better error handling**
  - [x] Design `try/catch` blocks or a `Result` type
  - [x] Show stack traces in error messages
  - [x] Add example programs/tests for error paths without aborting execution
- [x] **Tooling**
  - [x] Specify and implement a minimal formatter (spacing, semicolons, imports)
  - [x] Define lints for unused bindings, bare calls, and style rules
  - [x] Sketch a language-server prototype with hover/completion/diagnostics
- [x] **Parallelism**
  - [x] Design `async/await` or channel-based structured concurrency
  - [x] Add cancellation tokens and safe abort paths to the runtime model
  - [x] Create deterministic, race-free test cases
- [x] **Stdlib expansion**
  - [x] Design and implement core Collections APIs (maps, sets, deques)
  - [x] Add Math/Random extensions plus file/JSON utilities
  - [x] Document and demo new stdlib components
- [x] **Interop** (see [`docs/python_interop.md`](docs/python_interop.md) for the design)
  - [x] Define an FFI to Python functions/modules (argument/return mapping)
  - [x] Specify security and sandboxing mechanisms
  - [x] Document common Python interop scenarios

## Further issues to explore
- [x] **Native compiler**: Investigate emitting bytecode or native code directly from the TinyLanguage AST instead of interpreting it.
- [x] **Transpilers**: Prototype bidirectional translators to and from Python, Julia, JavaScript, and C++ while preserving semantics and idioms.
- [x] **VS Code extension**: Ship syntax highlighting, formatting, REPL integration, and diagnostics as a Visual Studio Code marketplace extension.
- [x] **Cross-language compatibility**: Document any constructs that do not map cleanly to other mainstream languages and propose portable alternatives.
- [x] **Full inline commentary**: Add exhaustive line-by-line comments across TinyLanguage source and sample programs for learners.

## Roadmap / TODO

This section gathers upcoming work for TinyLanguage.
Roughly grouped into frontend/language, type discipline, runtime, and tooling.
The “nativeCompiler” work is tracked separately.

### 1. Frontend / language

- [x] **Improve error positions and messages**
  - Tokens and AST nodes should consistently carry line and column information.
  - Unified error type with an optional `SourceSpan` that highlights the affected line when displayed.
  - Lexer, parser, and linter should all use this error type.

- [x] **Refine the linter**
  - “must use” rule across control flow: a variable counts as used only when referenced on all relevant paths.
  - Unreachable-code warnings (e.g., statements after `return`).

### 2. Type discipline

- [x] **No implicit type changes**
  - After `define i = 5;`, assigning `i = 0.5;` should be an error unless intentionally handled otherwise.
  - Apply type rules uniformly across expressions, functions, and heap operations.
- [x] (Optional) Simple type inference
  - Example: `define x = 0;` ⇒ `x` is of type `number` without an explicit annotation.

### 3. Runtime

- [x] **Harden the heap API**
  - More precise errors for invalid pointers, out-of-bounds, double `delete`, etc.
  - Simple leak tracking (e.g., for tests).
- [x] **Expand the test suite**
  - Edge cases: nested arrays, many `new/delete` pairs, deep recursion, heap-API failure scenarios.

### 4. Tooling

- [x] **CLI wrapper**
  - A small command-line tool that compiles/runs TinyLanguage files (e.g., `python -m tiny_lang_cli source.tiny`, depending on project layout).
- [x] **Document the language**
  - Short, stable language specification (syntax, type rules, “must use” rules) to keep behavior clear. See [`docs/language_spec.md`](docs/language_spec.md).

### 5. Native Compiler

The native compiler is developed in its own branch (`nativeCompiler`).

- [x] Define a custom native IR (stack- or register-based). See [`docs/native_ir.md`](docs/native_ir.md) for opcode overview and examples.
- [x] Small VM that executes this IR (interpreter in Python or as a separate module).
- [x] Lowering: AST → Native IR for expressions, statements, functions, heap API.
- [x] Optional: Backend targeting C/LLVM or “pure Python bytecode” to produce native code.
