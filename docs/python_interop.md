# Python-Interop und FFI-Entwurf

Dieser Entwurf beschreibt, wie TinyLanguage kontrolliert mit Python-Funktionen und -Modulen interagieren kann. Der Schwerpunkt liegt auf einer klaren Argument-/Return-Abbildung, vorhersehbaren Sicherheitsmechanismen und anschaulichen Beispielen.

## Ziele
- **Einfache API**: TinyLanguage-Code soll Python-Module laden und Funktionen mit minimaler Boilerplate aufrufen können.
- **Vorhersehbare Typabbildung**: Argumente und Rückgaben werden deterministisch zwischen TinyLanguage- und Python-Werten gemappt.
- **Sicherheit**: Ein Sandbox-Mechanismus verhindert ungewollte Dateisystem-, Netzwerk- oder Prozesszugriffe.
- **Testbarkeit**: Das Mapping und die Sandbox-Einstellungen sind deterministisch und pro Aufruf konfigurierbar.

## FFI-API und Typ-Mapping
- **Import**: `define os = Python.import_module("os", allow=["getcwd", "listdir"]);` lädt ein Python-Modul und gibt ein Namespace-Objekt zurück. Der optionale `allow`-Parameter schränkt zugängliche Attribute ein (siehe Sicherheit).
- **Direkter Funktionsaufruf**: `define now = Python.call("time", "time");` lädt das Modul bei Bedarf und ruft die Funktion auf. Zusatzoptionen wie `timeout_ms` sind erlaubt: `Python.call("requests", "get", new["https://example.com"], { timeout_ms: 500 });`.
- **Gebundene Funktionen**: `define sqrt = Python.fn("math", "sqrt"); define nine = sqrt(81);` erstellt einen TinyLanguage-Wrapper, der wie eine normale Funktion aufgerufen werden kann.
- **Exceptions**: Python-Ausnahmen werden als TinyLanguage-Fehler propagiert und behalten den Python-Fehlertyp im Fehlermeldungstext (`[PYERR] ValueError: ...`).

### Typ-Mapping TinyLanguage → Python
- `number` → `int` oder `float` (abhängig vom Vorhandensein von Nachkommastellen)
- `string` → `str`
- `Bool` → `bool`
- `Null` → `None`
- Heap-Array (`new[...]`) → `list`
- `Map` → `dict`
- `Set` → `set`
- `Deque` → `collections.deque`
- Klasseninstanzen → Python-Proxy-Objekte, die nur ihre Felder exponieren (keine Methodenaufrufe auf der Python-Seite)

### Typ-Mapping Python → TinyLanguage
- `None` → `Null`
- `bool` → `Bool`
- `int`/`float` → `number`
- `str` → `string`
- `list`/`tuple` → Heap-Array (`new[...]`)
- `dict` → `Map`
- `set` → `Set`
- `collections.deque` → `Deque`
- Andere Objekte → intransparente Proxy-Handles. Nur Identität, Pointer-Vergleiche und Übergabe zurück an Python sind erlaubt; Feldzugriff ist blockiert, sofern nicht explizit freigegeben (siehe Sicherheit).

## Sicherheits- und Sandbox-Mechanismen
- **Allowlist pro Modul**: `allow=[...]` definiert explizit, welche Attribute/Funktionen eines Moduls verfügbar sind. Standard ist ein leerer Allowlist-Eintrag, der alle Attribute blockiert.
- **Globale Sperren**: Bestimmte Module sind generell gesperrt (`subprocess`, `socket`, `multiprocessing`, `ctypes`, `sys.modules` Mutationen). Versuche, sie zu laden, erzeugen einen Fehler `[PYSEC] module denied`.
- **Timeouts**: Jeder Aufruf unterstützt `timeout_ms`; überschrittene Zeit führt zu `[PYTIMEOUT]` und bricht den Python-Call ab.
- **Side-Effect-Sandbox**: Dateisystemzugriffe sind nur erlaubt, wenn das Modul und die Funktion auf einer Allowlist stehen und das Arbeitsverzeichnis nicht verlassen. Netzwerkzugriffe sind standardmäßig verboten.
- **Isolation**: Proxy-Objekte, die aus Python zurückgegeben werden, erlauben keinen Attributzugriff, außer wenn sie via `allow` explizit freigegeben sind (`Python.import_module("pathlib", allow=["Path.name"])`). Dies verhindert das Einschleusen von beliebigem Python-Code über dynamische Attribute.
- **Deterministische Fehlercodes**: Sicherheitsverletzungen, Zeitüberschreitungen und fehlende Allowlist-Einträge liefern klar getrennte Fehlerpräfixe (`[PYSEC]`, `[PYTIMEOUT]`, `[PYDENY]`).

## Häufige Interop-Szenarien
- **Datei-Infos auslesen**
  ```tiny
  define os = Python.import_module("os", allow=["getcwd", "stat"]);
  define cwd = os.getcwd();
  define info = os.stat("./demo.tiny");
  print(info.st_size);
  ```

- **JSON per Python-Stdlib parsen** (als Alternative zur eingebauten `JSON`-Namespace)
  ```tiny
  define json = Python.import_module("json", allow=["loads", "dumps"]);
  define data = json.loads("{\"ok\": true}"); // Map aus Python-dict
  print(data["ok"]);
  print(json.dumps(data));
  ```

- **Numerik mit `math`**
  ```tiny
  define math = Python.import_module("math", allow=["sqrt", "isfinite"]);
  define root = math.sqrt(144);
  print(root);
  print(math.isfinite(root));
  ```

- **HTTP-Call mit Timeout**
  ```tiny
  define response = Python.call("requests", "get", new["https://example.com"], { allow=["status_code", "text"], timeout_ms: 300 });
  print(response.status_code);
  ```

- **Proxy-Weitergabe** (ohne Feldzugriff)
  ```tiny
  define datetime = Python.import_module("datetime", allow=["datetime"]);
  define now = datetime.datetime.utcnow(); // gibt Proxy zurueck
  // Proxy kann nur an andere Python-Aufrufe weitergereicht werden
  define iso = Python.call("datetime", "datetime.isoformat", new[now]);
  print(iso);
  ```
