# Building standalone executables

This guide shows how to bundle the TinyLanguage interpreter into a standalone executable, with a Windows-focused PyInstaller recipe. The same approach works on macOS/Linux with minor flag adjustments.

## Prerequisites

- Python 3.10+ with pip
- [PyInstaller](https://pyinstaller.org/en/stable/) installed locally (`pip install pyinstaller`)
- This repository checked out locally

## Create a Windows `.exe` with PyInstaller

1. **Install PyInstaller** (inside your virtual environment):

   ```bash
   pip install pyinstaller
   ```

2. **Run PyInstaller from the repo root** so the bundled data files match

TinyLanguage’s dynamic loader:

   ```bash
   pyinstaller --onefile ^
     --name tiny_language ^
     --add-data "src\\tiny_language_*.py;src" ^
     src\\tiny_language.py
   ```

   Explanation of the key flags:

- `--onefile` produces a single `tiny_language.exe` instead of a folder tree.
- `--add-data` copies the stitched source segments into the bundle so `tiny_language.py` can concatenate them at runtime (PyInstaller separates Python sources from bytecode by default). On Windows, the separator between source and destination paths is `;`.
- The destination `src` keeps the bundled files in the same relative layout that the loader expects.

1. **Pick up the executable** from `dist/tiny_language.exe`.

## Verify the executable

From a Windows shell, run a sample TinyLanguage program through the generated binary:

```powershell
PS> .\dist\tiny_language.exe src_tiny\class_demo.tiny
Hello, TinyLanguage!
```

If you prefer to keep the extracted bundle (instead of the single-file executable), drop `--onefile` to emit a `dist/tiny_language` directory and run `tiny_language.exe` from there.

## Notes for macOS/Linux

- Replace backslashes with forward slashes in the `--add-data` argument and use a colon `:` to separate source and destination paths (PyInstaller’s POSIX convention):

  ```bash
  pyinstaller --onefile \
    --name tiny_language \
    --add-data "src/tiny_language_*.py:src" \
    src/tiny_language.py
  ```

- The runtime extraction directory detected via `sys._MEIPASS` is supported automatically (see `src/tiny_language.py`), so no code changes are needed across platforms.

## Troubleshooting

- **Missing source segments**: If you see errors like `FileNotFoundError` for `tiny_language_lexer.py`, re-run PyInstaller with the `--add-data` flag above to ensure the stitched sources are bundled.
- **Native backend dependencies**: The interpreter and native bytecode backend are pure Python. If you later extend the LLVM/`llvmlite` path, add the corresponding shared libraries via additional `--add-binary` flags.
