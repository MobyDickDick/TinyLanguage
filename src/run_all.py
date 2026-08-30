"""Utility runner that executes the full TinyLanguage test and demo suite.

This script mirrors the VS Code launch configurations so you can validate
that everything still works with a single command or debug session.
"""
from __future__ import annotations  # Keep annotations as strings for forward references

import argparse  # Parse CLI options for smoke runs
import os  # Augment environment with src/ on PYTHONPATH
import re  # Match missing pytest errors for fallback handling
import subprocess  # Run external processes for demos and tests
import sys  # Discover the current Python interpreter path
from pathlib import Path  # Resolve project-relative paths

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Root directory of the repository
SRC_ROOT = PROJECT_ROOT / "src"
DEMO_ROOT = PROJECT_ROOT / "src_tiny"
PYTHON = sys.executable  # Absolute path to the active Python executable
VENV_ROOTS = [
    Path(path) for path in [os.environ.get("TINYLANGUAGE_VENV"), os.environ.get("VIRTUAL_ENV")] if path
] + [
    PROJECT_ROOT / ".venv",
]


def resolve_repo_python() -> str:
    """Prefer the repository virtualenv when available."""
    debug = os.environ.get("TINYLANGUAGE_DEBUG_PYTEST") == "1"
    if debug:
        print("TINYLANGUAGE_DEBUG_PYTEST=1 (debugging interpreter selection)")
        print("Candidate venv roots (in order):")
        for venv_root in VENV_ROOTS:
            print(f" - {venv_root}")
    for venv_root in VENV_ROOTS:
        if not venv_root:
            continue
        candidates = [
            venv_root / "Scripts" / "python.exe",
            venv_root / "Scripts" / "python",
            venv_root / "bin" / "python",
            venv_root / "bin" / "python.exe",
        ]
        for candidate in candidates:
            if debug:
                print(f"Checking candidate: {candidate}")
            if candidate.exists():
                if debug:
                    print(f"Selected interpreter: {candidate}")
                return str(candidate)
    if debug:
        print(f"Falling back to sys.executable: {PYTHON}")
    return PYTHON


def build_pytest_env() -> dict[str, str]:
    """Build a clean environment for pytest that prioritizes the repo venv."""
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    venv_root = Path(PYTEST_PYTHON).resolve().parent
    if venv_root.name.lower() in {"scripts", "bin"}:
        venv_root = venv_root.parent
    env["VIRTUAL_ENV"] = str(venv_root)
    script_dirs = [venv_root / "Scripts", venv_root / "bin"]
    existing_path = env.get("PATH", "")
    path_entries = [str(path) for path in script_dirs if path.exists()]
    if existing_path:
        path_entries.append(existing_path)
    env["PATH"] = os.pathsep.join(path_entries)
    site_packages = [
        venv_root / "Lib" / "site-packages",
        venv_root / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
    ]
    pythonpath_entries = [str(path) for path in site_packages if path.exists()]
    if pythonpath_entries:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    env.setdefault("PYTHONNOUSERSITE", "1")
    return env


def resolve_pytest_command(pytest_env: dict[str, str]) -> list[str]:
    """Resolve pytest to an absolute entrypoint path when available."""
    probe = subprocess.run(
        [
            PYTEST_PYTHON,
            "-c",
            (
                "import pathlib, pytest; "
                "print(pathlib.Path(pytest.__file__).resolve().with_name('__main__.py'))"
            ),
        ],
        cwd=PROJECT_ROOT,
        env=pytest_env,
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        candidate = probe.stdout.strip()
        if candidate:
            return [PYTEST_PYTHON, candidate]
    return PYTEST_COMMAND


def _candidate_pytest_fallback() -> str | None:
    """Return a fallback interpreter for pytest when the primary one lacks it."""
    fallback = os.environ.get("TINYLANGUAGE_PYTHON_FALLBACK")
    if fallback:
        return fallback
    return None

INTERPRETER = SRC_ROOT / "tiny_language.py"
REPO_PYTHON = resolve_repo_python()
PYTEST_PYTHON = REPO_PYTHON
PYTEST_COMMAND = [PYTEST_PYTHON, "-m", "pytest"]
# Pairs of human-friendly names and the commands they represent.
COMMANDS: list[tuple[str, list[str]]] = [
    ("demo.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "demo.tiny")]),  # Showcase basics
    ("class_demo.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "class_demo.tiny")]),  # Class walkthrough
    ("all_features.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "all_features.tiny")]),  # Feature tour
    ("number_class.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "number_class.tiny")]),  # Number class demo
    ("number_intervall.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "number_intervall.tiny")]),  # Interval arithmetic
    ("rosetta_fibonacci.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "rosetta_fibonacci.tiny")]),  # Rosetta Fibonacci sample
    ("concurrency_demo.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "concurrency_demo.tiny")]),  # Spawn/join example
    ("concurrency_pipeline.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "concurrency_pipeline.tiny")]),  # Pipeline concurrency
    ("parallel_map.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "parallel_map.tiny")]),  # Parallel map helper
    ("heap_pointer_demo.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "heap_pointer_demo.tiny")]),  # Heap safety showcase
    ("namespace_demo.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "namespace_demo.tiny")]),  # Namespaces walkthrough
    ("operator_overloading_demo.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "operator_overloading_demo.tiny")]),  # Operator overloads
    ("tests/logic_example.tiny", [REPO_PYTHON, str(INTERPRETER), "tests/logic_example.tiny"]),  # Logic test sample
    (".vscode/all_features.tiny", [REPO_PYTHON, str(INTERPRETER), ".vscode/all_features.tiny"]),  # VS Code tutorial copy
    (".vscode/rosetta_fibonacci.tiny", [REPO_PYTHON, str(INTERPRETER), ".vscode/rosetta_fibonacci.tiny"]),  # VS Code Fib copy
]
SMOKE_COMMANDS: list[tuple[str, list[str]]] = [
    ("demo.tiny", [REPO_PYTHON, str(INTERPRETER), str(DEMO_ROOT / "demo.tiny")]),  # Quick sanity check
    ("tests/logic_example.tiny", [REPO_PYTHON, str(INTERPRETER), "tests/logic_example.tiny"]),  # Tiny program sanity check
]
SMOKE_PYTEST_TARGETS = ["tests/test_smoke.py"]
TINY_CPU_ACCEPTANCE = PROJECT_ROOT / "scripts" / "test-logisim.sh"


def run_pytest(failures: list[str], extra_args: list[str] | None = None) -> None:
    """Run the Python test suite and record failures."""
    def run_and_echo(command: list[str], pytest_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=pytest_env,
            capture_output=True,
            text=True,
        )
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
        return proc

    name = "pytest (smoke subset)" if extra_args else "pytest (full suite)"
    pytest_env = build_pytest_env()
    pytest_command = resolve_pytest_command(pytest_env)
    if os.environ.get("TINY_ASSERT_NO_HEAP_LEAKS") == "1":
        pytest_command = [*pytest_command, "--assert-no-heap-leaks"]
    if extra_args:
        pytest_command = [*pytest_command, *extra_args]
    print(f"\n=== Running {name} ===")  # Banner to make output scannable
    print("Command:", " ".join(pytest_command))  # Show the exact invocation
    proc = run_and_echo(pytest_command, pytest_env)
    missing_pytest = bool(
        re.search(
            r"No module named ['\"]?pytest['\"]?",
            (proc.stderr or "") + (proc.stdout or ""),
        )
    )
    if not missing_pytest and proc.returncode == 0:
        return proc
    if missing_pytest:
        fallback = _candidate_pytest_fallback()
        if fallback and fallback != pytest_command[0]:
            retry_cmd = [fallback, "-m", "pytest"]
            if os.environ.get("TINY_ASSERT_NO_HEAP_LEAKS") == "1":
                retry_cmd.append("--assert-no-heap-leaks")
            print("Retrying pytest with:", " ".join(retry_cmd))
            return run_and_echo(retry_cmd, pytest_env)
        if fallback == pytest_command[0]:
            print(
                "pytest is missing from the current interpreter. "
                "Install it or set TINYLANGUAGE_PYTHON_FALLBACK to a Python "
                "that includes pytest."
            )
        elif not fallback:
            print(
                "No fallback interpreter found. Set TINYLANGUAGE_PYTHON_FALLBACK "
                "to a Python that includes pytest."
            )
    return proc


def run_tiny_cpu_acceptance(failures: list[str]) -> None:
    """Run the inseparable electrical proof for every TinyCPU instruction."""

    name = "TinyCPU electrical opcode acceptance"
    command = [str(TINY_CPU_ACCEPTANCE)]
    print(f"\n=== Running {name} ===")
    print("Command:", " ".join(command))
    proc = subprocess.run(command, cwd=PROJECT_ROOT, env=os.environ.copy())
    if proc.returncode != 0:
        failures.append(name)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the test runner."""
    parser = argparse.ArgumentParser(description="Run TinyLanguage tests and demos.")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run the smoke subset for quick local feedback.",
    )
    return parser.parse_args()


def main() -> int:
    """Run each configured command and report which ones fail."""
    args = parse_args()
    smoke_mode = args.smoke or os.environ.get("TINYLANGUAGE_SMOKE") == "1"
    if smoke_mode:
        print("Smoke mode enabled: running a reduced test/demo subset.")

    failures: list[str] = []  # Collect human-friendly names for failing runs
    pytest_args = SMOKE_PYTEST_TARGETS if smoke_mode else None
    run_pytest(failures, pytest_args)
    # A test run is not complete without exercising all 50 opcodes (plus both
    # outcomes of conditional jumps) in the real pinned simulator. Keep this
    # gate in smoke mode so the fast entry point cannot recreate the gap.
    run_tiny_cpu_acceptance(failures)

    commands = SMOKE_COMMANDS if smoke_mode else COMMANDS
    for name, cmd in commands:  # Iterate through each demo/test pair
        print(f"\n=== Running {name} ===")  # Banner to make output scannable
        print("Command:", " ".join(cmd))  # Show the exact invocation
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
