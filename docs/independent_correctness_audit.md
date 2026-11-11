# Independent correctness and backend execution audit

Work package 9, 2026-11-06. This is a local Windows x86-64 working-tree audit,
not release, platform, JIT, optimization-level or complete-language qualification.
The interpreter remains the reference implementation. Backend agreement alone
does not supply an independent expected result.

## Independent expected results

The executable corpus is `tools/correctness_cases.py`. Each case declares its
source, feature, correct output or error, supported routes and semantic basis.
Expected values are never generated from a Tiny implementation:

| Area | Oracle and reviewed expectations | Executable evidence |
| --- | --- | --- |
| Arithmetic | Python `Fraction`, seed 90210: 160 small integer/dyadic results; every decimal output must denote exactly the expected rational, with no tolerance. Separate witnesses exercise 2^31 and 2^53+1. | `exact-arithmetic`, `integer-boundary` |
| Comparisons | All six order/equality relations over {-2,0,3}: 54 exact rational comparisons, observed through branch selection. | `comparison-relations` |
| Intervals | Direct rational endpoint extrema, pointwise membership of ordinary/exterior/unbounded sets, overflow/subnormal boundaries. The mathematical set contract, not a displayed center/radius, determines enclosure. | `tests/detailtests/test_interval_enclosure.py`, `docs/interval_arithmetic_contract.md` |
| Historical interval defects | The old exterior result [6,-4] excludes the attainable quotient 0. The old singleton sum [1,1] excludes 1+1/2^53. A mutation-witness check explicitly confirms that the independent oracle rejects both. | `test_exact_oracle_rejects_both_historical_interval_defects` |
| Aliasing and copies | Default calls borrow; opt-in copies preserve internal sharing while isolating original graphs. Python standard-library `deepcopy` independently models 12 generated shared-record workloads per mode, including mutations after a return. Existing cycle/heap/method/protection tests remain required. | `tests/test_correctness_audit.py`, `tests/detailtests/test_copy_on_call.py`, `docs/copy_on_call_contract.md` |
| Ownership | Successful delete has error code 0; double delete and writing freed storage have code 1. Hide operations behind helpers to exercise runtime checks rather than only static lifetime rejection. | `heap`, `heap-error-status`, `docs/heap_usage_guidelines.md` |
| Error propagation | Wrong arity is frontend E009; division by zero must fail during execution and cannot reach a subsequent observable print. Backend diagnostic parity tests additionally inventory structured/opaque API differences. | `arity-error`, `division-error`, `tests/detailtests/test_native_backend_error_parity.py` |
| Other feature rows | Small semantic derivations: factorial induction, explicit evaluation trace, field updates, ADT tag selection, collection insertion/lookup, worker sum, token state/reason, separate-module doubling, sqrt(9)=3. | Remaining named corpus cases |

Review found an important distinction in the heap expectations: interpreter and
native heap operations generally return an error record or `Null` and record a
diagnostic; they do not universally throw. Static lifetime lints can reject a
program before those runtime paths run. The audit exercises both mechanisms
without changing a failed expected result to match an unrelated implementation.

## Execution and report contract

Run from a checkout with `src` on `PYTHONPATH` and a working clang/linker:

```bash
python -m tools.correctness_audit --report artifacts/correctness-audit/backend-results.json
```

The strict command returns nonzero while any applicable case fails or a tool is
unavailable. For CI regression monitoring of the inventoried prototype defects:

```bash
python -m tools.correctness_audit --allow-known-gaps --report artifacts/correctness-audit/backend-results.json
python -m tools.correctness_audit --verify artifacts/correctness-audit/backend-results.json
```

`--allow-known-gaps` permits only the narrow observed signatures in `known_gap`;
these entries still have status **failed** and do not establish support. A new
failure, timeout, missing compiler, worker crash or incomplete stage is a failing
gate. Fixing a known defect produces a real pass; the obsolete inventory entry
can then be removed. `--case` and `--backend` support focused investigation, but
the verifier refuses a partial report as evidence for the complete audit.

Each applicable matrix entry runs in a fresh Python process. Reports retain the
correct oracle and source, frontend acceptance, code generation, compiler
command/status/output, generated-source and executable hashes, execution
command/status, raw stdout/stderr and exceptions. `stages.* = passed` means the
stage completed: an executed process can still fail its semantic oracle or exit
with a hardware exception. Only the entry's overall `status = passed` establishes
the declared behavior. Interpreter/VM execution does not require a native build;
C and LLVM evidence requires both compilation/linking and executing the binary.
The LLVM route here is standalone IR plus clang, not LLVM-via-C or optional JIT.

Compiler and executable invocations have deadlines, workers have an overall
deadline, and missing prerequisites remain `unavailable`. Unsupported C features
and non-interpreter copy-on-call modes are explicit `not_applicable` entries,
never passes. Generated main/module files live in isolated temporary directories.
No broad output normalization can erase program lines: only equivalent decimal
number spellings and platform line endings are accepted. Booleans, `Null`, extra
lines, streams and exit codes remain observable.

The report records HEAD, Python/platform/compiler identity and hashes of all
maintained inputs, including untracked implementation files, before execution.
It detects source changes during the run. Verification checks the current source
manifest, every expected matrix entry, current correct oracles, stage evidence
and recomputed outcomes. Evidence files are excluded from the source identity.

## Retained local acceptance (original audit, 2026-11-06)

The [backend report](../artifacts/correctness-audit/backend-results.json) contains
24 cases across four routes: **65 passed, 15 failed in ten bounded issue groups,
16 not applicable, zero unavailable**. Failed cases are a result of the audit,
not evidence of backend equivalence. The
[validation checkpoint](../artifacts/correctness-audit/checkpoint.json) records
the exact commands, source identity and retained test/log hashes.

Supported feature claims in [the backend matrix](backend_feature_matrix.md) are
now tied to these bounded examples; failing or unqualified cells are partial or
unsupported. A passing example establishes only that example's declared subset.
In particular, token state and a joined worker sum do not establish parallel
scheduling or cooperative cancellation parity for LLVM. Formatter/lint behavior
is shared frontend tooling and retains its existing regression checks.

The older parity runner is hardened as well: undeclared common failures cannot
pass, independent stdout snapshots guard the positive bundled fixtures, negative
fixtures declare their expected failure, requested backend selection takes
precedence over fixture metadata, and zero executed backends fails. Negative
fixture expectations derive from undeclared-name rejection; positive sums derive
from 1+2+3=6, 1+3+5+7+9=25 and clamp(-2,5,22) to [0,10] = (0,5,10).

## Bounded follow-up work

Owner for these issues: Runtime/Compiler; priority P1 for semantic failures,
P2 for unsupported experimental features. The audit is complete; repairing
these defects is separate work and must not replace the correct audit oracles.

| ID | Observed boundary | Acceptance for repair |
| --- | --- | --- |
| AUD-001 (P1, closed 2026-11-11) | LLVM integer division truncated nonintegral quotients, including negative inputs. | All 160 exact rational arithmetic observations now compile and execute successfully without weakening numeric comparison. See the repair checkpoint below. |
| AUD-002 (P1) | On Windows, LLVM's integer output prints 2^53+1 as 1 and 2^31 as -2147483648; `%ld` is incompatible with the Windows host `long` width. | Both exact boundary values print intact on Windows and POSIX; cover signed 64-bit boundaries and the emitter's format-string ABI. |
| AUD-003 (P1) | Native/C print `null`; LLVM prints booleans as 1/0. | All literal outputs match the language's `Null`, `true`, `false` spelling; test mixed print arguments too. |
| AUD-004 (P1) | Native/C evaluate both RHS side effects; LLVM rejects boolean `and` lowering. | Both `&&`/`and` and `||`/`or` implement skipped and required RHS evaluation, preserving left-to-right effects and errors. |
| AUD-005 (P2) | LLVM rejects `len` on heap arrays during codegen. | Compile and execute the two-slot length witness; separately state supported string/collection length categories. |
| AUD-006 (P2) | LLVM cannot lower field access in the audited user-class operator overload (`__field_get expects class value and field name literal`; with module context, `unknown class`). | Compile, link and execute field-based user-class addition with result 7; retain the two original objects' fields. |
| AUD-007 (P1) | LLVM cannot read heap operation error records (`field access on unknown class value`). | Execute successful/double delete and freed write, preserving codes (0,1,1); reconcile its terminating heap-error policy with the reference result contract. |
| AUD-008 (P1) | Supplying a module/file path qualifies LLVM builtin calls as `<module>.heap_set`, which are then unresolved. | With file/module context, compile and run heap builtins and explicit join calls, including imported modules and Unicode paths. |
| AUD-009 (P2) | LLVM standalone interop emits external Python helper calls but linking fails on `__py_import_module`/`__py_call`. | Link an actual runtime bridge and execute the allowlisted sqrt witness; separately qualify denial and lifetime behavior. JIT symbol registration alone does not qualify a standalone executable. |
| AUD-010 (P1, C repair open) | C division by zero prints infinity and reaches the next statement. LLVM's former hardware exception is repaired alongside AUD-001. | LLVM integer, floating and signed-zero divisors now report a language error and exit 1 before subsequent effects. The same acceptance remains required for C. |

## AUD-001 repair checkpoint (2026-11-11)

LLVM `/` now converts integer operands to binary64 and uses checked floating
division. The inferred result is `double`, including in function returns.
Mixed integer/double arithmetic and comparisons widen the integer operand so
stored and returned quotients retain their fractional parts in later expressions.
Other integer arithmetic stays integer. Division by either sign of zero prints
`division by zero` and exits with status 1 before the next statement. This also
repairs the LLVM part of AUD-010; its C part remains open.

`tests/test_llvm_division.py` executes the unchanged 160-observation rational
corpus and checks signs, exact integral quotients, storage, function returns,
chained arithmetic, comparisons, mixed operands and the signed i64 minimum
divided by -1. Zero checks cover integer, floating, computed and negative zero.
The historical truncation output is now an unaccepted regression: the AUD-001
allowance and LLVM hardware-exception allowance have been removed from the audit.

The [source-bound repair report](../artifacts/llvm-division/backend-results.json)
retains the complete four-route audit. The
[validation checkpoint](../artifacts/llvm-division/checkpoint.json) records
commands, results and evidence hashes. The original audit above remains a
historical observation; the new report supersedes its two repaired LLVM cells.

This is a bounded local Windows acceptance, not general numeric or cross-platform
qualification. The exact corpus uses small binary-representable quotients;
binary64 rounding, i64 operand limits, the existing six-decimal LLVM print format
and monomorphic function inference still constrain the prototype. Large mixed
integer/double operations can lose precision during conversion. No arbitrary
precision or exact rational division is promised, and AUD-002–009 and the C part
of AUD-010 remain open. The next P1 backend repair is AUD-002.

This audit closes work package 9 by replacing broad implementation assertions
with independent oracles, executed evidence and explicitly reduced backend
claims. It does not close the remaining follow-up repairs or release packages 1, 3, 5
and 6, and does not expand the frozen stable interpreter contract.
