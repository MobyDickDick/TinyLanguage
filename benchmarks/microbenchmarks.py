"""
microbenchmarks.py — TinyLanguage Microbenchmarks (Interpreter & Backends)

Purpose
-------
This script runs a small suite of **short-running, deterministic** TinyLanguage
programs against multiple execution backends (e.g. interpreter, Python backend,
native backend). The goal is **relative** performance comparison during
development, without requiring external tooling.

Design Goals
------------
- Deterministic workloads:
  Benchmarks avoid randomness and (as far as feasible) avoid noisy I/O patterns.
- Short runtime:
  Each case is intended to complete quickly to enable frequent execution.
- Comparable results:
  All backends execute the *exact same Tiny source string* per case.

Notes on Measurement
--------------------
- Timing uses `time.perf_counter()` and reports wall-clock durations.
- A warmup phase runs each benchmark `--warmup` times (not measured) to reduce
  first-run effects (JIT, caching, imports, allocator state, etc.).
- Reported metrics: average/min/max over `--repeat` measured runs.

Usage
-----
Run all cases on all backends:

    python microbenchmarks.py

Limit to specific backends:

    python microbenchmarks.py --backend interpreter native

Limit to specific benchmark cases:

    python microbenchmarks.py --case tight_loop heap_roundtrip

Tune repetition:

    python microbenchmarks.py --warmup 2 --repeat 10

Project Layout Assumption
-------------------------
This file expects the repository root to contain a `src/` directory that
exposes the `tiny_language` package. It adjusts `sys.path` accordingly.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Callable, Iterable

# ---------------------------------------------------------------------------
# Local import setup
# ---------------------------------------------------------------------------
# We want to run this script directly (without installing the package).
# To do so reliably, we prepend `<repo-root>/src` to sys.path.
#
# repo-root/
#   src/
#     tiny_language/
#   scripts/ (or similar)
#     microbenchmarks.py
#
# ROOT is computed as: microbenchmarks.py -> parents[1]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_language import (  # noqa: E402  (import after sys.path manipulation is intentional)
    compile_and_run,
    run_with_native_backend,
    run_with_python_backend,
    run_with_python_bytecode_backend,
)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """A single benchmark definition.

    Attributes
    ----------
    name:
        Stable identifier used for CLI selection (e.g. `--case tight_loop`).
    description:
        Human-readable explanation printed alongside the results.
    source:
        TinyLanguage source code executed for this benchmark case.
    """

    name: str
    description: str
    source: str


# ---------------------------------------------------------------------------
# Timing & reporting helpers
# ---------------------------------------------------------------------------


def _time_runs(
    func: Callable[[str], str],
    source: str,
    warmup: int,
    repeat: int,
) -> list[float]:
    """Execute `source` repeatedly and return measured durations.

    Parameters
    ----------
    func:
        Backend runner that takes Tiny source and returns program output (string).
        The output is intentionally ignored for timing to avoid I/O overhead.
    source:
        TinyLanguage program to run.
    warmup:
        Number of warmup runs (not measured).
    repeat:
        Number of measured runs.

    Returns
    -------
    list[float]
        A list of wall-clock durations in seconds, length == `repeat`.

    Notes
    -----
    - We run warmups first to reduce first-run effects (imports, caching,
      allocator state, potential JIT compilation depending on backend).
    - We do not attempt to subtract overhead of the harness itself; this tool
      is for relative comparisons across backends.
    """
    for _ in range(warmup):
        func(source)

    timings: list[float] = []
    for _ in range(repeat):
        start = perf_counter()
        func(source)
        timings.append(perf_counter() - start)

    return timings


def _format_timings(timings: Iterable[float]) -> str:
    """Format timing statistics in a compact human-readable form.

    Output format is milliseconds and includes average, min and max.

    Examples
    --------
    avg=1.23ms min=1.10ms max=1.42ms
    """
    timings_list = list(timings)
    if not timings_list:
        return "n/a"

    avg_ms = mean(timings_list) * 1000.0
    min_ms = min(timings_list) * 1000.0
    max_ms = max(timings_list) * 1000.0
    return f"avg={avg_ms:.2f}ms min={min_ms:.2f}ms max={max_ms:.2f}ms"


# ---------------------------------------------------------------------------
# Benchmark program generators (TinyLanguage source strings)
# ---------------------------------------------------------------------------


def _loop_body(loop_bound: int) -> str:
    """Generate a tight arithmetic loop benchmark.

    This stresses:
    - integer arithmetic
    - assignment
    - while-loop control flow

    Parameters
    ----------
    loop_bound:
        Number of loop iterations (higher => longer runtime).
    """
    return f"""
// Tight arithmetic loop to stress integer operations and assignment.
define sum = 0;
define i = 0;
while (i < {loop_bound}) {{
    sum = sum + i;
    i = i + 1;
}}
print(sum);
"""


def _function_calls(call_depth: int) -> str:
    """Generate a naive recursive Fibonacci benchmark.

    This primarily measures:
    - function invocation overhead
    - recursion/return handling
    - expression evaluation

    Parameters
    ----------
    call_depth:
        Fibonacci input `n`. Runtime grows exponentially with `n`.
    """
    return f"""
// Small recursive call tree to exercise function invocation overhead.
fn fib(n) {{
    if (n <= 1) {{ return n; }}
    return fib(n - 1) + fib(n - 2);
}}
print(fib({call_depth}));
"""


def _heap_roundtrip(iterations: int, slots: int = 8) -> str:
    """Generate repeated heap read/write operations.

    This stresses:
    - heap pointer validation
    - index bounds checking
    - heap_get / heap_set performance

    Parameters
    ----------
    iterations:
        Number of loop iterations (higher => longer runtime).
    slots:
        Number of slots in the allocated heap array.
        Access cycles over [0..slots-1] to avoid unbounded growth.
    """
    initial_items = ", ".join("0" for _ in range(slots))
    return f"""
// Repeated heap reads/writes to stress pointer checks and indexing.
define ptr = new[{initial_items}];
define i = 0;
define idx = 0;
while (i < {iterations}) {{
    heap_set(ptr, idx, i);
    // Touch the next slot to include heap_get in the mix.
    heap_get(ptr, idx);
    idx = idx + 1;
    if (idx == {slots}) {{ idx = 0; }}
    i = i + 1;
}}
print(heap_get(ptr, 0));
"""


def _map_operations(iterations: int) -> str:
    """Generate repeated Map.set / Map.get operations.

    This stresses:
    - hash map operations (insert/update/get)
    - value allocation/writes (depending on runtime representation)

    Parameters
    ----------
    iterations:
        Number of set/get cycles.
    """
    return f"""
// Insert/update/get operations to stress hash maps and value writes.
define map = Map.new();
define i = 0;
define last = 0;
while (i < {iterations}) {{
    _ = Map.set(map, i, i + 1);
    // Read the value back to ensure lookups participate in timing.
    last = Map.get(map, i);
    i = i + 1;
}}
print(last);
"""


# ---------------------------------------------------------------------------
# Benchmark suite & backend registry
# ---------------------------------------------------------------------------

BENCHMARKS: list[BenchmarkCase] = [
    BenchmarkCase(
        name="tight_loop",
        description="Summation loop with predictable arithmetic",
        source=_loop_body(loop_bound=5000),
    ),
    BenchmarkCase(
        name="recursive_calls",
        description="Naive Fibonacci to measure call overhead",
        source=_function_calls(call_depth=16),
    ),
    BenchmarkCase(
        name="heap_roundtrip",
        description="Heap writes/reads to exercise pointer and index checks",
        source=_heap_roundtrip(iterations=4000),
    ),
    BenchmarkCase(
        name="map_operations",
        description="Hash map set/get workload to exercise Map helpers",
        source=_map_operations(iterations=2000),
    ),
]

BACKENDS: dict[str, Callable[[str], str]] = {
    # "interpreter" corresponds to TinyLanguage's in-process interpreter execution.
    "interpreter": compile_and_run,
    # "python" compiles TinyLanguage to a Python-level backend and executes it.
    "python": run_with_python_backend,
    # "native" executes via the native backend (e.g. compiled/optimized path).
    "native": run_with_native_backend,
    # Alternative execution mode that uses Python bytecode tooling.
    "native-python-bytecode": run_with_python_bytecode_backend,
}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for running the microbenchmark suite."""
    import argparse

    parser = argparse.ArgumentParser(description="Run TinyLanguage microbenchmarks")
    parser.add_argument(
        "--backend",
        choices=sorted(BACKENDS.keys()),
        nargs="*",
        help="Limit to specific backends",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=5,
        help="Number of timed runs per case/backend",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warmup runs per case/backend (not measured)",
    )
    parser.add_argument(
        "--case",
        choices=[b.name for b in BENCHMARKS],
        nargs="*",
        help="Limit to specific cases",
    )
    args = parser.parse_args()

    selected_backends = args.backend or list(BACKENDS.keys())
    selected_cases = args.case or [b.name for b in BENCHMARKS]

    for case in BENCHMARKS:
        if case.name not in selected_cases:
            continue

        print(f"\n=== {case.name} ===")
        print(case.description)

        for backend_name in selected_backends:
            runner = BACKENDS[backend_name]
            timings = _time_runs(runner, case.source, args.warmup, args.repeat)
            print(f"{backend_name:24s} {_format_timings(timings)}")


if __name__ == "__main__":
    main()
