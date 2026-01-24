"""Rosetta example calculating a factorial iteratively and printing the result."""

def factorial(n):
    """Return n! by multiplying the integer range from 1..n."""
    result = 1  # Running product that will accumulate the factorial.
    i = 2  # Start at 2 because multiplying by 1 is a no-op.
    while i <= n:
        result = result * i  # Multiply the running product by the next factor.
        i = i + 1  # Move to the next integer in the sequence.
    return result  # Provide the final factorial value.


print(factorial(5))  # Demonstrate the function with a small input.
