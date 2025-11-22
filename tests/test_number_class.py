import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import compile_and_run


def run_tiny(src: str) -> str:
    return compile_and_run(src)


def load_number_class() -> str:
    return (pathlib.Path(__file__).resolve().parents[1] / "number_class.tiny").read_text()


def test_subtraction_infinities_and_overflow():
    number_def = load_number_class()
    baseline = "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"
    extra = """
    define inf = __number_with_error("plus_infinity");
    define minf = __number_with_error("minus_infinity");
    define pos = Number(5);
    define neg = Number(-3);

    define any = inf - pos;
    define keep_inf = inf - neg;
    define plus_from_minus_b = pos - minf;
    define minf_result = minf - pos;
    define minus_from_plus_b = minf - inf;

    print(any.to_string());
    print(keep_inf.to_string());
    print(plus_from_minus_b.to_string());
    print(minf_result.to_string());
    print(minus_from_plus_b.to_string());

    define big = Number(PYTHON_FLOAT_MAX);
    define overflow = big - Number(-PYTHON_FLOAT_MAX);
    print(overflow.to_string());
    """

    out = run_tiny(number_def + "\n" + extra)

    assert out == (
        baseline
        + "any_number\n"
        + "plus_infinity\n"
        + "plus_infinity\n"
        + "minus_infinity\n"
        + "minus_infinity\n"
        + "plus_infinity\n"
    )


def test_multiplication_zero_and_infinity_signs():
    number_def = load_number_class()
    baseline = "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"
    extra = """
    define inf = __number_with_error("plus_infinity");
    define minf = __number_with_error("minus_infinity");
    define zero = Number(0);
    define pos = Number(2);
    define neg = Number(-2);

    define any1 = inf * zero;
    define any2 = zero * minf;
    define pos_inf = inf * pos;
    define neg_inf = inf * neg;
    define pos_inf2 = minf * neg;

    print(any1.to_string());
    print(any2.to_string());
    print(pos_inf.to_string());
    print(neg_inf.to_string());
    print(pos_inf2.to_string());
    """

    out = run_tiny(number_def + "\n" + extra)

    assert out == (
        baseline
        + "any_number\n"
        + "any_number\n"
        + "plus_infinity\n"
        + "minus_infinity\n"
        + "plus_infinity\n"
    )


def test_division_with_infinities_and_zero():
    number_def = load_number_class()
    baseline = "12.5\n-2.5\n37.5\n0.6666666666666666 (rounded)\n"
    extra = """
    define inf = __number_with_error("plus_infinity");
    define minf = __number_with_error("minus_infinity");
    define pos = Number(8);
    define neg = Number(-8);
    define zero = Number(0);

    define zero_from_inf = pos / inf;
    define zero_from_neg_inf = neg / inf;
    define pos_inf_over_pos = inf / pos;
    define minf_over_neg = minf / neg;
    define pos_over_zero = pos / zero;
    define neg_over_zero = neg / zero;

    print(zero_from_inf.to_string());
    print(zero_from_neg_inf.to_string());
    print(pos_inf_over_pos.to_string());
    print(minf_over_neg.to_string());
    print(pos_over_zero.to_string());
    print(neg_over_zero.to_string());
    """

    out = run_tiny(number_def + "\n" + extra)

    assert out == (
        baseline
        + "0\n"
        + "0\n"
        + "plus_infinity\n"
        + "plus_infinity\n"
        + "plus_infinity\n"
        + "minus_infinity\n"
    )


def test_division_rounding_marks_error_code():
    number_def = load_number_class()
    extra = """
    define one = Number(1);
    define two = Number(2);
    define four = Number(4);

    define rounded = one / two;
    define exact = four / two;

    print(rounded.to_string());
    print(exact.to_string());
    """

    out = run_tiny(number_def + "\n" + extra)

    assert out.endswith("0.5 (rounded)\n2\n")
