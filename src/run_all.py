"""Utility runner that executes the full TinyLanguage test and demo suite.

This script mirrors the VS Code launch configurations so you can validate
that everything still works with a single command or debug session.

Debug additions (opt-in via env vars):
  - TINYLANGUAGE_PYTEST_DIAG=1
      Always print interpreter + import-path diagnostics before running pytest.
  - TINYLANGUAGE_PYTEST_DIAG_ON_FAIL=1
      Print diagnostics (and a `-m pytest` reproduction probe) only when pytest fails.
  - TINYLANGUAGE_PYTEST_USE_CONSOLE_MAIN=1
      Run pytest via `pytest.console_main()` instead of `python -m pytest` (workaround).
"""
from __future__ import annotations  # Keep annotations as strings for forward references

import os  # Augment environment with src/ on PYTHONPATH
import re  # Match pytest import errors across outputs
import subprocess  # Run external processes for demos and tests
import sys  # Discover the current Python interpreter path
from pathlib import Path  # Resolve project-relative paths

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Root directory of the repository
SRC_ROOT = PROJECT_ROOT / "src"
DEMO_ROOT = PROJECT_ROOT / "src_tiny"
PYTHON = sys.executable  # Absolute path to the active Python executable

PYTHON_ENV = "TINYLANGUAGE_PYTHON"
PYTEST_FALLBACK_ENV = "TINYLANGUAGE_PYTHON_FALLBACK"

# Debug / behavior toggles (all optional)
PYTEST_DIAG_ENV = "TINYLANGUAGE_PYTEST_DIAG"
PYTEST_DIAG_ON_FAIL_ENV = "TINYLANGUAGE_PYTEST_DIAG_ON_FAIL"
PYTEST_USE_CONSOLE_MAIN_ENV = "TINYLANGUAGE_PYTEST_USE_CONSOLE_MAIN"

if os.environ.get(PYTHON_ENV):
    PYTHON = os.environ[PYTHON_ENV]

INTERPRETER = SRC_ROOT / "tiny_language.py"


def _env_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value not in ("", "0", "false", "False", "no", "No")


def _should_diag_always() -> bool:
    return _env_truthy(os.environ.get(PYTEST_DIAG_ENV))


def _should_diag_on_fail() -> bool:
    return _env_truthy(os.environ.get(PYTEST_DIAG_ON_FAIL_ENV))


def _use_console_main() -> bool:
    return _env_truthy(os.environ.get(PYTEST_USE_CONSOLE_MAIN_ENV))


def _print_diag_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _diagnose_python(python_exe: str, env: dict[str, str]) -> None:
    """Run a small inline script inside the given interpreter to show import/search paths."""
    _print_diag_header(f"PYTEST DIAGNOSTICS for interpreter: {python_exe}")

    diag_code = r"""
import os, sys, site, importlib.util

print("sys.executable:", sys.executable)
print("sys.version:", sys.version.replace("\n"," "))
print("cwd:", os.getcwd())

def show(k):
    v = os.environ.get(k)
    if v is None:
        return
    if k.upper() == "PATH":
        v = (v[:600] + "...(truncated)") if len(v) > 600 else v
    print(f"{k}:", v)

for k in [
    "TINYLANGUAGE_PYTHON",
    "TINYLANGUAGE_PYTHON_FALLBACK",
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONNOUSERSITE",
    "PYTHONSAFEPATH",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "PATH",
]:
    show(k)

print("sys.flags:", sys.flags)

try:
    print("site.ENABLE_USER_SITE:", site.ENABLE_USER_SITE)
except Exception as e:
    print("site.ENABLE_USER_SITE error:", e)

try:
    print("usersite:", site.getusersitepackages())
except Exception as e:
    print("usersite error:", e)

try:
    print("sitepackages:", site.getsitepackages())
except Exception as e:
    print("sitepackages error:", e)

spec = importlib.util.find_spec("pytest")
print("pytest spec:", spec)
if spec is not None:
    print("pytest origin:", getattr(spec, "origin", None))

spec_main = importlib.util.find_spec("pytest.__main__")
print("pytest.__main__ spec:", spec_main)
if spec_main is not None:
    print("pytest.__main__ origin:", getattr(spec_main, "origin", None))

print("sys.path:")
for p in sys.path:
    print("  ", p)

try:
    import pytest  # noqa: F401
    import pytest as _p
    print("pytest imported OK from:", getattr(_p, "__file__", None))
except Exception as e:
    print("pytest import FAILED:", repr(e))
"""

    proc = subprocess.run(
        [python_exe, "-c", diag_code],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print("--- diagnostics stderr ---")
        print(proc.stderr.rstrip())

    # pip info (important: "pip for this interpreter", if present)
    for pip_cmd in (
        [python_exe, "-m", "pip", "-V"],
        [python_exe, "-m", "pip", "show", "pytest"],
    ):
        proc2 = subprocess.run(
            pip_cmd,
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        print("\n$ " + " ".join(pip_cmd))
        if proc2.stdout:
            print(proc2.stdout.rstrip())
        if proc2.stderr:
            print(proc2.stderr.rstrip())


def _probe_run_module(python_exe: str, env: dict[str, str]) -> None:
    """Reproduce `python -m pytest` via runpy and print why it fails (full traceback)."""
    _print_diag_header(f"PROBE: reproducing `-m pytest` inside: {python_exe}")

    code = r"""
import os, sys, importlib.util, runpy, traceback

print("sys.executable:", sys.executable)
print("sys.version:", sys.version.replace("\n"," "))
print("cwd:", os.getcwd())
print("PYTHONPATH:", os.environ.get("PYTHONPATH"))
print("sys.path (first 15):")
for p in sys.path[:15]:
    print("  ", p)

def show_spec(name):
    try:
        spec = importlib.util.find_spec(name)
    except Exception as e:
        print(f"find_spec({name!r}) raised:", repr(e))
        return
    print(f"spec({name}):", spec)
    if spec is not None:
        print(f"  origin({name}):", getattr(spec, "origin", None))

show_spec("pytest")
show_spec("pytest.__main__")

print("\nNow runpy.run_module('pytest', run_name='__main__') ...")
try:
    runpy.run_module("pytest", run_name="__main__")
    print("run_module finished OK")
except Exception as e:
    print("run_module FAILED:", repr(e))
    traceback.print_exc()
"""

    p = subprocess.run(
        [python_exe, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if p.stdout:
        print(p.stdout.rstrip())
    if p.stderr:
        print("--- PROBE STDERR ---")
        print(p.stderr.rstrip())


def _candidate_pytest_fallback() -> str | None:
    """Return an alternate Python path for pytest when configured or discoverable."""
    fallback = os.environ.get(PYTEST_FALLBACK_ENV)
    if fallback:
        return fallback
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return None
        candidate = Path(local_app_data) / "Python" / "pythoncore-3.14-64" / "python.exe"
        if candidate.exists():
            return str(candidate)
    return None


def _pytest_command(python_exe: str) -> list[str]:
    """Return the command used to run pytest for a given interpreter."""
    # Workaround: avoids `python -m pytest` module-runner edge cases.
    return [python_exe, "-c", "import pytest; raise SystemExit(pytest.console_main())"]
    


# Pairs of human-friendly names and the commands they represent.
COMMANDS: list[tuple[str, list[str]]] = [
    ("pytest (full suite)", _pytest_command(PYTHON)),  # Run all Python tests
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


def _run_pytest(python_exe: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run pytest and retry with a fallback interpreter if needed."""
    cmd = _pytest_command(python_exe)

    if _should_diag_always():
        _diagnose_python(python_exe, env)

    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    combined = (proc.stderr or "") + (proc.stdout or "")
    missing_pytest = bool(re.search(r"No module named ['\"]?pytest['\"]?", combined))
    missing_pytest_main = ("pytest.__main__" in combined)

    if (proc.returncode != 0) and (_should_diag_on_fail() or _should_diag_always()):
        _print_diag_header("PYTEST RAW OUTPUT (stdout/stderr)")
        if proc.stdout:
            print(proc.stdout.rstrip())
        if proc.stderr:
            print(proc.stderr.rstrip())

        _diagnose_python(python_exe, env)
        if not _use_console_main():
            _probe_run_module(python_exe, env)

    if not missing_pytest and proc.returncode == 0:
        return proc

    if missing_pytest or missing_pytest_main:
        fallback = _candidate_pytest_fallback()
        print("fallback:", fallback)
        if fallback and fallback != python_exe:
            retry_proc = subprocess.run(
                _pytest_command(fallback),
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )

            if (retry_proc.returncode != 0) and (_should_diag_on_fail() or _should_diag_always()):
                _print_diag_header("FALLBACK PYTEST RAW OUTPUT (stdout/stderr)")
                if retry_proc.stdout:
                    print(retry_proc.stdout.rstrip())
                if retry_proc.stderr:
                    print(retry_proc.stderr.rstrip())
                _diagnose_python(fallback, env)
                if not _use_console_main():
                    _probe_run_module(fallback, env)

            return retry_proc

        if fallback == python_exe:
            print(
                "pytest appears missing/unusable in the current interpreter. "
                "Install it or set TINYLANGUAGE_PYTHON_FALLBACK to a Python "
                "that includes pytest."
            )
        elif not fallback:
            print(
                "No fallback interpreter found. Set TINYLANGUAGE_PYTHON_FALLBACK "
                "to a Python that includes pytest."
            )

    return proc


def main() -> int:
    """Run each configured command and report which ones fail."""
    failures: list[str] = []

    if os.environ.get(PYTHON_ENV):
        print(f"Using {PYTHON_ENV}:", PYTHON)

    for name, cmd in COMMANDS:
        print(f"\n=== Running {name} ===")
        print("Command:", " ".join(cmd))

        base_env = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
            ),
        }

        if name == "pytest (full suite)":
            proc = _run_pytest(PYTHON, base_env)
            if proc.stdout:
                print(proc.stdout.rstrip())
            if proc.stderr:
                print(proc.stderr.rstrip())
        else:
            proc = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                env=base_env,
            )

        if proc.returncode != 0:
            failures.append(name)

    if failures:
        print("\nSome commands failed:")
        for name in failures:
            print(" -", name)
        return 1

    print("\nAll commands completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
