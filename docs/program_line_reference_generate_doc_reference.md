# Line-by-line program documentation: doc reference generator

This document provides a line-level explanation for the Python implementation
and its TinyLanguage wrapper that generate the docstring reference. Each line
is documented with intent and rationale. Repeated patterns are explained once
and referenced via cross-reference tags.

## Cross-reference tags

- **[P-IMPORT]**: Import or built-in access line that gathers dependencies for
  later use; rationale is to keep the remaining logic focused and explicit.
- **[P-ASSIGN-INIT]**: Initialize a variable with a simple literal or computed
  value to make subsequent logic readable and to avoid re-computation.
- **[P-LIST-APPEND]**: Append to a list to preserve ordering for deterministic
  output.
- **[P-GUARD]**: Conditional guard that narrows logic, prevents invalid data,
  or skips work.
- **[P-RETURN]**: Return a computed value, making the function’s output
  explicit and traceable.
- **[T-PY-IMPORT]**: TinyLanguage wrapper line that imports Python modules or
  functions for parity with the Python implementation.
- **[T-ARRAY-BUILD]**: TinyLanguage list construction with a loop to mirror
  Python list handling.
- **[T-PY-ARGV]**: TinyLanguage lines that synchronize arguments with Python’s
  `sys.argv` for consistent CLI behavior.

## Python: `tools/generate_doc_reference.py`

**High-level intent:** Build a deterministic Markdown reference by extracting
module, class, and function docstrings from Python source files.

| Line | Explanation |
| --- | --- |
| 1 | Shebang identifies the script as Python 3 for direct CLI execution. |
| 2 | Module docstring declares the purpose so tooling can surface it in docs. |
| 3 | Blank line separates header/docstring from imports for readability. |
| 4 | Future import enables postponed annotations, keeping type hints clean without runtime dependency loops. |
| 5 | Blank line separates future import from standard imports. |
| 6 | [P-IMPORT] Pull in `argparse` for CLI argument parsing. |
| 7 | [P-IMPORT] Pull in `ast` for parsing Python source into AST nodes. |
| 8 | [P-IMPORT] Import `dataclass` to define structured, typed containers. |
| 9 | [P-IMPORT] Import `Path` for filesystem path handling. |
| 10 | [P-IMPORT] Import typing helpers for explicit iterable and list types. |
| 11 | Blank line separates imports from data model definitions. |
| 12 | Blank line keeps visual separation before the first dataclass. |
| 13 | Decorator turns `DocItem` into an immutable dataclass for consistent sorting and use in output. |
| 14 | Class header establishes a single documentation item record. |
| 15 | Field stores whether the item is a function, class, or method to format headings. |
| 16 | Field stores the simple name for quick reference. |
| 17 | Field stores the qualified name so class methods can be disambiguated. |
| 18 | Field stores the optional docstring extracted from the AST. |
| 19 | Blank line separates data model definitions. |
| 20 | Blank line keeps spacing between dataclasses. |
| 21 | Decorator turns `ModuleDoc` into an immutable dataclass for stable output. |
| 22 | Class header defines a module-level documentation container. |
| 23 | Field tracks the module path for deterministic ordering and headers. |
| 24 | Field stores the module docstring for the top-level description. |
| 25 | Field stores all items discovered within the module. |
| 26 | Blank line separates helper definitions. |
| 27 | Blank line creates space before the first helper function. |
| 28 | Function header defines the iterator over Python source files. |
| 29 | Loop walks each provided path so directories and files can be mixed. |
| 30 | [P-GUARD] Check for directories to allow recursive discovery. |
| 31 | Inner loop searches for `*.py` files recursively to catch nested modules. |
| 32 | [P-GUARD] Skip hidden files to avoid scanning editor or cache artifacts. |
| 33 | [P-GUARD] Continue immediately once a hidden file is detected. |
| 34 | [P-RETURN] Yield each discovered Python file to the caller. |
| 35 | [P-GUARD] Else branch handles direct file paths with `.py` suffixes. |
| 36 | [P-RETURN] Yield the file path directly when it is an explicit Python file. |
| 37 | Blank line separates helper functions. |
| 38 | Blank line keeps spacing before the next helper. |
| 39 | Function header defines the docstring extraction for a single module. |
| 40 | [P-ASSIGN-INIT] Read the source text as UTF-8 to preserve docstrings. |
| 41 | Parse the source into an AST so docstrings can be extracted reliably. |
| 42 | Extract the module-level docstring once for the module header. |
| 43 | [P-ASSIGN-INIT] Initialize the items list that will collect per-symbol docstrings. |
| 44 | Blank line separates setup from the AST walk. |
| 45 | Loop over top-level nodes to find functions and classes. |
| 46 | [P-GUARD] Identify top-level functions for doc extraction. |
| 47 | [P-LIST-APPEND] Begin constructing a `DocItem` for the function. |
| 48 | Continue building the `DocItem` with a `function` kind label. |
| 49 | [P-ASSIGN-INIT] Store the function name for the item. |
| 50 | [P-ASSIGN-INIT] Use the same name as the qualified name at module scope. |
| 51 | [P-ASSIGN-INIT] Pull the function docstring from the AST node. |
| 52 | Close the `DocItem` initializer for the function. |
| 53 | Close the `items.append` call for the function. |
| 54 | [P-GUARD] Else branch checks for class definitions. |
| 55 | [P-ASSIGN-INIT] Extract class docstring once to reuse. |
| 56 | [P-LIST-APPEND] Begin constructing a `DocItem` for the class itself. |
| 57 | Continue building the `DocItem` with a `class` kind label. |
| 58 | [P-ASSIGN-INIT] Store the class name for the item. |
| 59 | [P-ASSIGN-INIT] Use the class name as its qualified name. |
| 60 | [P-ASSIGN-INIT] Store the class docstring on the class entry. |
| 61 | Close the `DocItem` initializer for the class. |
| 62 | Close the `items.append` call for the class. |
| 63 | Loop over class body to find methods for additional doc entries. |
| 64 | [P-GUARD] Identify methods as `FunctionDef` nodes. |
| 65 | [P-LIST-APPEND] Begin constructing a `DocItem` for the method. |
| 66 | Continue building the `DocItem` with a `method` kind label. |
| 67 | [P-ASSIGN-INIT] Store the method name. |
| 68 | [P-ASSIGN-INIT] Format the qualified name as `Class.method` for clarity. |
| 69 | [P-ASSIGN-INIT] Extract the method docstring from the AST node. |
| 70 | Close the `DocItem` initializer for the method. |
| 71 | Close the `items.append` call for the method. |
| 72 | Blank line separates loop body from return. |
| 73 | [P-RETURN] Return a fully populated `ModuleDoc` for the caller. |
| 74 | Blank line separates helper functions. |
| 75 | Blank line keeps spacing before the next helper. |
| 76 | Function header formats docstrings into markdown lines. |
| 77 | [P-GUARD] Return placeholder text when no docstring is available. |
| 78 | [P-RETURN] Provide the placeholder line so output remains explicit. |
| 79 | [P-RETURN] Split docstring into lines and prefix indentation for markdown formatting. |
| 80 | Blank line separates helpers. |
| 81 | Blank line keeps spacing before the renderer. |
| 82 | Function header defines markdown rendering for the module list. |
| 83 | [P-ASSIGN-INIT] Initialize the markdown lines with a fixed header. |
| 84 | [P-LIST-APPEND] Include a blank line to separate header from description. |
| 85 | [P-LIST-APPEND] Provide a short description of generated content. |
| 86 | [P-LIST-APPEND] Add another blank line to separate description from modules. |
| 87 | Loop over modules to render each module’s section in order. |
| 88 | [P-LIST-APPEND] Add a module header using a stable path string. |
| 89 | [P-LIST-APPEND] Add a blank line before module docstring content. |
| 90 | [P-LIST-APPEND] Include formatted module docstring lines. |
| 91 | [P-LIST-APPEND] Add a blank line after module docstring. |
| 92 | [P-GUARD] If the module has no items, write a placeholder and skip item rendering. |
| 93 | [P-LIST-APPEND] Add the placeholder for empty modules. |
| 94 | [P-LIST-APPEND] Add a blank line after the placeholder. |
| 95 | [P-GUARD] Continue to the next module after handling an empty module. |
| 96 | Loop over items to render each function/class/method section. |
| 97 | [P-LIST-APPEND] Add a heading that names the item and its qualified name. |
| 98 | [P-LIST-APPEND] Add a blank line before the item docstring. |
| 99 | [P-LIST-APPEND] Include formatted docstring lines for the item. |
| 100 | [P-LIST-APPEND] Add a blank line after the item content. |
| 101 | [P-RETURN] Join lines into a single markdown string with trailing newline normalization. |
| 102 | Blank line separates the renderer from CLI entrypoint. |
| 103 | Blank line keeps spacing before `main`. |
| 104 | Function header defines CLI entrypoint used by scripts and tests. |
| 105 | Construct an argument parser with the same description as the module docstring. |
| 106 | Close the parser initializer call. |
| 107 | Add positional `paths` argument for modules/directories to scan. |
| 108 | Specify `nargs` so at least one path is required. |
| 109 | Provide help text for the `paths` argument. |
| 110 | Close the `paths` argument block. |
| 111 | Add `--output` argument to optionally write to a file. |
| 112 | Specify the type as `Path` for consistent path handling. |
| 113 | Provide help text for the output file. |
| 114 | Close the `--output` argument block. |
| 115 | Parse CLI arguments into the `args` namespace. |
| 116 | [P-ASSIGN-INIT] Convert string paths into `Path` objects. |
| 117 | Build the module doc list by iterating over discovered Python files. |
| 118 | Sort modules by their path strings for deterministic output. |
| 119 | Render the markdown output content from the collected modules. |
| 120 | [P-GUARD] If an output path is provided, write to the file. |
| 121 | Write the markdown to disk using UTF-8 encoding for reproducibility. |
| 122 | [P-GUARD] Else branch writes to stdout when no output file is provided. |
| 123 | Print the markdown to standard output. |
| 124 | [P-RETURN] Return zero to indicate success. |
| 125 | Blank line separates `main` from the script guard. |
| 126 | Blank line keeps spacing before the module guard. |
| 127 | Script guard ensures `main` is invoked only when run directly. |
| 128 | Convert the `main` return code into a `SystemExit` for shell integration. |

## TinyLanguage: `src_tiny/generate_doc_reference.tiny`

**High-level intent:** Provide a TinyLanguage CLI wrapper that forwards to the
Python doc reference generator while normalizing arguments and exit codes.

| Line | Explanation |
| --- | --- |
| 1 | File-level comment identifies the Tiny wrapper and its Python counterpart. |
| 2 | File-level comment clarifies parity intent with the Python implementation. |
| 3 | Blank line separates comments from imports. |
| 4 | [T-PY-IMPORT] Import the Python `main` function so Tiny can invoke it. |
| 5 | [T-PY-IMPORT] Import `os.getenv` to read CLI arguments from the environment. |
| 6 | [T-PY-IMPORT] Import `sys.argv` so it can be overridden for parity. |
| 7 | [T-PY-IMPORT] Import `exit`, `list`, and `setattr` for process control and argv setup. |
| 8 | Blank line separates imports from helper definitions. |
| 9 | Function header defines a helper to fetch JSON-encoded CLI args from `TINYLANG_ARGS`. |
| 10 | [P-ASSIGN-INIT] Read the environment variable with a default empty string. |
| 11 | [P-ASSIGN-INIT] Initialize a JSON fallback payload representing an empty argv list. |
| 12 | [P-GUARD] If the env var is present and non-empty, use it as the payload. |
| 13 | [P-RETURN] Parse the JSON payload into a Tiny array for argv processing. |
| 14 | Function end. |
| 15 | Blank line separates helper functions. |
| 16 | Function header defines a helper to add a program name to argv. |
| 17 | [P-ASSIGN-INIT] Seed the argv list with the program name string. |
| 18 | [P-ASSIGN-INIT] Initialize a loop index for array traversal. |
| 19 | [T-ARRAY-BUILD] Loop over the incoming argv array. |
| 20 | [T-ARRAY-BUILD] Push each argument into the new argv list. |
| 21 | [T-ARRAY-BUILD] Increment the index to progress the loop. |
| 22 | [T-ARRAY-BUILD] End the loop once all args are appended. |
| 23 | [P-RETURN] Return the completed argv list with the program name prefix. |
| 24 | Function end. |
| 25 | Blank line separates helper functions. |
| 26 | Function header defines argv synchronization with Python’s `sys.argv`. |
| 27 | [T-PY-ARGV] Convert the Tiny argv list into a Python list. |
| 28 | [T-PY-ARGV] Set `sys.argv` to the newly constructed list. |
| 29 | Function end. |
| 30 | Blank line separates helper functions. |
| 31 | Function header defines the main wrapper flow. |
| 32 | [P-ASSIGN-INIT] Load argv from the environment helper. |
| 33 | [T-PY-ARGV] Replace `sys.argv` with the normalized argv list. |
| 34 | [P-ASSIGN-INIT] Execute the Python `main` and capture its return code. |
| 35 | [P-GUARD] If Python returned `Null`, treat it as success and exit with `0`. |
| 36 | [P-RETURN] Exit the process with the explicit return code. |
| 37 | Function end. |
| 38 | Blank line separates the helper from the script guard. |
| 39 | Script guard ensures the wrapper runs when the module is executed. |
