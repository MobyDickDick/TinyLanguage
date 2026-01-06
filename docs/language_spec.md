# TinyLanguage: Quick reference and semantics

This file summarizes the most important TinyLanguage constructs. It is intended for readers who want to look up syntax and runtime behavior quickly without diving into the interpreter code.

## Lexical elements

- **Comments:** `//` starts a comment to the end of the line. Block comments have no special syntax.
- **Semicolons:** Every statement ends with `;`. The formatter inserts missing semicolons in simple cases, but programs should include them explicitly.
- **Identifiers and literals:**
  - Numbers support integers and decimals (`1`, `3.14`, `0.5`). Scientific notation is intentionally disallowed (`1.2e2` fails).
  - Strings use double quotes and allow basic escapes like `\n`.
  - Booleans are `true` and `false`; `null` indicates the absence of a value.
- **Reserved keywords vs. identifiers:** Keywords are reserved in declaration positions (e.g., `def if = 1;` is invalid), but the grammar explicitly allows keywords in some identifier slots via `NAME_or_kw`. Use this when you need a keyword-named method or member:
  - Keywords today include: `def`, `print`, `if`, `else`, `while`, `switch`, `default`, `fn`, `import`, `return`, `operator`, `new`, `type`, `class`, `namespace`, `as`, `spawn`, `async`, `await`, `true`, `false`, `flush`, `and`, `or`, `not`, `Null`, `try`, `catch`, `match`, `case`.
  - `NAME_or_kw` appears in member access, method declarations, and type annotations, so keywords can be used there without being treated as control flow.

  ```tiny
  class KeywordDemo {
      fn match(self) { return "ok"; } // method name uses a keyword
  }

  def demo = new KeywordDemo {};
  print(demo.match()); // member access accepts NAME_or_kw
  ```

## Expressions and operators

- **Arithmetic:** `+`, `-`, `*`, `/`, and exponentiation `^` (the exponent must be an integer). Division returns floating-point values; overflow is trapped and reported as an error.
- **Comparisons:** `==`, `!=`, `<`, `>`, `<=`, `>=` work on numbers, strings, booleans, and user types with operator overloads.
- **Booleans:** Short-circuit logic with `&&` and `||`, negation via `!expr`.
- **Arrays and heap:** `new[1, 2, 3]` creates an array; `new(3)` reserves heap space with three slots. Access via `heap_get(ptr, idx)` and `heap_set(ptr, idx, value)`. `tag(ptr, "Label")` attaches a type tag, and `delete(ptr)` frees memory.
- **Struct literals:** `{ a: 1, b: 2 }` builds an anonymous struct; fields are read with dot notation (`obj.a`).

## Bindings and visibility

- **Definitions:** `def x = expr;` creates a new variable. Later assignments without `def` update existing bindings and must not silently change the type when annotations are present.
- **Scopes:** Functions, namespaces, and match arms introduce their own scopes. Imported modules are registered under their fully qualified name and can be reached via aliases.

## Control flow

- **`if`/`while`:** Standard control structures with parentheses around the condition. Conditions must yield booleans; all paths in typed functions must return a value.
- **`switch`:** Compares a target expression against each case expression using equality; the first match runs its block, otherwise the optional `default` block runs. Each case is isolated (no fallthrough).
- **`match`:** Exhaustive pattern matching for `type` variants and structs. Wildcards (`_`) and named fields (`case Circle { radius: r }`) are supported; missing cases raise an error.
- **Error handling:** `try { ... } catch(err) { ... }` catches runtime errors and allows alternative returns or logging.

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
      heap_set(buf, 0, 99);
  }

  def data = new(1);
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
| Arrow | `->` |
| Comments | `//` (line comment) |

Literals:

- **Numbers:** digits with an optional fractional part (e.g., `42`, `3.14`).
- **Strings:** double-quoted with escapes for `\n`, `\t`, `\r`, `\"`, `\\` (unknown escapes are preserved).

```ebnf
program         ::= stmt* EOF ;

stmt            ::= "def" NAME "=" expr ";"
                  | "print" "(" [expr ("," expr)*] ")" ";"
                  | "flush" "(" ")" ";"
                  | "if" "(" expr ")" block ["else" block]
                  | "while" "(" expr ")" block
                  | "switch" "(" expr ")" "{" switch_case* "}"
                  | "try" block "catch" ["(" NAME ")"] NAME? block
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

type_annotation ::= NAME_or_kw ["?"] ;

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
                  | "await" expr
                  | "match" match_expr
                  | NUMBER
                  | STRING
                  | "true" | "false"
                  | "Null"
                  | NAME_or_kw primary_suffix
                  | obj_lit
                  ;

primary_suffix  ::= arg_list
                  | ("new" "[" [expr ("," expr)*] "]")
                  | ("new" NAME "{" class_init_fields "}")
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
variant_init_fields ::= field_init ((","|";") field_init)* ;

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
