import json
import os
import pathlib
import subprocess
import sys
from typing import List

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def run_cli(command: List[str]):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
        ),
    }
    proc = subprocess.run(
        [sys.executable, "src/language_server_cli.py", *command],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )
    return json.loads(proc.stdout)


def test_cli_completions_emit_labels():
    payload = run_cli(["--source", "fn alpha() { return 1; }", "completions", "--prefix", "a"])
    labels = {item["label"] for item in payload}
    assert "alpha" in labels


def test_cli_hover_returns_position():
    payload = run_cli(["--source", "fn probe() { return 1; }", "hover", "--symbol", "probe"])
    assert payload["symbol"] == "probe"
    assert isinstance(payload["position"], list)
    assert len(payload["position"]) == 2
    assert all(isinstance(item, int) for item in payload["position"])


def test_cli_reports_diagnostics():
    payload = run_cli(
        ["--source", "fn greet() -> string { return \"hi\"; }\ngreet();", "diagnostics"]
    )
    assert payload
    assert payload[0]["code"] == "E011"
