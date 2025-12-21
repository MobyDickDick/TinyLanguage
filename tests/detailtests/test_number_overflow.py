import pathlib


def test_number_error_propagation_and_printing(run_tiny_source):
    number_def = (pathlib.Path(__file__).resolve().parents[2] / "src_tiny" / "number_class.tiny").read_text()

    extra = """
    define big = Number(PYTHON_FLOAT_MAX);
    define overflow = big + big;
    print(overflow.to_string());

    define inf = __number_with_error("plus_infinity");
    define propagate = inf + big;
    print(propagate.to_string());

    define divpos = Number(5) / Number(0);
    define divneg = Number(-5) / Number(0);
    define divzero = Number(0) / Number(0);
    define finite = Number(10) / __number_with_error("plus_infinity");

    print(divpos.to_string());
    print(divneg.to_string());
    print(divzero.to_string());
    print(finite.to_string());

    define any = inf - Number(3);
    print(any.to_string());

    define minf = __number_with_error("minus_infinity");
    define any2 = minf + Number(3);
    print(any2.to_string());

    define mul_same = inf * inf;
    define mul_neg = minf * inf;
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
