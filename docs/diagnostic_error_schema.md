# Diagnostic error schema

This document defines the shared diagnostic payload emitted by the interpreter
and tooling so editors, CLI helpers, and test harnesses can consume a single
shape regardless of where an error originates.

## Goals

- Provide a stable machine-readable structure for parser, linter, and runtime
  errors.
- Preserve the human-readable formatted message used in CLI output.
- Make it easy to extend with optional metadata (hints, stacks, file URIs).

## Schema overview

Diagnostics are JSON objects with the following fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string | ✅ | Human-readable message. May include the formatted context block. |
| `code` | string | ✅ | Stable diagnostic code (e.g., `E010`). |
| `severity` | string | ✅ | One of `error`, `warning`, `info`, `hint`. |
| `phase` | string | ✅ | Execution phase: `parse`, `lint`, `runtime`, or `native`. |
| `range` | array[int, int, int, int] | ✅ | 1-based `[start_line, start_col, end_line, end_col]`, end-exclusive. |
| `origin` | string | ✅ | Producer identifier (e.g., `interpreter`, `language_server`). |
| `hint` | string | ❌ | Optional hint for remediation. |
| `uri` | string | ❌ | Optional file URI or path when available. |
| `stack` | array[object] | ❌ | Optional stack frames for runtime errors. |

`stack` entries use:

| Field | Type | Description |
| --- | --- | --- |
| `name` | string | Frame symbol name. |
| `namespace` | string/null | Module or namespace qualifier. |
| `line` | int | 1-based line for the frame. |
| `column` | int | 1-based column for the frame. |

## Examples

### Parser error

```json
{
  "message": "[E001] unexpected token ')' (line 1, col 10)\n> 1 | fn greet() ) { }\n  |          ^",
  "code": "E001",
  "severity": "error",
  "phase": "parse",
  "range": [1, 10, 1, 11],
  "origin": "language_server"
}
```

### Lint error with hint

```json
{
  "message": "[E010] not all paths in function describe return a value for annotated type number (line 1, col 1)",
  "code": "E010",
  "severity": "error",
  "phase": "lint",
  "range": [1, 1, 1, 2],
  "origin": "language_server",
  "hint": "Add return statements for every branch or provide a default return to satisfy the annotation."
}
```

### Runtime error with stack

```json
{
  "message": "[E009] type mismatch for assignment (line 4, col 5)",
  "code": "E009",
  "severity": "error",
  "phase": "runtime",
  "range": [4, 5, 4, 6],
  "origin": "interpreter",
  "stack": [
    { "name": "main", "namespace": null, "line": 1, "column": 1 },
    { "name": "update", "namespace": "Math", "line": 4, "column": 5 }
  ]
}
```

## Mapping from TinyLanguage errors

- `code`, `hint`, `span`, and `pos` come directly from `TinyLangError`.
- `range` is derived from `span` when available, otherwise from `pos`.
- `phase` is determined by the caller (`parse` for parser errors, `lint` for
  linter, `runtime` for interpreter/runtime checks, `native` for native backend).
- `origin` identifies which tool produced the payload (interpreter, language
  server CLI, etc.).

The language server CLI exposes this schema in `diagnostics` responses, and
other tooling should emit the same fields to stay compatible.
