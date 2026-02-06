"""Tests for number overflow."""

import pathlib


def test_number_error_propagation_and_printing(run_tiny_source):
    """Test that number error propagation and printing."""
    number_def = (pathlib.Path(__file__).resolve().parents[2] / "src_tiny" / "number_class.tiny").read_text()

    extra = """
    def big = Number(PYTHON_FLOAT_MAX);
    def overflow = big + big;
    print(overflow.to_string());

    def inf = __number_with_error("plus_infinity");
    def propagate = inf + big;
    print(propagate.to_string());

    def divpos = Number(5) / Number(0);
    def divneg = Number(-5) / Number(0);
    def divzero = Number(0) / Number(0);
    def finite = Number(10) / __number_with_error("plus_infinity");

    print(divpos.to_string());
    print(divneg.to_string());
    print(divzero.to_string());
    print(finite.to_string());

    def any = inf - Number(3);
    print(any.to_string());

    def minf = __number_with_error("minus_infinity");
    def any2 = minf + Number(3);
    print(any2.to_string());

    def mul_same = inf * inf;
    def mul_neg = minf * inf;
    print(mul_same.to_string());
    print(mul_neg.to_string());

    print(divpos.to_string());
    """

    out = run_tiny_source(number_def + "\n" + extra)

    assert (
        out
        == "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"
        "plus_infinity\nplus_infinity\nplus_infinity\nminus_infinity\nany_number\n0\n"
        "any_number\nany_number\nplus_infinity\nminus_infinity\nplus_infinity\n"
    )


def test_number_overflow_edges(run_tiny_source):
    """Test numeric overflow edges for multiplication and subtraction."""
    number_def = (pathlib.Path(__file__).resolve().parents[2] / "src_tiny" / "number_class.tiny").read_text()

    extra = """
    def big = Number(PYTHON_FLOAT_MAX);
    def overflow_mul = big * Number(2);
    print(overflow_mul.to_string());

    def neg_big = Number(PYTHON_FLOAT_MIN);
    def overflow_sub = neg_big - Number(2);
    print(overflow_sub.to_string());

    def normal = Number(1) - Number(2);
    print(normal.to_string());
    """

    out = run_tiny_source(number_def + "\n" + extra)

    assert (
        out
        == "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"
        "plus_infinity\nminus_infinity\n-1\n"
    )
