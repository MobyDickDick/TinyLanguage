"""Namespace scoping checks inspired by the README tutorial snippet.

Functions with identical names live in separate namespaces and can cooperate
without shadowing each other.
"""

from tests.utils import run_tiny


def test_parallel_namespaces_and_local_calls():
    """Ensure namespace-qualified calls remain isolated."""
    out = run_tiny(
        """
        namespace Math {
            fn add(a, b) { return a + b; }
            fn inc(x) { return add(x, 1); }
        }

        namespace Strings {
            fn add(a, b) { return a + b; }
            fn exclaim(text) { return add(text, "!"); }
        }

        print(Math.add(2, 3));
        print(Math.inc(4));
        print(Strings.exclaim("go"));
        """
    )

    # Each namespace keeps its own add implementation.
    assert out == "5\n5\ngo!\n"
