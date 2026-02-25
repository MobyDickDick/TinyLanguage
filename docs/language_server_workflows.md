# Language server workflows

This note bundles a quickstart for the `TinyLanguageServer` helper that lives in [`src/language_server.py`](../src/language_server.py). The goal is to give a lightweight, JSON-style interface for experiments with hover, completion, diagnostics, and basic LSP-style edits without implementing JSON-RPC wiring.


## End-to-end workflow: multi-file formatting via project mode

Use `--project` when you want language-server actions to operate on all
`.tiny` files in a workspace-like directory. This is useful for editor hooks
that request code actions and then apply returned edits.

```bash
# 1) Ask for code actions on the full project.
PYTHONPATH=src python src/language_server_cli.py --project path/to/project code-actions

# 2) Request the fully formatted source payload for the same project.
PYTHONPATH=src python src/language_server_cli.py --project path/to/project format
```

Expected behavior: `code-actions` includes exactly one `source.format` action,
its first edit range spans the complete aggregated project source, and that
edit's `newText` equals the `format` command's `source` string.

Regression coverage for this workflow lives in
`tests/detailtests/test_language_server_cli.py`
(`test_cli_project_formatting_hook_matches_format_output`).

## Quickstart: CLI demos

Use the small helper CLI to run the same operations from a terminal. Either provide inline source via `--source` or point to a `.tiny` file with `--file`.

```bash
# List completions for the prefix "g" in an inline program
PYTHONPATH=src python src/language_server_cli.py --source "fn greet() { return 1; }" completions --prefix g

# Inspect hover info for a symbol inside a file
PYTHONPATH=src python src/language_server_cli.py --file src_tiny/class_demo.tiny hover --symbol Greeter

# Capture diagnostics as JSON
PYTHONPATH=src python src/language_server_cli.py --source "fn describe(x: number) -> number { if (x > 0) { return x; } }" diagnostics

# Format source and emit JSON payloads
PYTHONPATH=src python src/language_server_cli.py --source "fn greet(){return 1;}" format

# Ask for formatter edits (text edits) instead of the full formatted source
PYTHONPATH=src python src/language_server_cli.py --source "fn greet(){return 1;}" format-edits

# Find references to a symbol
PYTHONPATH=src python src/language_server_cli.py --source $'fn add(x, y) { return x + y; }\nadd(1, 2);' references --symbol add

# Request rename edits for a symbol
PYTHONPATH=src python src/language_server_cli.py --source $'fn add(x, y) { return x + y; }\nadd(1, 2);' rename --symbol add --new-name sum

# List code actions (formatting is returned as a source-level action)
PYTHONPATH=src python src/language_server_cli.py --source "fn greet(){return 1;}" code-actions
```

The subcommands mirror common LSP request/response pairs:

- `completions --prefix <text>` filters all known symbols, keywords, and built-ins by the provided prefix.
- `hover --symbol <name>` locates a symbol and emits its name, a generic detail string, and a 1-based `(line, column)` position tuple.
- `definition --symbol <name>` resolves a symbol to its definition location (optionally disambiguated with `--line`/`--col`).
- `diagnostics` runs the built-in lints and surfaces the first encountered error with a four-tuple range `(start_line, start_col, end_line, end_col)` (1-based, end-exclusive). Parse errors are reported in the same payload shape so tooling stays stable when source is incomplete.
- `format` formats the source using the TinyLanguage formatter and returns the formatted source string.
- `format-edits` formats the source and returns text edits that replace the document contents.
- `references --symbol <name>` returns the 1-based ranges for each reference to a symbol (including its definition unless excluded).
- `rename --symbol <name> --new-name <name>` returns text edits that rename all references to the symbol.
- `code-actions` returns code action payloads, currently exposing a format document action when formatting changes are available.

Outputs are JSON so they can be piped into tools or inspected visually. Example diagnostics output:

```json
[
  {
    "message": "[E010] not all paths in function describe return a value for annotated type number",
    "code": "E010",
    "range": [
      1,
      1,
      1,
      2
    ],
    "severity": "error",
    "phase": "lint",
    "source": "linter",
    "origin": "language_server",
    "hint": "Add return statements for every branch or provide a default return to satisfy the annotation."
  }
]
```

The diagnostics payload follows the shared schema in
[`docs/diagnostic_error_schema.md`](diagnostic_error_schema.md).

## LSP feature matrix

This matrix summarizes which LSP-style capabilities are currently exposed by
the TinyLanguage language server helper and its CLI wrapper.

| Capability | LSP method | CLI subcommand | Status | Notes |
| --- | --- | --- | --- | --- |
| Completions | `textDocument/completion` | `completions` | ✅ Supported | Prefix-based matches across user symbols, keywords, and built-ins. |
| Hover | `textDocument/hover` | `hover` | ✅ Supported | Returns symbol name, detail, and 1-based position. |
| Definition | `textDocument/definition` | `definition` | ✅ Supported | Resolves symbols to their definition locations. |
| References | `textDocument/references` | `references` | ✅ Supported | Lexer-based reference ranges (1-based, end-exclusive). |
| Rename | `textDocument/rename` | `rename` | ✅ Supported | Returns text edits to rename all references. |
| Code actions | `textDocument/codeAction` | `code-actions` | ✅ Supported | Currently includes format-document action. |
| Formatting | `textDocument/formatting` | `format` / `format-edits` | ✅ Supported | Full-document formatting or text edits. |
| Diagnostics | `textDocument/diagnostic` | `diagnostics` | ✅ Supported | Lints + parse errors emitted as structured ranges. |
| Workspace symbols | `workspace/symbol` | `workspace-symbols` | ✅ Supported | Substring search across indexed symbols. |

## Editor-client compatibility matrix

The table below translates the core TinyLanguage helper capabilities into
editor-client expectations. It is intended as a practical reference for
integrators wiring the CLI helper (`src/language_server_cli.py`) into a
JSON-RPC/LSP bridge.

| Editor client | Hover | Diagnostics | Formatting | Code actions | Notes / caveats |
| --- | --- | --- | --- | --- | --- |
| VS Code (custom extension or task runner bridge) | ✅ Supported (`textDocument/hover`) | ✅ Supported (`textDocument/diagnostic`) | ✅ Supported (`textDocument/formatting`) | ✅ Supported (`textDocument/codeAction`) | Best fit for the current workflow: the repository already ships extension assets under `vscode-extension/`; bridge adapters should normalize 1-based TinyLanguage ranges to VS Code/LSP expectations consistently. |
| Neovim (built-in LSP client via wrapper) | ✅ Supported | ✅ Supported | ✅ Supported | ✅ Supported | Works when TinyLanguage CLI is wrapped by an LSP transport shim. Ensure response payloads are mapped into Neovim handler tables (especially for `codeAction` edits and diagnostic severity fields). |
| Generic LSP clients (Helix, Sublime LSP, Emacs eglot/lsp-mode, etc.) | ✅ Supported | ✅ Supported | ✅ Supported | ✅ Supported | Capability parity is available at the protocol level as long as the bridge exposes the methods listed in the feature matrix above. Clients that require strict schema validation may need adapter-side field normalization for optional metadata. |

### Capability caveats by method

- `hover`: returns symbol + detail + position; adapters should preserve symbol
  names exactly (including namespace-qualified names such as `Math.inc`).
- `diagnostics`: payload includes TinyLanguage-specific metadata (`phase`,
  `origin`, optional `hint`) in addition to standard code/range/severity
  fields; clients can surface extra metadata as diagnostic tags or hover text.
- `formatting`: supports either full-document output (`format`) or edit lists
  (`format-edits`); bridges should pick one strategy per client to avoid
  duplicate edits.
- `code actions`: currently includes formatting-focused source actions; adapter
  implementations should still advertise `codeActionProvider` so future
  non-format quick fixes can be adopted without client-side config changes.

## Supported methods and example payloads

Each subcommand is a thin wrapper around an internal request/response pair and can be copy/pasted into JSON-RPC glue code. Positions are 1-based and include namespace-qualified symbols (`Math.inc`, `Tools.double`, …). Currently exposed methods (keep this table in sync with the helpers in `src/language_server.py`):

| Method (LSP analog) | CLI subcommand | Request (JSON) | Response (JSON) | Notes |
| --- | --- | --- | --- | --- |
| `textDocument/completion` | `completions` | `{ "prefix": "gr" }` | `[{ "label": "greet", "kind": "identifier" }]` | Prefix-based lookup across user symbols, keywords, and stdlib names. |
| `textDocument/hover` | `hover` | `{ "symbol": "Greeter" }` | `{ "symbol": "Greeter", "detail": "TinyLanguage symbol", "position": [1, 7] }` | Returns the recorded 1-based position for the symbol. |
| `textDocument/definition` | `definition` | `{ "symbol": "greet" }` | `{ "symbol": "greet", "position": [1, 4] }` | Resolves a symbol to its definition position. |
| `workspace/symbol` | `workspace-symbols` | `{ "query": "gre" }` | `[{ "name": "greet", "kind": "function", "detail": "fn greet()", "position": [1, 4], "container": "" }]` | Substring search across indexed symbols. |
| `textDocument/diagnostic` | `diagnostics` | `{}` | `[{ "message": "[E010] ...", "code": "E010", "range": [1, 1, 1, 2], "severity": "error", "phase": "lint", "source": "linter", "origin": "language_server" }]` | Emits lint findings with machine-readable ranges. |
| `textDocument/formatting` | `format` | `{}` | `{ "source": "fn greet() { return 1; }\n" }` | Formats the input using the TinyLanguage formatter. |
| `textDocument/formatting` | `format-edits` | `{}` | `[{ "range": [1, 1, 1, 18], "newText": "fn greet() { return 1; }\n" }]` | Formatter edits as LSP-style text edits. |
| `textDocument/references` | `references` | `{ "symbol": "greet" }` | `[{ "range": [1, 4, 1, 9] }, { "range": [2, 1, 2, 6] }]` | Reference ranges for the symbol (1-based, end-exclusive). |
| `textDocument/rename` | `rename` | `{ "symbol": "greet", "newName": "hello" }` | `[{ "range": [1, 4, 1, 9], "newText": "hello" }]` | Rename edits that update each reference. |
| `textDocument/codeAction` | `code-actions` | `{}` | `[{ "title": "Format document", "kind": "source.format", "edits": [{ "range": [1, 1, 1, 18], "newText": "fn greet() { return 1; }\n" }], "diagnostics": [] }]` | Provides formatting as a source-level code action. |

**Request templates at a glance** (copy/paste into JSON-RPC envelopes):

- Completion: `{ "method": "textDocument/completion", "params": { "prefix": "gr" } }`
- Hover: `{ "method": "textDocument/hover", "params": { "symbol": "Greeter" } }`
- Definition: `{ "method": "textDocument/definition", "params": { "symbol": "greet" } }`
- Workspace symbols: `{ "method": "workspace/symbol", "params": { "query": "gre" } }`
- Diagnostics: `{ "method": "textDocument/diagnostic", "params": {} }`
- References: `{ "method": "textDocument/references", "params": { "symbol": "greet" } }`
- Rename: `{ "method": "textDocument/rename", "params": { "symbol": "greet", "newName": "hello" } }`
- Code actions: `{ "method": "textDocument/codeAction", "params": {} }`

- **Completions** (`textDocument/completion` equivalent)
  - Request payload:
  
    ```json
    { "prefix": "gr" }
    ```
  
  - Response payload:
  
    ```json
    [{ "label": "greet", "kind": "identifier" }, { "label": "greeting", "kind": "keyword" }]
    ```
  
  - CLI demo for inline source plus example output:
  
    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source $'fn greet() { return 1; }\ngreet();' completions --prefix gr
    # => [{"label": "greet", "kind": "identifier"}, {"label": "greeting", "kind": "keyword"}, ...]
    ```

- **Hover** (`textDocument/hover` equivalent)
  - Request payload:

    ```json
    { "symbol": "Greeter" }
    ```

  - Response payload:

    ```json
    { "symbol": "Greeter", "detail": "TinyLanguage symbol", "position": [10, 1] }
    ```

  - CLI demo for a file on disk with a resolved position:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --file src_tiny/class_demo.tiny hover --symbol Greeter
    # => {"symbol": "Greeter", "detail": "TinyLanguage symbol", "position": [1, 7]}
    ```

- **Definition** (`textDocument/definition` equivalent)
  - Request payload:

    ```json
    { "symbol": "greet" }
    ```

  - Response payload:

    ```json
    { "symbol": "greet", "position": [1, 4] }
    ```

  - CLI demo for a definition lookup:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source "fn greet() { return 1; }\ngreet();" definition --symbol greet
    # => {"symbol": "greet", "position": [1, 4]}
    ```

- **Diagnostics** (`textDocument/diagnostic` equivalent)
  - Request payload:

    ```json
    {}
    ```

  - Response payload:

    ```json
    [{ "message": "[E010] ...", "code": "E010", "range": [2, 1, 2, 2] }]
    ```

  - CLI demo for a missing return in an annotated function:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source $'fn describe(x: number) -> number { if (x > 0) { return x; } }' diagnostics
    # => [{"message": "[E010] not all paths in function describe return a value for annotated type number", "code": "E010", "range": [1, 0, 1, 1]}]
    ```

- **Workspace symbols** (`workspace/symbol` equivalent)
  - Request payload:

    ```json
    { "query": "Gre" }
    ```

  - Response payload:

    ```json
    [{ "name": "Greeter.hello", "kind": "method", "detail": "method hello(self, name)", "position": [1, 2], "container": "Greeter" }]
    ```

  - CLI demo for symbol search:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --file src_tiny/class_demo.tiny workspace-symbols --query Gre
    # => [{"name": "Greeter", "kind": "class", "detail": "", "position": [1, 1], "container": ""}, ...]
    ```

- **Formatting** (`textDocument/formatting` equivalent)
  - Request payload:

    ```json
    {}
    ```

  - Response payload:

    ```json
    { "source": "fn greet() { return 1; }\n" }
    ```

  - CLI demo for formatting:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source "fn greet(){return 1;}" format
    # => {"source": "fn greet() { return 1; }\n"}
    ```

- **Formatting edits** (`textDocument/formatting` equivalent)
  - Request payload:

    ```json
    {}
    ```

  - Response payload:

    ```json
    [{ "range": [1, 1, 1, 18], "newText": "fn greet() { return 1; }\n" }]
    ```

  - CLI demo for formatting edits:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source "fn greet(){return 1;}" format-edits
    # => [{"range": [1, 1, 1, 18], "newText": "fn greet() { return 1; }\n"}]
    ```

- **References** (`textDocument/references` equivalent)
  - Request payload:

    ```json
    { "symbol": "add" }
    ```

  - Response payload:

    ```json
    [{ "range": [1, 4, 1, 7] }, { "range": [2, 1, 2, 4] }]
    ```

  - CLI demo for references:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source $'fn add(x, y) { return x + y; }\nadd(1, 2);' references --symbol add
    # => [{"range": [1, 4, 1, 7]}, {"range": [2, 1, 2, 4]}]
    ```

- **Rename** (`textDocument/rename` equivalent)
  - Request payload:

    ```json
    { "symbol": "add", "newName": "sum" }
    ```

  - Response payload:

    ```json
    [{ "range": [1, 4, 1, 7], "newText": "sum" }, { "range": [2, 1, 2, 4], "newText": "sum" }]
    ```

  - CLI demo for rename edits:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source $'fn add(x, y) { return x + y; }\nadd(1, 2);' rename --symbol add --new-name sum
    # => [{"range": [1, 4, 1, 7], "newText": "sum"}, {"range": [2, 1, 2, 4], "newText": "sum"}]
    ```

- **Code actions** (`textDocument/codeAction` equivalent)
  - Request payload:

    ```json
    {}
    ```

  - Response payload:

    ```json
    [{ "title": "Format document", "kind": "source.format", "edits": [{ "range": [1, 1, 1, 18], "newText": "fn greet() { return 1; }\n" }], "diagnostics": [] }]
    ```

  - CLI demo for code actions:

    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source "fn greet(){return 1;}" code-actions
    # => [{"title": "Format document", "kind": "source.format", "edits": [{"range": [1, 1, 1, 18], "newText": "fn greet() { return 1; }\n"}], "diagnostics": []}]
    ```

### Multi-file formatting-hook acceptance flow (`--project`)

For project-wide acceptance checks, the CLI can concatenate all `*.tiny` files
under a folder and surface formatting through both `format` and
`code-actions` responses. The key invariant is:

- The `source.format` code action contains exactly one full-document edit.
- That edit's `newText` is byte-identical to the `format` command's returned
  `source` payload for the same `--project` input.

Minimal shell walkthrough:

```bash
tmp_dir="$(mktemp -d)"
cat >"$tmp_dir/math.tiny" <<'EOF'
fn add(x, y) { return x + y; }
EOF
cat >"$tmp_dir/main.tiny" <<'EOF'
fn main() { return add(1, 2); }
EOF
cat >"$tmp_dir/formatting.tiny" <<'EOF'
fn greet(){return 1;}
EOF

PYTHONPATH=src python src/language_server_cli.py --project "$tmp_dir" format
PYTHONPATH=src python src/language_server_cli.py --project "$tmp_dir" code-actions
```

The detail test `test_cli_project_formatting_hook_matches_format_output` in
`tests/detailtests/test_language_server_cli.py` automates this exact flow and
asserts the request/response contract for formatting hooks.

## "So testest du es" quick demos

The example programs referenced in the README’s “Syntax and Features” section can be exercised via the same CLI to validate hover/completion/diagnostics end-to-end. Each snippet includes a short expectation so results can be compared quickly:

- **Inline smoke test for the README quickstart snippet** (variables, functions, namespaces):

  ```bash
  # Copy the snippet from README.md → Syntax and Features → Mini tutorial
  README_SNIPPET=$'def a = 7 + 5 * 2;\nprint(a);\nfn add(x, y) { return x + y; }\ndefine sum = add(a, 3);\nprint(sum);\nnamespace Math { fn inc(x) { return add(x, 1); } }\nprint(Math.inc(4));'
  PYTHONPATH=src python src/language_server_cli.py --source "$README_SNIPPET" completions --prefix Ma
  # => [{"label": "Math", "kind": "identifier"}, {"label": "Math.inc", "kind": "identifier"}, ...]
  PYTHONPATH=src python src/language_server_cli.py --source "$README_SNIPPET" hover --symbol inc
  # => {"symbol": "inc", "detail": "TinyLanguage symbol", "position": [5, 4]}
  PYTHONPATH=src python src/language_server_cli.py --source "$README_SNIPPET" diagnostics
  # => [] (the tutorial snippet should lint clean)
  ```

- Hover over class names or methods in `src_tiny/class_demo.tiny`:

  ```bash
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/class_demo.tiny hover --symbol greeting
  # => {"symbol": "greeting", "detail": "TinyLanguage symbol", "position": [4, 7]}
  ```

- List completions for the namespace utilities in `src_tiny/namespace_demo.tiny`:

  ```bash
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/namespace_demo.tiny completions --prefix To
  # => [{"label": "Tools", "kind": "identifier"}, {"label": "Tools.double", "kind": "identifier"}, ...]
  ```

- Capture diagnostics for the standard library walkthrough in `src_tiny/stdlib_io_random_demo.tiny` to ensure lints stay quiet:

  ```bash
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/stdlib_io_random_demo.tiny diagnostics
  # => [] (no diagnostics expected when examples stay lint-clean)
  ```

- Inspect tagged-union coverage in `src_tiny/match_demo.tiny` via hover and completions to ensure ADT symbols are indexed:

  ```bash
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/match_demo.tiny hover --symbol Rectangle
  # => {"symbol": "Rectangle", "detail": "TinyLanguage symbol", "position": [5, 2]}
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/match_demo.tiny completions --prefix Cir
  # => [{"label": "Circle", "kind": "identifier"}, {"label": "Circle.radius", "kind": "identifier"}, ...]
  ```

- Validate operator overloading docs with completions and diagnostics from `src_tiny/operator_overloading_demo.tiny`:

  ```bash
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/operator_overloading_demo.tiny completions --prefix oper
  # => [{"label": "operator +", "kind": "identifier"}, {"label": "operator ==", "kind": "identifier"}, ...]
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/operator_overloading_demo.tiny diagnostics
  # => [] (the demo should lint clean)
  ```

- Probe concurrency helpers from `src_tiny/concurrency_demo.tiny` to confirm that spawned functions are indexed:

  ```bash
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/concurrency_demo.tiny completions --prefix spawn
  # => [{"label": "spawn", "kind": "keyword"}, {"label": "spawn label", "kind": "identifier"}, ...]
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/concurrency_demo.tiny diagnostics
  # => [] (tasks and joins should not emit lints)
  ```

- Walk through heap usage in `src_tiny/heap_pointer_demo.tiny` via diagnostics to catch common pointer mistakes:

  ```bash
  PYTHONPATH=src python src/language_server_cli.py --file src_tiny/heap_pointer_demo.tiny diagnostics
  # => [] (the curated example should stay lint-clean; modify it to provoke heap errors during experiments)
  ```

## API surface

The core dataclasses mirror the high-level Language Server Protocol structure:

- `HoverResult`: `{ symbol: str, detail: str, position: (line, column) }`
- `CompletionItem`: `{ label: str, kind: "identifier" }`
- `Diagnostic`: `{ message: str, code: str, range: (start_line, start_col, end_line, end_col) }` (1-based)
  where `range` reflects the full source span if the parser/linter provided one.

Instantiate the server with a source string and call the helpers directly:

```python
from language_server import TinyLanguageServer

server = TinyLanguageServer("fn describe(x: number) -> number { if (x > 0) { return x; } }")
print(server.completions("d"))      # CompletionItem objects for describe, def, ...
print(server.hover("describe"))     # HoverResult with 0-based line/column information
print(server.diagnostics())          # E010 diagnostic because not all paths return a value
```

## Request/response patterns

The API intentionally mirrors common LSP interactions so it can be wired into JSON-RPC with minimal glue:

- **Completions**: pass a prefix string, receive a sorted list of `CompletionItem` entries. Ideal for REPLs or editor completion popups.
- **Hover**: pass a symbol name, receive a `HoverResult` with the recorded position; `None` if the symbol cannot be resolved. Namespaces are indexed, so qualified symbols like `Math.add` work as well.
- **Diagnostics**: returns a list of `Diagnostic` objects generated by the built-in lints. The ranges are 1-based and underline the full span when available (for example, the entire function body that violates a return rule). Each result includes a machine-readable `code` such as `E009` or `E010` for downstream filtering.

## Tips for integration

- Keep `PYTHONPATH=src` when invoking helpers from the repository root so Python can locate `language_server.py`.
- Pair diagnostics with the formatter: running `python src/tiny_language.py --format your_file.tiny` before gathering diagnostics often removes avoidable lint errors (e.g., import order).
- When embedding this helper into editors, treat the JSON emitted by `language_server_cli.py` as a transport-neutral representation; mapping it to JSON-RPC messages is straightforward because the field names already mirror LSP concepts.
- For regression tests or scripted experiments, prefer `--source` so the entire interaction (request plus expected response) lives in version control without separate fixtures.
