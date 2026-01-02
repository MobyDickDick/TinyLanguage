"""Utility runner that executes the full TinyLanguage test and demo suite.

This script mirrors the VS Code launch configurations so you can validate
that everything still works with a single command or debug session.
"""
from __future__ import annotations  # Keep annotations as strings for forward references

import os  # Augment environment with src/ on PYTHONPATH
import site  # Report Python site-package locations for debugging
import subprocess  # Run external processes for demos and tests
import sys  # Discover the current Python interpreter path
from pathlib import Path  # Resolve project-relative paths

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Root directory of the repository
SRC_ROOT = PROJECT_ROOT / "src"
DEMO_ROOT = PROJECT_ROOT / "src_tiny"
PYTHON = sys.executable  # Absolute path to the active Python executable

# Pairs of human-friendly names and the commands they represent.
INTERPRETER = SRC_ROOT / "tiny_language.py"
COMMANDS: list[tuple[str, list[str]]] = [
    ("pytest (full suite)", [PYTHON, "-m", "pytest"]),  # Run all Python tests
    ("demo.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "demo.tiny")]),  # Showcase basics
    ("class_demo.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "class_demo.tiny")]),  # Class walkthrough
    ("all_features.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "all_features.tiny")]),  # Feature tour
    ("number_class.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "number_class.tiny")]),  # Number class demo
    ("number_intervall.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "number_intervall.tiny")]),  # Interval arithmetic
    ("rosetta_fibonacci.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "rosetta_fibonacci.tiny")]),  # Rosetta Fibonacci sample
    ("concurrency_demo.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "concurrency_demo.tiny")]),  # Spawn/join example
    ("concurrency_pipeline.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "concurrency_pipeline.tiny")]),  # Pipeline concurrency
    ("parallel_map.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "parallel_map.tiny")]),  # Parallel map helper
    ("heap_pointer_demo.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "heap_pointer_demo.tiny")]),  # Heap safety showcase
    ("namespace_demo.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "namespace_demo.tiny")]),  # Namespaces walkthrough
    ("operator_overloading_demo.tiny", [PYTHON, str(INTERPRETER), str(DEMO_ROOT / "operator_overloading_demo.tiny")]),  # Operator overloads
    ("tests/logic_example.tiny", [PYTHON, str(INTERPRETER), "tests/logic_example.tiny"]),  # Logic test sample
    (".vscode/all_features.tiny", [PYTHON, str(INTERPRETER), ".vscode/all_features.tiny"]),  # VS Code tutorial copy
    (".vscode/rosetta_fibonacci.tiny", [PYTHON, str(INTERPRETER), ".vscode/rosetta_fibonacci.tiny"]),  # VS Code Fib copy
]


def main() -> int:
    """Run each configured command and report which ones fail."""

    print("\n=== Debug environment (run_all.py) ===")
    print("Python executable:", sys.executable)
    print("sys.path:")
    for entry in sys.path:
        print(" -", entry)
    print("site-packages:", site.getsitepackages())
    print("user-site:", site.getusersitepackages())
    print("PYTHONPATH:", os.environ.get("PYTHONPATH"))
    print("=====================================")

    failures: list[str] = []  # Collect human-friendly names for failing runs

    for name, cmd in COMMANDS:  # Iterate through each demo/test pair
        print(f"\n=== Running {name} ===")  # Banner to make output scannable
        print("Command:", " ".join(cmd))  # Show the exact invocation
        if name == "pytest (full suite)":
            print("\n--- Debug: pytest resolution ---")
            probe_env = {
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
                ),
            }
            probe_cmds = [
                ("pip show pytest", [PYTHON, "-m", "pip", "show", "pytest"]),
                (
                    "python site config",
                    [
                        PYTHON,
                        "-c",
                        (
                            "import json, os, site, sys, sysconfig, importlib.util; "
                            "print('sys.executable:', sys.executable); "
                            "print('sys.path:', sys.path); "
                            "print('site-packages:', site.getsitepackages()); "
                            "print('user-site:', site.getusersitepackages()); "
                            "print('PYTHONNOUSERSITE:', os.environ.get('PYTHONNOUSERSITE')); "
                            "print('pip spec:', importlib.util.find_spec('pip')); "
                            "print('pytest spec:', importlib.util.find_spec('pytest')); "
                            "print('sysconfig paths:', json.dumps(sysconfig.get_paths(), indent=2)); "
                            "print('env PYTHONHOME:', os.environ.get('PYTHONHOME')); "
                            "print('env PYTHONPATH:', os.environ.get('PYTHONPATH')); "
                            "print('env PYTHONUSERBASE:', os.environ.get('PYTHONUSERBASE')); "
                            "print('env VIRTUAL_ENV:', os.environ.get('VIRTUAL_ENV')); "
                            "print('env PATH:', os.environ.get('PATH'))"
                        ),
                    ],
                ),
            ]
            for label, probe in probe_cmds:
                print(f"Probe command ({label}):", " ".join(probe))
                probe_proc = subprocess.run(
                    probe,
                    cwd=PROJECT_ROOT,
                    env=probe_env,
                    capture_output=True,
                    text=True,
                )
                if probe_proc.stdout:
                    print(probe_proc.stdout.rstrip())
                if probe_proc.stderr:
                    print(probe_proc.stderr.rstrip())
            print("--- End debug: pytest resolution ---")
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
                ),
            },
        )  # Execute the command inside the repo
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
