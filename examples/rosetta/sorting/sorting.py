"""Rosetta example that performs a simple bubble sort and prints the result.

This variant mirrors the Rosetta Code task using simple loops so the algorithm
is easy to trace when stepping through the code.
"""


def bubble_sort(values):
    """Return a new list sorted in ascending order using bubble sort."""
    # Capture the list length once to avoid recomputing it.
    n = len(values)
    # Each outer pass moves the next-largest value to the end of the list.
    i = 0
    while i < n:
        # Compare adjacent values in the unsorted portion of the list.
        j = 0
        while j < n - 1 - i:
            # Swap out-of-order elements to bubble larger values forward.
            if values[j] > values[j + 1]:
                values[j], values[j + 1] = values[j + 1], values[j]
            # Advance to the next pair.
            j += 1
        # After each pass, the tail segment is sorted.
        i += 1
    return values


def print_list(values):
    """Print each element of a list on its own line."""
    for value in values:
        # Print values individually for a clean Rosetta-style output.
        print(value)


# Provide a small input list to demonstrate the sort.
numbers = [5, 1, 4, 2, 8]
# Print the sorted list to stdout.
print_list(bubble_sort(numbers))
