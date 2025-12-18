# TinyLanguage: Quick reference and semantics

This file summarizes the most important TinyLanguage constructs. It is intended for readers who want to look up syntax and runtime behavior quickly without diving into the interpreter code.

## Lexical elements
- **Comments:** `//` starts a comment to the end of the line. Block comments have no special syntax.
- **Semicolons:** Every statement ends with `;`. The formatter inserts missing semicolons in simple cases, but programs should include them explicitly.
- **Identifiers and literals:**
  - Numbers support integers and decimals (`1`, `3.14`, `0.5`). Scientific notation is intentionally disallowed (`1.2e2` fails).
  - Strings use double quotes and allow basic escapes like `\n`.
  - Booleans are `true` and `false`; `null` indicates the absence of a value.

## Expressions and operators
- **Arithmetic:** `+`, `-`, `*`, `/`, and exponentiation `^` (the exponent must be an integer). Division returns floating-point values; overflow is trapped and reported as an error.
- **Comparisons:** `==`, `!=`, `<`, `>`, `<=`, `>=` work on numbers, strings, booleans, and user types with operator overloads.
- **Booleans:** Short-circuit logic with `&&` and `||`, negation via `!expr`.
- **Arrays and heap:** `new[1, 2, 3]` creates an array; `new(3)` reserves heap space with three slots. Access via `heap_get(ptr, idx)` and `heap_set(ptr, idx, value)`. `tag(ptr, "Label")` attaches a type tag, and `delete(ptr)` frees memory.
- **Struct literals:** `{ a: 1, b: 2 }` builds an anonymous struct; fields are read with dot notation (`obj.a`).

## Bindings and visibility
- **Definitions:** `define x = expr;` creates a new variable. Later assignments without `define` update existing bindings and must not silently change the type when annotations are present.
- **Scopes:** Functions, namespaces, and match arms introduce their own scopes. Imported modules are registered under their fully qualified name and can be reached via aliases.

## Control flow
- **`if`/`while`:** Standard control structures with parentheses around the condition. Conditions must yield booleans; all paths in typed functions must return a value.
- **`match`:** Exhaustive pattern matching for `type` variants and structs. Wildcards (`_`) and named fields (`case Circle { radius: r }`) are supported; missing cases raise an error.
- **Error handling:** `try { ... } catch(err) { ... }` catches runtime errors and allows alternative returns or logging.

## Functions and types
- **Declaration:** `fn add(x: number, y: number) -> number { return x + y; }`. Parameters and return values are optionally typed; annotations are enforced at runtime.
- **Return requirement:** Annotated functions must return a value on all paths, otherwise error `E010` is raised.
- **Closures:** Functions are first-class and can be returned or passed as arguments.

## Argument-Kapselung
- **Opt-in Flag:** `--copy-on-call` (oder `TINYLANG_COPY_ON_CALL=1`) aktiviert defensive Kopier-Semantik für Funktions- und Methodenaufrufe.
- **Wann kopiert wird:** Nicht-escaped, mutierbare Argumente (Heap-Pointer, Struct-/Variant-Maps, Klasseninstanzen) werden vor dem Binden tief kopiert. Parameter, die in einem `return`-Pfad vorkommen, gelten als escaped und behalten ihre Identität.
- **Schreibschutz:** Versuche, über andere Aliasse auf einen geschützten Parameter zu schreiben, schlagen mit einem Laufzeitfehler fehl, um Außenwirkungen zu verhindern.
- **Performance:** Das Kopieren ist zyklenfest, kann aber bei großen Objektgraphen merklich mehr Zeit und Speicher kosten.
- **Beispiel:**
  ```tiny
  fn bump(buf) {
      heap_set(buf, 0, 99);
  }

  define data = new(1);
  heap_set(data, 0, 1);
  bump(data); // mit --copy-on-call bleibt data[0] == 1
  ```

## Algebraic data types and pattern matching
- **`type` definitions:**
  ```tiny
  type Shape {
    Circle { radius: number };
    Rectangle { width: number, height: number };
  }
  ```
  Each variant automatically becomes a constructor (e.g., `Circle { radius: 2 }`).
- **Exhaustive matching:** `match` expressions must cover every variant; otherwise a hint about the missing cases is produced.

## Classes and operator overloading
- **Classes:** Fields declare types (`name: string;`). Methods use the same function syntax and receive `self` as the first argument. Constructor functions can be defined freely (`fn Greeter(name) { return new Greeter { name: name }; }`).
- **Multiple inheritance:** Classes can list multiple base types; method resolution follows a linear order that avoids conflicts.
- **Operators:** Any operator can be overloaded, e.g., `operator + (a: Point, b: Point) -> Point { ... }`. Comparisons (`==`) and arithmetic operators can use custom logic.

## Modules and namespaces
- **Loading modules:** `import math.trig;` loads `math/trig.tiny`. Aliases are allowed (`import utils.helpers as helpers;`). Re-importing a module returns the same namespace; cycles are detected and reported with `E008`.
- **Namespaces:** `namespace Tools { ... }` groups functions and constants. Fields are referenced with dot notation (`Tools.double(5)`), including across modules.

## Concurrency and async API
- **Tasks:** `spawn f(1, 2)` starts `f` asynchronously; `join(handle)` waits and forwards the result or error.
- **Cancellation:** `Async.token()` creates a token that can be cancelled via `Async.cancel(token, "reason")`. Tasks can be linked (`Async.link(token, handle)`) to propagate cancellations.

## Errors and diagnostics
- **Error messages:** The interpreter annotates lexer, parser, and runtime errors with codes like `E001` (syntax), `E008` (module resolution), or `E009` (type error). When possible, a `SourceSpan` with line/column information highlights the failing code.
- **Linter:** Warnings for unused bindings, style rules (semicolons, spacing), and simple “must use” checks are integrated and reported during formatting or by the LSP.

## Running and tools
- **Interpreter:** `python tiny_language.py <file.tiny>` executes a source file. Modules are resolved relative to the caller, `TINYPATH`, and the project root.
- **CLI demos:** Example programs live in `src_tiny/`; they cover classes, pattern matching, operators, concurrency, and Python interop.
- **Language server:** `python tiny_language_server.py --stdio` starts the LSP; a reference for available methods is in [`docs/language_server_workflows.md`](language_server_workflows.md).
