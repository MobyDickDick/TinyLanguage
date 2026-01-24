"""Rosetta example computing the nth Fibonacci number iteratively and printing a sample."""

def fibonacci(n):
    """Return the nth Fibonacci number using an iterative loop."""
    if n <= 1:
        return n  # Base cases: 0 -> 0, 1 -> 1.
    a = 0  # Represents F(n-2) in the rolling window.
    b = 1  # Represents F(n-1) in the rolling window.
    i = 2  # Start computing from the second index onward.
    while i <= n:
        temp = a + b  # Compute the next Fibonacci number.
        a = b  # Shift the window: previous F(n-1) becomes F(n-2).
        b = temp  # Store the newly computed value as F(n-1).
        i = i + 1  # Advance the index counter.
    return b  # b now holds F(n).


print(fibonacci(6))  # Demonstrate the function with a sample input.
