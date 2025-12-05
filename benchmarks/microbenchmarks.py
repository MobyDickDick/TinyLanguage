"""TinyLanguage microbenchmarks for interpreter and native backends.

This helper focuses on short-running, deterministic workloads so developers
can compare backend performance without external tools. The script deliberately
avoids noisy I/O and keeps allocations predictable to make relative timing
stable across runs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass
from statistics import mean
from time import perf_counter
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_language import (
    compile_and_run,
    run_with_native_backend,
    run_with_python_backend,
    run_with_python_bytecode_backend,
)


@dataclass
class BenchmarkCase:
    """Container for a benchmark case."""

    name: str
    description: str
    source: str


def _time_runs(func: Callable[[str], str], source: str, warmup: int, repeat: int) -> list[float]:
    """Return a list of wall-clock durations for executing ``source``."""
    for _ in range(warmup):
        func(source)
    timings: list[float] = []
    for _ in range(repeat):
        start = perf_counter()
        func(source)
        timings.append(perf_counter() - start)
    return timings


def _format_timings(timings: Iterable[float]) -> str:
    timings_list = list(timings)
    if not timings_list:
        return "n/a"
    return f"avg={mean(timings_list)*1000:.2f}ms min={min(timings_list)*1000:.2f}ms max={max(timings_list)*1000:.2f}ms"


def _loop_body(loop_bound: int) -> str:
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
    return f"""
// Small recursive call tree to exercise function invocation overhead.
fn fib(n) {{
    if (n <= 1) {{ return n; }}
    return fib(n - 1) + fib(n - 2);
}}
print(fib({call_depth}));
"""


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
]

BACKENDS: dict[str, Callable[[str], str]] = {
    "interpreter": compile_and_run,
    "python": run_with_python_backend,
    "native": run_with_native_backend,
    "native-python-bytecode": run_with_python_bytecode_backend,
}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run TinyLanguage microbenchmarks")
    parser.add_argument("--backend", choices=sorted(BACKENDS.keys()), nargs="*", help="Limit to specific backends")
    parser.add_argument("--repeat", type=int, default=5, help="Number of timed runs per case/backend")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup runs per case/backend (not measured)")
    parser.add_argument("--case", choices=[b.name for b in BENCHMARKS], nargs="*", help="Limit to specific cases")
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
