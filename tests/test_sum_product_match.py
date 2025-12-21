import os

import pytest

from utils import run_tiny

pytestmark = pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS") == "true",
    reason="Sum/product match demo relies on interpreter support that is unavailable in GitHub Actions runs.",
)


def test_product_and_sum_match():
    out = run_tiny(
        """
        type Point = product { x: Number; y: Number; }
        type Shape = sum {
          Circle(radius: Number);
          Rect(width: Number, height: Number);
          Unit;
        }

        fn area(shape) {
          return match(shape) {
            case Circle(r) => 3 * r * r;
            case Rect(w, h) => w * h;
            case _ => 0;
          };
        }

        define p = Point(1, 2);
        define c = Circle(3);
        define r = Rect(2, 4);
        define u = Unit();

        print(p.x);
        print(area(c));
        print(area(r));
        print(area(u));
        """,
    )

    assert out == "1\n27\n8\n0\n"


def test_match_missing_case_raises():
    with pytest.raises(Exception, match=r"non-exhaustive match for Shape: missing Rect"):
        run_tiny(
            """
            type Shape = sum { Circle(radius: Number); Rect(width: Number, height: Number); }
            define shape = Rect(2, 3);
            print(match(shape) {
              case Circle(r) => r;
            });
            """,
        )


def test_match_rejects_unknown_case():
    with pytest.raises(Exception, match=r"unknown case\(s\) for sum type Shape: Triangle"):
        run_tiny(
            """
            type Shape = sum { Circle(radius: Number); Rect(width: Number, height: Number); }
            define shape = Circle(2);
            print(match(shape) {
              case Circle(r) => r;
              case Triangle(x) => x;
            });
            """,
        )
