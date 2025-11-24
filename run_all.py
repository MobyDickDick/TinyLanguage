"""Utility runner that executes the full TinyLanguage test and demo suite.

This script mirrors the VS Code launch configurations so you can validate
that everything still works with a single command or debug session.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

COMMANDS: list[tuple[str, list[str]]] = [
    ("pytest (full suite)", [PYTHON, "-m", "pytest"]),
    ("demo.tiny", [PYTHON, "tiny_language.py", "demo.tiny"]),
    ("all_features.tiny", [PYTHON, "tiny_language.py", "all_features.tiny"]),
    ("number_class.tiny", [PYTHON, "tiny_language.py", "number_class.tiny"]),
    ("number_intervall.tiny", [PYTHON, "tiny_language.py", "number_intervall.tiny"]),
    ("rosetta_fibonacci.tiny", [PYTHON, "tiny_language.py", "rosetta_fibonacci.tiny"]),
    ("concurrency_demo.tiny", [PYTHON, "tiny_language.py", "concurrency_demo.tiny"]),
    ("heap_pointer_demo.tiny", [PYTHON, "tiny_language.py", "heap_pointer_demo.tiny"]),
    ("tests/logic_example.tiny", [PYTHON, "tiny_language.py", "tests/logic_example.tiny"]),
    (".vscode/all_features.tiny", [PYTHON, "tiny_language.py", ".vscode/all_features.tiny"]),
    (".vscode/rosetta_fibonacci.tiny", [PYTHON, "tiny_language.py", ".vscode/rosetta_fibonacci.tiny"]),
]


def main() -> int:
    failures: list[str] = []

    for name, cmd in COMMANDS:
        print(f"\n=== Running {name} ===")
        print("Command:", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if proc.returncode != 0:
            failures.append(name)
            # Continue to show as many failures as possible
    if failures:
        print("\nSome commands failed:")
        for name in failures:
            print(" -", name)
        return 1

    print("\nAll commands completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
