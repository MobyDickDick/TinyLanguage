# Argument-isolation experiment: protocol

Work package 11, protocol written on 2026-11-10 before the first measurement.
This is a local, source-hashed protocol, not an externally registered study.
Results and the decision belong in `argument_isolation_experiment.md`.

## Hypothesis and intended use

For learners writing speculative transformations over caller-owned mutable
data, opt-in copy-on-call can preserve the input without a programmer-written
copy at every Tiny function boundary. It might reduce opportunities to omit
that copy. This is a narrow ergonomics hypothesis, not a new concept, security
claim, performance advantage, or claim about measured human comprehension.

## Workload and baselines

Preview a half-unit increase to a flat price list, discard the preview, and
repeat from the original. Inputs are `1000.25 + i`, so all arithmetic is exactly
representable in binary64 and none of the prices are integer heap addresses.
Use 16, 256 and 1024 prices, three previews, one warmup and seven samples.
Check every original cell after every preview and retain each preview total.
Release returned Tiny heap copies and the original explicitly.

Execute the same Tiny source with isolation enabled and disabled. The disabled
route is a negative control. Working Python baselines use `copy.deepcopy`,
`list.copy`, and direct list construction; a shared-list route is a second
negative control. Shallow copying is sufficient for this flat immutable-leaf
workload; deepcopy must not be presented as the only established solution.

## Criteria fixed before measurement

1. Correctness: every protected route preserves all original cells and returns
   the independently derived exact preview totals. Shared controls must expose
   mutation and the accumulating preview totals. A control passing isolation
   invalidates the experiment. Oracle calculations use `fractions.Fraction`,
   not Tiny arithmetic or another baseline's output.
2. Clarity: enumerate copy sites, required configuration, adoption and cleanup
   obligations. Inspect source qualitatively; do not equate line counts with
   comprehension or infer fewer real-world defects without a user study.
3. Cost: retain raw wall-clock samples, median and a separately traced Python
   allocation peak for every route/size. Time complete application runs,
   including input construction, frontend compilation/linting and cleanup.
   Imports, warmup and correctness validation are outside timing. Tracemalloc
   is off during timing. Output construction is inside timing for both languages.
   Cross-language totals describe these implementations, not the isolated cost
   of copying. Compare Tiny on/off only as a whole-workload overhead estimate.
4. Counterexamples: execute global-alias mutation, a shared method receiver,
   nested calls whose local update is not adopted, and Python shallow copying
   of nested mutable rows. State thread, interop, pointer and heap-cleanup limits.
5. Decision: retain the feature as an opt-in learning experiment only if the
   correctness criterion passes. Recommend revising its scope if counterexamples
   defeat general isolation, and reject an efficiency/novelty claim without
   supporting evidence. A negative advantage result completes the package.

No absolute performance threshold is required: this package evaluates a design
tradeoff, not the release performance budget. Timing gates must not be added to
CI. Deterministic correctness and counterexamples should run in pytest.
