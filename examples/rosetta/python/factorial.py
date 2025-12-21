"""Rosetta example calculating a factorial iteratively and printing the result."""

def factorial(n):
    result = 1
    i = 2
    while i <= n:
        result = result * i
        i = i + 1
    return result


print(factorial(5))
