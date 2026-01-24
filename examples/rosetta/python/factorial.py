"""Rosetta example calculating a factorial iteratively and printing the result."""

def factorial(n):
    """Return ``n!`` using an iterative loop."""
    # Start with the multiplicative identity.
    result = 1
    # Multiply by each integer from 2 through n.
    i = 2
    while i <= n:
        result = result * i
        i = i + 1
    return result


# Demonstrate the helper with the classic value for 5.
print(factorial(5))
