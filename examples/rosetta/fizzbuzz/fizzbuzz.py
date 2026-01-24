"""Rosetta example implementing FizzBuzz with a simple counting loop.

The program prints the numbers from 1 to ``n`` while substituting:
- "Fizz" for multiples of 3
- "Buzz" for multiples of 5
- "FizzBuzz" for multiples of both 3 and 5
"""

def fizzbuzz(n):
    """Print FizzBuzz output for the range 1..n (inclusive)."""
    # Start counting from 1 to match the classic FizzBuzz problem statement.
    i = 1
    while i <= n:
        # Check divisibility by both 3 and 5 first to catch 15.
        if i % 15 == 0:
            print("FizzBuzz")
        elif i % 3 == 0:
            # Multiples of 3 that are not multiples of 5.
            print("Fizz")
        elif i % 5 == 0:
            # Multiples of 5 that are not multiples of 3.
            print("Buzz")
        else:
            # All other numbers are printed verbatim.
            print(i)
        # Move to the next number in the sequence.
        i = i + 1


# Print the FizzBuzz sequence up to 16.
fizzbuzz(16)
