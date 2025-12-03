# Language server workflows

This note bundles a quickstart for the `TinyLanguageServer` helper that lives in [`src/language_server.py`](../src/language_server.py). The goal is to give a lightweight, JSON-style interface for experiments with hover, completion, and diagnostics without implementing JSON-RPC wiring.

## Quickstart: CLI demos

Use the small helper CLI to run the same operations from a terminal. Either provide inline source via `--source` or point to a `.tiny` file with `--file`.

```bash
# List completions for the prefix "g" in an inline program
PYTHONPATH=src python src/language_server_cli.py --source "fn greet() { return 1; }" completions --prefix g

# Inspect hover info for a symbol inside a file
PYTHONPATH=src python src/language_server_cli.py --file src_tiny/class_demo.tiny hover --symbol Greeter

# Capture diagnostics as JSON
PYTHONPATH=src python src/language_server_cli.py --source "fn greet() -> string { return \"hi\"; }\ngreet();" diagnostics
```

The subcommands mirror common LSP request/response pairs:

- `completions --prefix <text>` filters all known symbols, keywords, and built-ins by the provided prefix.
- `hover --symbol <name>` locates a symbol and emits its name, a generic detail string, and a zero-based `(line, column)` position tuple.
- `diagnostics` runs the built-in lints and surfaces the first encountered error with a four-tuple range `(start_line, start_col, end_line, end_col)`.

Outputs are JSON so they can be piped into tools or inspected visually. Example diagnostics output:

```json
[
  {
    "message": "[E011] function greet discards return value; assign or ignore explicitly",
    "code": "E011",
    "range": [
      1,
      0,
      1,
      1
    ]
  }
]
```

## Supported methods and example payloads

Each subcommand is a thin wrapper around an internal request/response pair and can be copy/pasted into JSON-RPC glue code. Positions are zero-based and include namespace-qualified symbols (`Math.inc`, `Tools.double`, …). Currently exposed methods:

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
    # => {"symbol": "Greeter", "detail": "TinyLanguage symbol", "position": [0, 6]}
    ```
- **Diagnostics** (`textDocument/diagnostic` equivalent)
  - Request payload:
    ```json
    {}
    ```
  - Response payload:
    ```json
    [{ "message": "[E011] ...", "code": "E011", "range": [2, 1, 2, 2] }]
    ```
  - CLI demo for an unused return value:
    ```bash
    PYTHONPATH=src python src/language_server_cli.py --source $'fn greet() -> string { return "hi"; }\ngreet();' diagnostics
    # => [{"message": "[E011] function greet discards return value; assign or ignore explicitly", "code": "E011", "range": [1, 0, 1, 1]}]
    ```

Not implemented yet: definition jumps, formatting, or workspace symbol searches. Those can be layered on later by extending the helper functions in [`src/language_server.py`](../src/language_server.py).

## "So testest du es" quick demos

The example programs referenced in the README’s “Syntax and Features” section can be exercised via the same CLI to validate hover/completion/diagnostics end-to-end. Each snippet includes a short expectation so results can be compared quickly:

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
- `Diagnostic`: `{ message: str, code: str, range: (start_line, start_col, end_line, end_col) }`

Instantiate the server with a source string and call the helpers directly:

```python
from language_server import TinyLanguageServer

server = TinyLanguageServer("fn add(x, y) { return x + y; }\nadd(1, 2);")
print(server.completions("a"))      # CompletionItem objects for add, async keywords, stdlib, ...
print(server.hover("add"))          # HoverResult with 0-based line/column information
print(server.diagnostics())          # E011 diagnostic because the call result is unused
```

## Request/response patterns

The API intentionally mirrors common LSP interactions so it can be wired into JSON-RPC with minimal glue:

- **Completions**: pass a prefix string, receive a sorted list of `CompletionItem` entries. Ideal for REPLs or editor completion popups.
- **Hover**: pass a symbol name, receive a `HoverResult` with the recorded position; `None` if the symbol cannot be resolved. Namespaces are indexed, so qualified symbols like `Math.add` work as well.
- **Diagnostics**: returns a list of `Diagnostic` objects generated by the built-in lints. The ranges are 0-based and align with the lexer’s `SourcePos` data. Each result includes a machine-readable `code` such as `E009` or `E011` for downstream filtering.

## Tips for integration

- Keep `PYTHONPATH=src` when invoking helpers from the repository root so Python can locate `language_server.py`.
- Pair diagnostics with the formatter: running `python tiny_language.py --format your_file.tiny` before gathering diagnostics often removes avoidable lint errors (e.g., import order).
- When embedding this helper into editors, treat the JSON emitted by `language_server_cli.py` as a transport-neutral representation; mapping it to JSON-RPC messages is straightforward because the field names already mirror LSP concepts.
- For regression tests or scripted experiments, prefer `--source` so the entire interaction (request plus expected response) lives in version control without separate fixtures.
