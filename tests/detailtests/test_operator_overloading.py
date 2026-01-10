"""Focused operator overloading scenarios adapted from `all_features.tiny`'s Box example.

The tests verify that user-defined operators participate in dispatch for custom
record-like payloads and keep returning the wrapped values.
"""

from tests.utils import run_tiny


def test_box_addition_and_equality():
    out = run_tiny(
        """
        fn box(v) { return { __tag__: "Box", value: v }; }
        fn unbox(b) { return b.value; }

        operator + (a: Box, b: Box) -> Box { return box(unbox(a) + unbox(b)); }
        operator == (a: Box, b: Box) -> Bool { return unbox(a) == unbox(b); }

        def left = box(2);
        def right = box(3);
        def summed = left + right;
        print(unbox(summed));

        if (left == right) {
            print("boxes equal");
        } else {
            print("boxes differ");
        }
        """
    )

    assert out == "5\nboxes differ\n"
