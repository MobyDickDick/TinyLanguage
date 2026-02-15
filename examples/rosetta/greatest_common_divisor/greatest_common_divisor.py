"""Rosetta Code task: Greatest common divisor (subtraction-based Euclid variant)."""


def gcd(a, b):
    """Return the greatest common divisor of two positive integers."""
    x = a
    y = b
    while x != y:
        if x > y:
            x = x - y
        else:
            y = y - x
    return x


print(gcd(1071, 462))
