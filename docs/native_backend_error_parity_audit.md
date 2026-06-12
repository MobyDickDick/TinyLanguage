# Native backend error-parity audit

**Audit date:** 2026-06-06

**Owner:** Runtime/Compiler

**Scope:** focused comparison of user-facing diagnostics emitted by the default
interpreter (`compile_and_run`) and the native VM (`run_with_native_backend`).

## Method

The audit executes the same source text through both public entry points and
compares the complete rendered diagnostic, including error code, message,
source span, source excerpt, and hint. The executable matrix lives in
`tests/detailtests/test_native_backend_error_parity.py`.

This is deliberately a focused gate rather than a claim that every runtime
failure is already covered. It selects representative paths that pass through
different layers of the implementation:

| Scenario | Layer exercised | Result |
| --- | --- | --- |
| Unknown variable | Runtime name lookup | Full rendered-message parity |
| Division by zero | Expression evaluation / VM arithmetic | Full rendered-message parity |
| Function argument-count mismatch | Shared frontend lint | Full rendered-message parity |
| Statically known heap bounds violation | Shared heap lint | Full rendered-message parity |
| `len` called with an unsized value | Built-in runtime dispatch | Full rendered-message parity |

Exception classes are not part of this audit gate. Some native paths use
`RuntimeError` while the interpreter uses `TinyLangError`, but their complete
user-facing text is identical in the passing cases. A future structured-error
parity project may align exception metadata separately.

## Completed bounded follow-up issues

### NBEP-001: native `len` built-in parity (completed 2026-06-12)

Native VM dispatch now handles strings, collections, and heap pointers. Valid
calls are compared with interpreter output for all three value categories, and
unsized values now emit the interpreter-compatible `E005` diagnostic, hint, and
call-site span through the exact-message parity matrix.

## Remaining bounded follow-up issues

### NBEP-002: inventory exception metadata parity separately

- **Observed delta:** passing message-parity cases can still differ between
  `TinyLangError` and `RuntimeError` at the Python API boundary.
- **Boundary:** inventory only error type, code, hint, position, and span fields
  for the scenarios in this audit. Do not change CLI-rendered text.
- **Acceptance:** publish the intended API contract and either align the native
  exceptions or document the type difference as supported behavior.

## Re-running the audit

Run:

```bash
pytest -q tests/detailtests/test_native_backend_error_parity.py
```

When adding a native opcode, built-in, or runtime diagnostic, add a case to the
exact-message matrix when both backends support the behavior. If parity cannot
be achieved in the same change, add a narrowly scoped issue above with an
identifier, boundary, and acceptance criteria.
