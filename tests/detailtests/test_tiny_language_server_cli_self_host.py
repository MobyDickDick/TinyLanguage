import json
import os
import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
TINY_LANGUAGE = PROJECT_ROOT / "src" / "tiny_language.py"
TINY_SERVER_CLI = PROJECT_ROOT / "src_tiny" / "language_server_cli.tiny"


def run_tiny_language_server(args):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH")])
        ),
        "TINYPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src_tiny"), os.environ.get("TINYPATH")])
        ),
        "TINYLANG_ARGS": json.dumps(args),
    }
    return subprocess.run(
        [sys.executable, str(TINY_LANGUAGE), str(TINY_SERVER_CLI)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


def test_tiny_language_server_completions_and_hover():
    source = "fn add(x, y) { return x + y; }"

    completions = run_tiny_language_server(
        ["--source", source, "completions", "--prefix", "ad"]
    )

    assert completions.returncode == 0, completions.stderr
    completion_payload = json.loads(completions.stdout)
    assert any(item["label"] == "add" for item in completion_payload)

    hover = run_tiny_language_server(["--source", source, "hover", "--symbol", "add"])

    assert hover.returncode == 0, hover.stderr
    hover_payload = json.loads(hover.stdout)
    assert hover_payload["symbol"] == "add"
    assert "fn add" in hover_payload["detail"]


def test_tiny_language_server_diagnostics():
    diagnostics = run_tiny_language_server(
        [
            "--source",
            "fn greet() -> string { return \"hi\"; }\ngreet();",
            "diagnostics",
        ]
    )

    assert diagnostics.returncode == 0, diagnostics.stderr
    diagnostic_payload = json.loads(diagnostics.stdout)
    assert diagnostic_payload == []
