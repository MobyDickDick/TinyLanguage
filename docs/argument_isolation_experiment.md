# Argument isolation: a focused language experiment

Work package 11, 2026-11-10. **Decision: continue copy-on-call as a bounded,
opt-in learning experiment.** Automatic argument copies and active-call alias
guards work for the tested reference-interpreter workload. This study does
not demonstrate a general practical advantage over idiomatic Python, an
efficiency advantage, or a new underlying concept. General isolation would
require a revised design, particularly for method receivers and heap lifetime.

## Hypothesis and prior criteria

Intended users are learners experimenting with speculative changes to mutable
data. The hypothesis is that automatic argument copying can remove the need
to remember an explicit copy at each function boundary. It is a hypothesis
about an implementation's ergonomics, not an observed reduction in user bugs.

The [protocol](argument_isolation_protocol.md) was written before measurement.
Its SHA-256 is retained in the [raw report](../artifacts/argument-isolation/experiment.json).
It fixes the workload, exact correctness oracle, controls, measurement regions,
counterexamples and decision criteria. No timing threshold or user-study claim
was specified. The protocol was locally source-hashed, not externally registered.

## Reproducible application and established baseline

The [Tiny example](../examples/argument_isolation/price_preview.tiny) creates
prices `1000.25 + i`, previews an increase of `0.5`, then discards the preview.
Three previews must each start from the original. Every original cell is checked
after every call; each preview total and the final original total are retained.
Returned Tiny buffers and the original are explicitly freed. The values avoid
integer/pointer ambiguity, and every operation in these input sizes is exact
in binary64. These deliberate restrictions bound the result.

The [working Python baseline](../examples/argument_isolation/price_preview.py)
offers four implementations: deepcopy, shallow list copy, direct construction
of the changed list, and shared mutation. Both shared-mutation implementations
are negative controls. For `n` prices, the independent rational oracle derives:

```text
initial = n * 4001/4 + n*(n-1)/2
isolated preview total, every round = initial + n/2
shared preview total, round r       = initial + r*n/2
```

The isolated original must retain its initial total and every cell; shared
controls must fail preservation. Comparing Tiny with Python output alone would
not establish correctness. `fractions.Fraction` supplies the independent oracle.
The tests also deliberately feed both controls to the isolation checker and
require rejection.

From the checkout with Python 3.11 or newer:

```sh
python src/tiny_language.py --copy-on-call examples/argument_isolation/price_preview.tiny
python examples/argument_isolation/price_preview.py --strategy deepcopy
python examples/argument_isolation/price_preview.py --strategy shallow
python examples/argument_isolation/price_preview.py --strategy rebuild
python benchmarks/argument_isolation.py --sizes 16 256 1024 --rounds 3 --repeat 7
python -m pytest -q tests/test_argument_isolation_experiment.py tests/detailtests/test_copy_on_call.py tests/test_release_scope_contract.py tests/test_spec_conformance.py
```

The standalone examples default to 16 prices and three rounds: each preview
total is 16132, preservation is true, and the original total is 16124. Removing
the Tiny flag or selecting Python `--strategy shared` exposes accumulation.
The runner accepts an absolute path and `--output` when invoked elsewhere;
pytest exercises both standalone examples and the runner outside the checkout.

## Relationship to established semantics

Python assignment shares objects. Its standard copying facilities already
provide shallow copies and memoized recursive copies; user-defined types can
customize deep copying. Shallow copying suffices for these flat immutable
prices; it fails when rows themselves become mutable. This makes direct
construction and shallow copying essential baselines, rather than forcing an
unnecessarily general deepcopy comparison. [Python copying documentation](https://docs.python.org/3/library/copy.html).

Swift distinguishes value types from reference types. Value-type assignment
and argument passing provide value semantics; class instances share identity.
Swift's standard arrays and dictionaries are value types. Tiny's runtime flag
instead changes argument binding for supported mutable graphs while retaining
shared method receivers. This is a different boundary choice, not evidence of
a new concept. Swift is a semantic reference here; no Swift execution or
performance comparison was conducted. [Swift value and reference types](https://www.swift.org/documentation/articles/value-and-reference-types.html).

## Correctness and clarity findings

All four protected routes pass at all three measurement sizes. Both shared
controls produce the independently predicted mutation and accumulating totals.
The main Tiny application leaves zero live heap allocations. The focused run
has **67 passes, zero failures and zero skips**, including existing contract
and executable specification tests. Normal CI pytest collection includes the
new deterministic tests; no timing gate is introduced.

| Implementation | Explicit copying in the transformation | Obligations visible to its caller |
| --- | --- | --- |
| Tiny copy-on-call | No explicit copy operation | Enable the flag; adopt returned updates explicitly; free returned heap buffers |
| Python deepcopy | One copy operation at function entry | Adopt returned updates; add more copy boundaries if nested-call isolation is wanted |
| Python shallow | One copy operation at function entry | Keep leaves immutable or revise the copying strategy |
| Python reconstruction | Allocate the new list directly | Express the transformation without input mutation; adopt returned updates |

Tiny removes a programmer-written copy site in this example. Python's
reconstruction states the desired result directly and needs no mutation or
separate copying operation. This source inspection does not show that Tiny is
clearer: implicit configuration, receiver exceptions, nested adoption and manual
heap cleanup introduce their own reasoning obligations. No human comprehension
or defect-rate study was performed.

## Runtime and memory findings

Local Windows x86_64, CPython 3.12.14; one warmup and seven samples per cell.
The table shows medians for complete application runs, including compilation
(and Tiny linting), fresh runtime/definitions, input construction, all three
previews, output construction and cleanup. Imports are already cached; process
startup, source reading and correctness validation are outside timing.

| Route | 16 prices (ms) | 256 prices (ms) | 1024 prices (ms) | Traced peak at 1024 (bytes) |
| --- | ---: | ---: | ---: | ---: |
| Tiny copy-on-call | 5.898 | 56.629 | 494.572 | 394,234 |
| Tiny shared control | 6.356 | 55.430 | 478.829 | 281,009 |
| Python deepcopy | 0.457 | 0.668 | 1.083 | 176,100 |
| Python shallow | 0.468 | 0.542 | 0.695 | 176,100 |
| Python reconstruction | 0.541 | 0.500 | 0.700 | 176,100 |
| Python shared control | 0.470 | 0.495 | 0.734 | 176,100 |

These measurements show no implementation efficiency advantage for Tiny on
this workload. Cross-language totals include different frontends, execution
engines and data representations (Tiny heap versus Python list); they cannot
attribute the runtime difference to copying. Even Tiny on/off medians describe
the whole workload. Noise makes the smallest shared run slower than its copying
counterpart; this is not evidence that copying speeds it up.

Tracemalloc runs separately from timing and measures Python-managed allocation
peaks, not RSS. Python's compilation peak dominates all measured input sizes,
so equal peaks do not mean equal copy allocation costs. The Tiny runtime is
retained for post-run heap inspection; freed-allocation bookkeeping and other
interpreter state contribute to its peak. These figures are not portable memory
budgets. Raw samples are retained; route order rotates between sizes, but this
is still one host/process without confidence intervals. The earlier
[binding-only graph benchmark](copy_on_call_contract.md#reproduction-and-evidence)
provides a separate view of eager copying and alias/cycle preservation.

## Executed counterexamples and limits

The [counterexample sources](../examples/argument_isolation/counterexamples.py)
execute as part of the runner and tests. Their observed results are retained
separately from the main workload's successful isolation:

| Witness | Observed result | Implication |
| --- | --- | --- |
| Write through an original global alias during a Tiny call | Protected-parameter error | Tiny adds an active-call guard beyond Python deepcopy alone |
| Python copy plus write through a captured original alias | Original 1000.75, returned copy 1000.25 | Copying a parameter alone does not restrict other aliases |
| Tiny `original.bump()` method receiver | Original and result both 1000.75 | The flag does not isolate method receivers |
| Tiny outer call discards an inner call's changed copy | Original and outer result both 1000.25 | An inner update requires explicit adoption |
| Python with just one outer deepcopy | Original 1000.25, outer result 1000.75 | A single copy boundary has different nested semantics |
| Python deepcopy at both call boundaries | Original and outer result both 1000.25 | Explicit Python boundaries can reproduce this Tiny behavior |
| Python shallow copy of mutable rows | Original and result both 1000.75 | The successful flat-data baseline does not generalize automatically |
| Python deepcopy of mutable rows | Original 1000.25, result 1000.75 | Established copying handles this nested example |
| Tiny read-only scalar-return call discards its copied heap argument | One live copy after deleting the original | Even read-only calls need a heap-lifetime policy; copying is not resource safety |

The final witness intentionally demonstrates a retained allocation; it is
not reported as successful cleanup. The process ends after inspection.
The [contract](copy_on_call_contract.md#limits-and-cost) also excludes general
Python interop, arbitrary host resources and cross-thread protection. Numeric
values can collide with live heap addresses. Recursive graph depth remains
limited, and exceptions do not automatically reclaim heap copies. No concurrency,
security, backend-isolation or user-study claim follows from this experiment.

## Decision and retained evidence

Continue the opt-in interpreter experiment because the narrow argument-binding
criterion passes and the alias guard is a concrete observable difference.
Revise its positioning to automatic argument copying with explicit exceptions.
Do not recommend enabling it as a general isolation or resource-safety default.
For this application, idiomatic Python already provides small, correct solutions;
a practical superiority claim is unsupported. Novelty was not established by
this comparison, which is not an exhaustive novelty search.

Before proposing broader adoption, Language Design/Runtime should separately
evaluate an explicit receiver/mutation model and a lifetime policy for discarded
heap copies. Acceptance would require receiver and exceptional-path examples,
zero unintended retained allocations over repeated calls, and a new comparison
against reconstruction/value-oriented alternatives. These are future design
criteria, not new behavior shipped by this work package.

The [checkpoint](../artifacts/argument-isolation/checkpoint.json) binds commands,
runner identity, source hashes, logs, JUnit and measurement artifacts. The
[measurement report](../artifacts/argument-isolation/experiment.json) retains
18 route/size cells, raw timing samples, exact observations, protocol hash and
all nine counterexample observations. This closes package 11 with a bounded
result, including the negative advantage finding. Release/platform qualification
and previously discovered backend repairs remain separate work.
