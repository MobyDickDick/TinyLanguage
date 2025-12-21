"""Minimal endless loop used to exercise stdout performance in TinyLanguage demos."""

i = 0
while True:
    print("This is a simple Test", i)
    i = (i + 1) % 10_000_000
