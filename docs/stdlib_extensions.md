# Neue Stdlib-Bausteine

## Collections: Map, Set, Deque

- **Map**: `Map.new()` erzeugt eine leere Map auf dem Heap. `Map.set(map, key, value)` setzt Werte, `Map.get(map, key, default)` liest sie aus. `Map.has`, `Map.delete`, `Map.keys`, `Map.values`, `Map.entries` (Liste aus `[key, value]`) runden die API ab. `Map.from_entries(list)` baut eine Map aus 2-Element-Listen.
- **Set**: `Set.new()` creates an empty set. `Set.add` inserts a value and returns `true` if the value was not already present war. `Set.delete` entfernt, `Set.has` prueft Mitgliedschaft, `Set.to_list` gibt die Elemente als Heap-Liste aus.
- **Deque**: `Deque.new([items])` creates a double-ended queue. `Deque.push_left/right` add elements, `Deque.pop_left/right` entnimmt (mit Fehler bei leerer Queue), `Deque.peek_left/right` schaut nur, `Deque.len` zaehlt, `Deque.to_list` exportiert.

## Math & Random

- **Math**: In addition to `abs`, `pow`, `sqrt`, `max`, `min`, `clamp`, there is now `Math.round(value, digits?)`, `Math.floor(value)`, `Math.ceil(value)` und `Math.sign(value)` fuer Rundungen und Vorzeichenchecks.
- **Random**: `Random.random()` (0-1), `Random.randint(lower, upper)`, `Random.choice(seq)` and `Random.shuffle(seq)` arbeiten direkt auf Listen oder Heap-Pointern.

## File and JSON helpers

- **File**: `File.read(path)` reads UTF-8, `File.write(path, text)` writes and creates directories as needed, `File.exists(path)` prueft Pfade, `File.remove(path)` loescht optional.
- **JSON**: `JSON.parse(text)` converts text into Maps/Lists backed by native Python containers; numbers/bools/null remain erhalten. `JSON.stringify(value)` serialisiert kompatible TinyLanguage-Werte (inkl. Map/Deque/List-Heap-Pointer) zu String.

## Beispielprogramme

- [`stdlib_collections_demo.tiny`](../[[src_tiny/stdlib_collections_demo.tiny](src_tiny/stdlib_collections_demo.tiny)]([src_tiny/stdlib_collections_demo.tiny](src_tiny/stdlib_collections_demo.tiny))) zeigt Map/Set/Deque.
- [`stdlib_io_random_demo.tiny`](../[[src_tiny/stdlib_io_random_demo.tiny](src_tiny/stdlib_io_random_demo.tiny)]([src_tiny/stdlib_io_random_demo.tiny](src_tiny/stdlib_io_random_demo.tiny))) kombiniert Random, File und JSON.
