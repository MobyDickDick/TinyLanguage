"""Tests for tiny language cli self host."""

import json
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
TINY_LANGUAGE = PROJECT_ROOT / "src" / "tiny_language.py"
TINY_CLI = PROJECT_ROOT / "src_tiny" / "tiny_language_cli.tiny"
TINY_LANG_CLI = PROJECT_ROOT / "src_tiny" / "tiny_lang_cli.tiny"


@dataclass(frozen=True)
class CliSnapshot:
    args: list[str]
    stdout: str
    stderr: str
    returncode: int


SNAPSHOTS = [
    CliSnapshot(
        args=[
            "--source",
            "def total = 0; def i = 0; while (i < 3) { total = total + i; i = i + 1; } print(total);",
        ],
        stdout="3\n",
        stderr="",
        returncode=0,
    ),
    CliSnapshot(
        args=["--source", "print(5 + 2);", "--backend", "python"],
        stdout="7\n",
        stderr="",
        returncode=0,
    ),
    CliSnapshot(
        args=["--source", "print(1 / 0);"],
        stdout="",
        stderr=(
            "[E000] division by zero (line 1, col 7 to line 1, col 11)\n"
            "> 1 | print(1 / 0);\n"
            "    |       ^^^^^\n"
        ),
        returncode=1,
    ),
    CliSnapshot(
        args=["--source", "def x = 1; @"],
        stdout="",
        stderr=(
            "[E000] lexing error: unexpected character '@' (line 1, col 12)\n"
            "> 1 | def x = 1; @\n"
            "    |            ^\n"
        ),
        returncode=1,
    ),
    CliSnapshot(
        args=["--source", "print(File.remove(\"missing.txt\"));"],
        stdout="false\n",
        stderr="",
        returncode=0,
    ),
    CliSnapshot(
        args=["--source", "import stdlib.os;\ndef _unused = os.read_text(\"missing.txt\");"],
        stdout="",
        stderr=(
            "[E000] file does not exist: missing.txt (line 57, col 10 to line 57, col 24)\n"
            "   56 | fn read_text(path) {\n"
            ">  57 |   return File.read(path);\n"
            "      |          ^^^^^^^^^^^^^^^\n"
            "   58 | }\n"
            "Stack trace:\n"
            "  at stdlib.os.read_text (line 56, col 1)\n"
        ),
        returncode=1,
    ),
]


def run_tiny_cli(args, cli_path=TINY_CLI, extra_env=None):
    """Helper to run tiny cli."""
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH")])
        ),
        "TINYLANG_ARGS": json.dumps(args),
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(TINY_LANGUAGE), str(cli_path)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def run_python_cli(args, extra_env=None):
    """Helper to run python cli."""
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH")])
        ),
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "src/tiny_language_cli.py", *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def assert_cli_parity(args, cli_path=TINY_CLI, extra_env=None):
    """Helper to assert cli parity."""
    python_proc = run_python_cli(args, extra_env=extra_env)
    tiny_proc = run_tiny_cli(args, cli_path=cli_path, extra_env=extra_env)
    assert tiny_proc.returncode == python_proc.returncode
    assert tiny_proc.stdout == python_proc.stdout
    assert tiny_proc.stderr == python_proc.stderr


def assert_cli_snapshot(snapshot: CliSnapshot, cli_path=TINY_CLI):
    """Helper to assert cli snapshot."""
    python_proc = run_python_cli(snapshot.args)
    assert python_proc.stdout == snapshot.stdout
    assert python_proc.stderr == snapshot.stderr
    assert python_proc.returncode == snapshot.returncode

    tiny_proc = run_tiny_cli(snapshot.args, cli_path=cli_path)
    assert tiny_proc.stdout == snapshot.stdout
    assert tiny_proc.stderr == snapshot.stderr
    assert tiny_proc.returncode == snapshot.returncode


def test_tiny_cli_runs_inline_source():
    """Test that tiny cli runs inline source."""
    proc = run_tiny_cli(["--source", "print(1 + 2);"])

    assert proc.returncode == 0
    assert proc.stdout == "3\n"
    assert proc.stderr == ""


def test_tiny_cli_parity_inline_source():
    """Test that tiny cli parity inline source."""
    assert_cli_parity(["--source", "print(10 - 3);"])


def test_tiny_cli_parity_file_and_backend(tmp_path):
    """Test that tiny cli parity file and backend."""
    program = "print(6 * 7);"
    file_path = tmp_path / "program.tiny"
    file_path.write_text(program, encoding="utf-8")

    assert_cli_parity(["--file", str(file_path), "--backend", "python"])


def test_tiny_cli_parity_errors(tmp_path):
    """Test that tiny cli parity errors."""
    program = "def x = 1; @"
    file_path = tmp_path / "bad.tiny"
    file_path.write_text(program, encoding="utf-8")

    assert_cli_parity(["--file", str(file_path)])


def test_tiny_lang_cli_parity_inline_source():
    """Test that tiny lang cli parity inline source."""
    assert_cli_parity(["--source", "print(5 + 4);"], cli_path=TINY_LANG_CLI)


@pytest.mark.parametrize("snapshot", SNAPSHOTS, ids=lambda snapshot: " ".join(snapshot.args))
def test_tiny_cli_parity_snapshots(snapshot: CliSnapshot) -> None:
    """Test that tiny cli parity snapshots."""
    assert_cli_snapshot(snapshot)


def test_tiny_cli_typecheck_then_backend_run_workflow(tmp_path):
    """Typecheck-first workflow should pass before backend execution."""
    program = "fn add(x: number, y: number) -> number { return x + y; }\nprint(add(2, 3));\n"
    file_path = tmp_path / "typed_program.tiny"
    file_path.write_text(program, encoding="utf-8")

    typecheck_proc = run_tiny_cli(["--file", str(file_path), "--typecheck"])
    assert typecheck_proc.returncode == 0
    assert typecheck_proc.stdout == "5\n"
    assert typecheck_proc.stderr == ""

    backend_proc = run_tiny_cli(["--file", str(file_path), "--backend", "python"])
    assert backend_proc.returncode == 0
    assert backend_proc.stdout == "5\n"
    assert backend_proc.stderr == ""
