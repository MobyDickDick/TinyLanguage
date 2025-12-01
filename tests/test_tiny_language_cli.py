import os
import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def run_cli(command):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
        ),
    }
    return subprocess.run(
        [sys.executable, "src/tiny_language_cli.py", *command],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def test_cli_runs_file(tmp_path):
    program = "print(1 + 2);"
    file_path = tmp_path / "hello.tiny"
    file_path.write_text(program, encoding="utf-8")

    proc = run_cli(["--file", str(file_path)])

    assert proc.returncode == 0
    assert proc.stdout == "3\n"
    assert proc.stderr == ""


def test_cli_supports_inline_source_and_backends():
    proc = run_cli(["--source", "print(7);", "--backend", "python"])

    assert proc.returncode == 0
    assert proc.stdout == "7\n"
    assert proc.stderr == ""


def test_cli_renders_spans_on_errors(tmp_path):
    program = "define x = 1; @"
    file_path = tmp_path / "bad.tiny"
    file_path.write_text(program, encoding="utf-8")

    proc = run_cli(["--file", str(file_path)])

    assert proc.returncode == 1
    assert "[E000]" in proc.stderr
    assert "line 1" in proc.stderr
    assert "^" in proc.stderr
