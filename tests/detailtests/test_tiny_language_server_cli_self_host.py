"""Tests for tiny language server cli self host."""

import json
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
TINY_LANGUAGE = PROJECT_ROOT / "src" / "tiny_language.py"
TINY_SERVER_CLI = PROJECT_ROOT / "src_tiny" / "language_server_cli.tiny"
PYTHON_SERVER_CLI = PROJECT_ROOT / "src" / "language_server_cli.py"
FIXTURE_SOURCE = PROJECT_ROOT / "tests" / "fixtures" / "language_server_entrypoint_sample.tiny"


@dataclass(frozen=True)
class ServerSnapshot:
    args: list[str]
    payload: object

def run_tiny_language_server(args):
    """Helper to run tiny language server."""
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


def run_python_language_server(args):
    """Helper to run python language server."""
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(PROJECT_ROOT / "src"), os.environ.get("PYTHONPATH")])
        ),
    }
    return subprocess.run(
        [sys.executable, str(PYTHON_SERVER_CLI), *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )


SNAPSHOTS = [
    ServerSnapshot(
        args=["--source", "fn add(x, y) { return x + y; }", "completions", "--prefix", "ad"],
        payload=[{"label": "add", "kind": "function"}],
    ),
    ServerSnapshot(
        args=["--source", "fn add(x, y) { return x + y; }", "hover", "--symbol", "add"],
        payload={"symbol": "add", "detail": "fn add(x, y)", "position": [1, 1]},
    ),
    ServerSnapshot(
        args=["--source", "def x = 1; @", "diagnostics"],
        payload=[
            {
                "message": "[E000] lexing error: unexpected character '@' (line 1, col 12)\n> 1 | def x = 1; @\n    |            ^",
                "code": "E000",
                "range": [1, 12, 1, 13],
                "severity": "error",
                "phase": "parse",
                "source": "parser",
                "origin": "language_server",
                "hint": None,
            }
        ],
    ),
    ServerSnapshot(
        args=["--file", str(FIXTURE_SOURCE), "completions", "--prefix", "ad"],
        payload=[{"label": "add", "kind": "function"}],
    ),
    ServerSnapshot(
        args=["--file", str(FIXTURE_SOURCE), "hover", "--symbol", "add"],
        payload={"symbol": "add", "detail": "fn add(x, y)", "position": [1, 1]},
    ),
    ServerSnapshot(
        args=["--file", str(FIXTURE_SOURCE), "diagnostics"],
        payload=[],
    ),
]


def test_tiny_language_server_completions_and_hover():
    """Test that tiny language server completions and hover."""
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
    """Test that tiny language server diagnostics."""
    diagnostics = run_tiny_language_server(
        [
            "--source",
            "fn greet() -> string { return \"hi\"; }\ndef ignored1 = greet();",
            "diagnostics",
        ]
    )

    assert diagnostics.returncode == 0, diagnostics.stderr
    diagnostic_payload = json.loads(diagnostics.stdout)
    assert diagnostic_payload == []


def assert_server_snapshot(snapshot: ServerSnapshot) -> None:
    """Helper to assert server snapshot."""
    python_proc = run_python_language_server(snapshot.args)
    assert python_proc.returncode == 0, python_proc.stderr
    python_payload = json.loads(python_proc.stdout)
    assert python_payload == snapshot.payload

    tiny_proc = run_tiny_language_server(snapshot.args)
    assert tiny_proc.returncode == 0, tiny_proc.stderr
    tiny_payload = json.loads(tiny_proc.stdout)
    assert tiny_payload == snapshot.payload


def test_tiny_language_server_cli_parity_snapshots() -> None:
    """Test that tiny language server cli parity snapshots."""
    for snapshot in SNAPSHOTS:
        assert_server_snapshot(snapshot)
