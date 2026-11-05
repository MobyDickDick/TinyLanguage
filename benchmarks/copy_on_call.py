"""Measure parameter binding on shared, cyclic object and Tiny heap graphs.

Run from any directory with ``python benchmarks/copy_on_call.py``. Setup and
identity validation are outside the timed region; peak allocation is measured
in a separate run so tracemalloc does not distort the timing samples.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tiny_language import Environment, Param, Runtime, SourcePos  # noqa: E402


def make_graph(kind: str, size: int, enabled: bool):
    """Build a shallow graph with repeated edges, a cycle and aliased arguments."""
    runtime = Runtime("")
    runtime.copy_on_call = enabled
    if kind == "object":
        leaves = [{"value": "leaf"} for _ in range(size)]
        graph = {"left": leaves, "right": leaves}
        graph["cycle"] = graph
        shared = leaves
    else:
        allocate = runtime._Runtime__new
        shared = allocate(1)
        runtime.heap_set(shared, 0, "leaf")
        graph = allocate(size * 2 + 1)
        for index in range(size):
            leaf = shared if index == 0 else allocate(1)
            runtime.heap_set(leaf, 0, "leaf")
            runtime.heap_set(graph, index * 2, leaf)
            runtime.heap_set(graph, index * 2 + 1, leaf)
        runtime.heap_set(graph, size * 2, graph)
    env = Environment(parent=None, runtime=runtime)
    return runtime, env, graph, shared


def bind(runtime, env, graph, shared):
    """Use the production call binder with shared memos for both arguments."""
    return runtime._bind_parameters_to_env(
        [Param("graph"), Param("shared")], [graph, shared], env,
        pos=SourcePos.origin(), type_label="copy-on-call benchmark",
    )


def validate(kind, size, enabled, runtime, env, original, shared):
    """Check isolation, shared edges and cycles independently of copying code."""
    result = env.get("graph")
    shared_result = env.get("shared")
    if kind == "object":
        assert (result is not original) == enabled
        assert (shared_result is not shared) == enabled
        assert result["left"] is result["right"] is shared_result
        assert result["cycle"] is result
        assert len(result["left"]) == size
        return 0, 0
    assert (result != original) == enabled
    assert (shared_result != shared) == enabled
    assert runtime.heap_get(result, 0) == shared_result
    for index in range(size):
        left = runtime.heap_get(result, index * 2)
        assert left == runtime.heap_get(result, index * 2 + 1)
        assert runtime.heap_get(left, 0) == "leaf"
    assert runtime.heap_get(result, size * 2) == result
    expected_allocations = (size + 1) * (2 if enabled else 1)
    assert len(runtime.heap) == expected_allocations
    return (size + 1, size * 3 + 1) if enabled else (0, 0)


def measure(kind: str, size: int, enabled: bool, repeat: int):
    """Collect raw binding times and a separate traced peak on fresh runtimes."""
    samples = []
    for _ in range(repeat):
        gc.collect()
        runtime, env, graph, shared = make_graph(kind, size, enabled)
        start = time.perf_counter_ns()
        bindings = bind(runtime, env, graph, shared)
        samples.append(time.perf_counter_ns() - start)
        validate(kind, size, enabled, runtime, env, graph, shared)
        del bindings, runtime, env, graph, shared
    gc.collect()
    runtime, env, graph, shared = make_graph(kind, size, enabled)
    tracemalloc.start()
    bindings = bind(runtime, env, graph, shared)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    allocations, cells = validate(kind, size, enabled, runtime, env, graph, shared)
    return {
        "graph": kind, "size": size, "copy_on_call": enabled,
        "samples_ns": samples, "median_ns": statistics.median(samples),
        "traced_retained_bytes": current, "traced_peak_bytes": peak,
        "copied_heap_allocations": allocations, "copied_heap_cells": cells,
        "identity_checks": "passed",
    }


def main() -> int:
    """Write reproducible inputs, source hashes and machine-specific measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[16, 64, 256, 1024])
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/copy-on-call/benchmark.json")
    args = parser.parse_args()
    if args.repeat < 1 or any(size < 1 for size in args.sizes):
        parser.error("sizes and repeat must be positive")
    sources = ["src/tiny_language_runtime.py", "src/tiny_language_parser.py",
               "src/tiny_language_api.py", "src/tiny_language_cli.py",
               "src/tiny_language_ast.py", "src_tiny/tiny_language_parser.tiny",
               "tests/detailtests/test_copy_on_call.py", "benchmarks/copy_on_call.py"]
    report = {
        "schema": 1, "python": sys.version, "platform": platform.platform(),
        "base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": "working-tree call-binding measurements, not release qualification",
        "repeat": args.repeat, "sizes": args.sizes,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in sources},
        "results": [measure(kind, size, enabled, args.repeat)
                    for kind in ("object", "heap") for size in args.sizes
                    for enabled in (False, True)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(report['results'])} validated measurements to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
