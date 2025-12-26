import json
import os
import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
TINY_LANGUAGE = PROJECT_ROOT / "src" / "tiny_language.py"
TINY_CLI = PROJECT_ROOT / "src_tiny" / "tiny_language_cli.tiny"


def run_tiny_cli(args):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH")])
        ),
        "TINYLANG_ARGS": json.dumps(args),
    }
    return subprocess.run(
        [sys.executable, str(TINY_LANGUAGE), str(TINY_CLI)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def test_tiny_cli_runs_inline_source():
    proc = run_tiny_cli(["--source", "print(1 + 2);"])

    assert proc.returncode == 0
    assert proc.stdout == "3\n"
    assert proc.stderr == ""
