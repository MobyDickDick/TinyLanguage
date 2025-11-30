"""
Run a representative set of TinyLanguage demos and the Python test suite.

This script is meant for the VS Code "Python: run_all.py" launcher so that
developers can validate the interpreter plus standard library in one go.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

def run_step(name: str, args: list[str]) -> None:
    print(f"\n=== {name} ===")
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)

def main() -> None:
    tiny_language = ROOT / "tiny_language.py"
    demo_files = [
        "demo.tiny",
        "all_features.tiny",
        "class_demo.tiny",
        "namespace_demo.tiny",
        "match_demo.tiny",
        "operator_overloading_demo.tiny",
        "heap_pointer_demo.tiny",
        "concurrency_demo.tiny",
        "concurrency_pipeline.tiny",
        "result_demo.tiny",
        "try_catch_demo.tiny",
        "parallel_map.tiny",
        "number_class.tiny",
        "number_intervall.tiny",
        "stdlib_collections_demo.tiny",
        "stdlib_io_random_demo.tiny",
        "rosetta_fibonacci.tiny",
    ]

    for demo in demo_files:
        demo_path = ROOT / demo
        if not demo_path.exists():
            print(f"Skipping missing demo: {demo}")
            continue
        run_step(f"tiny_language.py {demo}", [PYTHON, str(tiny_language), str(demo_path)])

    run_step("pytest", [PYTHON, "-m", "pytest", "-q"])


if __name__ == "__main__":
    main()
