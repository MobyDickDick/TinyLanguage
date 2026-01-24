"""Rosetta example computing the nth Fibonacci number iteratively and printing a sample."""

def fibonacci(n):
    """Compute the nth Fibonacci number with a loop."""
    # Base cases: 0 -> 0, 1 -> 1.
    if n <= 1:
        return n
    # Track the two preceding values.
    a = 0
    b = 1
    i = 2
    while i <= n:
        # Shift the window forward one step.
        temp = a + b
        a = b
        b = temp
        i = i + 1
    return b


# Print a sample value for the Rosetta task.
print(fibonacci(6))
