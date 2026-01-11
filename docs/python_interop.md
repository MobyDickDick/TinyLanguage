# Python interop and FFI design

This draft describes how TinyLanguage can interact safely with Python functions and modules. The focus is on clear argument/return mapping, predictable security controls, and illustrative examples.

## Goals

- **Simple API**: TinyLanguage code should load Python modules and call functions with minimal boilerplate.
- **Predictable type mapping**: Arguments and returns are deterministically mapped between TinyLanguage and Python values.
- **Security**: Sandbox rules prevent unwanted filesystem, network, or process access.
- **Testability**: Mapping and sandbox settings are deterministic and configurable per call.

## FFI API and type mapping

- **Import**: `def os = Python.import_module("os", new["getcwd", "listdir"]);` loads a Python module and returns a namespace object. The allowlist (heap array) restricts accessible attributes (see security).
- **Direct function call**: `def now = Python.call("time", "time", Null, { allow: new["time"] });` loads the module if needed and invokes the function. Extra options like `timeout_ms` are supported: `Python.call("requests", "get", new["https://example.com"], { allow: new["status_code", "text"], timeout_ms: 500 });`.
- **Bound functions**: `def sqrt = Python.fn("math", "sqrt"); def nine = sqrt(81);` creates a TinyLanguage wrapper that can be called like a regular function.
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

- **Per-module allowlist**: `new[...]` explicitly defines which attributes/functions of a module are available. The default is an empty allowlist entry that blocks everything.
- **Global bans**: Certain modules are always denied (`subprocess`, `socket`, `multiprocessing`, `ctypes`, `ssl`, `sys`). Attempts to load them raise `[PYSEC] module denied`.
- **Timeouts**: Every call supports `timeout_ms`; exceeding it yields `[PYTIMEOUT]` and aborts the Python call.
- **Allowlist enforcement**: Calls without an explicit allowlist rely on the attributes registered through `Python.import_module`; without one, the call is denied with `[PYDENY]`.
- **Side-effect sandbox**: Filesystem access is allowed only when the module and function are allowlisted and do not escape the working directory. Network access is disabled by default.
- **Isolation**: Proxy objects returned from Python do not allow attribute access unless explicitly freed via `allow` (`Python.import_module("pathlib", new["Path.name"])`). This prevents injecting arbitrary Python code through dynamic attributes.
- **Deterministic error codes**: Security violations, timeouts, and missing allowlist entries produce clear, distinct error prefixes (`[PYSEC]`, `[PYTIMEOUT]`, `[PYDENY]`).

## Common interop scenarios

- **Read file info**

  ```tiny
  def os = Python.import_module("os", new["getcwd", "stat"]);
  def cwd = os.getcwd();
  def info = os.stat("./src_tiny/demo.tiny");
  print(info.st_size);
  ```

- **Parse JSON via the Python stdlib** (as an alternative to the built-in `JSON` namespace)

  ```tiny
  def json = Python.import_module("json", new["loads", "dumps"]);
  def data = json.loads("{\"ok\": true}"); // Map from Python dict
  print(data["ok"]);
  print(json.dumps(data));
  ```

- **Numerics with `math`**

  ```tiny
  def math = Python.import_module("math", new["sqrt", "isfinite"]);
  def root = math.sqrt(144);
  print(root);
  print(math.isfinite(root));
  ```

- **HTTP call with timeout**

  ```tiny
  def response = Python.call("requests", "get", new["https://example.com"], { allow: new["status_code", "text"], timeout_ms: 300 });
  print(response.status_code);
  ```

- **Proxy pass-through** (without field access)

  ```tiny
  def datetime = Python.import_module("datetime", new["datetime"]);
  def now = datetime.datetime.utcnow(); // returns proxy
  // Proxy can only be forwarded into other Python calls
  def iso = Python.call("datetime", "datetime.isoformat", new[now], { allow: new["datetime"] });
  print(iso);
  ```

## End-to-end checklist: modules, namespaces, typing

The most important `.tiny` demos combine modular imports, namespaces, and (where given) typed signatures. Each run lists the exact command and an expected output as a quick regression check:

- **Typed namespace plus two modules** (`src_tiny/python_namespace_typed_demo.tiny`)

  ```bash
  PYTHONPATH=src python src/tiny_language.py src_tiny/python_namespace_typed_demo.tiny
  # Expected output
  13.0
  tau fraction=0.499999999985709
  file=example.txt
  ```

  Shows encapsulated allowlist imports (`math`, `os.path`) under `namespace PyInterop` with annotated wrapper functions.

- **JSON parsing and OS interop** (`src_tiny/python_json_demo.tiny`)

  ```bash
  PYTHONPATH=src python src/tiny_language.py src_tiny/python_json_demo.tiny
  # Expected output
  cwd=.../TinyLanguage
  ok=True
  payload={"ok": true}
  ```

  Combines `Python.call` and `Python.import_module` with separate allowlists and demonstrates how a Python proxy (`os.getcwd`) can be threaded into further Python calls.

- **Numerics with a tight allowlist** (`src_tiny/python_math_demo.tiny`)

  ```bash
  PYTHONPATH=src python src/tiny_language.py src_tiny/python_math_demo.tiny
  # Expected output
  13.0
  tau=6.283185307179586
  isfinite=true
  ```

  Shows the round trip for numbers/booleans plus the restricted exposure of selected `math` attributes (`sqrt`, `isfinite`, `tau`).

- **Proxy pipeline with namespaces and type annotations** (`src_tiny/python_proxy_pipeline_demo.tiny`)

  ```bash
  PYTHONPATH=src python src/tiny_language.py src_tiny/python_proxy_pipeline_demo.tiny
  # Expected output
  81.0
  /tmp/example.txt
  {"area": 12}
  ```

  Combines two Python modules in one namespace (`math`, `os.path`) plus a typed helper function that supplies Python strings via `builtins.str`.

All four runs document modular import, namespaces, and typed signatures in one go. When adding new demos, always record the allowed attributes and expected output so they remain reliable regression tests.

## Additional end-to-end demos with combined feature focus

The following mini-scenarios complement the list above and highlight common pitfalls (allowlist, proxy passing, optional types) in one sweep:

- **Compact allowlist comparison** (`src_tiny/python_json_demo.tiny` versus an intentionally strict allowlist):

  ```bash
  PYTHONPATH=src python src/tiny_language.py src_tiny/python_json_demo.tiny
  # Expected output
  cwd=.../TinyLanguage
  ok=True
  payload={"ok": true}

  # A tighter allowlist forces an error; this is a good security regression test
  PYTHONPATH=src python src/tiny_language.py --eval 'def json = Python.import_module("json", new["loads"]); def _unused8 = json.dumps(new["x"]);'
  # Expected output
  # [PYDENY] attribute dumps not allowlisted on module json
  ```

  - **Proxy pipeline plus namespace signatures** (`src_tiny/python_proxy_pipeline_demo.tiny`):

  ```bash
  PYTHONPATH=src python src/tiny_language.py src_tiny/python_proxy_pipeline_demo.tiny
  # Expected output
  81.0
  /tmp/example.txt
  {"area": 12}
  ```

  Shows transporting a Python proxy across multiple namespaces and typed wrappers.

- **Type annotations plus modular imports together** (`src_tiny/python_namespace_typed_demo.tiny`):

  ```bash
  PYTHONPATH=src python src/tiny_language.py src_tiny/python_namespace_typed_demo.tiny
  # Expected output
  13.0
  tau fraction=0.499999999985709
  file=example.txt
  ```

  Combination of namespaces, allowlists, and strict return types (the linter flags missing returns immediately with `[E010]`).

- **Timeout- und Fehlercodes sichtbar machen** (bewusst lange HTTP-Anfrage):

  ```bash
  PYTHONPATH=src python src/tiny_language.py --eval 'Python.call("requests", "get", new["https://example.com"], { allow: new["status_code", "text"], timeout_ms: 1 });'
  # Expected output
  # [PYTIMEOUT] requests.get exceeded 1 ms
  ```

  Helps keep the deterministic error prefixes `[PYSEC]`, `[PYTIMEOUT]`, `[PYDENY]` visible.
