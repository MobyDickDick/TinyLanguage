# Python interop and FFI design

This draft describes how TinyLanguage can interact safely with Python functions and modules. The focus is on clear argument/return mapping, predictable security controls, and illustrative examples.

## Goals
- **Simple API**: TinyLanguage code should load Python modules and call functions with minimal boilerplate.
- **Predictable type mapping**: Arguments and returns are deterministically mapped between TinyLanguage and Python values.
- **Security**: Sandbox rules prevent unwanted filesystem, network, or process access.
- **Testability**: Mapping and sandbox settings are deterministic and configurable per call.

## FFI API and type mapping
- **Import**: `define os = Python.import_module("os", allow=["getcwd", "listdir"]);` loads a Python module and returns a namespace object. The optional `allow` parameter restricts accessible attributes (see security).
- **Direct function call**: `define now = Python.call("time", "time");` loads the module if needed and invokes the function. Extra options like `timeout_ms` are supported: `Python.call("requests", "get", new["https://example.com"], { timeout_ms: 500 });`.
- **Bound functions**: `define sqrt = Python.fn("math", "sqrt"); define nine = sqrt(81);` creates a TinyLanguage wrapper that can be called like a regular function.
- **Exceptions**: Python exceptions propagate as TinyLanguage errors and keep the Python error type in the message (`[PYERR] ValueError: ...`).

### Type mapping TinyLanguage → Python
- `number` → `int` or `float` (depending on the presence of a fractional part)
- `string` → `str`
- `Bool` → `bool`
- `Null` → `None`
- Heap array (`new[...]`) → `list`
- `Map` → `dict`
- `Set` → `set`
- `Deque` → `collections.deque`
- Class instances → Python proxy objects that expose only their fields (no method calls on the Python side)

### Type mapping Python → TinyLanguage
- `None` → `Null`
- `bool` → `Bool`
- `int`/`float` → `number`
- `str` → `string`
- `list`/`tuple` → heap array (`new[...]`)
- `dict` → `Map`
- `set` → `Set`
- `collections.deque` → `Deque`
- Other objects → opaque proxy handles. Only identity, pointer comparisons, and passing back into Python are allowed; field access is blocked unless explicitly allowed (see security).

## Security and sandboxing
- **Per-module allowlist**: `allow=[...]` explicitly defines which attributes/functions of a module are available. The default is an empty allowlist entry that blocks everything.
- **Global bans**: Certain modules are always denied (`subprocess`, `socket`, `multiprocessing`, `ctypes`, `sys.modules` mutations). Attempts to load them raise `[PYSEC] module denied`.
- **Timeouts**: Every call supports `timeout_ms`; exceeding it yields `[PYTIMEOUT]` and aborts the Python call.
- **Side-effect sandbox**: Filesystem access is allowed only when the module and function are allowlisted and do not escape the working directory. Network access is disabled by default.
- **Isolation**: Proxy objects returned from Python do not allow attribute access unless explicitly freed via `allow` (`Python.import_module("pathlib", allow=["Path.name"])`). This prevents injecting arbitrary Python code through dynamic attributes.
- **Deterministic error codes**: Security violations, timeouts, and missing allowlist entries produce clear, distinct error prefixes (`[PYSEC]`, `[PYTIMEOUT]`, `[PYDENY]`).

## Common interop scenarios
- **Read file info**
  ```tiny
  define os = Python.import_module("os", allow=["getcwd", "stat"]);
  define cwd = os.getcwd();
  define info = os.stat("./src_tiny/demo.tiny");
  print(info.st_size);
  ```

- **Parse JSON via the Python stdlib** (as an alternative to the built-in `JSON` namespace)
  ```tiny
  define json = Python.import_module("json", allow=["loads", "dumps"]);
  define data = json.loads("{\"ok\": true}"); // Map from Python dict
  print(data["ok"]);
  print(json.dumps(data));
  ```

- **Numerics with `math`**
  ```tiny
  define math = Python.import_module("math", allow=["sqrt", "isfinite"]);
  define root = math.sqrt(144);
  print(root);
  print(math.isfinite(root));
  ```

- **HTTP call with timeout**
  ```tiny
  define response = Python.call("requests", "get", new["https://example.com"], { allow=["status_code", "text"], timeout_ms: 300 });
  print(response.status_code);
  ```

- **Proxy pass-through** (without field access)
  ```tiny
  define datetime = Python.import_module("datetime", allow=["datetime"]);
  define now = datetime.datetime.utcnow(); // returns proxy
  // Proxy can only be forwarded into other Python calls
  define iso = Python.call("datetime", "datetime.isoformat", new[now]);
  print(iso);
  ```

## Demo programmes zum Ausprobieren

Die `.tiny`-Beispiele im Repository spiegeln die oben beschriebenen Flows wider und können direkt ausgeführt werden:

- `src_tiny/python_math_demo.tiny`: lädt `math` mit einer Allowlist, ruft `sqrt`/`isfinite` auf und liest die Konstante `tau`.
- `src_tiny/python_json_demo.tiny`: kombiniert einen direkten `Python.call` auf `os.getcwd` mit JSON-`loads`/`dumps` und zeigt, wie Listen aus Python als Heap-Pointer zurückkommen.

Aufruf jeweils mit:

```
python src/tiny_language.py <pfad_zur_datei.tiny>
```
