# TinyLanguage formatter rules

This document captures the stable rules enforced by the TinyLanguage formatter
(`src/formatter.py`). The formatter is intentionally minimal: it keeps comments
and syntax intact while normalizing whitespace so diffs stay predictable.

## Core layout rules

### Spacing

- Binary operators, keywords, identifiers, and commas are separated with a
  single space when adjacent tokens would otherwise run together.
- Parentheses and brackets stay tight to their inner content (`fn call(x)` not
  `fn call( x )`).
- Member access via `.` never inserts spaces (`object.field`).
- A space is inserted after commas and colons.

### Semicolons

- Statement terminators (`;`) stay attached to the preceding token.
- Each semicolon ends the current line; the formatter starts the next statement
  on a new line.

### Braces and indentation

- Opening braces (`{`) stay on the same line as the preceding token and start a
  new line after the brace.
- Closing braces (`}`) always appear on their own line at the current indent
  level.
- Indentation uses 4 spaces per nesting level.

### Imports

- Import statements are normalized to the canonical form:
  `import <path> [as <alias>];`
- The formatter keeps the original import order. Linting is responsible for
  enforcing placement or grouping rules.

### Comments

- Line comments (`//`) are preserved verbatim.
- A comment appearing after code is moved to its own line in the current block
  indentation.

## Example

**Before**

```tiny
import stdlib.io   as io
fn greet ( name )  { // greet someone
return  "hi"+name;
}
```

**After**

```tiny
import stdlib.io as io;
fn greet(name) {
    // greet someone
    return "hi" + name;
}
```

## Related tooling

- Run the formatter via `python src/tiny_language.py --format <file>`.
- Run formatter checks + lints via `python tools/check_format_lint.py`.
- See `docs/developer_tooling_workflows.md` for workflow context.
