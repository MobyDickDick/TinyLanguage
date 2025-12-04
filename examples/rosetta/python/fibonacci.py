"""Iterative Fibonacci sequence in Python for Rosetta-style translation."""


def fibonacci(count):
    a = 0
    b = 1
    i = 0
    while i < count:
        print(a)
        temp = a + b
        a = b
        b = temp
        i = i + 1


fibonacci(10)
