# New stdlib building blocks

## Collections: Map, Set, Deque

- **Map**: `Map.new()` creates an empty map on the heap. `Map.set(map, key, value)` writes values, and `Map.get(map, key, default)` reads them back. `Map.has`, `Map.delete`, `Map.keys`, `Map.values`, and `Map.entries` (a list of `[key, value]` pairs) complete the API. `Map.from_entries(list)` builds a map from a list of 2-element lists.
- **Set**: `Set.new()` creates an empty set. `Set.add` inserts values and returns `true` if the value was not already present. `Set.delete` removes values, `Set.has` checks membership, and `Set.to_list` returns the elements as a heap list.
- **Deque**: `Deque.new([items])` creates a double-ended queue. `Deque.push_left/right` inserts elements, `Deque.pop_left/right` removes elements (raising an error on an empty deque), `Deque.peek_left/right` reads without removing, `Deque.len` returns the length, and `Deque.to_list` exports the contents.

## Math & Random

- **Math**: In addition to `abs`, `pow`, `sqrt`, `max`, `min`, and `clamp`, there are now `Math.round(value, digits?)`, `Math.floor(value)`, `Math.ceil(value)`, and `Math.sign(value)` for rounding and sign checks.
- **Random**: `Random.random()` (0–1), `Random.randint(lower, upper)`, `Random.choice(seq)`, and `Random.shuffle(seq)` operate directly on lists or heap pointers.

## Statistics (Julia-style subset)

- **Statistics**: `Statistics.mean(values)` computes the mean of a list/heap pointer (requires at least one value). `Statistics.std(values)` returns the sample standard deviation using `n - 1` in the denominator (requires at least two values).
- **Julia differences**: Only `mean` and `std` are provided. The TinyLanguage `std` helper errors for sequences shorter than two values instead of returning `NaN`, and it does not expose options like `corrected=false` or handling of `missing` values.

## File and JSON helpers

- **File**: `File.read(path)` reads UTF-8 text. `File.write(path, text)` writes text and creates directories as needed. `File.exists(path)` checks whether a path exists. `File.remove(path)` deletes (if present, depending on implementation).
- **JSON**: `JSON.parse(text)` converts text into maps/lists using native Python containers; numbers/bools/null are preserved. `JSON.stringify(value)` serializes compatible TinyLanguage values (including Map/Deque/List heap pointers) into a string.

## Example programs

- [`stdlib_collections_demo.tiny`](../src_tiny/stdlib_collections_demo.tiny) demonstrates Map/Set/Deque.
- [`stdlib_io_random_demo.tiny`](../src_tiny/stdlib_io_random_demo.tiny) combines Random, File, and JSON.
