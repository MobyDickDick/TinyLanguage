# Rosetta Code style: Python → TinyLanguage

These examples start from common Python snippets on Rosetta Code and show a direct TinyLanguage translation. Each Tiny program is runnable with the interpreter:

```bash
python src/tiny_language.py src_tiny/<file>.tiny
```

## 1) FizzBuzz (control flow and modulo)

### Python template of fizzBuzz

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

**TinyLanguage translation** (`src_tiny/rosetta_fizzbuzz.tiny`)

- Replace `for` with a `while` loop and increment manually.
- TinyLanguage has no `%` operator, so a helper handles divisibility via subtraction.

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

## 2) Factorial (recursion and return values)

### Python template of factorial function

```python
def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)

for i in range(1, 6):
    print(i, fact(i))
```

### TinyLanguage translation (`src_tiny/rosetta_factorial.tiny`)

- Functions and return requirements are identical; just add semicolons.
- The loop stays a `while`, and `print` accepts multiple arguments.

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

## 3) Word count (String.split + Map)

### Python template of word count template

```python
from collections import Counter

def word_counts(text: str) -> Counter:
    words = text.lower().split()
    return Counter(words)

counts = word_counts("To be or not to be")
for word, freq in counts.items():
    print(word, freq)
```

**TinyLanguage translation** (`src_tiny/rosetta_word_count.tiny`)

- Uses `String.lower`, `String.split`, and the Map stdlib (`Map.new`, `Map.get`, `Map.set`).
- Iterate over the word list with `len(...)` and `heap_get(...)`, which address arrays stored on the heap.
- Then print word/frequency pairs from the map keys.

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

## Automatisches Kopieren und Transpilieren neuer Rosetta-Skripts

- Use `examples/rosetta/copy_rosetta_samples.py` to copy missing Rosetta Code Python files into a target directory. Example with filter and dry-run: `python examples/rosetta/copy_rosetta_samples.py ~/rosetta_import --include fib --include fizz --limit 5 --delay 0 --dry-run`. The script compares filenames in the default source folder `examples/rosetta/python` with the destination, offers prefix filters for subsets, and optionally waits between copy operations.
- With `--transpile`, the script automatically kicks off translation after copying. Destination and source can be customized, e.g.: `python examples/rosetta/copy_rosetta_samples.py examples/rosetta/python --transpile --transpile-dest examples/rosetta/expected`.
- You can also run transpilation directly: `python -m transpile_rosetta --source examples/rosetta/python --dest examples/rosetta/expected`. Adjust `--dest` if the TinyLanguage files should land in a different folder.
- A pre-generated collection of the existing Python examples lives under `src_tiny/from_python/` — it was created via `python -m transpile_rosetta --dest $(pwd)/src_tiny/from_python` and can be run directly with `python src/tiny_language.py src_tiny/from_python/<name>.tiny`.
