"""Rosetta example implementing FizzBuzz with a simple counting loop."""

def fizzbuzz(n):
    """Print the classic FizzBuzz sequence from 1 through ``n``."""
    i = 1
    while i <= n:
        # Choose the most specific label first (both divisible by 3 and 5).
        if i % 15 == 0:
            print("FizzBuzz")
        elif i % 3 == 0:
            print("Fizz")
        elif i % 5 == 0:
            print("Buzz")
        else:
            print(i)
        i = i + 1


# Run the task with a small sample range.
fizzbuzz(16)
