import pytest

from tests.utils import run_tiny
from tiny_language import compile_and_run


def test_sum_type_match_and_bindings():
    out = run_tiny(
        """
        type Option {
          Some { value: number };
          None;
        }

        fn describe(o) {
          return match o {
            case Some { value: v }: v + 1;
            case None: 0;
          };
        }

        def a = Some { value: 3 };
        def b = None {};
        print(describe(a));
        print(describe(b));
        """
    )

    assert out == "4\n0\n"


def test_match_requires_exhaustive_cases():
    with pytest.raises(Exception, match=r"missing cases: None"):
        compile_and_run(
            """
            type Option {
              Some { value: number };
              None;
            }

            fn describe(o) {
              return match o {
                case Some { value: v }: v;
              };
            }

            def a = Some { value: 7 };
            print(describe(a));
            """
        )


def test_match_rejects_unknown_case():
    with pytest.raises(Exception, match=r"unexpected case Maybe for type Option"):
        compile_and_run(
            """
            type Option {
              Some { value: number };
              None;
            }

            fn describe(o) {
              return match o {
                case Some { value: v }: v;
                case Maybe: 0;
                case None: 0;
              };
            }

            def a = Some { value: 2 };
            print(describe(a));
            """
        )
