"""Smoke tests for the TinyLanguage CLI entry point."""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_cli(args, *, stdin_data=None):
    """Invoke the CLI with ``args`` and return the completed subprocess."""
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH")])
        ),
    }
    return subprocess.run(
        [sys.executable, "-m", "tiny_lang_cli", *args],
        input=stdin_data,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def test_cli_runs_inline_source_with_default_backend():
    """Ensure inline ``--source`` runs on the default backend."""
    result = run_cli(["--source", "print(1 + 2);"])

    assert result.returncode == 0
    assert result.stdout == "3\n"
    assert result.stderr == ""


def test_cli_runs_file_with_python_backend(tmp_path):
    """Ensure ``--backend python`` executes a file and returns output."""
    program = "print(6 * 7);"
    src_file = tmp_path / "program.tiny"
    src_file.write_text(program, encoding="utf-8")

    result = run_cli(["--file", str(src_file), "--backend", "python"])

    assert result.returncode == 0
    assert result.stdout == "42\n"
    assert result.stderr == ""


def test_cli_runs_file_with_native_backend(tmp_path):
    """Ensure ``--native-backend`` executes a file and returns output."""
    program = "print(5 + 4);"
    src_file = tmp_path / "program.tiny"
    src_file.write_text(program, encoding="utf-8")

    result = run_cli(["--file", str(src_file), "--native-backend"])

    assert result.returncode == 0
    assert result.stdout == "9\n"
    assert result.stderr == ""


def test_cli_reads_stdin_via_dash():
    """Verify ``--file -`` reads TinyLanguage source from stdin."""
    result = run_cli(["--file", "-"], stdin_data="print(1 + 1);")

    assert result.returncode == 0
    assert result.stdout == "2\n"
    assert result.stderr == ""
