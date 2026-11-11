"""Evaluate speculative price previews against explicit Python alternatives.

Run from any directory. The source-hashed protocol fixes criteria in advance;
raw application timing and separate tracemalloc measurements are descriptive.
Correctness uses an independent exact-rational oracle, including the controls.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import gc
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tiny_language import Runtime, TinyLangError, compile_and_run  # noqa: E402
from examples.argument_isolation import counterexamples as cases  # noqa: E402

ROUTES = ("tiny_copy", "tiny_shared", "python_deepcopy", "python_shallow",
          "python_rebuild", "python_shared")
PROTOCOL = ROOT / "docs/argument_isolation_protocol.md"
EXAMPLES = ROOT / "examples/argument_isolation"


def oracle(size, rounds, isolated):
    """Derive exact totals without executing either transformation algorithm."""
    initial = size * Fraction(4001, 4) + Fraction(size * (size - 1), 2)
    totals = [initial + size * Fraction(1 if isolated else step, 2)
              for step in range(1, rounds + 1)]
    return totals, isolated, initial if isolated else totals[-1]


def decode(output, rounds):
    """Parse language-independent observable values, rejecting malformed output."""
    lines = output.strip().splitlines()
    if len(lines) != rounds + 2 or lines[-2] not in {"true", "false"}:
        raise AssertionError(f"Malformed preview output: {output!r}")
    return ([Fraction(value) for value in lines[:rounds]],
            lines[-2] == "true", Fraction(lines[-1]))


def make_runner(route, size, rounds):
    """Prepare source outside timing; compile and run it inside each sample."""
    if route not in ROUTES:
        raise ValueError(f"Unknown route: {route}")
    if route.startswith("tiny_"):
        source = (EXAMPLES / "price_preview.tiny").read_text(encoding="utf-8")
        source = source.replace("def size = 16;", f"def size = {size};")
        source = source.replace("def rounds = 3;", f"def rounds = {rounds};")

        def run():
            """Include fresh runtime, frontend, application execution and cleanup."""
            runtime = Runtime(source)
            output = compile_and_run(source, runtime=runtime, stream_output=False,
                                     copy_on_call=route == "tiny_copy")
            return output, runtime

        return run
    source = (EXAMPLES / "price_preview.py").read_text(encoding="utf-8")
    strategy = route.removeprefix("python_")

    def run():
        """Include Python compilation, definitions, execution and output creation."""
        namespace = {"__name__": "argument_isolation_baseline"}
        exec(compile(source, str(EXAMPLES / "price_preview.py"), "exec"), namespace)
        return namespace["run"](size, rounds, strategy), None

    return run


def validate(result, route, size, rounds):
    """Fail on incorrect values, failed controls, or unfreed application buffers."""
    output, runtime = result
    observed = decode(output, rounds)
    expected = oracle(size, rounds, not route.endswith("shared"))
    if observed != expected:
        raise AssertionError(f"{route}: observed {observed!r}, expected {expected!r}")
    if runtime is not None and runtime.heap:
        raise AssertionError(f"{route}: {len(runtime.heap)} live heap allocations")
    return {"preview_totals": [str(value) for value in observed[0]],
            "preserves_original": observed[1], "final_original_total": str(observed[2]),
            "contract_check": "pass" if observed[1] else "expected negative control",
            "live_tiny_heap_allocations": len(runtime.heap) if runtime is not None else None}


def measure(route, size, rounds, repeat):
    """Measure full runs with a warmup and an independently traced allocation run."""
    run = make_runner(route, size, rounds)
    validate(run(), route, size, rounds)
    samples = []
    for _ in range(repeat):
        gc.collect()
        start = time.perf_counter_ns()
        result = run()
        samples.append(time.perf_counter_ns() - start)
        observed = validate(result, route, size, rounds)
        del result
    gc.collect()
    tracemalloc.start()
    try:
        result = run()
        retained, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    validate(result, route, size, rounds)
    return {"route": route, "size": size, "rounds": rounds, "samples_ns": samples,
            "median_ns": statistics.median(samples), "traced_retained_bytes": retained,
            "traced_peak_bytes": peak, "observed": observed}


def counterexamples():
    """Execute and check the deliberately bounded and negative design witnesses."""
    try:
        compile_and_run(cases.GLOBAL_ALIAS, copy_on_call=True, stream_output=False)
    except TinyLangError as error:
        if "protected parameter" not in str(error):
            raise
        global_tiny = "protected parameter error"
    else:
        raise AssertionError("Global alias escaped protection")
    receiver = compile_and_run(cases.METHOD_RECEIVER, copy_on_call=True, stream_output=False)
    nested = compile_and_run(cases.NESTED_CALL, copy_on_call=True, stream_output=False)
    assert [Fraction(x) for x in receiver.splitlines()] == [Fraction(4003, 4)] * 2
    assert [Fraction(x) for x in nested.splitlines()] == [Fraction(4001, 4)] * 2
    runtime = Runtime(cases.DISCARDED_HEAP)
    output = compile_and_run(cases.DISCARDED_HEAP, runtime=runtime, copy_on_call=True,
                             stream_output=False)
    assert output.strip() == "1" and len(runtime.heap) == 1
    results = {
        "global_alias_tiny": global_tiny,
        "global_alias_python_deepcopy": cases.python_global_alias(),
        "shared_method_receiver_tiny": receiver.splitlines(),
        "nested_nonadoption_tiny": nested.splitlines(),
        "nested_python_outer_copy_only": cases.python_nested(False),
        "nested_python_copy_each_call": cases.python_nested(True),
        "nested_rows_python_shallow": cases.python_nested_rows(False),
        "nested_rows_python_deepcopy": cases.python_nested_rows(True),
        "discarded_tiny_heap_copy_live_allocations": len(runtime.heap),
    }
    assert results["global_alias_python_deepcopy"] == [1000.75, 1000.25]
    assert results["nested_python_outer_copy_only"] == [1000.25, 1000.75]
    assert results["nested_python_copy_each_call"] == [1000.25, 1000.25]
    assert results["nested_rows_python_shallow"] == [1000.75, 1000.75]
    assert results["nested_rows_python_deepcopy"] == [1000.25, 1000.75]
    return results


def source_hashes():
    """Bind the experiment to maintained interpreter sources and fixed protocol."""
    paths = [*sorted((ROOT / "src").rglob("*.py")), *sorted(EXAMPLES.glob("*.py")),
             EXAMPLES / "price_preview.tiny", PROTOCOL, Path(__file__).resolve(),
             ROOT / "tests/test_argument_isolation_experiment.py"]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def main(argv=None):
    """Write checked observations, raw samples and reproducible source identities."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[16, 256, 1024])
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--repeat", type=int, default=7)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/argument-isolation/experiment.json")
    args = parser.parse_args(argv)
    if min([args.rounds, args.repeat, *args.sizes]) < 1:
        parser.error("sizes, rounds and repeat must be positive")
    before = source_hashes()
    witnesses = counterexamples()
    # Rotate the route order between sizes to reduce fixed-order bias. This is
    # still one process on one host, not a controlled performance comparison.
    results = []
    for index, size in enumerate(args.sizes):
        offset = index % len(ROUTES)
        for route in ROUTES[offset:] + ROUTES[:offset]:
            results.append(measure(route, size, args.rounds, args.repeat))
            print(f"Validated {route}, size={size}", flush=True)
    if source_hashes() != before:
        raise AssertionError("Experiment sources changed during measurement")
    report = {
        "schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                text=True).strip(),
        "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
        "scope": "Working-tree design experiment; no release or cross-platform qualification",
        "protocol_sha256": before[PROTOCOL.relative_to(ROOT).as_posix()],
        "source_sha256": before, "source_changed_during_run": False,
        "sizes": args.sizes, "rounds": args.rounds, "repeat": args.repeat, "warmup": 1,
        "timing_region": "Compile/lint, fresh runtime/definitions, input, previews, output and cleanup; imports cached",
        "memory_scope": "Separate tracemalloc Python allocation peak, not RSS or total process memory",
        "counterexamples": witnesses, "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} validated application measurements to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
