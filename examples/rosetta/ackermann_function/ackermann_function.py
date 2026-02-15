"""Rosetta Code task: Ackermann function."""


def ackermann(m, n):
    """Compute Ackermann's function for small non-negative integers."""
    if m == 0:
        return n + 1
    if n == 0:
        return ackermann(m - 1, 1)
    return ackermann(m - 1, ackermann(m, n - 1))


print(ackermann(3, 4))
