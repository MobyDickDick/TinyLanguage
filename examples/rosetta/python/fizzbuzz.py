"""Rosetta example implementing FizzBuzz with a simple counting loop."""

def fizzbuzz(n):
    """Print the FizzBuzz sequence from 1 to n inclusive."""
    i = 1  # Start counting at one to align with the standard FizzBuzz rules.
    while i <= n:
        if i % 15 == 0:
            print("FizzBuzz")  # Multiples of both 3 and 5.
        elif i % 3 == 0:
            print("Fizz")  # Multiples of 3 only.
        elif i % 5 == 0:
            print("Buzz")  # Multiples of 5 only.
        else:
            print(i)  # All other numbers are printed directly.
        i = i + 1  # Increment the loop counter.


fizzbuzz(16)  # Demonstrate output for the first 16 numbers.
