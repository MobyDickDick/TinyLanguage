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

### Standardbibliothek
Vor jedem Programmstart registriert der Interpreter die eingebaute Stdlib mit folgenden Namespaces:

- **Math**: `Math.abs(x)`, `Math.pow(base, exp)`, `Math.sqrt(x)` fuer grundlegende Mathematik. Neu hinzugekommen sind `Math.max(a, b)` und `Math.min(a, b)` zum Vergleichen sowie `Math.clamp(value, lower, upper)`, um Werte einzugrenzen. Beispiel: `print(Math.clamp(Math.max(-2, 10), 0, 5));` gibt `5` aus.
- **String**: `String.split(text, sep)` liefert einen Heap-Pointer auf ein Array der Teilstrings, `String.join(items, sep)` verbindet eine Liste/Pointer, `String.contains(text, needle)` prueft Teilstrings. Zusaetzlich gibt es `String.upper(text)`, `String.lower(text)`, `String.trim(text)` und `String.repeat(text, count)` fuer Gross-/Kleinschreibung, Whitespace-Trimming und Wiederholung. Beispiel: `print(String.upper(String.trim("  tiny "))); print(String.repeat("ha", 3));` erzeugt `TINY` und `hahaha`.
- **Collections**: `Collections.len(x)` misst die Laenge von Heap-Pointern oder Python-Listen, `Collections.push(target, value)` fuegt am Ende an und liefert die neue Laenge, `Collections.pop(target)` entfernt das letzte Element oder wirft einen Fehler bei leeren Collections. Neu sind `Collections.slice(target, start, end)` fuer Teilbereiche und `Collections.contains(target, value)` zum Nachschlagen: `define mid = Collections.slice(new[1, 2, 3], 1, 3); print(Collections.contains(mid, 2));` druckt `true`.

## Beispielprogramme
- [`demo.tiny`](demo.tiny): Kleines Schaufenster fuer Variablen, Schleifen, Funktionen, Klassen und Heap-Operationen. Laeuft sequenziell durch und druckt Zwischenergebnisse, wodurch man die Sprachfeatures in Aktion sieht.
- [`rosetta_fibonacci.tiny`](rosetta_fibonacci.tiny): Implementiert die klassische Fibonacci-Folge; zeigt Funktionsdefinitionen und einfache Loops. Erwartet werden die ersten 10 Fibonacci-Zahlen auf der Konsole.
- [`all_features.tiny`](all_features.tiny): Umfangreiches Feature-Rundlaufprogramm mit Arrays, Klassen und Operator-Overloading. Praktisch, um die Sprache als Ganzes zu erkunden.
- [`number_class.tiny`](number_class.tiny): Demonstriert die `Number`-Klasse und den ueberladenen `+`-Operator; instanziiert Objekte, ruft Methoden auf und gibt das Ergebnis aus.
- [`number_intervall.tiny`](number_intervall.tiny): Beispiel fuer numerische Intervallrechnungen und Grenzenkontrolle.
- [`concurrency_demo.tiny`](concurrency_demo.tiny): Startet mehrere Aufgaben mit `spawn`, sammelt die Ergebnisse ueber `join` und kombiniert sie mit `String.split`/`String.join` zu einer Ausgabe.

## Haeufige Fehler
- **Ungenutzte Bindungen**: Nicht verwendete lokale Variablen oder Parameter fuehren zu Fehlern (z. B. "unused parameter(s) in function f: b", "unused local binding(s): t").
- **Mutierte Parameter nicht zurueckgegeben**: Wird ein Parameter veraendert, muss er im Rueckgabewert enthalten sein (z. B. "mutated parameter(s) in function bump must be returned: a").
- **Unvollstaendiges Destructuring**: Alle Felder eines zurueckgegebenen Structs muessen gebunden werden ("destructuring call to f must include output for argument(s): a"), und jede Bindung muss benutzt werden.
- **Bare Calls**: Funktionsaufrufe duerfen nicht allein als Statement stehen ("bare call statements are not allowed"); Ergebnis ausgeben oder zuweisen.
- **Arithmetik-Einschraenkungen**: Der `^`-Operator akzeptiert nur ganzzahlige Exponenten ("exponent for ^ must be an integer"); fuer Brueche `power` nutzen.
- **Heap/Field-Zugriffe**: Out-of-Bounds oder fehlende Felder melden Laufzeitfehler (z. B. "heap access error: index 5 out of range ...", "unknown field missing"). `errorMessage` enthaelt den letzten Laufzeitfehler.

## Programme ausfuehren und testen
- **Programm starten**: `python tiny_language.py <datei.tiny>` fuehrt ein TinyLanguage-Programm aus und beendet sich bei Erfolg mit Status 0. Beispiel: `python tiny_language.py demo.tiny`.
- **Test-Suite**: `python -m pytest` fuehrt alle Tests aus. Einzelne Dateien lassen sich gezielt starten, z. B. `python -m pytest tests/test_tiny_language.py -k class`.

Hinweis: Auf Plattformen ohne `readline` (z. B. Windows) werden die REPL-History-Tests automatisch mit `1 skipped` uebersprungen. Die uebrigen Tests laufen trotzdem und das Testergebnis bleibt gueltig; der Skip ist lediglich ein Hinweis auf die optionale Abhaengigkeit.

Weitere Beispiele und erwartete Diagnosen finden sich in `tests/test_tiny_language.py` und den Beispielprogrammen oben.
