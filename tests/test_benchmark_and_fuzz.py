import importlib.util
import multiprocessing
import pathlib
import random
import signal
import sys
import time
from contextlib import contextmanager
from typing import List, Tuple

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import TinyLangError, compile_and_run


FIBONACCI_PROGRAM = """
fn fib(n) {
    if (n < 2) { return n; }
    return fib(n - 1) + fib(n - 2);
}

print(fib(10));
"""


@contextmanager
def _time_limit(seconds: float):
    def _timeout_handler(signum, frame):
        raise TimeoutError(f"program exceeded {seconds:.2f}s time limit")

    if not hasattr(signal, "setitimer"):
        # setitimer is missing on Windows; enforcement handled elsewhere.
        yield
        return

    previous = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _worker_run_program(queue: multiprocessing.Queue, source: str) -> None:
    """Helper to run ``compile_and_run`` in a child process."""

    try:
        compile_and_run(source)
    except Exception as exc:  # pragma: no cover - subprocess bridge
        queue.put(("error", exc))
    else:  # pragma: no cover - subprocess bridge
        queue.put(("ok", None))


def _run_program_with_timeout(source: str, seconds: float) -> None:
    """Run ``compile_and_run`` with a timeout on all platforms."""

    if hasattr(signal, "setitimer"):
        with _time_limit(seconds):
            compile_and_run(source)
        return

    # ``spawn`` has noticeable process-start overhead on Windows; add a
    # generous buffer so legitimate programs are not incorrectly flagged as
    # hung while still enforcing a hard upper bound.
    # Give the worker ample time to start up and finish even on slower
    # machines while still bounding total runtime. A larger buffer keeps the
    # fuzz test stable on Windows where spawning carries noticeable overhead
    # and child creation can vary widely based on host load.
    padded_seconds = max(seconds * 12, seconds + 8.0)

    ctx = multiprocessing.get_context("spawn")
    result_queue: multiprocessing.Queue = ctx.Queue()
    proc = ctx.Process(target=_worker_run_program, args=(result_queue, source))
    proc.start()
    proc.join(padded_seconds)

    if proc.is_alive():
        proc.terminate()
        proc.join()
        raise TimeoutError(
            f"program exceeded {seconds:.2f}s time limit "
            f"({padded_seconds:.2f}s with spawn overhead)"
        )

    if result_queue.empty():  # pragma: no cover - defensive
        return

    status, payload = result_queue.get()
    if status == "error":
        raise payload


def test_recursive_fibonacci_benchmark(record_property) -> None:
    start = time.perf_counter()
    output = compile_and_run(FIBONACCI_PROGRAM)
    duration = time.perf_counter() - start

    record_property("fibonacci_runtime_s", duration)
    assert output.strip() == "55"
    # Simple guardrail to detect major slowdowns without being flaky
    assert duration < 2.0


def _random_expression(
    rng: random.Random, defined_vars: List[str], used_vars: set[str], depth: int = 0
) -> str:
    leaf_options = ["0", "1", "2", "true", "false"] + defined_vars
    if depth > 2 or rng.random() < 0.4:
        choice = rng.choice(leaf_options)
        if choice in defined_vars:
            used_vars.add(choice)
        return choice

    operator = rng.choice(["+", "-", "*", "/", "==", "<", ">", "&&", "||"])
    left = _random_expression(rng, defined_vars, used_vars, depth + 1)
    right = _random_expression(rng, defined_vars, used_vars, depth + 1)
    if rng.random() < 0.2:
        return f"({left} {operator} {right})"
    return f"{left} {operator} {right}"


def _random_statement(rng: random.Random, defined_vars: List[str], used_vars: set[str]) -> str:
    choice = rng.random()
    if choice < 0.25:
        new_var = f"v{rng.randint(0, max(5, len(defined_vars) + 2))}"
        defined_vars.append(new_var)
        value = _random_expression(rng, defined_vars, used_vars)
        used_vars.add(new_var)
        return f"define {new_var} = {value}; print({new_var});"
    if choice < 0.5:
        target = _random_expression(rng, defined_vars, used_vars)
        return f"print({target});"
    if choice < 0.7:
        body = "\n    ".join(
            _random_statement(rng, defined_vars, used_vars)
            for _ in range(rng.randint(1, 3))
        )
        return f"if ({_random_expression(rng, defined_vars, used_vars)}) {{\n    {body}\n}} else {{ print(0); }}"
    if choice < 0.85:
        loop_var = f"i{rng.randint(0, max(5, len(defined_vars) + 2))}"
        defined_vars.append(loop_var)
        used_vars.add(loop_var)

        # Keep while loops bounded so fuzzing cannot generate programs that spin
        # forever. The explicit counter forces an exit after ``limit``
        # iterations even if the body never changes the condition.
        limit = rng.randint(0, 4)
        body_statements = [
            _random_statement(rng, defined_vars, used_vars)
            for _ in range(rng.randint(1, 2))
        ]
        body_statements.append(f"{loop_var} = {loop_var} + 1;")
        body = "\n    ".join(body_statements)

        return "\n".join(
            [
                f"define {loop_var} = 0;",
                f"while ({loop_var} < {limit}) {{",
                f"    {body}",
                "}",
            ]
        )

    fn_defined_vars = list(defined_vars) + ["a", "b"]
    fn_used_vars: set[str] = set()
    fn_body = [
        _random_statement(rng, fn_defined_vars, fn_used_vars)
        for _ in range(rng.randint(1, 3))
    ]
    for param in ("a", "b"):
        if param not in fn_used_vars:
            fn_body.append(f"print({param});")
            fn_used_vars.add(param)

    body_text = "\n    ".join(fn_body)
    return "\n".join(
        [
            f"fn f{rng.randint(0, 3)}(a, b) {{",
            f"    {body_text}",
            f"    return {_random_expression(rng, fn_defined_vars, fn_used_vars)};",
            "}",
            f"print(f{rng.randint(0, 3)}({_random_expression(rng, defined_vars, used_vars)}, {_random_expression(rng, defined_vars, used_vars)}));",
        ]
    )


def _generate_program(seed: int) -> Tuple[int, str]:
    rng = random.Random(seed)
    size = rng.randint(3, 7)
    defined_vars: List[str] = []
    used_vars: set[str] = set()
    statements = [_random_statement(rng, defined_vars, used_vars) for _ in range(size)]

    for var in defined_vars:
        if var not in used_vars:
            statements.append(f"print({var});")
            used_vars.add(var)

    return seed, "\n".join(statements)


def _record_failures(
    failing: List[int],
    timeouts: List[int],
    runtime_errors: List[int],
    record_property,
):
    record_property("failing_seeds", failing)
    record_property("timeout_seeds", timeouts)
    record_property("runtime_error_seeds", runtime_errors)


def test_randomized_programs_do_not_crash(record_property) -> None:
    rng = random.Random(1337)
    failing_seeds: List[int] = []
    timeout_seeds: List[int] = []
    runtime_error_seeds: List[int] = []
    successes = 0

    # Keep the loop count modest so CI does not cancel the job for taking too
    # long on slower runners while still exercising a broad sample of seeds.
    for _ in range(12):
        seed = rng.getrandbits(32)
        _, src = _generate_program(seed)
        try:
            _run_program_with_timeout(src, 0.5)
            successes += 1
        except TimeoutError:
            timeout_seeds.append(seed)
        except TinyLangError:
            failing_seeds.append(seed)
        except Exception:
            runtime_error_seeds.append(seed)

    _record_failures(failing_seeds, timeout_seeds, runtime_error_seeds, record_property)

    assert not timeout_seeds, f"programs timed out for seeds: {timeout_seeds}"
    assert not runtime_error_seeds, f"unexpected runtime errors for seeds: {runtime_error_seeds}"
    assert successes > 0, "generator did not produce any runnable program"


hypothesis_spec = importlib.util.find_spec("hypothesis")
if hypothesis_spec:  # pragma: no cover - optional
    from hypothesis import given, settings
    from hypothesis import strategies as st

    hypothesis_available = True

    @pytest.mark.skipif(not hypothesis_available, reason="hypothesis not installed")
    # Fewer examples keep CI runtimes short while still providing shrinkable
    # seeds when Hypothesis is available locally.
    @settings(max_examples=10, deadline=1000)
    @given(st.integers(min_value=0, max_value=2**32 - 1))
    def test_randomized_programs_shrink_on_failure(seed: int, record_property):
        seed, src = _generate_program(seed)
        try:
            _run_program_with_timeout(src, 1.0)
        except TimeoutError:
            record_property("timeout_seed", seed)
            pytest.fail(f"program timed out for seed {seed}")
        except TinyLangError:
            record_property("failing_seed", seed)
            pytest.fail(f"program failed to parse for seed {seed}")
        except Exception as exc:
            record_property("runtime_error_seed", seed)
            pytest.fail(f"unexpected runtime error for seed {seed}: {exc}")
else:  # pragma: no cover - optional
    hypothesis_available = False
