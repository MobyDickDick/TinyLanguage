# 1.0 candidate contract and evidence

`VERSION` is **1.0.0**, a planned release identifier. It does not establish a
published or qualified stable release. This document is the canonical scope
decision for work package 5 and supersedes historical release-completion boxes.

## Candidate stability target

The default Python interpreter is the reference implementation. The candidate
contract covers literals, bindings and type stability, evaluation order,
control flow, functions and recursion, heap access and diagnostics, classes,
operators, ADTs, namespaces/imports, and cooperative task/cleanup semantics as
specified in [language_spec.md](language_spec.md). The proposed
[strict profile](strict_by_default_safety_profile.md) is a design, not an
implemented default. Default calls retain the documented shared mutation
behavior. Optional copy-on-call remains outside the frozen stability target;
work package 7 replaces return inference with the explicit adoption contract in
[copy_on_call_contract.md](copy_on_call_contract.md).

The stable stdlib target is the existing API of `stdlib.math`, `stdlib.random`,
`stdlib.string`, `stdlib.collections`, `stdlib.io` and `stdlib.json`, with the
deviations and maturity tiers in [stdlib_compatibility.md](stdlib_compatibility.md).
Beta and experimental modules retain their stated tiers. Ordinary floating-point
math does not promise exact real arithmetic. `NumberIntervall` has a separate
[set and rounding contract](interval_arithmetic_contract.md) with independent
reference-interpreter checks (package 8) and remains excluded from this frozen
target. Copy-on-call's revised contract
has regression and migration evidence but is not added to this frozen target.
Its numeric-pointer representation, manual heap cleanup and interop limits are
documented separately. Future interval inclusion requires its own stability
and backend/platform qualification decision.

The CLI target is the installed interpreter, version reporting, project/local
package workflows, and LSP/editor operations demonstrated in
[installed_workflows_acceptance.md](installed_workflows_acceptance.md).
Registry publication remains incomplete (package 4); external package integrity
and complete application qualification remain open (package 6). The absence of
those checks must not be described as a completed ecosystem or security audit.

Native VM, native Python bytecode, Python transpilation, C and LLVM are
experimental. Their feature matrices describe implemented subsets, not a
stability promise or successful machine-code execution of every cell. C does
not implement heap, imports, or Python interop, so file/JSON and heap-error
parity across interpreter/C/native cannot be a required supported scenario.

## Evidence map

These are executable checks, not a claim that the current candidate has passed.
The CI evidence gate records their results for the exact checked source.

| Contract area | Executable evidence | What it establishes |
| --- | --- | --- |
| Grammar and observable interpreter behavior | `tests/test_language_spec_grammar.py`, `tests/test_spec_conformance.py` | Grammar checks and verbatim fixture stdout/errors |
| Evaluation order, scopes, types, tasks | `tests/detailtests/test_semantics_suite.py`, `tests/test_tiny_language.py`, `tests/detailtests/test_async_structured.py` | Spec-derived expected outputs and error/cleanup cases |
| Heap safety and structured errors | `tests/detailtests/test_heap_api_errors.py`, `tests/test_release_scope_contract.py` | Invalid operations fail; documented error codes/positions remain observable |
| Arithmetic and documentation | `tests/test_release_scope_contract.py` | Exact rational oracle for small core arithmetic; actual encapsulation snippet executes |
| Opt-in argument encapsulation (outside frozen target) | `tests/detailtests/test_copy_on_call.py`, [contract and measurements](copy_on_call_contract.md) | Scalar/alias returns, protected writes, nested calls, methods and shared/cyclic graphs |
| Source-preserving module summaries | `tests/test_module_summary_persistence.py` | Unchanged LF/CRLF summaries keep their bytes and timestamp; changed summaries update |
| Stable stdlib | `tests/test_stdlib_compatibility.py`, `tests/detailtests/test_stdlib_parity.py`, `tests/detailtests/test_stdlib_doc_examples.py` | Reference parity and executable documented outputs |
| CLI/editor | `tests/detailtests/test_cli_smoke.py`, LSP suites in the evidence gate; installed acceptance records | CLI/LSP behavior; external installation and actual editor evidence have distinct scopes |
| Experimental native VM | `tests/test_parity_runner.py`, `tests/detailtests/test_native_backend_error_parity.py` | Execution and observable outputs/errors for named fixtures, not independent proof of all semantics |
| Experimental C/LLVM | `tests/test_c_backend.py`, `tests/detailtests/test_llvm_conformance_smoke.py` | Required compiler execution, including LLVM executable API/CLI entry points; text emission alone is insufficient |

The full regression check includes all listed suites. The focused
`interpreter-contract`, `lsp`, and `native-parity` checks reject skipped tests.
The full regression report counts optional/platform skips separately. Mandatory
C/LLVM execution belongs to the sixteen platform jobs with
`--require-backend-toolchains`; an ordinary skipped regression is not platform
acceptance.

## Candidate evidence gate

Run each fixed check in a committed candidate checkout:

```bash
python tools/release/check_release_candidate_checklist.py --run-check docstrings
python tools/release/check_release_candidate_checklist.py --run-check format-lint
python tools/release/check_release_candidate_checklist.py --run-check lsp
python tools/release/check_release_candidate_checklist.py --run-check interpreter-contract
python tools/release/check_release_candidate_checklist.py --run-check native-parity
python tools/release/check_release_candidate_checklist.py --run-check regression
python tools/release/check_release_candidate_checklist.py --run-check unsigned-source
python tools/release/check_release_candidate_checklist.py
```

The helper executes each command with a valid closed-input handle and retains
exit status, command, Python/platform identity, log hashes and JUnit hashes in
`artifacts/release-candidate/`. Source identity includes HEAD and a digest of
maintained working files, including untracked additions and deletions; generated
`artifacts/`, `build/` and `dist/` are excluded. Source changes during a check
invalidate the record. An unrelated successful command, empty result, missing
record or modified payload cannot satisfy a gate. The unsigned-source check
also verifies version, source commit, payload hashes and checksum inventory.
Because that builder archives HEAD, uncommitted candidate changes prevent
complete qualification. Working-tree focused tests remain useful checkpoints.

CI uploads the records, logs, JUnit and unsigned source payload together as
`candidate-regression-evidence`, even after a failure. Hashes detect accidental
changes and source mismatches; records are not cryptographic attestations from
a trusted builder. Preserve the CI run ID alongside the candidate commit when
reviewing them. Release-key signatures and independent reproducibility remain
package 1 requirements.

## Release status and exit

The candidate regression gate verifies regression evidence only. Release
approval additionally requires all acceptance evidence in packages 1–3:
four-platform artifacts, immutable inputs, signatures and independent rebuilds;
installed/editor workflows; and all sixteen OS/Python qualification runs.
See [release_packaging_acceptance.md](release_packaging_acceptance.md),
[installed_workflows_acceptance.md](installed_workflows_acceptance.md), and
[platform_verification_acceptance.md](platform_verification_acceptance.md).

Work package 5 stays open until a committed candidate has retained passing
evidence and those delivery packages pass. No tag, publication or approval is
implied by a checked documentation item or a historical regression count.
