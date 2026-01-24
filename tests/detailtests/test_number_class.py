"""Tests for number class."""

import pathlib


def load_number_class() -> str:
    """Helper to load number class."""
    return (pathlib.Path(__file__).resolve().parents[2] / "src_tiny" / "number_class.tiny").read_text()


def test_subtraction_infinities_and_overflow(run_tiny_source):
    """Test that subtraction infinities and overflow."""
    number_def = load_number_class()
    baseline = "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"
    extra = """
    def inf = __number_with_error("plus_infinity");
    def minf = __number_with_error("minus_infinity");
    def pos = Number(5);
    def neg = Number(-3);

    def any = inf - pos;
    def keep_inf = inf - neg;
    def plus_from_minus_b = pos - minf;
    def minf_result = minf - pos;
    def minus_from_plus_b = minf - inf;

    print(any.to_string());
    print(keep_inf.to_string());
    print(plus_from_minus_b.to_string());
    print(minf_result.to_string());
    print(minus_from_plus_b.to_string());

    def big = Number(PYTHON_FLOAT_MAX);
    def overflow = big - Number(-PYTHON_FLOAT_MAX);
    print(overflow.to_string());
    """

    out = run_tiny_source(number_def + "\n" + extra)

    assert out == (
        baseline
        + "any_number\n"
        + "plus_infinity\n"
        + "plus_infinity\n"
        + "minus_infinity\n"
        + "minus_infinity\n"
        + "plus_infinity\n"
    )


def test_multiplication_zero_and_infinity_signs(run_tiny_source):
    """Test that multiplication zero and infinity signs."""
    number_def = load_number_class()
    baseline = "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"
    extra = """
    def inf = __number_with_error("plus_infinity");
    def minf = __number_with_error("minus_infinity");
    def zero = Number(0);
    def pos = Number(2);
    def neg = Number(-2);

    def any1 = inf * zero;
    def any2 = zero * minf;
    def pos_inf = inf * pos;
    def neg_inf = inf * neg;
    def pos_inf2 = minf * neg;

    print(any1.to_string());
    print(any2.to_string());
    print(pos_inf.to_string());
    print(neg_inf.to_string());
    print(pos_inf2.to_string());
    """

    out = run_tiny_source(number_def + "\n" + extra)

    assert out == (
        baseline
        + "any_number\n"
        + "any_number\n"
        + "plus_infinity\n"
        + "minus_infinity\n"
        + "plus_infinity\n"
    )


def test_division_with_infinities_and_zero(run_tiny_source):
    """Test that division with infinities and zero."""
    number_def = load_number_class()
    baseline = "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"
    extra = """
    def inf = __number_with_error("plus_infinity");
    def minf = __number_with_error("minus_infinity");
    def pos = Number(8);
    def neg = Number(-8);
    def zero = Number(0);

    def zero_from_inf = pos / inf;
    def zero_from_neg_inf = neg / inf;
    def pos_inf_over_pos = inf / pos;
    def minf_over_neg = minf / neg;
    def pos_over_zero = pos / zero;
    def neg_over_zero = neg / zero;

    print(zero_from_inf.to_string());
    print(zero_from_neg_inf.to_string());
    print(pos_inf_over_pos.to_string());
    print(minf_over_neg.to_string());
    print(pos_over_zero.to_string());
    print(neg_over_zero.to_string());
    """

    out = run_tiny_source(number_def + "\n" + extra)

    assert out == (
        baseline
        + "0\n"
        + "0\n"
        + "plus_infinity\n"
        + "plus_infinity\n"
        + "plus_infinity\n"
        + "minus_infinity\n"
    )


def test_division_rounding_marks_error_code(run_tiny_source):
    """Test that division rounding marks error code."""
    number_def = load_number_class()
    extra = """
    def one = Number(1);
    def two = Number(2);
    def four = Number(4);

    def rounded = one / two;
    def exact = four / two;

    print(rounded.to_string());
    print(exact.to_string());
    """

    out = run_tiny_source(number_def + "\n" + extra)

    assert out.endswith("0.5 (rounded)\n2\n")
