"""Rosetta Code–style factorial using an iterative loop."""


def factorial(n):
    result = 1
    while n > 1:
        result = result * n
        n = n - 1
    return result


print(factorial(5))
