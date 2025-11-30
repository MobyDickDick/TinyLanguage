# Rosetta-Code-Style: Python → TinyLanguage
These examples start from common Python snippets on Rosetta Code and show a direct TinyLanguage translation. Each Tiny program is runnable with the interpreter:

```bash
python src/tiny_language.py src_tiny/<file>.tiny
```

## 1) FizzBuzz (Kontrollfluss und Modulo)
**Python-Vorlage**
```python
for n in range(1, 16):
    if n % 15 == 0:
        print("FizzBuzz")
    elif n % 3 == 0:
        print("Fizz")
    elif n % 5 == 0:
        print("Buzz")
    else:
        print(n)
```

**TinyLanguage-Übersetzung** (`src_tiny/rosetta_fizzbuzz.tiny`)
- Ersetze `for` durch eine `while`-Schleife und incrementiere manuell.
- Da TinyLanguage kein `%`-Operator kennt, erledigt eine kleine Hilfsfunktion die Divisibilitätsprüfung per Subtraktion.

```tiny
fn is_divisible(n, divisor) {
    define remainder = n;
    while (remainder >= divisor) {
        remainder = remainder - divisor;
    }
    return remainder == 0;
}

fn fizzbuzz(limit) {
    define n = 1;
    while (n <= limit) {
        if (is_divisible(n, 15)) { print("FizzBuzz"); }
        else {
            if (is_divisible(n, 3)) { print("Fizz"); }
            else {
                if (is_divisible(n, 5)) { print("Buzz"); }
                else { print(n); }
            }
        }
        n = n + 1;
    }
}

define _ = fizzbuzz(16);
```

## 2) Fakultät (Rekursion und Rückgabewerte)
**Python-Vorlage**
```python
def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)

for i in range(1, 6):
    print(i, fact(i))
```

**TinyLanguage-Übersetzung** (`src_tiny/rosetta_factorial.tiny`)
- Funktionen und `return`-Pflicht sind identisch, nur Semikolons hinzufügen.
- Die Schleife bleibt eine `while`, und `print` akzeptiert mehrere Argumente.

```tiny
fn fact(n) {
    if (n <= 1) { return 1; }
    return n * fact(n - 1);
}

define i = 1;
while (i <= 5) {
    print(i, fact(i));
    i = i + 1;
}
```

## 3) Wortzählung (String.split + Map)
**Python-Vorlage**
```python
from collections import Counter

def word_counts(text: str) -> Counter:
    words = text.lower().split()
    return Counter(words)

counts = word_counts("To be or not to be")
for word, freq in counts.items():
    print(word, freq)
```

**TinyLanguage-Übersetzung** (`src_tiny/rosetta_word_count.tiny`)
- Nutzt `String.lower`, `String.split` und die Map-Stdlib (`Map.new`, `Map.get`, `Map.set`).
- Iteriere über die Wortliste mit `len(...)` und `heap_get(...)`, die auf dem Heap gespeicherte Arrays adressieren.
- Drucke anschließend Wort/Frequenz-Paare aus den Map-Schlüsseln.

```tiny
fn word_counts(text) {
    define normalized = String.lower(text);
    define words = String.split(normalized, " ");
    define counts = Map.new();

    define index = 0;
    define total = len(words);
    while (index < total) {
        define word = heap_get(words, index);
        define seen = Map.get(counts, word, 0);
        define _ = Map.set(counts, word, seen + 1);
        index = index + 1;
    }

    return counts;
}

define counts = word_counts("To be or not to be");
print("unique words", Map.len(counts));

define keys = Map.keys(counts);

define i = 0;
while (i < len(keys)) {
    define word = heap_get(keys, i);
    define freq = Map.get(counts, word, 0);
    print(word, freq);
    i = i + 1;
}
```
