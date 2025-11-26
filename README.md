# TinyLanguage

TinyLanguage ist eine kleine, von Julia inspirierte Sprache mit einem Python-Interpreter. Dieses README liefert eine Stackedit.io-artige Markdown-Uebersicht: Syntax-Highlights, ein kompaktes Tutorial, Hinweise zu Beispielen, haeufige Fehlermeldungen und die wichtigsten Run-/Test-Kommandos.

## Syntax und Features

### Mini-Tutorial: von Variablen bis Funktionen
```tiny
// Variablen, Arithmetik, Ausgabe
define a = 7 + 5 * 2;
print(a);                // -> 17

// Funktionen definieren und aufrufen
fn add(x, y) {
    return x + y;
}

define sum = add(a, 3);
print(sum);

// If/while und Mutation
define i = 0;
while (i < 3) {
    if (i == 1) { print("in the middle"); }
    i = i + 1;
}

// Namenraeume
namespace Math {
    fn inc(x) { return add(x, 1); }
}
print(Math.inc(4));
```

### Weitere Sprachbausteine
- **Vergleiche und Strings**: `>`, `>=`, `<`, `<=`, `==`, `!=` sowie String-Konkatenation mit `+`. Wissenschaftliche Notation wie `1.2e2` wird nicht unterstuetzt.
- **Potenzieren**: Der Operator `^` akzeptiert nur ganzzahlige Exponenten; fuer Brueche `power(base, exponent)` nutzen.
- **Heap und Arrays**: `new(3)` erzeugt einen Pointer mit drei Plaetzen, `new[1, 2, 3]` legt ein Array auf dem Heap an. `heap_get`/`heap_set` greifen darauf zu, `tag` versieht Pointer mit Typ-Tags, `delete` entfernt sie.
- **Destructuring**: Funktionen koennen Strukturen zurueckgeben: `fn bump(a) { a = a + 1; return { a: a, e: 0 }; }` wird mit `{ a, e } = bump(1);` gebunden.
- **Klassen und Operatoren**: Klassen besitzen Felder und Methoden, Mehrfachvererbung ist erlaubt. Operatoren lassen sich ueberladen, etwa `operator + (a: Number, b: Number) -> Number { ... }`.
- **Nebenlaeufigkeit**: `spawn f(1, 2)` startet einen Task, `join` wartet und liefert das Ergebnis.

### Typ-Hinweise und Gradual Typing
- **Syntax**: Parameter und Rueckgaben koennen annotiert werden: `fn label(x: string, times: number) -> string { return x * times; }`. Methoden nutzen dieselbe Syntax.
- **Gradual-Typing-Checks**: Annotierte Argumente und Rueckgaben werden zur Laufzeit geprueft. Ein Aufruf wie `label(1, "x")` fuehrt zu einem `[E009] type mismatch ... expected string/number ...`-Hinweis.
- **Einfache Exhaustiveness-Checks**: Annotierte Funktionen muessen auf allen Pfaden einen Wert liefern. Fehlt ein `return`, meldet der Linter `[E010] not all paths ... return a value ...` mit Hinweis auf fehlende Branch-Rueckgaben.

### Klassen
Minimalbeispiel mit Konstruktor-Funktion und Methode. Die Ausgabe wurde mit `python tiny_language.py class_demo.tiny` verifiziert.

```tiny
class Greeter {
    name: string;

    fn greeting(self) {
        return "Hallo, " + self.name + "!";
    }
}

fn Greeter(name) { return new Greeter { name: name }; }

define greeter = Greeter("TinyLanguage");
print(greeter.greeting());
```

Erwartete Ausgabe:

```
Hallo, TinyLanguage!
```

Mehr dazu in [`class_demo.tiny`](class_demo.tiny).

### Operator-Overloading
Ein `Point`-Typ ueberschreibt `+` und `==`. Ergebnis bestaetigt via `python tiny_language.py operator_overloading_demo.tiny`.

```tiny
class Point {
    x: number; y: number;
    fn to_tuple(self) { return new[self.x, self.y]; }
}

fn Point(x, y) { return new Point { x: x; y: y }; }
operator + (a: Point, b: Point) -> Point { return Point(a.x + b.x, a.y + b.y); }
operator == (left: Point, right: Point) -> Bool { return left.x == right.x && left.y == right.y; }

define p = Point(1, 2);
define q = Point(3, 4);
define sum = p + q;
print(heap_get(sum.to_tuple(), 0));
print(heap_get(sum.to_tuple(), 1));
print(p == sum);
```

Erwartete Ausgabe:

```
4
6
false
```

Vollstaendiges Programm: [`operator_overloading_demo.tiny`](operator_overloading_demo.tiny).

### Namespaces
Namenraeume koennen Funktionen logisch gruppieren. Lauf getestet mit `python tiny_language.py namespace_demo.tiny`.

```tiny
namespace Tools {
    fn double(x) { return x * 2; }
    fn label(x) { return "#" + x; }
}

define value = Tools.double(5);
print(value);
print(Tools.label("done"));
```

Erwartete Ausgabe:

```
10
#done
```

Siehe [`namespace_demo.tiny`](namespace_demo.tiny) fuer mehr Kontext.

### Module laden
- **Import-Syntax**: `import math.trig;` holt `math/trig.tiny` und bindet es standardmaessig unter dem letzten Pfadsegment (`trig`). Optional kann via Alias gebunden werden: `import utils.helpers as helpers;` oder relativ aus einem Modul heraus: `import .shared as shared;`.
- **Namespacing**: Jede importierte Datei wird unter ihrem vollqualifizierten Modulnamen registriert (z. B. `pkg.core`), sodass Funktionen und Konstanten als Namespace-Felder abrufbar sind (`core.helper_fn()` bzw. `core.value`).
- **Suchpfad**: Der Resolver prueft zuerst das Verzeichnis der aufrufenden Datei, dann Eintraege aus `TINYPATH` (mit `:` getrennt), gefolgt vom aktuellen Arbeitsverzeichnis und dem Verzeichnis von `tiny_language.py`. Fehlende Module oder Kreisimporte werden als `E008` gemeldet.
- **Caching**: Eine Moduldatei wird pro Runtime nur einmal ausgefuehrt; Mehrfach-Imports liefern denselben Namespace-Ref und vermeiden doppelte Nebeneffekte.

### Nebenlaeufigkeit
`spawn` und `join` kombinieren Aufgaben und Rueckgaben. Das untenstehende Ergebnis stammt aus `python tiny_language.py concurrency_demo.tiny`.

```tiny
fn label(prefix, word) { return prefix + "=" + word; }

define keywords = String.split("spawn,join,string,interop", ",");
define first = spawn label("erstes", heap_get(keywords, 0));
define second = spawn label("zweites", heap_get(keywords, 1));
define third = spawn label("drittes", heap_get(keywords, 2));
define fourth = spawn label("viertes", heap_get(keywords, 3));

print("etiketten");
print(String.join(new[join(first), join(second), join(third), join(fourth)], " | "));
```

Erwartete Ausgabe:

```
etiketten
erstes=spawn | zweites=join | drittes=string | viertes=interop
```

Vollversion mit erneutem Split/Join: [`concurrency_demo.tiny`](concurrency_demo.tiny).

### Heap/Pointer
`new[...]` legt Arrays an, `heap_get`/`heap_set` lesen bzw. schreiben, `delete` raeumt auf. Ausgabedaten stammen aus `python tiny_language.py heap_pointer_demo.tiny`.

```tiny
define pointer = new[1, 2, 3];
print(heap_get(pointer, 1));
heap_set(pointer, 1, 5);
print(heap_get(pointer, 1));
delete(pointer);
```

Erwartete Ausgabe:

```
2
5
```

Mehr Beispiele und Fehlerszenarien finden sich in [`heap_pointer_demo.tiny`](heap_pointer_demo.tiny).

### Standardbibliothek
Vor jedem Programmstart registriert der Interpreter die eingebaute Stdlib mit folgenden Namespaces:

- **Math**: `Math.abs(x)`, `Math.pow(base, exp)`, `Math.sqrt(x)` fuer grundlegende Mathematik. Neu hinzugekommen sind `Math.max(a, b)` und `Math.min(a, b)` zum Vergleichen sowie `Math.clamp(value, lower, upper)`, um Werte einzugrenzen. Beispiel: `print(Math.clamp(Math.max(-2, 10), 0, 5));` gibt `5` aus.
- **String**: `String.split(text, sep)` liefert einen Heap-Pointer auf ein Array der Teilstrings, `String.join(items, sep)` verbindet eine Liste/Pointer, `String.contains(text, needle)` prueft Teilstrings. Zusaetzlich gibt es `String.upper(text)`, `String.lower(text)`, `String.trim(text)` und `String.repeat(text, count)` fuer Gross-/Kleinschreibung, Whitespace-Trimming und Wiederholung. Beispiel: `print(String.upper(String.trim("  tiny "))); print(String.repeat("ha", 3));` erzeugt `TINY` und `hahaha`.
- **Collections**: `Collections.len(x)` misst die Laenge von Heap-Pointern oder Python-Listen, `Collections.push(target, value)` fuegt am Ende an und liefert die neue Laenge, `Collections.pop(target)` entfernt das letzte Element oder wirft einen Fehler bei leeren Collections. Neu sind `Collections.slice(target, start, end)` fuer Teilbereiche und `Collections.contains(target, value)` zum Nachschlagen: `define mid = Collections.slice(new[1, 2, 3], 1, 3); print(Collections.contains(mid, 2));` druckt `true`.

## Beispielprogramme
- [`demo.tiny`](demo.tiny): Kleines Schaufenster fuer Variablen, Schleifen, Funktionen, Klassen und Heap-Operationen. Laeuft sequenziell durch und druckt Zwischenergebnisse, wodurch man die Sprachfeatures in Aktion sieht.
- [`rosetta_fibonacci.tiny`](rosetta_fibonacci.tiny): Implementiert die klassische Fibonacci-Folge; zeigt Funktionsdefinitionen und einfache Loops. Erwartet werden die ersten 10 Fibonacci-Zahlen auf der Konsole.
- [`all_features.tiny`](all_features.tiny): Umfangreiches Feature-Rundlaufprogramm mit Arrays, Klassen und Operator-Overloading. Praktisch, um die Sprache als Ganzes zu erkunden.
- [`class_demo.tiny`](class_demo.tiny): Minimaler Klassen-Constructor mit Methode; gibt einen personalisierten Gruss aus.
- [`operator_overloading_demo.tiny`](operator_overloading_demo.tiny): Schlanke Punkt-Klasse, die `+` und `==` ueberschreibt und Zwischenergebnisse ausgibt.
- [`number_class.tiny`](number_class.tiny): Demonstriert die `Number`-Klasse und den ueberladenen `+`-Operator; instanziiert Objekte, ruft Methoden auf und gibt das Ergebnis aus.
- [`number_intervall.tiny`](number_intervall.tiny): Beispiel fuer numerische Intervallrechnungen und Grenzenkontrolle.
- [`namespace_demo.tiny`](namespace_demo.tiny): Kleine `Tools`-Bibliothek als Namespace mit `double` und `label`.
- [`concurrency_demo.tiny`](concurrency_demo.tiny): Startet mehrere Aufgaben mit `spawn`, sammelt die Ergebnisse ueber `join` und kombiniert sie mit `String.split`/`String.join` zu einer Ausgabe.
- [`heap_pointer_demo.tiny`](heap_pointer_demo.tiny): Zeigt sicheres Heap-Handling mit `new`, `heap_get`/`heap_set` und `delete` sowie typische Fehlermeldungen bei Out-of-Bounds- oder Feldzugriffen.

## Haeufige Fehler
- **Ungenutzte Bindungen**: Nicht verwendete lokale Variablen oder Parameter fuehren zu Fehlern (z. B. "unused parameter(s) in function f: b", "unused local binding(s): t").
- **Mutierte Parameter nicht zurueckgegeben**: Wird ein Parameter veraendert, muss er im Rueckgabewert enthalten sein (z. B. "mutated parameter(s) in function bump must be returned: a").

## Formatter, Lints und Language-Server
- **Formatter**: `python tiny_language.py --format datei.tiny` erzwingt Einrueckungen mit vier Leerzeichen, genau ein Leerzeichen um Operatoren und nach Kommas sowie normierte Import-Zeilen (`import pfad as alias;`). Kommentare bleiben erhalten.
- **Linter-Stilregeln**: Ungenutzte Bindungen lassen sich jetzt mit einem vorangestellten `_` gezielt unterdruecken. Import-Anweisungen muessen sortiert vor dem restlichen Code stehen (`E012`). Funktionsaufrufe mit Rueckgabetyp duerfen nicht laienhaft ignoriert werden (`E011`); entweder das Ergebnis binden oder bewusst mit `_ = fn();` verwerfen.
- **Language-Server-Prototyp**: Das Modul `language_server.py` bietet eine Mini-API fuer Hover, Completions und Diagnostics. Ideal, um LSP-Ideen auszuprobieren, ohne direkt einen JSON-RPC-Server zu schreiben.
- **Unvollstaendiges Destructuring**: Alle Felder eines zurueckgegebenen Structs muessen gebunden werden ("destructuring call to f must include output for argument(s): a"), und jede Bindung muss benutzt werden.
- **Bare Calls**: Funktionsaufrufe duerfen nicht allein als Statement stehen ("bare call statements are not allowed"); Ergebnis ausgeben oder zuweisen.
- **Arithmetik-Einschraenkungen**: Der `^`-Operator akzeptiert nur ganzzahlige Exponenten ("exponent for ^ must be an integer"); fuer Brueche `power` nutzen.
- **Heap/Field-Zugriffe**: Out-of-Bounds oder fehlende Felder melden Laufzeitfehler (z. B. "heap access error: index 5 out of range ...", "unknown field missing"). `errorMessage` enthaelt den letzten Laufzeitfehler.

## Programme ausfuehren und testen
- **Programm starten**: `python tiny_language.py <datei.tiny>` fuehrt ein TinyLanguage-Programm aus und beendet sich bei Erfolg mit Status 0. Beispiel: `python tiny_language.py demo.tiny`.
- **Test-Suite**: `python -m pytest` fuehrt alle Tests aus. Einzelne Dateien lassen sich gezielt starten, z. B. `python -m pytest tests/test_tiny_language.py -k class`.

### CLI: Module-Init und Publish
- **Init**: Neues Modul-Verzeichnis anlegen (`mkdir my_pkg && cd my_pkg`), einen Einstiegspunkt wie `main.tiny` erzeugen und optional eine `module.json` mit Metadaten pflegen:

  ```json
  {"name": "my_pkg", "version": "1.0.0", "entrypoint": "main.tiny", "dependencies": ["utils@^2.1.0"]}
  ```

  Anschliessend per `python ../tiny_language.py main.tiny` lokal validieren; relative Imports wie `import .helpers;` funktionieren dank des Modul-Resolvers out-of-the-box.
- **Publish**: Die Modul-Quellen samt `module.json` paketieren, z. B. `tar -czf my_pkg-1.0.0.tgz module.json *.tiny`, und in das Ziel-Repository oder Artefakt-Registry hochladen. Version-Pins (z. B. `lib@1.4.2` oder `lib@~1.4`) werden im Manifest dokumentiert und erleichtern reproduzierbare Builds.

Hinweis: Auf Plattformen ohne `readline` (z. B. Windows) werden die REPL-History-Tests automatisch mit `1 skipped` uebersprungen. Die uebrigen Tests laufen trotzdem und das Testergebnis bleibt gueltig; der Skip ist lediglich ein Hinweis auf die optionale Abhaengigkeit.

### Interaktiver REPL
- Tab-Autocomplete beruecksichtigt Keywords, Stdlib-Namen und bereits definierte Bindungen aus der aktuellen Sitzung. Die Vervollstaendigung funktioniert auch ohne native `readline`-Bibliothek.
- Die History wird im Speicher gefuehrt und kann ueber Pfeiltasten oder eine einfache Reverse-Suche (`Ctrl + R`) erneut geladen werden. Beim Beenden wird sie unter `~/.tiny_language_history` persistiert, sofern Schreibrechte vorhanden sind.

Weitere Beispiele und erwartete Diagnosen finden sich in `tests/test_tiny_language.py` und den Beispielprogrammen oben.

## Ideen für Erweiterungen
- [ ] **Pattern Matching und Algebraic Data Types**
  - [ ] Syntax-Entwurf für Sum-/Product-Types und Match-Expressions
  - [ ] Exhaustiveness-Checks im Parser/Interpreter implementieren
  - [ ] Beispielprogramme und Tests für fehlende/zusätzliche Fälle ergänzen
- [x] **Module/Packages**
  - [x] Modul-Ladesemantik (Namespacing, relative Imports, Suchpfad) definieren
  - [x] Interpreter um Modul-Resolver und Caching erweitern
  - [x] CLI-Workflow für Modul-Init/Publish (Version-Pins optional) beschreiben
- [ ] **Optionale Typ-Hinweise**
  - [ ] Syntax für optionale Typ-Anmerkungen auf Funktionen, Parametern und Rückgabewerten festlegen
  - [ ] Gradual-Typing-Prüfungen und einfache Exhaustiveness-Checks implementieren
  - [ ] Fehlermeldungen und Docs um Typ-Hinweise erweitern
- [ ] **Verbesserte Fehlerbehandlung**
  - [ ] Entwurf für `try/catch`-Blöcke oder `Result`-Typ erstellen
  - [ ] Stacktraces in Fehlermeldungen einblenden
  - [ ] Beispielprogramme/Tests für Fehlerpfade ohne Programmabbruch hinzufügen
- [ ] **Tooling**
  - [ ] Minimalen Formatter (Spacing, Semikolons, Imports) spezifizieren und implementieren
  - [ ] Linter-Regeln für ungenutzte Bindungen, Bare Calls, Style-Lints definieren
  - [ ] Language-Server-Prototyp mit Hover/Completion/Diagnostics skizzieren
- [ ] **Parallelität**
  - [ ] Design für `async/await` oder Channels mit strukturiertem Concurrency-Model beschreiben
  - [ ] Cancellation-Tokens und sichere Abbruchpfade im Runtime-Model ergänzen
  - [ ] Testfälle für deterministische und rennfreie Ausführung erstellen
- [ ] **Stdlib-Ausbau**
  - [ ] Collections-API (Maps, Sets, Deques) entwerfen und kernelnah implementieren
  - [ ] Math/Random-Erweiterungen plus File-/JSON-Utilities hinzufügen
  - [ ] Dokumentation und Beispielprogramme für neue Stdlib-Teile schreiben
- [ ] **Interop**
  - [ ] FFI-Schnittstelle zu Python-Funktionen/Modulen definieren (Argument/Return-Mapping)
  - [ ] Sicherheits- und Sandbox-Mechanismen festlegen
  - [ ] Beispiele für häufige Python-Interop-Szenarien dokumentieren
