import os
import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def run_cli(command, extra_env=None):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
        ),
    }
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "src/tiny_language_cli.py", *command],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def run_cli_module(command):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
        ),
    }
    return subprocess.run(
        [sys.executable, "src/tiny_lang_cli.py", *command],
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


def test_cli_reports_file_remove_missing_path():
    proc = run_cli(["--source", "print(File.remove(\"missing.txt\"));"])

    assert proc.returncode == 0
    assert proc.stdout == "false\n"
    assert proc.stderr == ""


def test_cli_renders_spans_on_errors(tmp_path):
    program = "def x = 1; @"
    file_path = tmp_path / "bad.tiny"
    file_path.write_text(program, encoding="utf-8")

    proc = run_cli(["--file", str(file_path)])

    assert proc.returncode == 1
    assert "[E000]" in proc.stderr
    assert "line 1" in proc.stderr
    assert "^" in proc.stderr


def test_cli_reports_missing_path_in_stdlib_helpers():
    proc = run_cli(
        [
            "--source",
            "import stdlib.os;\ndef _unused = os.read_text(\"missing.txt\");",
        ]
    )

    assert proc.returncode == 1
    assert proc.stdout == ""
    assert "file does not exist: missing.txt" in proc.stderr
    assert "Stack trace:" in proc.stderr
    assert "stdlib.os.read_text" in proc.stderr


def test_cli_supports_positional_path(tmp_path):
    program = "print(4 * 5);"
    file_path = tmp_path / "positional.tiny"
    file_path.write_text(program, encoding="utf-8")

    proc = run_cli_module([str(file_path)])

    assert proc.returncode == 0
    assert proc.stdout == "20\n"
    assert proc.stderr == ""


def test_cli_module_reports_file_remove_missing_path():
    proc = run_cli_module(["--source", "print(File.remove(\"missing.txt\"));"])

    assert proc.returncode == 0
    assert proc.stdout == "false\n"
    assert proc.stderr == ""


def test_cli_module_reports_missing_path_in_stdlib_helpers():
    proc = run_cli_module(
        [
            "--source",
            "import stdlib.os;\ndef _unused = os.read_text(\"missing.txt\");",
        ]
    )

    assert proc.returncode == 1
    assert proc.stdout == ""
    assert "file does not exist: missing.txt" in proc.stderr
    assert "Stack trace:" in proc.stderr
    assert "stdlib.os.read_text" in proc.stderr


def test_cli_respects_copy_on_call_env():
    program = (
        "fn mutate(a) { def ignored1 = heap_set(a, 0, 9); }\n"
        "def xs = new(1);\n"
        "def ignored1 = heap_set(xs, 0, 1);\n"
        "mutate(xs);\n"
        "print(heap_get(xs, 0));"
    )

    proc = run_cli(["--source", program], extra_env={"TINYLANG_COPY_ON_CALL": "1"})

    assert proc.returncode == 0
    assert proc.stdout == "1\n"
    assert proc.stderr == ""
