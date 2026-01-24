"""Rosetta example implementing FizzBuzz with a simple counting loop.

The program prints the numbers from 1 to ``n`` while substituting:
- "Fizz" for multiples of 3
- "Buzz" for multiples of 5
- "FizzBuzz" for multiples of both 3 and 5
"""

def fizzbuzz(n):
    """Print the FizzBuzz sequence from 1 through n inclusive."""
    i = 1  # Start counting from 1 to match the standard FizzBuzz specification.
    while i <= n:  # Continue looping until we have handled the requested upper bound.
        if i % 15 == 0:  # Multiples of both 3 and 5 should show the combined label.
            print("FizzBuzz")  # Emit the combined label for shared multiples.
        elif i % 3 == 0:  # Multiples of 3 but not 5 get the "Fizz" label.
            print("Fizz")  # Emit the label for a multiple of three.
        elif i % 5 == 0:  # Multiples of 5 but not 3 get the "Buzz" label.
            print("Buzz")  # Emit the label for a multiple of five.
        else:
            print(i)  # Fall back to the raw number when no rule applies.
        i = i + 1  # Advance to the next number in the sequence.


fizzbuzz(16)  # Run a sample sequence that prints 1 through 16.
