"""Rosetta example computing the nth Fibonacci number iteratively.

The script prints the 6th Fibonacci number using a small loop to illustrate
state updates across iterations.
"""

def fibonacci(n):
    """Return the nth Fibonacci number using an iterative approach."""
    # Handle the base cases directly without entering the loop.
    if n <= 1:
        return n
    # Initialize the two most recent Fibonacci values.
    a = 0
    b = 1
    # Start from index 2 because indices 0 and 1 are already covered.
    i = 2
    while i <= n:
        # Compute the next value and shift the window forward.
        temp = a + b
        a = b
        b = temp
        # Move to the next index.
        i = i + 1
    return b


# Print the 6th Fibonacci number as a simple demonstration.
print(fibonacci(6))
