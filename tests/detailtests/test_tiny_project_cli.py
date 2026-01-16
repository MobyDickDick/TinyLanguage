import json
import os
import pathlib
import subprocess
import sys
from textwrap import dedent

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


def run_cli(command, cwd):
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            filter(None, [str(SRC_ROOT), os.environ.get("PYTHONPATH")])
        ),
    }
    cmdline = [sys.executable, "-m", "tiny_project_cli", *command]
    try:
        subprocess.run(
            cmdline,
            capture_output=True,
            text=True,
            cwd=cwd,
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


def test_project_cli_init_scaffolds_project(tmp_path):
    project_dir = tmp_path / "my_app"
    run_cli(["init", str(project_dir), "--vscode"], cwd=PROJECT_ROOT)

    manifest = json.loads((project_dir / "module.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "my_app"
    assert manifest["entry"] == "src/main.tiny"

    main_source = (project_dir / "src" / "main.tiny").read_text(encoding="utf-8")
    assert "Hello from my_app" in main_source

    launch = json.loads((project_dir / ".vscode" / "launch.json").read_text(encoding="utf-8"))
    assert launch["configurations"][0]["type"] == "tinylanguage"

    settings = json.loads((project_dir / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    assert settings["tinylanguage.pythonPath"] == "python"
    assert settings["tinylanguage.runtimePath"] == str(SRC_ROOT / "tiny_language.py")
