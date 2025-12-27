# TL-Stdlib: Kompatibilitätsziel & Struktur

## 1) API-Kompatibilitätsziel
Für die erste Ausbaustufe orientiert sich die TL-Stdlib an diesen Python-Modulen:

- `math` (numerische Grundfunktionen)
- `random` (Zufall)
- `string` (String-Utilities, z. B. Split/Join)
- `datetime` (geplant, noch nicht umgesetzt)

**Status heute:** Die Kern-Namensräume `Math`, `Random` und `String` sind nativ implementiert. Darüber hinaus existieren `Collections`, `Map`, `Set`, `Deque`, `File`, `JSON`, `Async` und `Result`.

## 2) FFI/Runtime-Strategie
Standardmäßig werden die TL-Stdlib-Funktionen **nativ** in der Runtime implementiert (siehe `src/stdlib/__init__.py`).

Für Spezialfälle oder Erweiterungen kann optional die Python-Bridge genutzt werden:

- `Python.import_module("...")` lädt ein Python-Modul (mit Allowlist).
- `Python.call(...)` bzw. `Python.fn(...)` rufen Funktionen auf.

Damit bleibt die Standardbibliothek deterministisch und kontrollierbar, während erweiterte Features über den Bridge-Mechanismus möglich sind.

## 3) Struktur der TL-Stdlib
Die Standardbibliothek besteht aus zwei Schichten:

- **Native Runtime-Implementierung:** `src/stdlib/__init__.py`
- **TinyLanguage-Module:** `stdlib/` (TinyLanguage-Quellen, per `import` nutzbar)

Das Verzeichnis `stdlib/` ist das feste Zuhause für TL-Module, die die native API in eine Python-ähnliche Modulform gießen.

## 4) Erstes Modul: `stdlib.math`
Das erste TinyLanguage-Modul ist **`stdlib.math`** mit einem Python-ähnlichen API-Ausschnitt.

Import und Nutzung:

```tiny
import stdlib.math;
print(math.sqrt(9));
print(math.round_digits(math.pi, 3));
```

## 5) API-Abweichungen gegenüber Python
- `math.round_digits(value, digits)` ersetzt das optionale `round(x, ndigits)`.
- Die Funktionen sind auf die in TL verfügbaren Math-Operationen begrenzt.
- `string`-Utilities leben im `String`-Namespace (nicht als separates Modul).
- `datetime` ist aktuell nur ein Kompatibilitätsziel.

Weitere Erweiterungen werden in der stdlib erweitert, sobald die Runtime-Funktionen existieren.
