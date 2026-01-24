"""Tests for semantics suite."""

import textwrap

from tests.utils import run_tiny


def test_semantics_eval_order_for_call_args():
    """Test that semantics eval order for call args."""
    out = run_tiny(
        textwrap.dedent(
            """
            def steps = 0;
            fn mark(v) {
                steps = steps * 10 + v;
                return v;
            }

            fn combine(a, b, c) {
                return a + b + c;
            }

            print(combine(mark(1), mark(2), mark(3)));
            print(steps);
            """
        )
    )

    assert out == "6\n123\n"


def test_semantics_eval_order_for_binops():
    """Test that semantics eval order for binops."""
    out = run_tiny(
        textwrap.dedent(
            """
            def steps = 0;
            fn mark(v) {
                steps = steps * 10 + v;
                return v;
            }

            print(mark(1) + mark(2) * mark(3));
            print(steps);
            """
        )
    )

    assert out == "7\n123\n"


def test_semantics_short_circuit_and_or():
    """Test that semantics short circuit and or."""
    out = run_tiny(
        textwrap.dedent(
            """
            def steps = 0;
            fn mark(v) {
                steps = steps * 10 + v;
                return v;
            }

            print(false and mark(1));
            print(true or mark(2));
            print(steps);
            """
        )
    )

    assert out == "false\ntrue\n0\n"


def test_semantics_eval_order_for_array_literals():
    """Test that semantics eval order for array literals."""
    out = run_tiny(
        textwrap.dedent(
            """
            def steps = 0;
            fn mark(v) {
                steps = steps * 10 + v;
                return v;
            }

            def arr = new[mark(1), mark(2), mark(3)];
            print(len(arr));
            print(steps);
            def _unused = delete(arr);
            """
        )
    )

    assert out == "3\n123\n"
