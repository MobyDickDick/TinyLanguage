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

Rendered-message parity and Python exception metadata are separate contracts.
The rendered-message gate remains strict for every scenario above. NBEP-002 now
also locks the currently supported metadata behavior at the public Python API
boundary; the inventory and rationale are documented below.

## Completed bounded follow-up issues

### NBEP-001: native `len` built-in parity (completed 2026-06-12)

Native VM dispatch now handles strings, collections, and heap pointers. Valid
calls are compared with interpreter output for all three value categories, and
unsized values now emit the interpreter-compatible `E005` diagnostic, hint, and
call-site span through the exact-message parity matrix.

### NBEP-002: exception metadata inventory (completed 2026-06-12)

The public Python API intentionally preserves the existing distinction between
frontend/structured failures and native VM runtime failures. The executable
contract in `tests/detailtests/test_native_backend_error_parity.py` inventories
exception type, code, hint, position, and span independently from rendered text.

| Scenario | Interpreter metadata | Native metadata | Supported contract |
| --- | --- | --- | --- |
| Unknown variable | `TinyLangError`; `E003`; declaration hint; position `1:7`; span `1:7-1:13` | `RuntimeError`; no structured fields | A native VM name-lookup failure is an opaque runtime exception whose string contains the complete formatted diagnostic. |
| Division by zero | `TinyLangError`; `E000`; no hint; position `1:9`; span `1:7-1:11` | `TinyLangError`; `E000`; no hint; position `1:7`; span `1:7-1:11` | The expression span is authoritative for rendering; backend-specific point positions may identify different points inside that span. |
| Function argument-count mismatch | `TinyLangError`; `E009`; argument-count hint; position `2:7`; span `2:7-2:12` | Same | Shared frontend lint failures expose identical structured metadata. |
| Statically known heap bounds violation | `TinyLangError`; `E020`; bounds hint; position `2:7`; span `2:7-2:20` | Same | Shared frontend lint failures expose identical structured metadata. |
| `len` called with an unsized value | `TinyLangError`; `E005`; sized-value hint; position `1:7`; span `1:7-1:12` | `RuntimeError`; no structured fields | A native built-in dispatch failure is an opaque runtime exception whose string contains the complete formatted diagnostic. |

This difference is supported behavior for the experimental native backend. API
consumers must use `str(error)` when they need a backend-neutral diagnostic.
They may consume `TinyLangError` fields when the raised exception provides them,
but must not assume that every native VM runtime failure is structured. This
choice avoids changing exception inheritance or catch behavior while preserving
the exact CLI-visible diagnostic contract.

## Remaining bounded follow-up issues

None from this focused audit. New parity gaps should be recorded as separately
bounded issues rather than widening this gate implicitly.

## Re-running the audit

Run:

```bash
pytest -q tests/detailtests/test_native_backend_error_parity.py
```

When adding a native opcode, built-in, or runtime diagnostic, add a case to the
exact-message matrix when both backends support the behavior. If parity cannot
be achieved in the same change, add a narrowly scoped issue above with an
identifier, boundary, and acceptance criteria.
