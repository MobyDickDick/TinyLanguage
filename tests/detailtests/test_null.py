import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src"))

from tests.utils import run_tiny


def test_null_literal_prints():
    out = run_tiny(
        """
        print(Null);
        """,
    )
    assert out == "Null\n"


def test_null_is_falsy_and_zero_like_in_arithmetic():
    out = run_tiny(
        """
        define a = Null;
        if (a) { print(1); } else { print(2); }
        print(a + 5);
        print(3 + Null);
        """,
    )
    assert out == "2\n5\n3\n"


def test_null_can_be_compared():
    out = run_tiny(
        """
        define val = Null;
        print(val == Null);
        print(val == 0);
        """,
    )
    assert out == "true\ntrue\n"
