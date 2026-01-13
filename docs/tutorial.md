# TinyLanguage beginner tutorial

This tutorial shows how to get TinyLanguage running locally, walk through the core syntax, and explore the tooling that ships with the repository. Run the commands from the repository root and keep `src/` on your `PYTHONPATH` when a command mentions it.

## 1. Setup

- Install Python 3 and clone the repository.
- From the repo root, you can run the interpreter directly with `python src/tiny_language.py`.
- The bundled demos live in `src_tiny/`; they work without additional dependencies.

## 2. Your first TinyLanguage program

Create `hello.tiny` with a single print statement:

```tiny
print("Hello, TinyLanguage!");
```

Run it through the interpreter:

```bash
python src/tiny_language.py hello.tiny
```

You can also try the richer demo that exercises variables, functions, and control flow:

```bash
python src/tiny_language.py src_tiny/demo.tiny
```

## 3. Language basics in one file

The snippet below shows the most common constructs together. Save it as `basics.tiny` and compare the output to the inline comments.

```tiny
// Variables, arithmetic, printing
def a = 7 + 5 * 2;
print(a);                // -> 17

// Declare and call functions
fn add(x, y) {
    return x + y;
}

def sum = add(a, 3);
print(sum);

// If/while and mutation
def i = 0;
while (i < 3) {
    if (i == 1) { print("in the middle"); }
    i = i + 1;
}

// Namespaces
namespace Math {
    fn inc(x) { return add(x, 1); }
}
print(Math.inc(4));
```

Run it with the interpreter or the native backend to see both execution paths:

```bash
python src/tiny_language.py basics.tiny
python src/tiny_language.py --native-backend basics.tiny
```

## 4. Types, pattern matching, and classes

Once you are comfortable with the basics, explore the feature-specific demos:

- Type hints and exhaustiveness checks: `python src/tiny_language.py src_tiny/all_features.tiny`
- Pattern matching and algebraic data types: `python src/tiny_language.py src_tiny/match_demo.tiny`
- Classes and methods: `python src/tiny_language.py src_tiny/class_demo.tiny`
- Namespaces and modular structure: `python src/tiny_language.py src_tiny/namespace_demo.tiny`

Each file prints its expected output and doubles as a runnable reference.

## 5. Modules and the CLI wrapper

For multi-file projects, use the CLI helper that understands module manifests:

```bash
python -m tiny_lang_cli --file my_pkg/main.tiny --backend interpreter
TINYPATH=../deps python -m tiny_lang_cli --file my_pkg/main.tiny --native-backend
python -m tiny_lang_cli -e "print(1 + 2);" --backend interpreter
python -m tiny_lang_cli --file my_pkg/main.tiny -- --flag value
```

The `module.json` file in a package declares entry points and dependencies; see the module workflows in `docs/demo_run_commands.md` for more examples.

## 6. Tooling and tests

- Run a focused example set and the pytest suite together with `python run_all.py`.
- Call the language-server helper for hover, completions, or diagnostics, e.g. `PYTHONPATH=src python src/language_server_cli.py --file src_tiny/class_demo.tiny hover --symbol Greeter`.
- Compare interpreter vs. native backend output with `python src/tiny_language.py --native-backend src_tiny/all_features.tiny`.

These commands give quick feedback loops for experimenting with new code or validating changes.
