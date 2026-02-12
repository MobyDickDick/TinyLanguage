"""CLI regression tests for the Tiny Language language server entrypoint.

These tests invoke the CLI with temporary sources and validate that JSON
responses include the expected structures for completions, hover data,
diagnostics, formatting, and workspace symbol queries.
"""

import json
import os
import pathlib
import subprocess
import sys
from textwrap import dedent
from typing import List

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


def run_cli(command: List[str]):
    """Run the language server CLI with a clean PYTHONPATH and parse JSON."""
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


def build_multi_file_project(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a multi-file TinyLanguage project for end-to-end LSP checks."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "math.tiny").write_text(
        "fn add(x, y) { return x + y; }\n",
        encoding="utf-8",
    )
    (project_dir / "main.tiny").write_text(
        "fn main() { return add(1, 2); }\n",
        encoding="utf-8",
    )
    (project_dir / "formatting.tiny").write_text(
        "fn greet(){return 1;}\n",
        encoding="utf-8",
    )
    return project_dir


def read_project_source(project_dir: pathlib.Path) -> str:
    """Return the concatenated project source payload used by ``--project``."""
    paths = sorted(project_dir.rglob("*.tiny"))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def source_end_position(source: str) -> tuple[int, int]:
    """Return the same 1-based end position logic used by the language server."""
    if not source:
        return (1, 1)
    last_newline = source.rfind("\n")
    if last_newline == -1:
        return (1, len(source) + 1)
    line = source.count("\n") + 1
    col = len(source) - last_newline
    return (line, col)


def test_cli_completions_emit_labels():
    """Completions should list identifiers defined in the source."""
    payload = run_cli(["--source", "fn alpha() { return 1; }", "completions", "--prefix", "a"])
    labels = {item["label"] for item in payload}
    assert "alpha" in labels


def test_cli_completions_respect_prefix_filter(tmp_path):
    """Completions from files should respect the prefix filter."""
    program = "fn zero() { return 0; }\nfn main() { return zero(); }"
    file_path = tmp_path / "program.tiny"
    file_path.write_text(program, encoding="utf-8")

    payload = run_cli(["--file", str(file_path), "completions", "--prefix", "ze"])
    labels = {item["label"] for item in payload}
    assert "zero" in labels
    assert all(label.startswith("ze") for label in labels)


def test_cli_hover_returns_position():
    """Hover requests return the resolved symbol name and location."""
    payload = run_cli(["--source", "fn probe() { return 1; }", "hover", "--symbol", "probe"])
    assert payload["symbol"] == "probe"
    assert isinstance(payload["position"], list)
    assert len(payload["position"]) == 2
    assert all(isinstance(item, int) for item in payload["position"])


def test_cli_reports_diagnostics():
    """Valid source should yield an empty diagnostics list."""
    payload = run_cli(
        ["--source", "fn greet() -> string { return \"hi\"; }\ndef ignored1 = greet();", "diagnostics"]
    )
    assert payload == []


def test_cli_reports_diagnostics_from_file(tmp_path):
    """Linting a file should return structured diagnostics."""
    source = "fn describe(x: number) -> number { if (x > 0) { return x; } }"
    file_path = tmp_path / "lint_example.tiny"
    file_path.write_text(source, encoding="utf-8")

    payload = run_cli(["--file", str(file_path), "diagnostics"])
    assert payload
    diag = payload[0]
    assert diag["code"] == "E010"
    assert isinstance(diag["range"], list)
    assert len(diag["range"]) == 4


def test_cli_reports_typing_profile_diagnostics():
    """Typing profile should surface assignment type mismatches."""
    source = 'fn main() { def value = 1; value = "no"; return value; }'
    default_payload = run_cli(["--source", source, "diagnostics"])
    assert default_payload == []

    typing_payload = run_cli(["--lint-profile", "typing", "--source", source, "diagnostics"])
    assert any(diag["code"] == "E014" for diag in typing_payload)


def test_cli_format_emits_formatted_source():
    """Formatting should return a normalized, pretty-printed source string."""
    payload = run_cli(["--source", "fn add(x,y){return x+y;}", "format"])
    assert payload["source"] == "fn add(x, y) {\n    return x + y;\n}\n"


def test_cli_workspace_symbols():
    """Workspace symbol search should return a matching method entry."""
    source = "class Greeter { fn hello(self, name) { return name; } }"
    payload = run_cli(["--source", source, "workspace-symbols", "--query", "hello"])
    assert payload
    assert payload[0]["name"].endswith("hello")
    assert payload[0]["container"] == "Greeter"


def test_cli_reports_parse_errors_as_diagnostics():
    """Parse errors should be returned as diagnostics instead of crashes."""
    payload = run_cli(["--source", "fn broken() { return 1 ", "diagnostics"])
    assert payload
    diag = payload[0]
    assert diag["code"]
    assert isinstance(diag["range"], list)
    assert len(diag["range"]) == 4


def test_cli_project_references_span_multiple_files(tmp_path):
    """Reference lookups should include usages across project files."""
    project_dir = build_multi_file_project(tmp_path)
    payload = run_cli(["--project", str(project_dir), "references", "--symbol", "add"])
    assert len(payload) == 2


def test_cli_project_rename_returns_multi_file_edits(tmp_path):
    """Rename operations should include edits from all project files."""
    project_dir = build_multi_file_project(tmp_path)
    payload = run_cli(["--project", str(project_dir), "rename", "--symbol", "add", "--new-name", "sum"])
    assert len(payload) == 2
    assert all(edit["newText"] == "sum" for edit in payload)


def test_cli_project_code_actions_offer_formatting(tmp_path):
    """Code actions should surface formatting when any project file is unformatted."""
    project_dir = build_multi_file_project(tmp_path)
    payload = run_cli(["--project", str(project_dir), "code-actions"])
    assert any(action["kind"] == "source.format" for action in payload)


def test_cli_project_formatting_hook_matches_format_output(tmp_path):
    """Formatting code-action edits should match the formatted project payload."""
    project_dir = build_multi_file_project(tmp_path)
    source_payload = read_project_source(project_dir)

    formatted_payload = run_cli(["--project", str(project_dir), "format"])
    code_actions_payload = run_cli(["--project", str(project_dir), "code-actions"])

    format_actions = [action for action in code_actions_payload if action["kind"] == "source.format"]
    assert len(format_actions) == 1

    format_action = format_actions[0]
    assert format_action["title"] == "Format document"
    assert format_action["diagnostics"] == []
    assert len(format_action["edits"]) == 1

    edit = format_action["edits"][0]
    expected_end_line, expected_end_col = source_end_position(source_payload)
    assert edit["range"] == [1, 1, expected_end_line, expected_end_col]
    assert edit["newText"] == formatted_payload["source"]
