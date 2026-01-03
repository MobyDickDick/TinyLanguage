"""Utility runner that executes the full TinyLanguage test and demo suite.

This script mirrors the VS Code launch configurations so you can validate
that everything still works with a single command or debug session.
"""
from __future__ import annotations  # Keep annotations as strings for forward references

import os  # Augment environment with src/ on PYTHONPATH
import subprocess  # Run external processes for demos and tests
import sys  # Discover the current Python interpreter path
from pathlib import Path  # Resolve project-relative paths

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Root directory of the repository
SRC_ROOT = PROJECT_ROOT / "src"
DEMO_ROOT = PROJECT_ROOT / "src_tiny"
PYTHON = sys.executable  # Absolute path to the active Python executable
PYTEST_FALLBACK_ENV = "TINYLANGUAGE_PYTHON_FALLBACK"

# Pairs of human-friendly names and the commands they represent.
INTERPRETER = SRC_ROOT / "tiny_language.py"
PYTEST_COMMAND = [PYTHON, "-m", "pytest"]
COMMANDS: list[tuple[str, list[str]]] = [
    ("pytest (full suite)", PYTEST_COMMAND),  # Run all Python tests
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


def _candidate_pytest_fallback() -> str | None:
    """Return an alternate Python path for pytest when configured or discoverable."""
    fallback = os.environ.get(PYTEST_FALLBACK_ENV)
    if fallback:
        return fallback
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return None
        candidate = (
            Path(local_app_data) / "Python" / "pythoncore-3.14-64" / "python.exe"
        )
        if candidate.exists():
            return str(candidate)
    return None


def _run_pytest(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run pytest and retry with a fallback interpreter if needed."""
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return proc
    if proc.stderr and "No module named pytest" in proc.stderr:
        fallback = _candidate_pytest_fallback()
        if fallback and fallback != cmd[0]:
            retry_cmd = [fallback, "-m", "pytest"]
            print("Retrying pytest with:", " ".join(retry_cmd))
            return subprocess.run(
                retry_cmd,
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
    return proc


def main() -> int:
    """Run each configured command and report which ones fail."""

    failures: list[str] = []  # Collect human-friendly names for failing runs

    for name, cmd in COMMANDS:  # Iterate through each demo/test pair
        print(f"\n=== Running {name} ===")  # Banner to make output scannable
        print("Command:", " ".join(cmd))  # Show the exact invocation
        if name == "pytest (full suite)":
            env = {
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
                ),
            }
            proc = _run_pytest(cmd, env)
            if proc.stdout:
                stdout = proc.stdout.rstrip()
                print(stdout)
            if proc.stderr:
                stderr = proc.stderr.rstrip()
                print(stderr)
        else:
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
