import json
import os
import pathlib
import subprocess
import sys
from typing import List
from textwrap import dedent

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


def run_cli(command: List[str]):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
        ),
    }
    cmdline = [sys.executable, "src/language_server_cli.py", *command]
    try:
        proc = subprocess.run(
            cmdline,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        debug = dedent(
            f"""
            Command: {exc.cmd}
            Return code: {exc.returncode}
            --- STDOUT ---
            {exc.stdout}
            --- STDERR ---
            {exc.stderr}
            --- ENV (PYTHONPATH only) ---
            {env.get("PYTHONPATH")}
            """
        )
        raise AssertionError(f"CLI invocation failed.\n{debug}") from exc

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        debug = dedent(
            f"""
            Command: {cmdline}
            --- RAW STDOUT ---
            {proc.stdout}
            --- RAW STDERR ---
            {proc.stderr}
            """
        )
        raise AssertionError(f"Failed to parse CLI JSON output.\n{debug}") from exc


def test_cli_completions_emit_labels():
    payload = run_cli(["--source", "fn alpha() { return 1; }", "completions", "--prefix", "a"])
    labels = {item["label"] for item in payload}
    assert "alpha" in labels


def test_cli_completions_respect_prefix_filter(tmp_path):
    program = "fn zero() { return 0; }\nfn main() { return zero(); }"
    file_path = tmp_path / "program.tiny"
    file_path.write_text(program, encoding="utf-8")

    payload = run_cli(["--file", str(file_path), "completions", "--prefix", "ze"])
    labels = {item["label"] for item in payload}
    assert "zero" in labels
    assert all(label.startswith("ze") for label in labels)


def test_cli_hover_returns_position():
    payload = run_cli(["--source", "fn probe() { return 1; }", "hover", "--symbol", "probe"])
    assert payload["symbol"] == "probe"
    assert isinstance(payload["position"], list)
    assert len(payload["position"]) == 2
    assert all(isinstance(item, int) for item in payload["position"])


def test_cli_reports_diagnostics():
    payload = run_cli(
        ["--source", "fn greet() -> string { return \"hi\"; }\ndef ignored1 = greet();", "diagnostics"]
    )
    assert payload == []


def test_cli_reports_diagnostics_from_file(tmp_path):
    source = "fn describe(x: number) -> number { if (x > 0) { return x; } }"
    file_path = tmp_path / "lint_example.tiny"
    file_path.write_text(source, encoding="utf-8")

    payload = run_cli(["--file", str(file_path), "diagnostics"])
    assert payload
    diag = payload[0]
    assert diag["code"] == "E010"
    assert isinstance(diag["range"], list)
    assert len(diag["range"]) == 4


def test_cli_format_emits_formatted_source():
    payload = run_cli(["--source", "fn add(x,y){return x+y;}", "format"])
    assert payload["source"] == "fn add(x, y) {\n    return x + y;\n}\n"


def test_cli_workspace_symbols():
    source = "class Greeter { fn hello(self, name) { return name; } }"
    payload = run_cli(["--source", source, "workspace-symbols", "--query", "hello"])
    assert payload
    assert payload[0]["name"].endswith("hello")
    assert payload[0]["container"] == "Greeter"


def test_cli_reports_parse_errors_as_diagnostics():
    payload = run_cli(["--source", "fn broken() { return 1 ", "diagnostics"])
    assert payload
    diag = payload[0]
    assert diag["code"]
    assert isinstance(diag["range"], list)
    assert len(diag["range"]) == 4
