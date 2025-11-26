# TinyLanguage

TinyLanguage is a small Julia-inspired language with a Python interpreter. This README provides a StackEdit-style Markdown overview: syntax highlights, a compact tutorial, pointers to examples, common error messages, and the most important run/test commands.

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
A minimal example with a constructor function and a method. The output was verified via `python tiny_language.py class_demo.tiny`.

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

See [`class_demo.tiny`](class_demo.tiny) for the full program.

### Operator overloading
A `Point` type overrides `+` and `==`. Verified via `python tiny_language.py operator_overloading_demo.tiny`.

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

Full program: [`operator_overloading_demo.tiny`](operator_overloading_demo.tiny).

### Namespaces
Namespaces help group related functions. Run with `python tiny_language.py namespace_demo.tiny`.

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

More context in [`namespace_demo.tiny`](namespace_demo.tiny).

### Importing modules
- **Syntax**: `import math.trig;` loads `math/trig.tiny` and binds it under the last path segment (`trig`). Optional aliasing works too: `import utils.helpers as helpers;` or relative imports from inside modules: `import .shared as shared;`.
- **Namespacing**: Every imported file is registered under its fully qualified module name (e.g. `pkg.core`), so functions and constants are accessible as namespace fields (`core.helper_fn()` or `core.value`).
- **Search path**: The resolver checks the caller directory, entries from `TINYPATH` (colon-separated), then the current working directory and the directory containing `tiny_language.py`. Missing modules or cyclic imports raise `E008`.
- **Caching**: Each module file executes only once per runtime; repeated imports return the same namespace reference and avoid duplicate side effects.

### Concurrency
`spawn` and `join` mix tasks and results. Output from `python tiny_language.py concurrency_demo.tiny`:

```tiny
fn label(prefix, word) { return prefix + "=" + word; }

define keywords = String.split("spawn,join,string,interop", ",");
define first = spawn label("erstes", heap_get(keywords, 0));
define second = spawn label("zweites", heap_get(keywords, 1));
define third = spawn label("drittes", heap_get(keywords, 2));
define fourth = spawn label("viertes", heap_get(keywords, 3));

print("etiketten");
print(String.join(new[join(first), join(second), join(third), join(fourth)], " | "));
```

Expected output:

```
etiketten
erstes=spawn | zweites=join | drittes=string | viertes=interop
```

The full version with another split/join lives in [`concurrency_demo.tiny`](concurrency_demo.tiny).

### Heap/pointer operations
`new[...]` allocates arrays, `heap_get`/`heap_set` read and write, `delete` cleans up. Output from `python tiny_language.py heap_pointer_demo.tiny`.

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

Mehr Beispiele und Fehlerszenarien finden sich in [`heap_pointer_demo.tiny`](heap_pointer_demo.tiny).

### Standardbibliothek
Vor jedem Programmstart registriert der Interpreter die eingebaute Stdlib mit folgenden Namespaces:

- **Math**: `Math.abs(x)`, `Math.pow(base, exp)`, `Math.sqrt(x)` fuer grundlegende Mathematik. Neu hinzugekommen sind `Math.max(a, b)` und `Math.min(a, b)` zum Vergleichen sowie `Math.clamp(value, lower, upper)`, um Werte einzugrenzen. Beispiel: `print(Math.clamp(Math.max(-2, 10), 0, 5));` gibt `5` aus.
- **String**: `String.split(text, sep)` liefert einen Heap-Pointer auf ein Array der Teilstrings, `String.join(items, sep)` verbindet eine Liste/Pointer, `String.contains(text, needle)` prueft Teilstrings. Zusaetzlich gibt es `String.upper(text)`, `String.lower(text)`, `String.trim(text)` und `String.repeat(text, count)` fuer Gross-/Kleinschreibung, Whitespace-Trimming und Wiederholung. Beispiel: `print(String.upper(String.trim("  tiny "))); print(String.repeat("ha", 3));` erzeugt `TINY` und `hahaha`.
- **Collections**: `Collections.len(x)` misst die Laenge von Heap-Pointern oder Python-Listen, `Collections.push(target, value)` fuegt am Ende an und liefert die neue Laenge, `Collections.pop(target)` entfernt das letzte Element oder wirft einen Fehler bei leeren Collections. Neu sind `Collections.slice(target, start, end)` fuer Teilbereiche und `Collections.contains(target, value)` zum Nachschlagen: `define mid = Collections.slice(new[1, 2, 3], 1, 3); print(Collections.contains(mid, 2));` druckt `true`.

## Beispielprogramme
- [`demo.tiny`](demo.tiny): Kleines Schaufenster fuer Variablen, Schleifen, Funktionen, Klassen und Heap-Operationen. Laeuft sequenziell durch und druckt Zwischenergebnisse, wodurch man die Sprachfeatures in Aktion sieht.
- [`rosetta_fibonacci.tiny`](rosetta_fibonacci.tiny): Implementiert die klassische Fibonacci-Folge; zeigt Funktionsdefinitionen und einfache Loops. Erwartet werden die ersten 10 Fibonacci-Zahlen auf der Konsole.
- [`all_features.tiny`](all_features.tiny): Umfangreiches Feature-Rundlaufprogramm mit Arrays, Klassen und Operator-Overloading. Praktisch, um die Sprache als Ganzes zu erkunden.
- [`class_demo.tiny`](class_demo.tiny): Minimaler Klassen-Constructor mit Methode; gibt einen personalisierten Gruss aus.
- [`operator_overloading_demo.tiny`](operator_overloading_demo.tiny): Schlanke Punkt-Klasse, die `+` und `==` ueberschreibt und Zwischenergebnisse ausgibt.
- [`number_class.tiny`](number_class.tiny): Demonstriert die `Number`-Klasse und den ueberladenen `+`-Operator; instanziiert Objekte, ruft Methoden auf und gibt das Ergebnis aus.
- [`number_intervall.tiny`](number_intervall.tiny): Beispiel fuer numerische Intervallrechnungen und Grenzenkontrolle.
- [`namespace_demo.tiny`](namespace_demo.tiny): Kleine `Tools`-Bibliothek als Namespace mit `double` und `label`.
- [`concurrency_demo.tiny`](concurrency_demo.tiny): Startet mehrere Aufgaben mit `spawn`, sammelt die Ergebnisse ueber `join` und kombiniert sie mit `String.split`/`String.join` zu einer Ausgabe.
- [`heap_pointer_demo.tiny`](heap_pointer_demo.tiny): Zeigt sicheres Heap-Handling mit `new`, `heap_get`/`heap_set` und `delete` sowie typische Fehlermeldungen bei Out-of-Bounds- oder Feldzugriffen.

## Haeufige Fehler
- **Ungenutzte Bindungen**: Nicht verwendete lokale Variablen oder Parameter fuehren zu Fehlern (z. B. "unused parameter(s) in function f: b", "unused local binding(s): t").
- **Mutierte Parameter nicht zurueckgegeben**: Wird ein Parameter veraendert, muss er im Rueckgabewert enthalten sein (z. B. "mutated parameter(s) in function bump must be returned: a").

## Formatter, Lints und Language-Server
- **Formatter**: `python tiny_language.py --format datei.tiny` erzwingt Einrueckungen mit vier Leerzeichen, genau ein Leerzeichen um Operatoren und nach Kommas sowie normierte Import-Zeilen (`import pfad as alias;`). Kommentare bleiben erhalten.
- **Linter-Stilregeln**: Ungenutzte Bindungen lassen sich jetzt mit einem vorangestellten `_` gezielt unterdruecken. Import-Anweisungen muessen sortiert vor dem restlichen Code stehen (`E012`). Funktionsaufrufe mit Rueckgabetyp duerfen nicht laienhaft ignoriert werden (`E011`); entweder das Ergebnis binden oder bewusst mit `_ = fn();` verwerfen.
- **Language-Server-Prototyp**: Das Modul `language_server.py` bietet eine Mini-API fuer Hover, Completions und Diagnostics. Ideal, um LSP-Ideen auszuprobieren, ohne direkt einen JSON-RPC-Server zu schreiben.
- **Unvollstaendiges Destructuring**: Alle Felder eines zurueckgegebenen Structs muessen gebunden werden ("destructuring call to f must include output for argument(s): a"), und jede Bindung muss benutzt werden.
- **Bare Calls**: Funktionsaufrufe duerfen nicht allein als Statement stehen ("bare call statements are not allowed"); Ergebnis ausgeben oder zuweisen.
- **Arithmetik-Einschraenkungen**: Der `^`-Operator akzeptiert nur ganzzahlige Exponenten ("exponent for ^ must be an integer"); fuer Brueche `power` nutzen.
- **Heap/Field-Zugriffe**: Out-of-Bounds oder fehlende Felder melden Laufzeitfehler (z. B. "heap access error: index 5 out of range ...", "unknown field missing"). `errorMessage` enthaelt den letzten Laufzeitfehler.

## Programme ausfuehren und testen
- **Programm starten**: `python tiny_language.py <datei.tiny>` fuehrt ein TinyLanguage-Programm aus und beendet sich bei Erfolg mit Status 0. Beispiel: `python tiny_language.py demo.tiny`.
- **Test-Suite**: `python -m pytest` fuehrt alle Tests aus. Einzelne Dateien lassen sich gezielt starten, z. B. `python -m pytest tests/test_tiny_language.py -k class`.

### CLI: Module-Init und Publish
- **Init**: Neues Modul-Verzeichnis anlegen (`mkdir my_pkg && cd my_pkg`), einen Einstiegspunkt wie `main.tiny` erzeugen und optional eine `module.json` mit Metadaten pflegen:
See [`heap_pointer_demo.tiny`](heap_pointer_demo.tiny) for more examples and failure scenarios.

### Standard library
The interpreter registers the built-in stdlib before running any program. Namespaces include:

- **Math**: `Math.abs(x)`, `Math.pow(base, exp)`, `Math.sqrt(x)` for basics. New helpers `Math.max(a, b)`, `Math.min(a, b)`, and `Math.clamp(value, lower, upper)` make comparisons and clamping easier. Example: `print(Math.clamp(Math.max(-2, 10), 0, 5));` prints `5`.
- **String**: `String.split(text, sep)` returns a heap pointer to an array of substrings; `String.join(items, sep)` joins a list/pointer; `String.contains(text, needle)` checks for substrings. Extras: `String.upper(text)`, `String.lower(text)`, `String.trim(text)`, and `String.repeat(text, count)` for casing, trimming, and repetition. Example: `print(String.upper(String.trim("  tiny "))); print(String.repeat("ha", 3));` prints `TINY` and `hahaha`.
- **Collections**: `Collections.len(x)` measures the length of heap pointers or Python lists, `Collections.push(target, value)` appends and returns the new length, `Collections.pop(target)` removes the last element or raises on empty collections. New helpers: `Collections.slice(target, start, end)` and `Collections.contains(target, value)` for slicing and lookups: `define mid = Collections.slice(new[1, 2, 3], 1, 3); print(Collections.contains(mid, 2));` prints `true`.

## Example programs
- [`demo.tiny`](demo.tiny): Small showcase for variables, loops, functions, classes, and heap operations. Runs sequentially and prints intermediate results.
- [`rosetta_fibonacci.tiny`](rosetta_fibonacci.tiny): Classic Fibonacci implementation demonstrating function declarations and simple loops. Prints the first 10 numbers.
- [`all_features.tiny`](all_features.tiny): Comprehensive feature tour with arrays, classes, and operator overloading.
- [`class_demo.tiny`](class_demo.tiny): Minimal constructor + method that prints a personalized greeting.
- [`operator_overloading_demo.tiny`](operator_overloading_demo.tiny): Lean point class that overrides `+` and `==` and prints intermediate results.
- [`number_class.tiny`](number_class.tiny): Demonstrates the `Number` class and overloaded `+`, instantiates objects, calls methods, and prints results.
- [`number_intervall.tiny`](number_intervall.tiny): Example for numeric interval calculations and bounds checking.
- [`namespace_demo.tiny`](namespace_demo.tiny): A small `Tools` namespace with `double` and `label` helpers.
- [`concurrency_demo.tiny`](concurrency_demo.tiny): Starts multiple tasks with `spawn`, collects them via `join`, and combines them with `String.split`/`String.join`.
- [`heap_pointer_demo.tiny`](heap_pointer_demo.tiny): Safe heap handling with `new`, `heap_get`/`heap_set`, `delete`, and typical error messages for out-of-bounds or field access mistakes.

## Common errors
- **Unused bindings**: Unused local variables or parameters raise errors (e.g., "unused parameter(s) in function f: b", "unused local binding(s): t").
- **Mutated parameters not returned**: When parameters are mutated they must be included in the return value (e.g., "mutated parameter(s) in function bump must be returned: a").
- **Incomplete destructuring**: All fields of a returned struct must be bound ("destructuring call to f must include output for argument(s): a"), and every binding must be used.
- **Bare calls**: Function calls cannot stand alone as statements ("bare call statements are not allowed"); print or assign the result instead.
- **Arithmetic limits**: The `^` operator accepts only integer exponents ("exponent for ^ must be an integer"); use `power` for fractions.
- **Heap/field access**: Out-of-bounds or missing fields raise runtime errors (e.g., "heap access error: index 5 out of range ...", "unknown field missing"). `errorMessage` stores the last runtime error.

## Running programs and tests
- **Run a program**: `python tiny_language.py <file.tiny>` executes a TinyLanguage program and exits with status 0 on success. Example: `python tiny_language.py demo.tiny`.
- **Test suite**: `python -m pytest` runs all tests. Target individual files with commands like `python -m pytest tests/test_tiny_language.py -k class`.

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

## Ideas for future extensions
- [ ] **Pattern matching and algebraic data types**
  - [ ] Design syntax for sum/product types and match expressions
  - [ ] Implement exhaustiveness checks in the parser/interpreter
  - [ ] Add example programs and tests for missing/extra cases
- [x] **Modules/packages**
  - [x] Define module loading semantics (namespacing, relative imports, search path)
  - [x] Extend the interpreter with a module resolver and caching
  - [x] Describe CLI workflow for module init/publish (version pins optional)
- [ ] **Optional type hints**
  - [ ] Specify syntax for optional type annotations on functions, parameters, and return values
  - [ ] Implement gradual typing checks and simple exhaustiveness checks
  - [ ] Extend error messages and docs with type hints
- [ ] **Better error handling**
  - [ ] Design `try/catch` blocks or a `Result` type
  - [ ] Show stack traces in error messages
  - [ ] Add example programs/tests for error paths without aborting execution
- [ ] **Tooling**
  - [ ] Specify and implement a minimal formatter (spacing, semicolons, imports)
  - [ ] Define lints for unused bindings, bare calls, and style rules
  - [ ] Sketch a language-server prototype with hover/completion/diagnostics
- [ ] **Parallelism**
  - [ ] Design `async/await` or channel-based structured concurrency
  - [ ] Add cancellation tokens and safe abort paths to the runtime model
  - [ ] Create deterministic, race-free test cases
- [ ] **Stdlib expansion**
  - [ ] Design and implement core Collections APIs (maps, sets, deques)
  - [ ] Add Math/Random extensions plus file/JSON utilities
  - [ ] Document and demo new stdlib components
- [ ] **Interop**
  - [ ] Define an FFI to Python functions/modules (argument/return mapping)
  - [ ] Specify security and sandboxing mechanisms
  - [ ] Document common Python interop scenarios
