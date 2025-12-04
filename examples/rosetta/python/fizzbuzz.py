"""Rosetta Code–style FizzBuzz written in Python.

The sample intentionally sticks to simple control flow and arithmetic so it
can be translated to TinyLanguage via the shared IR.
"""


def is_divisible(n, divisor):
    remainder = n
    while remainder >= divisor:
        remainder = remainder - divisor
    return remainder == 0


def fizzbuzz(limit):
    n = 1
    while n <= limit:
        if is_divisible(n, 15):
            print("FizzBuzz")
        else:
            if is_divisible(n, 3):
                print("Fizz")
            else:
                if is_divisible(n, 5):
                    print("Buzz")
                else:
                    print(n)
        n = n + 1


fizzbuzz(16)
