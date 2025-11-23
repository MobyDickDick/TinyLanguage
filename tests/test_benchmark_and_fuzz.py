import random
import time

import pathlib
import sys

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


def test_recursive_fibonacci_benchmark(record_property) -> None:
    start = time.perf_counter()
    output = compile_and_run(FIBONACCI_PROGRAM)
    duration = time.perf_counter() - start

    record_property("fibonacci_runtime_s", duration)
    assert output.strip() == "55"
    # Simple guardrail to detect major slowdowns without being flaky
    assert duration < 2.0


def _random_statement(rng: random.Random) -> str:
    choice = rng.random()
    if choice < 0.35:
        value = rng.randint(0, 20)
        return f"define v{rng.randint(0, 5)} = {value};"
    if choice < 0.7:
        target = rng.choice(["0", "1", "2", f"v{rng.randint(0, 5)}"])
        return f"print({target});"

    token_pool = ["define", "=", "{", "}", "(", ")", "+", "-", "*", ";", "foo", "bar", "0", "1", "2"]
    size = rng.randint(3, 12)
    return " ".join(rng.choice(token_pool) for _ in range(size))


def test_randomized_programs_do_not_crash() -> None:
    rng = random.Random(1337)
    for _ in range(50):
        src = "\n".join(_random_statement(rng) for _ in range(rng.randint(2, 6)))
        try:
            compile_and_run(src)
        except (TinyLangError, RuntimeError):
            # Parser/semantic failures are expected for malformed sources
            continue
