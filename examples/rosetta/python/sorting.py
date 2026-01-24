"""Rosetta example that performs a simple bubble sort and prints the result."""


def bubble_sort(values):
    """Sort the provided list in ascending order using bubble sort."""
    n = len(values)
    i = 0
    while i < n:
        # Bubble the largest remaining element toward the end.
        j = 0
        while j < n - 1 - i:
            if values[j] > values[j + 1]:
                values[j], values[j + 1] = values[j + 1], values[j]
            j += 1
        i += 1
    return values


def print_list(values):
    """Print each value on its own line."""
    for value in values:
        print(value)


# Demonstrate the sort with a small sample list.
numbers = [5, 1, 4, 2, 8]
print_list(bubble_sort(numbers))
