"""Rosetta example implementing FizzBuzz with a simple counting loop.

The output substitutes "Fizz", "Buzz", or "FizzBuzz" for multiples of 3, 5,
or both.
"""

def fizzbuzz(n):
    """Print the FizzBuzz sequence from 1 through n."""
    # Initialize the counter at 1 for the classic FizzBuzz range.
    i = 1
    while i <= n:
        # Prefer the combined condition so 15 prints "FizzBuzz".
        if i % 15 == 0:
            print("FizzBuzz")
        elif i % 3 == 0:
            # Multiples of 3 only.
            print("Fizz")
        elif i % 5 == 0:
            # Multiples of 5 only.
            print("Buzz")
        else:
            # All other numbers are printed as-is.
            print(i)
        # Advance to the next integer.
        i = i + 1


# Print a short sample up to 16.
fizzbuzz(16)
