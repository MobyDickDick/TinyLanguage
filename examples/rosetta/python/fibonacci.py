"""Rosetta example computing the nth Fibonacci number iteratively.

This script is kept deliberately small for transpiler input, but the comments
call out the algorithmic steps for clarity.
"""

def fibonacci(n):
    """Return the nth Fibonacci number using a loop."""
    # Base cases for n = 0 and n = 1.
    if n <= 1:
        return n
    # Track the two most recent Fibonacci values.
    a = 0
    b = 1
    # Start the loop at index 2.
    i = 2
    while i <= n:
        # Sum the previous two values and advance the window.
        temp = a + b
        a = b
        b = temp
        # Increment to the next index in the sequence.
        i = i + 1
    return b


# Print a sample result for verification.
print(fibonacci(6))
