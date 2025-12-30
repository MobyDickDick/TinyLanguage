"""
rosetta_factorial_iterative.py

Rosetta example: factorial (iterative)

Purpose
-------
Demonstrate an iterative computation of the factorial function and print the
result for a small input. This example is intentionally simple and mirrors a
typical Rosetta Code task.

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
    result = 1
    i = 2
    while i <= n:
        result = result * i
        i = i + 1
    return result


# Example run: print 5! (= 120).
print(factorial(5))
