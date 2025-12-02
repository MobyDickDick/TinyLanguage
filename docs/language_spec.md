# TinyLanguage: Kurzreferenz und Semantik

Diese Datei beschreibt die wichtigsten Sprachkonstrukte von TinyLanguage in komprimierter Form. Sie richtet sich an Leser, die die Syntax schnell nachschlagen und das Laufzeitverhalten verstehen wollen, ohne den Interpreter-Code durchgehen zu müssen.

## Lexikalische Elemente
- **Kommentare:** `//` leitet einen Kommentar bis zum Zeilenende ein. Blockkommentare werden nicht speziell behandelt.
- **Semikolons:** Jedes Statement endet mit `;`. Der Formatter fügt fehlende Semikolons in einfachen Fällen automatisch hinzu, dennoch sollten Programme sie explizit setzen.
- **Bezeichner und Literale:**
  - Zahlen unterstützen Ganzzahlen und Dezimalzahlen (`1`, `3.14`, `0.5`). Wissenschaftliche Notation ist absichtlich nicht erlaubt (`1.2e2` schlägt fehl).
  - Strings verwenden doppelte Anführungszeichen und erlauben einfache Escape-Sequenzen wie `\n`.
  - Wahrheitswerte heißen `true` und `false`; `null` signalisiert das Fehlen eines Wertes.

## Ausdrücke und Operatoren
- **Arithmetik:** `+`, `-`, `*`, `/` sowie Potenzen `^` (der Exponent muss ganzzahlig sein). Division liefert Fließkommazahlen, Overflow wird abgefangen und als Fehler gemeldet.
- **Vergleiche:** `==`, `!=`, `<`, `>`, `<=`, `>=` arbeiten auf Zahlen, Strings, Booleans und benutzerdefinierten Typen mit Operator-Overloads.
- **Booleans:** Kurzschluss-Logik mit `&&` und `||`, Negation über `!expr`.
- **Arrays und Heap:** `new[1, 2, 3]` erzeugt ein Array; `new(3)` reserviert Speicher mit drei Slots. Zugriff erfolgt über `heap_get(ptr, idx)` und `heap_set(ptr, idx, value)`. `tag(ptr, "Label")` versieht Pointer mit einem Typnamen, `delete(ptr)` gibt Speicher frei.
- **Struct-Literale:** `{ a: 1, b: 2 }` baut ein anonymes Struct; Felder werden mit Punktnotation gelesen (`obj.a`).

## Bindungen und Sichtbarkeit
- **Definitionen:** `define x = expr;` legt eine neue Variable an. Nachträgliche Zuweisungen ohne `define` aktualisieren bestehende Bindungen und dürfen den Typ nicht heimlich wechseln, wenn Annotationen gesetzt sind.
- **Gültigkeitsbereiche:** Funktionen, Namespaces und Match-Arme führen eigene Scopes ein. Importierte Module werden unter ihrem vollqualifizierten Namen registriert und können über Aliase erreichbar gemacht werden.

## Kontrollfluss
- **`if`/`while`:** Standardkontrollstrukturen mit runden Klammern um die Bedingung. Bedingungen müssen Boolean-Werte liefern; alle Pfade in getypten Funktionen müssen ein `return` besitzen.
- **`match`:** Exhaustives Pattern-Matching für `type`-Varianten und Structs. Wildcards (`_`) und benannte Felder (`case Circle { radius: r }`) werden unterstützt; fehlende Fälle führen zu einem Fehler.
- **Fehlerbehandlung:** `try { ... } catch(err) { ... }` fängt Laufzeitfehler ab und erlaubt alternative Rückgabewerte oder Logging.

## Funktionen und Typen
- **Deklaration:** `fn add(x: number, y: number) -> number { return x + y; }`. Parameter und Rückgabewerte sind optional typisiert; Typannotationen werden zur Laufzeit geprüft.
- **Rückgabepflicht:** Annotierte Funktionen müssen auf allen Pfaden einen Wert liefern, sonst entsteht Fehler `E010`.
- **Closures:** Funktionen sind First-Class-Werte und können als Rückgabewerte oder Argumente verwendet werden.

## Algebraische Datentypen und Pattern Matching
- **`type`-Definitionen:**
  ```tiny
  type Shape {
    Circle { radius: number };
    Rectangle { width: number, height: number };
  }
  ```
  Jede Variante wird automatisch zu einem Konstruktor (z. B. `Circle { radius: 2 }`).
- **Exhaustive Matching:** `match`-Ausdrücke müssen alle Varianten abdecken; ansonsten wird ein Hinweis auf die fehlenden Fälle ausgegeben.

## Klassen und Operator-Overloading
- **Klassen:** Felder werden mit Typen deklariert (`name: string;`). Methoden verwenden denselben Funktionssyntax und erhalten `self` als erstes Argument. Konstruktorfunktionen können frei definiert werden (`fn Greeter(name) { return new Greeter { name: name }; }`).
- **Mehrfachvererbung:** Klassen können mehrere Basistypen angeben; Methodenauflösung folgt einer linearen Reihenfolge, die Konflikte verhindert.
- **Operatoren:** Beliebige Operatoren lassen sich über `operator + (a: Point, b: Point) -> Point { ... }` überladen. Vergleiche (`==`) und arithmetische Operatoren können damit eigene Logik erhalten.

## Module und Namespaces
- **Module laden:** `import math.trig;` lädt `math/trig.tiny`. Aliase sind möglich (`import utils.helpers as helpers;`). Wiederholte Importe eines Moduls liefern denselben Namespace, Zyklen werden erkannt und mit `E008` gemeldet.
- **Namespaces:** `namespace Tools { ... }` fasst Funktionen und Konstanten zusammen. Felder werden mit Punktnotation referenziert (`Tools.double(5)`), auch aus anderen Modulen heraus.

## Nebenläufigkeit und Async-API
- **Tasks:** `spawn f(1, 2)` startet `f` asynchron, `join(handle)` wartet und liefert das Ergebnis oder den Fehler weiter.
- **Cancellation:** Über `Async.token()` wird ein Token erstellt, das mit `Async.cancel(token, "reason")` abgebrochen werden kann. Tasks können verknüpft werden (`Async.link(token, handle)`), um Abbrüche zu propagieren.

## Fehler und Diagnostik
- **Fehlermeldungen:** Der Interpreter versieht Lexer-, Parser- und Laufzeitfehler mit Codes wie `E001` (Syntax), `E008` (Modulauflösung) oder `E009` (Typfehler). Wo möglich, wird ein `SourceSpan` mit Zeilen- und Spalteninformation ausgegeben, der die fehlerhafte Stelle unterstreicht.
- **Linter:** Warnungen für ungenutzte Bindungen, Stilregeln (Semikolons, Spacing) und einfache „must use“-Prüfungen sind integriert und werden beim Formatieren bzw. beim LSP ausgegeben.

## Lauf und Tools
- **Interpreter:** `python tiny_language.py <datei.tiny>` führt eine Quelle aus. Module werden relativ zur aufrufenden Datei, `TINYPATH` und dem Projektstamm gesucht.
- **CLI-Demos:** Beispielprogramme liegen in `src_tiny/`; sie decken Klassen, Pattern Matching, Operatoren, Concurrency und Python-Interop ab.
- **Language Server:** `python tiny_language_server.py --stdio` startet den LSP; eine Referenz der verfügbaren Methoden steht in [`docs/language_server_workflows.md`](language_server_workflows.md).
