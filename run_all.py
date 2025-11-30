"""Utility runner that executes the full TinyLanguage test and demo suite.

This script mirrors the VS Code launch configurations so you can validate
that everything still works with a single command or debug session.
"""
from __future__ import annotations  # Keep annotations as strings for forward references

import subprocess  # Run external processes for demos and tests
import sys  # Discover the current Python interpreter path
from pathlib import Path  # Resolve project-relative paths

PROJECT_ROOT = Path(__file__).resolve().parent  # Root directory of the repository
PYTHON = sys.executable  # Absolute path to the active Python executable

# Pairs of human-friendly names and the commands they represent.
COMMANDS: list[tuple[str, list[str]]] = [
    ("pytest (full suite)", [PYTHON, "-m", "pytest"]),  # Run all Python tests
    ("demo.tiny", [PYTHON, "tiny_language.py", "demo.tiny"]),  # Showcase basics
    ("class_demo.tiny", [PYTHON, "tiny_language.py", "class_demo.tiny"]),  # Class walkthrough
    ("all_features.tiny", [PYTHON, "tiny_language.py", "all_features.tiny"]),  # Feature tour
    ("number_class.tiny", [PYTHON, "tiny_language.py", "number_class.tiny"]),  # Number class demo
    ("number_intervall.tiny", [PYTHON, "tiny_language.py", "number_intervall.tiny"]),  # Interval arithmetic
    ("rosetta_fibonacci.tiny", [PYTHON, "tiny_language.py", "rosetta_fibonacci.tiny"]),  # Rosetta Fibonacci sample
    ("concurrency_demo.tiny", [PYTHON, "tiny_language.py", "concurrency_demo.tiny"]),  # Spawn/join example
    ("concurrency_pipeline.tiny", [PYTHON, "tiny_language.py", "concurrency_pipeline.tiny"]),  # Pipeline concurrency
    ("parallel_map.tiny", [PYTHON, "tiny_language.py", "parallel_map.tiny"]),  # Parallel map helper
    ("heap_pointer_demo.tiny", [PYTHON, "tiny_language.py", "heap_pointer_demo.tiny"]),  # Heap safety showcase
    ("namespace_demo.tiny", [PYTHON, "tiny_language.py", "namespace_demo.tiny"]),  # Namespaces walkthrough
    ("operator_overloading_demo.tiny", [PYTHON, "tiny_language.py", "operator_overloading_demo.tiny"]),  # Operator overloads
    ("tests/logic_example.tiny", [PYTHON, "tiny_language.py", "tests/logic_example.tiny"]),  # Logic test sample
    (".vscode/all_features.tiny", [PYTHON, "tiny_language.py", ".vscode/all_features.tiny"]),  # VS Code tutorial copy
    (".vscode/rosetta_fibonacci.tiny", [PYTHON, "tiny_language.py", ".vscode/rosetta_fibonacci.tiny"]),  # VS Code Fib copy
]


def main() -> int:
    """Run each configured command and report which ones fail."""

    failures: list[str] = []  # Collect human-friendly names for failing runs

    for name, cmd in COMMANDS:  # Iterate through each demo/test pair
        print(f"\n=== Running {name} ===")  # Banner to make output scannable
        print("Command:", " ".join(cmd))  # Show the exact invocation
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT)  # Execute the command inside the repo
        if proc.returncode != 0:  # Non-zero exit signals a failure
            failures.append(name)  # Record the failing entry for summary output
            # Continue so we can see all failures in one pass instead of stopping early
    if failures:  # If anything went wrong, print a summary and exit with error
        print("\nSome commands failed:")
        for name in failures:
            print(" -", name)
        return 1

    print("\nAll commands completed successfully.")  # Happy path summary
    return 0


if __name__ == "__main__":  # Allow running the module directly
    raise SystemExit(main())  # Exit using the return code from main()
