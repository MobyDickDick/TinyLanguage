import math
import pathlib


def load_number_intervall() -> str:
    return (pathlib.Path(__file__).resolve().parents[1] / "number_intervall.tiny").read_text()


def test_basic_interval_operations_and_formatting(run_tiny_source):
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

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "2.0 +/- 1.0\n1.0 +/- 1.0\n1.0 +/- 1.0\n2.5 +/- 1.5\n"


def test_wrapped_intervals_and_zero_division_expand_to_wrapped_result(run_tiny_source):
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

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "0.5 +/- -0.5\nany_number\n[3.0, -3.0]\n"


def test_interval_number_uses_neighboring_floats(run_tiny_source):
    interval_def = load_number_intervall()

    extra = """
    define around_five = interval_number(5);
    define around_negative = interval_number(-2.5);
    define around_zero = interval_number(0);

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
    interval_def = load_number_intervall()

    extra = """
    define plus_inf = __intervall_with_error("plus_infinity");
    define minus_inf = __intervall_with_error("minus_infinity");
    define crosses_zero = NumberIntervall(-2, 3);

    print((plus_inf / crosses_zero).to_string());
    print((minus_inf / crosses_zero).to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "any_number\nany_number\n"


def test_dividing_zero_spanning_intervals_yields_wrapped_interval(run_tiny_source):
    interval_def = load_number_intervall()

    extra = """
    define numerator = NumberIntervall(-2, 3);
    define denominator = NumberIntervall(-5, 0.5);

    print((numerator / denominator).to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "[6.0, -4.0]\n"


def test_division_results_with_infinite_bounds(run_tiny_source):
    interval_def = load_number_intervall()

    extra = """
    define base = NumberIntervall(1, 1);
    define crosses_zero = NumberIntervall(-1, 1);
    define touches_zero_positive = NumberIntervall(0, 1);
    define touches_zero_negative = NumberIntervall(-1, 0);

    define upper_inf = base / touches_zero_positive;
    define lower_inf = base / touches_zero_negative;
    define wrapped_denominator = NumberIntervall(1, -1);

    print((base / crosses_zero).to_string());
    print(upper_inf.to_string());
    print(lower_inf.to_string());
    print((base / wrapped_denominator).to_string());
    print((base / upper_inf).to_string());
    print((base / lower_inf).to_string());
    """

    out = run_tiny_source(interval_def + "\n" + extra)

    assert out == "[1.0, -1.0]\n[1.0, infinity]\n[-infinity, -1.0]\n[-1.0, 1.0]\n[0, 1.0]\n[-1.0, 0]\n"
