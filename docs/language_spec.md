# TinyLanguage: Language Spec (Quick Reference + Semantics)

This document summarizes the most important TinyLanguage constructs.
It is intended as a *practical* reference: syntax, runtime behavior, and
common pitfalls, without requiring readers to inspect the interpreter code.

If you are looking for “how to run demos”, see:
- `docs/tutorial.md`
- `docs/demo_run_commands.md`

---

## Table of contents

- [Lexical elements](#lexical-elements)
- [Values and types](#values-and-types)
- [Bindings and scope](#bindings-and-scope)
- [Expressions and operators](#expressions-and-operators)
- [Statements and control flow](#statements-and-control-flow)
- [Functions](#functions)
- [Copy-on-call (defensive argument copying)](#copy-on-call-defensive-argument-copying)
- [Algebraic data types and pattern matching](#algebraic-data-types-and-pattern-matching)
- [Classes and operator overloading](#classes-and-operator-overloading)
- [Modules and namespaces](#modules-and-namespaces)
- [Concurrency and async API](#concurrency-and-async-api)
- [Errors, diagnostics, and linting](#errors-diagnostics-and-linting)
- [Running and tools](#running-and-tools)
- [Grammar (EBNF)](#grammar-ebnf)
- [Lexer/token reference](#lexertoken-reference)
- [Maintainer notes (documentation tasks)](#maintainer-notes-documentation-tasks)

---

## Lexical elements

### Comments

- `//` starts a line comment until end-of-line.
- Block comments are not a distinct lexical feature (no `/* ... */`).

### Statement terminators (semicolons)

- Every statement ends with `;`.
- The formatter may insert missing semicolons in simple cases, but **source
  should include them explicitly** for correctness and clarity.

### Identifiers, keywords, and literals

#### Numbers
- Integers and decimals are supported: `1`, `3.14`, `0.5`
- Scientific notation is intentionally disallowed: `1.2e2` is a lexer/parser error.
- Division returns floating-point values.
- Overflow is trapped and reported as a runtime error.

#### Strings
- Double-quoted: `"hello"`
- Basic escapes are supported (at least `\n`, see full list in the token section).

#### Booleans
- `true`, `false`

#### Null
- TinyLanguage uses a null literal to represent absence of a value.
- In the current grammar/token set this is spelled `Null` (capital N).
  Some docs/snippets may say `null`; treat `Null` as the canonical spelling.

### Reserved keywords vs. identifiers

Keywords are reserved in declaration positions (e.g. `define if = 1;` is invalid),
but the grammar allows keywords in some identifier slots via `NAME_or_kw`.

`NAME_or_kw` is used in member access, method declarations, and type annotations,
so keywords can be used there without being treated as control flow.

**Keyword list (current):**
`define`, `print`, `flush`, `if`, `else`, `while`, `switch`, `case`, `default`,
`fn`, `return`, `import`, `namespace`, `as`,
`operator`, `new`, `type`, `class`,
`spawn`, `async`, `await`,
`true`, `false`, `Null`,
`try`, `catch`,
`match`,
`and`, `or`, `not`

Example (keyword as method name):

```tiny
class KeywordDemo {
    fn match(self) { return "ok"; } // method name uses a keyword
}

define demo = new KeywordDemo {};
print(demo.match()); // member access accepts NAME_or_kw
