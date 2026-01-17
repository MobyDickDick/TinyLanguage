# Documentation tooling pipeline

This repository now includes a small, deterministic pipeline for turning Python
module docstrings into a generated Markdown reference. The goal is to make it
practical to add line-level rationale in docstrings without manually curating a
separate reference document.

## What the generator does

- Scans Python modules from a list of files or directories.
- Captures module docstrings along with top-level functions, classes, and class
  methods.
- Emits a Markdown file that can be checked in or referenced during reviews.

## Usage

From the repository root, run:

```bash
python tools/generate_doc_reference.py src stdlib --output docs/reference_generated.md
```

You can also narrow the scope to a specific module:

```bash
python tools/generate_doc_reference.py src/tiny_language_ast.py
```

## Notes

- The generator is deterministic and emits a stable ordering based on file
  paths.
- If a module or symbol does not have a docstring, the output includes a short
  placeholder so missing documentation is obvious.
- The generated file is intended as a lightweight reference. It can be
  committed or kept local, depending on whether the changes are relevant to the
  documentation review.
