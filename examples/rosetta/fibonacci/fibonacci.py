"""Rosetta example computing the nth Fibonacci number iteratively and printing a sample."""

def fibonacci(n):
    if n <= 1:
        return n
    a = 0
    b = 1
    i = 2
    while i <= n:
        temp = a + b
        a = b
        b = temp
        i = i + 1
    return b


print(fibonacci(6))
