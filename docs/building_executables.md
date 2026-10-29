# Building standalone executables

This guide shows how to bundle the TinyLanguage interpreter into a standalone executable, with a Windows-focused PyInstaller recipe. The same approach works on macOS/Linux with minor flag adjustments.

## Native executable via LLVM (experimental)

If you want a true native binary compiled from TinyLanguage source (no Python interpreter bundled), use the LLVM prototype backend and a system compiler like `clang`. This is **experimental** and only supports the LLVM subset (numeric literals, assignments, basic arithmetic/comparisons, and `print`).

```bash
python src/tiny_language.py --emit-exe hello_native src_tiny/demo.tiny
```

For a stable C backend that emits a C source file plus a tiny VM, see
[`docs/c_backend.md`](c_backend.md). The `tinyc_cli` command can emit C, LLVM IR,
or LLVM bitcode via `clang`, and it is documented separately.

To inspect the LLVM IR first:

```bash
python src/tiny_language.py --emit-llvm - src_tiny/demo.tiny
```

Notes:

- Requires `clang` to be available on `PATH` (override with `--compiler` if needed).
- The LLVM prototype supports basic control flow, functions, and heap helpers (`new`, `heap_get`, `heap_set`, `delete`), but does not include the interpreter-style safety checks for invalid pointers or indices.

## Prerequisites

- Python 3.11+ with pip
- Build dependencies installed with `python -m pip install -r tools/release/requirements.txt`
- This repository checked out locally

## Create a Windows `.exe` with PyInstaller

1. **Install PyInstaller** (inside your virtual environment):

   ```bash
   python -m pip install -r tools/release/requirements.txt
   ```

2. **Run the maintained spec from the repo root**. It includes Python source
segments, the Tiny standard library, and parser bootstrap assets:

   ```bash
   python -m PyInstaller --clean --noconfirm tools/release/tinylanguage.spec
   ```

The spec produces a single console executable and disables UPX. Imports keep
stitched source in memory. Pick up `dist/tiny-language.exe` on Windows or
`dist/tiny-language` on macOS/Linux.

## Verify the executable

From a Windows shell, run a sample TinyLanguage program through the generated binary:

```powershell
PS> .\dist\tiny-language.exe src_tiny\class_demo.tiny
Hello, TinyLanguage!
```

## Notes for macOS/Linux

Use the same spec command on each target architecture. PyInstaller builds for
the host; it does not cross-compile the four release binaries from Windows.
For archived-source builds with platform filenames, hashes and reproducibility
checks, use the [release helper](../tools/release/README.md). Actual target
qualification remains recorded in [packaging acceptance](release_packaging_acceptance.md).

## Troubleshooting

- **Missing source segments**: Build with the maintained spec, which includes source files as data at the frozen loader's expected location.
- **Native backend dependencies**: The interpreter and native bytecode backend are pure Python. If you later extend the LLVM/`llvmlite` path, add the corresponding shared libraries via additional `--add-binary` flags.
