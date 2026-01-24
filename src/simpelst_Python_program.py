"""Minimal endless loop used to exercise stdout performance in TinyLanguage demos.

The counter wraps around to avoid growing without bound during long runs.
"""

# Start the counter at zero for predictable output.
i = 0
while True:
    # Print the current value to simulate console-heavy workloads.
    print("This is a simple Test", i)
    # Cycle the counter to keep numbers within a manageable range.
    i = (i + 1) % 10_000_000
