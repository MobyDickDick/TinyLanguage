"""Rosetta example: factorial (iterative).

Purpose
-------
Demonstrate an iterative computation of the factorial function and print the
result for a small input. This example mirrors a typical Rosetta Code task.

Definition
----------
factorial(n) = 1 * 2 * 3 * ... * n   for n >= 0
with factorial(0) = 1.

What it demonstrates
--------------------
- A basic `while` loop
- Integer multiplication and reassignment
- A function that returns a computed value
- Printing the result to stdout

Complexity
----------
Time:  O(n)
Space: O(1)

Notes / edge cases
------------------
- For n in {0, 1} the loop body is skipped and the function returns 1.
- For negative n, the loop condition `i <= n` is false initially, so the
  function also returns 1. If you want to reject negative inputs, add:

    if n < 0:
        raise ValueError("n must be >= 0")

Expected output
---------------
For n = 5 the program prints:

    120
"""


def factorial(n: int) -> int:
    """Compute n! iteratively.

    Parameters
    ----------
    n:
        The input value.

    Returns
    -------
    int
        The factorial of `n`.

    See Notes in the module docstring for behavior on negative inputs.
    """
    # Initialize the running product to the multiplicative identity.
    result = 1
    # Start multiplying from 2 because multiplying by 1 is a no-op.
    i = 2
    while i <= n:
        # Multiply the accumulator by the current counter.
        result = result * i
        # Increment the counter to progress toward the loop end.
        i = i + 1
    return result


# Example run: print 5! (= 120) to demonstrate the function.
print(factorial(5))
