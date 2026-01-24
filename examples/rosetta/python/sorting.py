"""Rosetta example that performs a simple bubble sort and prints the result."""


def bubble_sort(values):
    """Sort a list in ascending order using the bubble sort algorithm."""
    n = len(values)  # Cache the list length for loop boundaries.
    i = 0  # Tracks how many passes have been completed.
    while i < n:
        j = 0  # Index for each adjacent comparison in the current pass.
        while j < n - 1 - i:
            if values[j] > values[j + 1]:
                # Swap neighbors that are out of order.
                values[j], values[j + 1] = values[j + 1], values[j]
            j += 1  # Move to the next pair.
        i += 1  # Reduce the remaining unsorted portion.
    return values  # Return the sorted list for convenience.


def print_list(values):
    """Print each value from the list on its own line."""
    for value in values:
        print(value)  # Output a single element at a time.


numbers = [5, 1, 4, 2, 8]  # Sample list to be sorted.
print_list(bubble_sort(numbers))  # Sort and display the result.
