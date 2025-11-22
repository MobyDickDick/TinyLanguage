import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from tiny_language import compile_and_run


def run_tiny(src: str) -> str:
    return compile_and_run(src)


def test_number_error_propagation_and_printing():
    number_def = (pathlib.Path(__file__).resolve().parents[1] / "number_class.tiny").read_text()

    extra = """
    define big = Number(PYTHON_FLOAT_MAX);
    define overflow = big + big;
    print(overflow.error);

    define inf = __number_with_error("plus_infinity");
    define propagate = inf + big;
    print(propagate.error);

    define divpos = Number(5) / Number(0);
    define divneg = Number(-5) / Number(0);
    define divzero = Number(0) / Number(0);
    define finite = Number(10) / __number_with_error("plus_infinity");

    print(divpos.error);
    print(divneg.error);
    print(divzero.error);
    print(finite.value);

    define any = inf - Number(3);
    print(any.error);

    define minf = __number_with_error("minus_infinity");
    define any2 = minf + Number(3);
    print(any2.error);

    define mul_same = inf * inf;
    define mul_neg = minf * inf;
    print(mul_same.error);
    print(mul_neg.error);

    print(divpos);
    """

    out = run_tiny(number_def + "\n" + extra)

    assert (
        out
        == "12.5\n-2.5\n37.5\n0.6666666666666666\n"
        "plus_infinity\nplus_infinity\nplus_infinity\nminus_infinity\nany_number\n0\n"
        "any_number\nany_number\nplus_infinity\nminus_infinity\nplus_infinity\n"
    )
