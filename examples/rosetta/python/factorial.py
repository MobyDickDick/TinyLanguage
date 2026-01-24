"""Rosetta example calculating a factorial iteratively and printing the result.

This Python-only sample is used as source input for the Rosetta transpiler
tests, so the implementation is intentionally compact but still annotated.
"""

def factorial(n):
    """Return n! by multiplying a counter into an accumulator."""
    # Start with 1 because factorial multiplies into the identity element.
    result = 1
    # Begin at 2; multiplying by 1 is unnecessary.
    i = 2
    while i <= n:
        # Fold the counter into the running product.
        result = result * i
        # Step the counter forward until the loop condition fails.
        i = i + 1
    return result


# Print a sample value so the script is self-contained.
print(factorial(5))
