# Self-hosting regression matrix

This matrix tracks the last-verified parity checkpoints between the Python
implementation and the self-hosted Tiny modules. Update it whenever parity
snapshots or regression checks are refreshed so reviewers can quickly see which
areas are current and which still deviate.

## How to update

1. Run the relevant parity tests or manual checks.
2. Update the **Last verified** fields with the Tiny commit hash and Python
   interpreter version used.
3. Capture any behavioral or diagnostic differences in **Known deviations** and
   link to follow-up tasks.

## Matrix

| Area | Python implementation | Tiny self-hosted module | Last verified (Tiny commit) | Last verified (Python) | Known deviations / notes |
| --- | --- | --- | --- | --- | --- |
| Lexer | `src/tiny_language_lexer.py` | `src_tiny/tiny_language_lexer.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| Parser | `src/tiny_language_parser.py` | `src_tiny/tiny_language_parser.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| AST | `src/tiny_language_ast.py` | `src_tiny/tiny_language_ast.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| Runtime | `src/tiny_language_runtime.py` | `src_tiny/tiny_language_runtime.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| Eval | `src/tiny_language_eval.py` | `src_tiny/tiny_language_eval.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| Linter | `src/tiny_language_linter.py` | `src_tiny/tiny_language_linter.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| Formatter | `src/formatter.py` | `src_tiny/formatter.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| Transpilers | `src/tiny_language_transpilers.py` | `src_tiny/tiny_language_transpilers.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| CLI | `src/tiny_language_cli.py` | `src_tiny/tiny_language_cli.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| LSP server | `src/language_server.py` | `src_tiny/language_server.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
| Debug adapter | `vscode-extension/python/tiny_debug_adapter.py` | `src_tiny/tiny_debug_adapter.tiny` | `1f6856b` | `Python 3.10.19` | _None recorded._ |
