"""Rosetta example that performs a simple bubble sort and prints the result.

Bubble sort is intentionally inefficient but easy to follow for demonstration
purposes. The script sorts a small list and prints each value.
"""


def bubble_sort(values):
    """Sort a list in ascending order using bubble sort."""
    # Capture the list length once to avoid recomputing it.
    n = len(values)
    # Outer loop controls how many passes have been completed.
    i = 0
    while i < n:
        # Inner loop pushes the largest element to the end of the unsorted slice.
        j = 0
        while j < n - 1 - i:
            # Swap adjacent elements if they are out of order.
            if values[j] > values[j + 1]:
                values[j], values[j + 1] = values[j + 1], values[j]
            # Move to the next pair.
            j += 1
        # After each pass, one more element is in its final position.
        i += 1
    return values


def print_list(values):
    """Print each value on its own line."""
    for value in values:
        # Print each item to stdout for readability.
        print(value)


# Provide a small, unsorted list to demonstrate the algorithm.
numbers = [5, 1, 4, 2, 8]
# Print the sorted results in order.
print_list(bubble_sort(numbers))
