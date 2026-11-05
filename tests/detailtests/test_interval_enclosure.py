"""Independent rational oracles for the interval contract (work package 8).

The oracle uses direct endpoint formulas and pointwise rational samples. It
never calls the kernel's decode, reciprocal, merge or rounding helpers.
Integration checks print actual Tiny fields; center/radius display is not proof.
"""

from fractions import Fraction as Q
import itertools
import math
from pathlib import Path
import random
import re
import struct
import sys

import pytest

import tiny_intervals as intervals

SOURCE = (Path(__file__).resolve().parents[2] / "src_tiny/number_intervall.tiny").read_text()
NUMBER_SOURCE = (Path(__file__).resolve().parents[2] / "src_tiny/number_class.tiny").read_text()
OPS = {
    "+": lambda x, y: x + y,
    "-": lambda x, y: x - y,
    "*": lambda x, y: x * y,
    "/": lambda x, y: x / y,
}


def fields(iv):
    return dict(zip(("lower", "upper", "error"), iv))


def contains(iv, value):
    """Mathematical membership, independent of the implementation's helpers."""
    lo, hi, status = iv
    if status == "any_number":
        return True
    if status in {"empty_interval", "invalid_number", "approximate"}:
        return False
    if status == "wrapped_interval":
        return value <= hi or value >= lo
    return lo <= value <= hi


def assert_encloses(iv, values):
    assert iv[2] not in {"invalid_number", "approximate"}
    assert not math.isnan(iv[0]) and not math.isnan(iv[1])
    for value in values:
        assert contains(iv, value), (iv, value)


@pytest.mark.parametrize("op", OPS)
def test_finite_bounds_against_direct_exact_endpoint_oracle(op):
    """Tight enclosure for exact extrema, large exponents and subnormal values."""
    rng = random.Random(84721)
    smallest = math.ulp(0.0)
    values = [-sys.float_info.max, -1e300, -2**53, -1.0, -smallest,
              -0.0, smallest, sys.float_info.min, 2**-53, 1.0,
              math.nextafter(1, math.inf), 2**53 + 1, 1e300, sys.float_info.max]
    while len(values) < 94:
        value = struct.unpack(">d", rng.getrandbits(64).to_bytes(8, "big"))[0]
        if math.isfinite(value):
            values.append(value)
    pairs = [(x, x) for x in values]
    pairs += [tuple(sorted(rng.sample(values, 2))) for _ in range(120)]
    for a, b in zip(pairs, pairs[17:] + pairs[:17]):
        if op == "/" and b[0] <= 0 <= b[1]:
            continue
        endpoints = [OPS[op](Q(x), Q(y)) for x in a for y in b]
        lo, hi = min(endpoints), max(endpoints)
        # Inputs are supplied exactly, bypassing constructor quantization here.
        result = intervals.binary(op, fields((*a, "normal")), fields((*b, "normal")))
        assert_encloses(result, [lo, hi])
        # Tightness: moving a finite output endpoint inward must lose an extremum.
        if math.isfinite(result[0]):
            inward = math.nextafter(result[0], math.inf)
            assert math.isinf(inward) or Q(inward) > lo
        if math.isfinite(result[1]):
            inward = math.nextafter(result[1], -math.inf)
            assert math.isinf(inward) or Q(inward) < hi


@pytest.mark.parametrize("op", OPS)
def test_pointwise_oracle_for_ordinary_wrapped_unbounded_and_empty_sets(op):
    sets = [(-2, 3, "normal"), (0, 0, "normal"), (1, 4, "normal"),
            (-4, -1, "normal"), (-2, 0, "normal"), (0, 3, "normal"),
            (2, -1, "wrapped_interval"), (-1, -3, "wrapped_interval"),
            (3, 1, "wrapped_interval"), (-math.inf, -2, "lower_bound_is_minus_infinity"),
            (2, math.inf, "upper_bound_is_plus_infinity"), intervals.ENTIRE, intervals.EMPTY]
    samples = [Q(n, d) for n in (-100, -7, -4, -2, -1, 0, 1, 2, 3, 6, 100)
               for d in (1, 3, 1024)]
    for a, b in itertools.product(sets, repeat=2):
        result = intervals.binary(op, fields(a), fields(b))
        exact = [OPS[op](x, y) for x in samples if contains(a, x)
                 for y in samples if contains(b, y) and (op != "/" or y)]
        assert_encloses(result, exact)
        if a == intervals.EMPTY or b == intervals.EMPTY or (op == "/" and b == (0, 0, "normal")):
            assert result == intervals.EMPTY


@pytest.mark.parametrize("numerator,denominator,expected", [
    ((-2, 3), (-5, .5), intervals.ENTIRE),
    ((0, 3), (-5, .5), intervals.ENTIRE),
    ((0, 0), (-5, .5), (0., 0., "normal")),
    ((2, 3), (-1, 1), (2., -2., "wrapped_interval")),
    ((-3, -2), (-1, 1), (2., -2., "wrapped_interval")),
    ((-3, -2), (0, 1), (-math.inf, -2., "lower_bound_is_minus_infinity")),
    ((2, 3), (-1, 0), (-math.inf, -2., "lower_bound_is_minus_infinity")),
    ((-3, 0), (0, 1), (-math.inf, 0., "lower_bound_is_minus_infinity")),
    ((0, 0), (0, 1), (0., 0., "normal")),
    ((1, 1), (0, 0), intervals.EMPTY),
    ((0, 0), (0, 0), intervals.EMPTY),
])
def test_zero_divisor_set_cases(numerator, denominator, expected):
    result = intervals.binary("/", fields((*numerator, "normal")), fields((*denominator, "normal")))
    assert result == expected


@pytest.mark.parametrize("value", [0., -0., math.ulp(0.), -math.ulp(0.), 2**53, -2**53, 1e300, -1e300])
def test_neighbors_use_infinite_directions(value):
    assert intervals.neighboring(value) == (math.nextafter(value, -math.inf),
                                           math.nextafter(value, math.inf), "normal")


def test_constructors_extreme_integers_overflow_nan_and_empty():
    for value in [2**53 + 1, -(2**53 + 1), 10**400, -10**400]:
        assert_encloses(intervals.bounds(value, value), [Q(value)])
    assert intervals.bounds(math.nan, 1) == intervals.INVALID
    assert intervals.bounds(0, math.nan) == intervals.INVALID
    assert intervals.bounds(True, 1) == intervals.INVALID
    assert intervals.bounds(math.inf, math.inf) == intervals.EMPTY
    assert intervals.bounds(-math.inf, -math.inf) == intervals.EMPTY
    assert intervals.bounds(math.inf, -math.inf) == intervals.EMPTY
    assert intervals.bounds(2, -1) == (2., -1., "wrapped_interval")
    assert intervals.bounds(0, 0, "unexpected") == intervals.INVALID
    assert intervals.neighboring(math.nan) == intervals.INVALID
    assert intervals.neighboring(math.inf) == intervals.ENTIRE
    assert intervals.neighboring(sys.float_info.max) == (
        math.nextafter(sys.float_info.max, -math.inf), math.inf, "upper_bound_is_plus_infinity")


@pytest.mark.parametrize("op", OPS)
def test_invalid_and_approximate_states_cannot_claim_enclosure(op):
    for error in ["invalid_number", "approximate", "unknown"]:
        invalid = fields((0, 0, error))
        for other in [fields((1, 2, "normal")), fields(intervals.EMPTY)]:
            assert intervals.binary(op, invalid, other) == intervals.INVALID
            assert intervals.binary(op, other, invalid) == intervals.INVALID


def test_exterior_gap_rounds_inwards_and_zero_times_unbounded_is_zero():
    result = intervals.binary("/", fields((1, 2, "normal")), fields((-3, 3, "normal")))
    assert result[2] == "wrapped_interval"
    assert result[0] <= Q(1, 3) and result[1] >= -Q(1, 3)
    assert Q(math.nextafter(result[0], math.inf)) > Q(1, 3)
    assert Q(math.nextafter(result[1], -math.inf)) < -Q(1, 3)
    assert intervals.binary("*", fields(intervals.ENTIRE), fields((0, 0, "normal"))) == (0., 0., "normal")


def tiny_results(run_tiny_source, expressions, prefix="", setup=""):
    statements = []
    for i, expression in enumerate(expressions):
        statements.append(f"def result{i} = {expression};\n"
                          f"print(result{i}.lower); print(result{i}.upper); print(result{i}.error);")
    lines = run_tiny_source(prefix + SOURCE + "\n" + setup + "\n" + "\n".join(statements)).splitlines()
    return [(float(lines[i]), float(lines[i + 1]), lines[i + 2]) for i in range(0, len(lines), 3)]


def test_both_reported_defects_with_independent_exact_oracles(run_tiny_source):
    quotient, total = tiny_results(run_tiny_source, [
        "NumberIntervall(-2, 3) / NumberIntervall(-5, 0.5)",
        "NumberIntervall(1, 1) + NumberIntervall(2 ^ -53, 2 ^ -53)",
    ])
    # Choosing y sufficiently close to zero realizes arbitrary positive/negative
    # quotients; zero is realized by x=0. The whole real line is required.
    assert quotient == intervals.ENTIRE
    assert_encloses(total, [Q(1) + Q(1, 2**53)])
    assert total == (1., math.nextafter(1., math.inf), "normal")


@pytest.mark.parametrize("op", OPS)
def test_tiny_extreme_arithmetic_uses_the_same_guaranteed_contract(run_tiny_source, op):
    pairs = [(.1, .2), (1., 2**-53), (sys.float_info.max, 2.),
             (-sys.float_info.max, 2.), (math.ulp(0.), .5),
             (-math.ulp(0.), .5), (sys.float_info.min, 3.)]
    expressions = [f"NumberIntervall({a!r}, {a!r}) {op} NumberIntervall({b!r}, {b!r})"
                   for a, b in pairs]
    results = tiny_results(run_tiny_source, expressions)
    for (a, b), result in zip(pairs, results):
        assert_encloses(result, [OPS[op](Q(a), Q(b))])


def test_documented_migration_example_executes_verbatim(run_tiny_source):
    text = (Path(__file__).resolve().parents[2] / "docs/interval_arithmetic_contract.md").read_text()
    example = re.search(r"```tiny\n(.*?)```", text, re.DOTALL)
    assert example
    assert run_tiny_source(SOURCE + "\n" + example.group(1)) == (
        "any_number\n1.0\n1.0000000000000002\nnormal\n")


@pytest.mark.parametrize("copy_on_call", [False, True])
def test_tiny_operators_promotions_and_chained_states(copy_on_call):
    from tiny_language import compile_and_run

    def run_source(source):
        return compile_and_run(source, copy_on_call=copy_on_call, stream_output=False)

    results = tiny_results(run_source, [
        "NumberIntervall(2, 3) / NumberIntervall(-1, 1)",
        "(NumberIntervall(2, 3) / NumberIntervall(-1, 1)) * NumberIntervall(0, 0)",
        "NumberIntervall(1, 1) / (NumberIntervall(1, 1) / NumberIntervall(0, 1))",
        "NumberIntervall(1, 1) / NumberIntervall(0, 0)",
        "(NumberIntervall(1, 1) / NumberIntervall(0, 0)) + 3",
        "Number(9007199254740993) + NumberIntervall(0, 0)",
        "NumberIntervall(0, 0) + 9007199254740993",
        "NumberIntervall(0, 0) + __number_with_error(\"plus_infinity\")",
        "NumberIntervall(0, 0) + __number_with_error(\"rounded\")",
        "NumberIntervall(0, 0) + (Number(1) / Number(3))",
        "NumberIntervall(0, 0) + 1e309",
        "Number(1e309) + NumberIntervall(0, 0)",
        "NumberIntervall(0, 0) + Number(-1e309)",
        "NumberIntervall(0, 0) + Number(1e309 - 1e309)",
        "NumberIntervall(0, 0) + __number_with_error(\"unknown\")",
    ], prefix=NUMBER_SOURCE.split("// Sample calculations.")[0])
    assert results[:5] == [(2., -2., "wrapped_interval"), (0., 0., "normal"),
                           (0., 1., "normal"), intervals.EMPTY, intervals.EMPTY]
    for result in results[5:7]:
        assert_encloses(result, [Q(9007199254740993)])
    assert results[7] == intervals.ENTIRE
    assert results[8] == (0., 0., "normal")
    assert results[9] == (1 / 3, 1 / 3, "normal")
    assert results[10:13] == [intervals.ENTIRE] * 3
    assert results[13:] == [intervals.INVALID] * 2


@pytest.mark.parametrize("expression", [
    "Math.abs(a)", "Math.min(a, b)", "Math.max(a, b)", "Math.pow(a, b)",
    "Math.sqrt(a)", "Math.round(a)", "Math.round(a, 2)", "Math.floor(a)",
    "Math.ceil(a)", "Math.clamp(a, b, c)",
])
def test_legacy_math_estimates_are_explicitly_excluded_from_enclosure(run_tiny_source, expression):
    setup = "def a = NumberIntervall(1, 2);"
    if "b" in expression.split("(", 1)[1]:
        setup += "def b = NumberIntervall(2, 3);"
    if "c" in expression.split("(", 1)[1]:
        setup += "def c = NumberIntervall(4, 5);"
    result, chained = tiny_results(
        run_tiny_source, [expression, f"({expression}) + a"],
        setup=setup)
    assert result[2] == "approximate"
    assert chained == intervals.INVALID
