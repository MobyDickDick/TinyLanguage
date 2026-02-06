# TinyLanguage: Quick reference and semantics

This file summarizes the most important TinyLanguage constructs. It is intended for readers who want to look up syntax and runtime behavior quickly without diving into the interpreter code.

## Language core alignment (roadmap scope)

The language-core roadmap scope calls out evaluation order, scoping, error
handling, and concurrency semantics. This spec explicitly covers those topics
in the sections below so the roadmap and the documentation stay in sync.

- **Evaluation order** is defined in **Evaluation order and side effects**,
  including left-to-right argument evaluation and short-circuit logic.
- **Scoping** rules are summarized in **Bindings and visibility**, including
  where new scopes are introduced and how bindings are resolved.
- **Error handling** is defined in **Control flow** and elaborated in
  **Errors and diagnostics**, covering runtime `try`/`catch` behavior and the
  structured error format used across tooling.
- **Concurrency semantics** are described in **Control flow** (task scopes)
  and **Concurrency and async API** (spawn/await/cancellation behavior).

## Version 1.0 feature status

The v1 language profile separates stable, mandatory features from opt-in
experiments. Use `TINYLANG_V1_ONLY=1` (or `--v1-only` in the CLI) to ensure a
program stays within the v1 feature set.

**V1 core (mandatory)**
- Lexical elements, literals, and identifiers.
- Expressions, operators, and evaluation order.
- Control-flow (`if`, `while`, `switch`, `match`, `try`/`catch`).
- Functions, classes/types, namespaces, and module imports.
- Struct literals, arrays, and heap operations (including linted safety rules).
- Concurrency primitives (`spawn`, `await`, `task` scopes) as documented below.

**Experimental (opt-in)**
- Math tuple sugar `(name: expr)` gated behind `--experimental-math-tuples`.
- Math formula blocks `#[ ... ]` gated behind `--experimental-math-formula`.

## Lexical elements

- **Comments:** `//` starts a comment to the end of the line. Block comments have no special syntax.
- **Semicolons:** Simple statements (`def`, assignments, calls, `return`, etc.) end with `;`. Block statements (`if`, `while`, `switch`, `try`, `task`, `fn`, `class`, `type`, `namespace`) use braces and do not take a trailing semicolon. The formatter inserts missing semicolons in simple cases, but programs should include them explicitly.
- **Identifiers and literals:**
  - Numbers support integers, decimals, and scientific notation (`1`, `3.14`, `0.5`, `1.2e2`).
  - Strings use double quotes and allow basic escapes like `\n`.
  - Booleans are `true` and `false`; `Null` indicates the absence of a value.
- **Reserved keywords vs. identifiers:** Keywords are still used to start control-flow statements, but Tiny deliberately allows keywords in select identifier slots so you can name members or new bindings with them. The grammar uses `NAME_or_kw` for those positions, and the parser accepts keywords when introducing a new binding (e.g., `def match = 1;`). Assignments, function parameters, destructuring targets, and module path segments remain strict `NAME` only.
  - Keywords today include: `def`, `print`, `if`, `else`, `while`, `switch`, `default`, `fn`, `import`, `return`, `operator`, `new`, `type`, `class`, `namespace`, `as`, `spawn`, `async`, `await`, `task`, `true`, `false`, `flush`, `and`, `or`, `not`, `Null`, `try`, `catch`, `match`, `case`.
  - `NAME_or_kw` appears in member access, method declarations, and type annotations, so keywords can be used there without being treated as control flow.

  ```tiny
  class KeywordDemo {
      fn match(self) { return "ok"; } // method name uses a keyword
  }

  def match = "ok"; // keyword used as a binding name
  def demo = new KeywordDemo {};
  print(demo.match()); // member access accepts NAME_or_kw
  ```

## Expressions and operators

- **Arithmetic:** `+`, `-`, `*`, `/`, `%`, and exponentiation `^` (the exponent must be an integer, or a float that is an integer value; fractional exponents require a non-negative base). Division follows Python semantics (integers become floats when needed); tagged `Number`/`NumberIntervall` values use runtime error states like `plus_infinity` instead of raising overflow errors.
- **Comparisons:** `==`, `!=`, `<`, `>`, `<=`, `>=` work on numbers, strings, booleans, and user types with operator overloads.
- **Booleans:** Short-circuit logic with `&&`/`||` or keyword `and`/`or`; negation via `!expr` or `not expr`.
- **Experimental math tuples (opt-in):** With `--experimental-math-tuples`, a single tuple-like form `(name: expr)` desugars to `Math.name(expr)` for quick formula-style calls.
- **Experimental math formulas (opt-in):** With `--experimental-math-formula`, `#[ ... ]` delimits an expression that is parsed using the existing precedence rules.
- **Arrays and heap:** `new[1, 2, 3]` creates an array; `new(3)` reserves heap space with three slots. Access via `heap_get(ptr, idx)` and `heap_set(ptr, idx, value)`. `tag(ptr, "Label")` attaches a type tag, and `delete(ptr)` frees memory.
  - **Ownership + aliasing (single-owner model):**
    - Heap pointers have a single logical owner; lints treat pointer-to-pointer assignments as aliasing violations instead of implicit sharing.
    - Passing a pointer into a helper is a temporary borrow; the caller retains ownership and must still `delete` the allocation.
    - Returning a pointer hands ownership to the caller, which must treat the result as the new owner and avoid continuing to use the previous binding.
    - Copy data or allocate a new buffer when two independent mutable references are needed. See `docs/heap_usage_guidelines.md` for patterns.
  - **Safety profile (current):** heap management is still manual, but the interpreter enables lifetime lints by default. Set `TINY_LINT_HEAP=0` to opt out; the lints catch use-after-free access (including double deletes), leak-prone rebinding of live pointers, and aliasing. These checks are conservative and do not replace a full ownership or GC model.
- **Struct literals:** `{ a: 1, b: 2 }` builds an anonymous struct; fields are read with dot notation (`obj.a`).
  - Curly braces are reserved for struct literals and destructuring assignments (`{ a, b } = expr;`). Tiny does not support unordered set literals. Prefer ordered `new[...]` arrays when iteration order matters, and use stdlib `Set`/`Map` types when you need true unordered semantics.

## Evaluation order and side effects

TinyLanguage guarantees a deterministic left-to-right evaluation order for the
core expression forms that can introduce side effects. The baseline rules are
captured by the semantics suite in `docs/semantics_suite.md`, and the language
spec treats those behaviors as stable.

- **Function and method call arguments** are evaluated left to right before the
  call is applied.
- **Binary operators** evaluate the left operand before the right operand.
- **Short-circuit boolean operators** (`and`/`or`, `&&`/`||`) only evaluate the
  right operand when needed to determine the result.
- **Array literals** created with `new[...]` evaluate item expressions from left
  to right.

**Example: left-to-right evaluation**

```tiny
fn record(label, value) {
  print(label);
  return value;
}

def result = record("left", 1) + record("right", 2);
print(result);
```

Expected output:

```text
left
right
3
```

**Example: short-circuiting**

```tiny
fn side_effect() {
  print("should not run");
  return true;
}

def ok = false && side_effect();
print("done");
```

Expected output:

```text
done
```

## Bindings and visibility

- **Definitions:** `def x = expr;` creates a new variable. Later assignments without `def` update existing bindings and must keep the same inferred type (or a compatible type) to avoid implicit type changes.
- **Type stability rules:**
  - The first assignment to a binding infers its type; `int`/`float` literals normalize to `number`.
  - Future assignments must stay compatible (e.g., `number` accepts both `int` and `float`; `Bool` matches `bool`; `string` stays `string`).
  - Annotated types follow the same compatibility rules (including `T?` accepting `Null`, and `any` allowing any value).
  - Compatibility is structural for built-ins: `number` accepts `int`/`float`, `Bool`/`boolean` accept `true`/`false`, `string` accepts only string values, and `Null` accepts only `Null`.
  - Optional annotations (`T?`) accept `Null` and any value compatible with `T`.
  - `any` disables type-change checks for that binding, but still reports mismatches when a stricter annotation is present on parameters or returns.
  - To change a binding to an unrelated type, introduce a new variable (or annotate the binding as `any`/`T?` when appropriate) instead of reassigning.
  - Unannotated function returns also infer a type; returning a different type later triggers `E014` unless a return annotation is provided.
- **Scopes:** Functions, namespaces, and match arms introduce their own scopes. Imported modules are registered under their fully qualified name and can be reached via aliases.

**Example: function scope shadowing**

```tiny
def x = 1;

fn demo() {
  def x = 2;
  return x;
}

print(demo());
print(x);
```

Expected output:

```text
2
1
```

**Example: match arm bindings are local**

```tiny
type Shape {
  Circle { radius: number };
}

def shape = Shape.Circle { radius: 3 };
match(shape) {
  case Shape.Circle { radius: r } => { print(r); }
}
```

Expected output:

```text
3
```

## Control flow

- **`if`/`while`:** Standard control structures with parentheses around the condition. Conditions use truthiness (`false`, `Null`, `0`, and empty strings are falsey); all paths in typed functions must return a value.
- **`switch`:** Compares a target expression against each case expression using equality; the first match runs its block, otherwise the optional `default` block runs. Each case is isolated (no fallthrough).
- **`match`:** Exhaustive pattern matching for tagged values (sum-type variants, classes, and structs). Wildcards (`_`) and named fields (`case Circle { radius: r }`) are supported, along with positional bindings (`case Circle(r) => ...`); missing cases raise an error.
- **Error handling:** `try { ... } catch(err) { ... }` catches runtime errors and allows alternative returns or logging.
- **Task scopes:** `task { ... }` introduces a structured concurrency scope. When the scope exits, TinyLanguage waits up to a small timeout (defaults to `50ms`, configurable via `TINYLANG_TASK_SCOPE_TIMEOUT_MS`) for outstanding `spawn`ed work to finish; any tasks still running after the timeout are cancelled and joined automatically.

**Example: try/catch**

```tiny
try {
  def x = 1 / 0;
  print("unreachable");
} catch(err) {
  print("caught");
}
```

Expected output:

```text
caught
```

## Functions and types

- **Declaration:** `fn add(x: number, y: number) -> number { return x + y; }`. Parameters and return values are optionally typed; annotations are enforced at runtime.
- **Return requirement:** Annotated functions must return a value on all paths, otherwise error `E010` is raised.
- **Closures:** Functions are first-class and can be returned or passed as arguments.

## Argument-Kapselung

- **Opt-in flag:** `--copy-on-call` (or `TINYLANG_COPY_ON_CALL=1`) enables defensive copy semantics for function and method calls.
- **When copying happens:** Non-escaped, mutable arguments (heap pointers, struct/variant maps, class instances) are deep-copied before binding. Parameters that appear on a `return` path are treated as escaped and keep their identity.
- **Write protection:** Attempts to write to a protected parameter through other aliases fail with a runtime error to avoid side effects.
- **Performance:** Copying is cycle-safe but can cost noticeably more time and memory for large object graphs.
- **Beispiel:**

  ```tiny
  fn bump(buf) {
      def _unused2 = heap_set(buf, 0, 99);
  }

  def data = new(1);
  def _unused3 = heap_set(data, 0, 1);
  def _unused4 = bump(data); // mit --copy-on-call bleibt data[0] == 1
  ```

## Algebraic data types and pattern matching

- **`type` definitions:**

  ```tiny
  type Shape {
    Circle { radius: number };
    Rectangle { width: number, height: number };
  }
  ```

  - Sum types can also be spelled explicitly with `type Shape = sum { ... }`.
  - Product types can be declared as `type Point = product { x: number; y: number; }`.
  - When the `=` kind is omitted, the parser treats a body that starts with
    `name: type` as a product type; otherwise it parses a sum type.
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
- **Async functions:** `async fn work() { ... }` returns a task handle when invoked. Use `await expr` to join a handle inline (equivalent to `join(expr)`), which returns the result or raises an error.
- **Spawn targets:** `spawn` expects a function name (`spawn work(1)`); use helpers or wrappers when you need to call methods or field-based callables.
- **Cancellation:** `Async.token()` creates a token that can be cancelled via `Async.cancel(token, "reason")`. Tasks can be linked (`Async.link(token, handle)`) to propagate cancellations.
- **Scheduling semantics:** `spawn` begins work as soon as the runtime can schedule it; there is no guaranteed ordering between sibling tasks, so any ordering requirements should be encoded explicitly (e.g., by awaiting a handle or using synchronization primitives).
- **Cancellation semantics:** cancellation is cooperative—tasks observe cancellation through linked tokens and should exit promptly when signaled. A cancelled task reports a cancellation error to `join`/`await` instead of a successful result.

## Versioning and deprecation policies

- **Versioning:** TinyLanguage uses SemVer release tags (`MAJOR.MINOR.PATCH`).
  The current release number lives in `VERSION`, and `CHANGELOG.md` captures
  Added/Changed/Fixed entries plus known issues. The canonical policy is
  documented in [`docs/versioning_deprecation_policy.md`](versioning_deprecation_policy.md).
- **Stability guarantees:** the interpreter behavior documented in this spec is
  considered stable for the current major line; breaking changes require a major
  version bump and an explicit migration plan.
- **Deprecations:** breaking or removed features must be announced in the
  changelog and documentation before removal. When possible, tooling should emit
  deprecation warnings and maintain backwards-compatible shims through at least
  one minor release to ease migrations.

## Errors and diagnostics

- **Unified error format:** Parser, linter, and runtime errors all use the same
  human-readable shape:
  - **Header:** `[E###] <message> (line <start>, col <start>)` or, for spans,
    `[E###] <message> (line <start>, col <start> to line <end>, col <end>)`.
  - **Context lines:** A short excerpt of source with a `^` underline marking
    the location or span.
  - **Optional hint:** A trailing `Hint:` line when a fix can be suggested.
  - **Machine-readable fields:** Each error also carries `code`, `pos`, `span`
    (when available), and `hint` fields for tooling workflows.
  - **Shared schema:** Tooling should emit the structured diagnostic schema
    defined in [`docs/diagnostic_error_schema.md`](diagnostic_error_schema.md)
    so editors and CLI helpers can consume a consistent payload.

  Example:

  ```text
  [E003] unknown variable val (line 2, col 15)
    1 | def value = 1;
  > 2 | print(value + val);
      |               ^
    Hint: Did you mean `value`? Declare the variable first, e.g. `def name = ...;`.
  ```
- **Error messages:** The interpreter annotates lexer, parser, and runtime errors with codes like `E001` (syntax), `E008` (module resolution), or `E009` (type error). When possible, a `SourceSpan` with line/column information highlights the failing code.
- **Linter:** Warnings for unused bindings, style rules (semicolons, spacing), and simple “must use” checks are integrated and reported during formatting or by the LSP.

## Running and tools

- **Interpreter:** `python src/tiny_language.py <file.tiny>` executes a source file. Modules are resolved relative to the caller, `TINYPATH`, and the project root.
- **CLI demos:** Example programs live in `src_tiny/`; they cover classes, pattern matching, operators, concurrency, and Python interop.
- **Language server:** `python tiny_language_server.py --stdio` starts the LSP; a reference for available methods is in [`docs/language_server_workflows.md`](language_server_workflows.md).

## Grammar (BNF/EBNF)

This grammar is derived from the current lexer/parser implementation and mirrors the statement and expression split in `tiny_language_parser.py`.

## Lexer/token reference

The lexer lives in [`src/tiny_language_lexer.py`](../src/tiny_language_lexer.py). It recognizes keywords, identifiers (`NAME`), literals, and the following symbols/operators.

| Category | Tokens |
| --- | --- |
| Grouping/structure | `(` `)` `{` `}` `[` `]` `,` `;` `.` `:` `?` |
| Assignment | `=` |
| Arithmetic | `+` `-` `*` `/` `^` `%` |
| Comparison | `==` `!=` `<` `<=` `>` `>=` |
| Boolean | `&&` `||` `!` |
| Comments | `//` (line comment) |

Return type arrows are tokenized as `-` followed by `>` (there is no dedicated `->` token).

Literals:

- **Numbers:** digits with an optional fractional part (e.g., `42`, `3.14`).
- **Strings:** double-quoted with escapes for `\n`, `\t`, `\r`, `\"`, `\\` (unknown escapes are preserved).

```ebnf
program         ::= stmt* EOF ;

stmt            ::= "def" NAME_or_kw "=" expr ";"
                  | "print" "(" [expr ("," expr)*] ")" ";"
                  | "flush" "(" ")" ";"
                  | "if" "(" expr ")" block ["else" block]
                  | "while" "(" expr ")" block
                  | "switch" "(" expr ")" "{" switch_case* "}"
                  | "try" block "catch" ("(" NAME ")" | NAME) block
                  | "task" block
                  | "import" module_path ["as" NAME] ";"
                  | "namespace" qualified_name block
                  | ("async" "fn" | "fn") NAME param_list ["-" ">" type_annotation] block
                  | "return" expr ";"
                  | "type" NAME [ "=" ("product" | "sum") ] type_body
                  | "class" NAME [ ":" NAME ("," NAME)* ] class_body
                  | "operator" OP "(" NAME ":" NAME "," NAME ":" NAME ")" "-" ">" NAME block
                  | "{" destruct_names "}" "=" expr ";"
                  | NAME stmt_suffix
                  ;

stmt_suffix     ::= "." NAME_or_kw ("=" expr ";" | arg_list ";")
                  | "=" expr ";"
                  | arg_list ";"
                  ;

block           ::= "{" stmt* "}" ;

param_list      ::= "(" [param ("," param)*] ")" ;
param           ::= NAME [":" type_annotation] ;

type_annotation ::= NAME_or_kw ["[" type_annotation ("," type_annotation)* "]"] ["?"] ;

expr            ::= logic_or ;
logic_or        ::= logic_and (("or" | "||") logic_and)* ;
logic_and       ::= compare (("and" | "&&") compare)* ;
compare         ::= term ((">" | ">=" | "<" | "<=" | "==" | "!=") term)* ;
term            ::= factor (("+" | "-") factor)* ;
factor          ::= power (("*" | "/" | "%") power)* ;
power           ::= unary ["^" power] ;
unary           ::= "-" unary
                  | ("not" | "!") unary
                  | postfix ;

postfix         ::= primary ( "." NAME_or_kw [arg_list]? )* ;

primary         ::= "(" expr ")"
                  | "spawn" NAME_or_kw arg_list
                  | "await" expr
                  | "match" match_expr
                  | "new" "[" [expr ("," expr)*] "]"
                  | "new" NAME "{" class_init_fields "}"
                  | NUMBER
                  | STRING
                  | "true" | "false"
                  | "Null"
                  | NAME_or_kw primary_suffix
                  | obj_lit
                  ;

primary_suffix  ::= arg_list
                  | variant_ctor
                  | /* empty -> Var */
                  ;

arg_list        ::= "(" [expr ("," expr)*] ")" ;

obj_lit         ::= "{" obj_fields "}" ;
obj_fields      ::= [field_init ((","|";") field_init)*] ;
field_init      ::= field_name ":" expr ;

field_name      ::= NAME ["." NAME] ;

destruct_names  ::= NAME ("," NAME)* ;

match_expr      ::= expr "{" match_case* "}" ;
match_case      ::= "case" pattern (":" | "=>") expr ";" ;

switch_case     ::= "case" expr ":" block
                  | "default" ":" block
                  ;

pattern         ::= "_" 
                  | NAME pattern_bindings? ;

pattern_bindings::= "{" pattern_fields "}"
                  | "(" pattern_args ")"
                  ;

pattern_fields  ::= pattern_field ((","|";") pattern_field)* ;
pattern_field   ::= NAME [":" (NAME_or_kw | "_")] ;

pattern_args    ::= (NAME_or_kw | "_") ((","|";") (NAME_or_kw | "_"))* ;

variant_ctor    ::= "{" variant_init_fields "}" ;
variant_init_fields ::= [field_init ((","|";") field_init)*] ;
class_init_fields ::= [field_init ((","|";") field_init)*] ;

module_path     ::= ("."*) NAME ("." NAME)* ;
qualified_name  ::= NAME ("." NAME)* ;

class_body      ::= "{" class_member* "}" ;
class_member    ::= ("async" "fn" | "fn") NAME_or_kw param_list ["-" ">" type_annotation] block
                  | NAME ":" NAME ";" ;

type_body       ::= "{" type_variant_list "}" ;
type_variant_list ::= variant_def (";" variant_def)* ";"?
                   | field_def (";" field_def)* ";"? ;

variant_def     ::= NAME variant_fields ;
variant_fields  ::= ("{" variant_field_list "}" | "(" variant_field_list ")")? ;
variant_field_list ::= field_def ((","|";") field_def)* ;

field_def       ::= NAME ":" NAME_or_kw ;

NAME_or_kw      ::= NAME | KW ;
```

## Next steps (documentation tasks)

### Open tasks

_None_

### Closed tasks

- [x] Add a dedicated grammar test suite that parses the EBNF samples above and ensures parser parity with `tiny_language_parser.py`.

- [x] Document reserved keywords vs. identifiers with examples for `NAME_or_kw` usage (e.g., method names that are keywords).

- [x] Expand the grammar section with a concise lexer/token table (operators, symbols, literal forms) and link to the lexer source.

- [x] Document comment syntax and string escape sequences in the lexer/token reference.
