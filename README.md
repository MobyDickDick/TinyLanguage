# TinyLanguage

TinyLanguage is a small Julia-inspired language with a Python interpreter. This README provides a StackEdit-style Markdown overview: syntax highlights, a compact tutorial, pointers to examples, common error messages, and the most important run/test commands.

For interoperability guidance, see the cross-language compatibility notes in [`docs/cross_language_compatibility.md`](docs/cross_language_compatibility.md). For concrete Rosetta Code–style ports from Python to TinyLanguage, walk through [`docs/rosetta_python_examples.md`](docs/rosetta_python_examples.md). A kompakte Sprachreferenz mit Syntax, Typregeln und Operatorübersicht steht in [`docs/language_spec.md`](docs/language_spec.md).

## Transpiler roadmap (task list)
- [x] **Expand the shared IR**: Ergänze neue Statement-/Expression-Typen (z. B. Kontrollflussknoten wie `IfElse` und `While`) und rüste die Hilfsfunktionen in [`tiny_language_transpilers.py`](tiny_language_transpilers.py) so auf, dass spätere Sprachen-Erweiterungen darauf aufbauen können.
- [x] **Update language transpilers**: Ziehe die Parser/Renderer der `PythonTranspiler`, `JuliaTranspiler`, `JavaScriptTranspiler` und `CppTranspiler` nach, damit die neuen IR-Knoten korrekt hin- und zurückübersetzt werden.
- [x] **Add tests**: Erweitere die Round-Trip-Tests (Quelle → IR → Quelle) für jede neue Sprachfunktion und ergänze Negativtests für nicht unterstützte Konstrukte.

## Offene Aufgaben
- [x] **Language-Server-Workflows dokumentieren (gestartet)**: Eine kompakte Referenz für `TinyLanguageServer` schreiben, Beispiel-Requests/-Responses aufnehmen und die neuen CLI-Demos dokumentieren (siehe [`docs/language_server_workflows.md`](docs/language_server_workflows.md)). Ergänzend dazu Tests für Hover/Completion/Diagnostics hinzufügen, damit künftige Änderungen abgesichert sind.
- [x] **Python-Interop-Demos ausbauen**: Zusätzliche `.tiny`-Programme bereitstellen, die die Anleitung in [`docs/python_interop.md`](docs/python_interop.md) konkret durchspielen, inklusive How-to-Run-Hinweisen und Tests.
- [x] **Native-Compiler-Prototyp evaluieren**: Einen alternativen Backend-Pfad implementieren, der aus dem vorhandenen AST Bytecode oder native IR erzeugt und über eine kleine VM lauffähig ist. Iterativ über Smoke-Tests (Arithmetik, Branching, Funktionen) mit dem Interpreter abgleichen. Siehe [`docs/native_compiler.md`](docs/native_compiler.md) für CLI-Aufrufe, Regression-Tests und bekannte Grenzen.

## Nächste sinnvolle Schritte
- [x] **Dokumentation vertiefen/aktualisieren (Startpunkt, erledigt)**: Die bestehenden Guides in `docs/` gegeneinander abgleichen und auf den neuesten Stand bringen. Konkret:
  - In [`docs/language_server_workflows.md`](docs/language_server_workflows.md) alle derzeit verfügbaren LSP-Methoden mit Beispiel-Requests/-Responses ergänzen und die Demo-Aufrufe aus der README-Sektion „Syntax and Features“ als kurze „So testest du es“-Abschnitte einfügen.
  - In [`docs/python_interop.md`](docs/python_interop.md) mehr Durchstich-Beispiele aufnehmen, die modulare Imports, Namespaces und typisierte Funktionssignaturen gemeinsam demonstrieren; dabei die passenden `.tiny`-Demos aus `src_tiny/` verlinken und deren erwartete Ausgaben dokumentieren.
  - In [`docs/native_compiler.md`](docs/native_compiler.md) den aktuellen CLI-Workflow und Grenzen der VM betonen und eine kleine Troubleshooting-Liste (häufige Fehlercodes, typisches Stacktrace-Beispiel) anhängen.

## Neue Schnellreferenzen
- **Feature Cheat Sheet**: [`docs/feature_cheat_sheet.md`](docs/feature_cheat_sheet.md) fasst die Kernkonstrukte mit kurzen Hinweisen zu den zugehörigen `.tiny`-Demos zusammen.
- **Run-/Test-Befehle gebündelt**: [`docs/demo_run_commands.md`](docs/demo_run_commands.md) listet Interpreterläufe, Native-Backend-Vergleiche, Python-Interop-Demos und Language-Server-CLI-Checks auf. Als Komplettlauf eignet sich weiterhin `python run_all.py`.

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
- **Destructuring**: Functions can return structs: `fn bump(a) { a = a + 1; return { a: a, e: 0 }; }` can be bound with `{ a, e } = bump(1);`.
- **Classes and operators**: Classes have fields and methods and allow multiple inheritance. Operators can be overloaded, e.g. `operator + (a: Number, b: Number) -> Number { ... }`.
- **Concurrency**: `spawn f(1, 2)` starts a task, `join` waits and returns its result.
- **Cancellation tokens**: The `Async` namespace offers `token()`, `cancel(token, reason)`, `is_cancelled(token)`, `reason(token)`, and `link(token, handle)` so tasks can cooperate on structured cancellation. See [`docs/structured_concurrency.md`](docs/structured_concurrency.md) for the design sketch.

### Type hints and gradual typing
- **Syntax**: Annotate parameters and return values: `fn label(x: string, times: number) -> string { return x * times; }`. Methods follow the same syntax.
- **Gradual typing checks**: Annotated arguments and returns are validated at runtime. A call like `label(1, "x")` yields `[E009] type mismatch ... expected string/number ...`.
- **Basic exhaustiveness checks**: Annotated functions must return a value on all paths. Missing `return` statements trigger `[E010] not all paths ... return a value ...` with hints about missing branch returns.

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
- **Python CLI wrapper**: `python -m tiny_lang_cli path/to/program.tiny` uses the same interpreter but can also switch backends with `--backend interpreter|python|native`. Inline snippets remain available via `--source "print(1+2);"`.
- **Test suite**: `python -m pytest` runs all tests. Target individual files with commands like `python -m pytest tests/test_tiny_language.py -k class`.

### Optional type hints
- **Syntax**: Parameters and return types can be annotated with a trailing `?` (for example, `fn greet(name: string?) -> string?`). The suffix allows `Null` values in addition to the annotated type.
- **Gradual checks**: Type hints remain optional, but when provided the runtime enforces them on call boundaries and returns. Non-optional annotations still require every control-flow path to return a value.
- **Diagnostics**: Type errors surface with code `E009` and mention that `?` can be used to permit `Null` when desired.

### CLI: module init and publish
- **Init**: Create a new module directory (`mkdir my_pkg && cd my_pkg`), add an entry point such as `main.tiny`, and optionally maintain a `module.json` with metadata:

  ```json
  {"name": "my_pkg", "version": "1.0.0", "entrypoint": "main.tiny", "dependencies": ["utils@^2.1.0"]}
  ```

  Then validate locally with `python ../tiny_language.py main.tiny`; relative imports like `import .helpers;` work thanks to the module resolver.
- **Publish**: Package the module sources plus `module.json`, e.g., `tar -czf my_pkg-1.0.0.tgz module.json *.tiny`, and upload to your target repository or artifact registry. Document version pins (e.g., `lib@1.4.2` or `lib@~1.4`) in the manifest to keep builds reproducible.

Note: On platforms without `readline` (e.g., Windows) the REPL history tests are automatically skipped (`1 skipped`). Other tests still run; the skip simply notes the optional dependency.

### Interactive REPL
- Tab completion covers keywords, stdlib names, and bindings defined in the current session. Completion works even without the native `readline` library.
- History is kept in memory and can be replayed via arrow keys or a simple reverse search (`Ctrl + R`). On exit it is persisted to `~/.tiny_language_history` when possible.

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

Dieser Abschnitt sammelt anstehende Aufgaben für TinyLanguage.
Grob unterteilt in: Frontend/Sprache, Typdisziplin, Runtime und Tooling.
Der „nativeCompiler“ wird separat geführt.

### 1. Frontend / Sprache

- [x] **Fehlerpositionen und Fehlermeldungen verbessern**
  - Tokens und AST-Knoten sollen konsistent Zeilen- und Spalteninformation tragen.
  - Einheitlicher Fehlertyp mit optionalem `SourceSpan`, der bei Ausgabe die betroffene Zeile und eine Unterstreichung zeigt.
  - Lexer, Parser und Linter sollen diesen Fehlertyp verwenden.

- [x] **Linter verfeinern**
  - „must use“-Regel über Kontrollfluss: eine Variable gilt nur als benutzt, wenn sie auf allen relevanten Pfaden verwendet wird.
  - Unreachable-Code-Warnungen (z.B. Code nach `return`).

### 2. Typdisziplin

- [x] **Keine impliziten Typänderungen**
  - Nach `define i = 5;` soll `i = 0.5;` ein Fehler sein, sofern nicht bewusst ein anderer Weg gewählt wird.
  - Typregeln einheitlich in Ausdrücken, Funktionen und Heap-Operationen anwenden.
- [x] (Optional) Einfache Typinferenz
  - Z.B. `define x = 0;` ⇒ `x` ist vom Typ `number`, ohne explizite Annotation.

### 3. Runtime

- [x] **Heap-API robuster machen**
  - Präzisere Fehlermeldungen für ungültige Pointer, Out-of-Bounds, doppelte `delete` usw.
  - Einfaches Leak-Tracking (z.B. für Tests).
- [x] **Test-Suite erweitern**
  - Randfälle: verschachtelte Arrays, viele `new/delete`, tiefe Rekursion, Fehlerfälle der Heap-API.

### 4. Tooling

- [x] **CLI-Wrapper**
  - Ein kleines Kommandozeilentool, das TinyLanguage-Dateien kompiliert/ausführt
    (z.B. `python -m tiny_lang_cli source.tiny` o.ä., abhängig von der Projektstruktur).
- [x] **Sprache dokumentieren**
  - Kurze, stabile Sprachspezifikation (Syntax, Typregeln, „must use“-Regeln), damit das Verhalten klar bleibt. Siehe [`docs/language_spec.md`](docs/language_spec.md).

### 5. Native Compiler

Der native Compiler wird in einem eigenen Branch (`nativeCompiler`) entwickelt.

- [x] Eigenes Native-IR definieren (stack-/registerbasiert). Siehe [`docs/native_ir.md`](docs/native_ir.md) für Opcode-Übersicht und Beispiele.
- [x] Kleine VM, die dieses IR ausführt (Interpreter in Python oder als separates Modul).
- [x] Lowering: AST → Native-IR für Ausdrücke, Statements, Funktionen, Heap-API.
- [x] Optional: Backend auf C/LLVM oder „reinem Python-Bytecode“ zur Erzeugung nativen Codes.
