# Performance microbenchmarks

This guide introduces a small harness for comparing TinyLanguage execution backends. It focuses on deterministic, CPU-heavy samples so relative timing remains stable across machines.

## Benchmarks and backends

The harness in [`benchmarks/microbenchmarks.py`](../benchmarks/microbenchmarks.py) ships with three representative programs:

- `tight_loop`: a summation loop that stresses integer arithmetic and assignment.
- `recursive_calls`: a naive Fibonacci implementation that highlights function-call overhead.
- `heap_roundtrip`: repeated `heap_set`/`heap_get` calls over a small allocation to measure pointer validation and indexed writes.
- `map_operations`: repeated `Map.set`/`Map.get` calls over sequential integer keys to exercise hash-map helpers.

All built-in backends are supported:

- `interpreter` (default runtime)
- `python` (Python source generation)
- `native` (native bytecode + `NativeVM`)
- `native-python-bytecode` (native IR lowered to Python bytecode)

## Running the benchmarks

From the repository root, run:

```bash
python benchmarks/microbenchmarks.py
```

Key flags:

- `--backend interpreter native` limits which backends are exercised.
- `--case tight_loop` selects individual benchmark cases.
- `--repeat 3` and `--warmup 0` adjust timing samples.

Sample output:

``` (Python)
=== tight_loop ===
Summation loop with predictable arithmetic
interpreter             avg=3.80ms min=3.75ms max=3.92ms
python                  avg=0.75ms min=0.72ms max=0.81ms
native                  avg=1.10ms min=1.05ms max=1.15ms
native-python-bytecode  avg=0.98ms min=0.95ms max=1.00ms

=== heap_roundtrip ===
Heap writes/reads to exercise pointer and index checks
interpreter             avg=7.55ms min=7.40ms max=7.68ms
python                  avg=2.10ms min=2.04ms max=2.16ms
native                  avg=2.95ms min=2.88ms max=3.01ms
native-python-bytecode  avg=2.65ms min=2.60ms max=2.70ms
```

Use these numbers for relative comparisons; absolute times will vary by hardware and interpreter version.
