"""Console helper that reads two numbers from stdin and prints their sum.

Inputs are parsed via JSON so that integers and floats can be entered without
custom parsing logic.
"""

import json

def read_number(prompt: str) -> float:
    """Prompt repeatedly until a valid JSON number is provided."""
    while True:
        # Read raw user input and trim surrounding whitespace.
        raw = input(prompt)
        text = raw.strip()
        if text == "":
            # Treat empty input as zero to keep demos quick.
            print("Keine Eingabe erkannt, verwende 0.")
            return 0
        try:
            # Use JSON parsing to accept numbers like 3, 3.14, or -2.
            return json.loads(text)
        except Exception:
            # Fall back to a friendly error message on invalid JSON.
            print("Please enter a valid number.")

# Prompt for two values and output their sum.
a = read_number("Erste Zahl: ")
b = read_number("Zweite Zahl: ")
print("Summe:", a + b)
