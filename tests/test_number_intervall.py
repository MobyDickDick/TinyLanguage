import math
import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import compile_and_run


def run_tiny(src: str) -> str:
    return compile_and_run(src)


def load_number_intervall() -> str:
    return (pathlib.Path(__file__).resolve().parents[1] / "number_intervall.tiny").read_text()


def test_basic_interval_operations_and_formatting():
    interval_def = load_number_intervall()
    extra = """
    define a = NumberIntervall(0, 1);
    define b = NumberIntervall(1, 2);
    define div_base = NumberIntervall(2, 4);
    define divisor = NumberIntervall(1, 2);

    define sum = a + b;
    define diff = b - a;
    define prod = a * b;
    define quot = div_base / divisor;

    print(sum.to_string());
    print(diff.to_string());
    print(prod.to_string());
    print(quot.to_string());
    """

    out = run_tiny(interval_def + "\n" + extra)

    assert out == "2.0 +/- 1.0\n1.0 +/- 1.0\n1.0 +/- 1.0\n2.5 +/- 1.5\n"


def test_wrapped_intervals_and_zero_division_expand_to_any_number():
    interval_def = load_number_intervall()
    extra = """
    define wrapped = NumberIntervall(1, 0);
    define normal = NumberIntervall(2, 3);
    define with_zero = NumberIntervall(-1, 1);

    define wrap_sum = wrapped + normal;
    define division_issue = normal / with_zero;

    print(wrapped.to_string());
    print(wrap_sum.to_string());
    print(division_issue.to_string());
    """

    out = run_tiny(interval_def + "\n" + extra)

    assert out == "0.5 +/- -0.5\nany_number\nany_number\n"


def test_interval_number_uses_neighboring_floats():
    interval_def = load_number_intervall()

    extra = """
    define around_five = interval_number(5);
    define around_negative = interval_number(-2.5);
    define around_zero = interval_number(0);

    print(around_five.to_string());
    print(around_negative.to_string());
    print(around_zero.to_string());
    """

    out = run_tiny(interval_def + "\n" + extra)

    def expected_line(value: float) -> str:
        lower = math.nextafter(value, value - 1)
        upper = math.nextafter(value, value + 1)
        center = (lower + upper) / 2
        radius = (upper - lower) / 2
        return f"{center} +/- {radius}\n"

    assert out == (
        expected_line(5)
        + expected_line(-2.5)
        + expected_line(0)
    )


def test_dividing_infinities_by_zero_spanning_interval_yields_any_number():
    interval_def = load_number_intervall()

    extra = """
    define plus_inf = __intervall_with_error("plus_infinity");
    define minus_inf = __intervall_with_error("minus_infinity");
    define crosses_zero = NumberIntervall(-2, 3);

    print((plus_inf / crosses_zero).to_string());
    print((minus_inf / crosses_zero).to_string());
    """

    out = run_tiny(interval_def + "\n" + extra)

    assert out == "any_number\nany_number\n"
