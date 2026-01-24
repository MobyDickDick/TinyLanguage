"""Tests for number intervall."""

import math
import pathlib


def load_number_intervall() -> str:
    """Helper to load number intervall."""
    return (pathlib.Path(__file__).resolve().parents[2] / "src_tiny" / "number_intervall.tiny").read_text()


def load_number_class() -> str:
    """Helper to load number class."""
    return (pathlib.Path(__file__).resolve().parents[2] / "src_tiny" / "number_class.tiny").read_text()


def test_basic_interval_operations_and_formatting(run_tiny_source):
    """Test that basic interval operations and formatting."""
    interval_def = load_number_intervall()
    extra = """
    def a = NumberIntervall(0, 1);
    def b = NumberIntervall(1, 2);
    def div_base = NumberIntervall(2, 4);
    def divisor = NumberIntervall(1, 2);

    def sum = a + b;
    def diff = b - a;
    def prod = a * b;
    def quot = div_base / divisor;

    print(sum.to_string());
    print(diff.to_string());
    print(prod.to_string());
    print(quot.to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "2.0 +/- 1.0\n1.0 +/- 1.0\n1.0 +/- 1.0\n2.5 +/- 1.5\n"


def test_wrapped_intervals_and_zero_division_expand_to_wrapped_result(run_tiny_source):
    """Test that wrapped intervals and zero division expand to wrapped result."""
    interval_def = load_number_intervall()
    extra = """
    def wrapped = NumberIntervall(1, 0);
    def normal = NumberIntervall(2, 3);
    def with_zero = NumberIntervall(-1, 1);

    def wrap_sum = wrapped + normal;
    def division_issue = normal / with_zero;

    print(wrapped.to_string());
    print(wrap_sum.to_string());
    print(division_issue.to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "0.5 +/- -0.5\nany_number\n[3.0, -3.0]\n"


def test_interval_number_uses_neighboring_floats(run_tiny_source):
    """Test that interval number uses neighboring floats."""
    interval_def = load_number_intervall()

    extra = """
    def around_five = interval_number(5);
    def around_negative = interval_number(-2.5);
    def around_zero = interval_number(0);

    print(around_five.to_string());
    print(around_negative.to_string());
    print(around_zero.to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

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


def test_dividing_infinities_by_zero_spanning_interval_yields_any_number(run_tiny_source):
    """Test that dividing infinities by zero spanning interval yields any number."""
    interval_def = load_number_intervall()

    extra = """
    def plus_inf = __intervall_with_error("plus_infinity");
    def minus_inf = __intervall_with_error("minus_infinity");
    def crosses_zero = NumberIntervall(-2, 3);

    print((plus_inf / crosses_zero).to_string());
    print((minus_inf / crosses_zero).to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "any_number\nany_number\n"


def test_dividing_zero_spanning_intervals_yields_wrapped_interval(run_tiny_source):
    """Test that dividing zero spanning intervals yields wrapped interval."""
    interval_def = load_number_intervall()

    extra = """
    def numerator = NumberIntervall(-2, 3);
    def denominator = NumberIntervall(-5, 0.5);

    print((numerator / denominator).to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "[6.0, -4.0]\n"


def test_division_results_with_infinite_bounds(run_tiny_source):
    """Test that division results with infinite bounds."""
    interval_def = load_number_intervall()

    extra = """
    def base = NumberIntervall(1, 1);
    def crosses_zero = NumberIntervall(-1, 1);
    def touches_zero_positive = NumberIntervall(0, 1);
    def touches_zero_negative = NumberIntervall(-1, 0);

    def upper_inf = base / touches_zero_positive;
    def lower_inf = base / touches_zero_negative;
    def wrapped_denominator = NumberIntervall(1, -1);

    print((base / crosses_zero).to_string());
    print(upper_inf.to_string());
    print(lower_inf.to_string());
    print((base / wrapped_denominator).to_string());
    print((base / upper_inf).to_string());
    print((base / lower_inf).to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "[1.0, -1.0]\n[1.0, infinity]\n[-infinity, -1.0]\n[-1.0, 1.0]\n[0, 1.0]\n[-1.0, 0]\n"


def test_python_numbers_promote_to_intervals(run_tiny_source):
    """Test that python numbers promote to intervals."""
    interval_def = load_number_intervall()
    number_def = load_number_class()

    extra = """
    def a = Number(5);
    def b = NumberIntervall(6, 7);
    def c = 42 * a;
    def d = (9 * c) * b;

    print(c.to_string());
    print(d.to_string());
    """

    out = run_tiny_source(number_def + "\n" + interval_def + "\n" + extra)

    baseline = "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"

    assert out == baseline + "210\n12285.0 +/- 945.0\n"
