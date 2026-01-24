# Runtime performance goals

This document defines the runtime-performance goals for TinyLanguage and
captures how we plan to measure, optimize, and guard them across backends.
It is intentionally high level so it can evolve alongside the interpreter,
C backend, and LLVM pipeline.

## Goals by backend

### Interpreter (reference implementation)

**Primary goal:** predictable semantics and fast iteration time.

- Maintain correctness-first behavior with clear diagnostics.
- Optimize for low overhead in typical scripts (short startup, reasonable
  throughput for loops, collections, and I/O).
- Serve as the reference point for backend parity tests.

### Native/C/LLVM backends (performance-oriented)

**Primary goal:** higher throughput than the interpreter while preserving
language semantics and diagnostics.

- Provide clear performance wins on compute-heavy workloads (tight loops,
  arithmetic, allocations) without sacrificing observable behavior.
- Maintain feature parity with the interpreter (supported syntax + runtime
  error shapes) as part of performance regressions.
- Keep startup latency acceptable for CLI tooling and short programs.

## Performance target categories

We will track performance in **relative** terms, using the interpreter as a
baseline until stable numeric targets are established.

- **Throughput targets:** C/LLVM backends should show a meaningful speedup on
  CPU-bound microbenchmarks compared to the interpreter.
- **Allocation targets:** heap-heavy benchmarks should show reduced overhead
  relative to interpreter execution.
- **Startup targets:** interpreter should remain fast enough for short scripts
  and tooling commands; native backends should avoid large startup penalties.

These targets are intentionally qualitative today. The benchmarking workflow
below provides the data needed to refine them into numerical thresholds.

## Optimization stages (by backend)

This section outlines the intended optimization stages. Some items are already
present, while others describe the planned structure for future improvements.

### Common frontend stages

1. **Parsing + AST validation**: build the syntax tree and enforce structural
   constraints.
2. **Semantic checks**: linting, type-related checks (where applicable), and
   early error reporting.
3. **Lowering**: convert to backend-specific IR or bytecode representation.

### Interpreter stages

1. **Baseline execution**: direct AST/IR evaluation with correctness-first
   behavior.
2. **Targeted fast paths**: optimize hot operations (loop counters, numeric
   ops, collection access) while preserving semantics.
3. **Runtime optimizations** (planned): reduce repeated dispatch costs and
   tighten heap operations without changing user-visible behavior.

### Native/C backend stages

1. **IR emission**: lower TinyLanguage constructs into C/native instructions.
2. **Basic cleanup**: remove redundant moves/loads and simplify literal
   expressions.
3. **Backend optimizations** (planned): improve register allocation, tighter
   stack/heap management, and better inlining for stdlib helpers.

### LLVM backend stages

1. **IR emission**: generate LLVM IR from TinyLanguage constructs.
2. **Baseline LLVM pass pipeline**: rely on LLVM's default optimization passes
   for general improvements.
3. **Targeted LLVM tuning** (planned): customize pass pipelines for hot loops,
   constant folding, and alloc-heavy workloads.

## Profiling + benchmarking workflow

We will use a combination of microbenchmarks and targeted regression checks to
observe performance trends and catch regressions.

### Microbenchmarks (relative throughput)

- Use `benchmarks/microbenchmarks.py` to compare backends on deterministic
  workloads.
- Typical usage:
  - `python benchmarks/microbenchmarks.py`
  - `python benchmarks/microbenchmarks.py --backend interpreter native`
  - `python benchmarks/microbenchmarks.py --case tight_loop heap_roundtrip`
- Track results locally and in CI logs (when available) to spot regressions.

### Profiling (problem-focused)

- When a regression appears, isolate the program and measure with:
  - reduced benchmark input sizes to confirm hot spots,
  - backend comparison (interpreter vs. native/C/LLVM), and
  - changes in heap operations (allocation volume and pointer churn).
- Prefer small, deterministic repro cases that can be added as a benchmark
  or test fixture.

### Regression guarding

- Store performance notes alongside fixes to capture expected deltas.
- Add or update microbenchmarks to encode new hot paths (e.g., collections
  usage, numeric loops, I/O parsing).

## Maintaining parity

Performance improvements must not change language behavior. Each backend should
continue to pass the existing correctness and parity test suites while pursuing
speedups. Any optimization that changes diagnostics or observable output must be
explicitly documented and justified.
