# Performance microbenchmarks

This guide introduces a small harness for comparing TinyLanguage execution backends. It focuses on deterministic, CPU-heavy samples so relative timing remains stable across machines.

## Benchmarks and backends

The harness in [`benchmarks/microbenchmarks.py`](../benchmarks/microbenchmarks.py) ships with two representative programs:

- `tight_loop`: a summation loop that stresses integer arithmetic and assignment.
- `recursive_calls`: a naive Fibonacci implementation that highlights function-call overhead.

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

```
=== tight_loop ===
Summation loop with predictable arithmetic
interpreter             avg=3.80ms min=3.75ms max=3.92ms
python                  avg=0.75ms min=0.72ms max=0.81ms
native                  avg=1.10ms min=1.05ms max=1.15ms
native-python-bytecode  avg=0.98ms min=0.95ms max=1.00ms
```

Use these numbers for relative comparisons; absolute times will vary by hardware and interpreter version.
