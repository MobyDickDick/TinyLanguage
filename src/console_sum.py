import json

def read_number(prompt: str) -> float:
    while True:
        raw = input(prompt)
        text = raw.strip()
        if text == "":
            print("Keine Eingabe erkannt, verwende 0.")
            return 0
        try:
            return json.loads(text)
        except Exception:
            print("Bitte eine gültige Zahl eingeben.")

a = read_number("Erste Zahl: ")
b = read_number("Zweite Zahl: ")
print("Summe:", a + b)
