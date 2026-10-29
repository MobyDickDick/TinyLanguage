"""Qualify installed CLI/editor helpers in a separate project without a checkout."""

from __future__ import annotations

import argparse
import json
import hashlib
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile

from verify_python_package import verify as verify_package


def verify(wheel: Path, extension: Path, work: Path, *, editor: Path | None = None) -> dict:
    """Install a wheel and exercise project, backend, tooling and DAP workflows."""
    report = verify_package(wheel, work)
    scripts = work / "environment" / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    tiny = scripts / ("tiny.exe" if os.name == "nt" else "tiny")
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "PYTHONHOME", "TINYPATH"}}
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    commands = []

    def run(arguments, *, source=None, cwd=work):
        result = subprocess.run([str(arg) for arg in arguments], input=source,
                                cwd=cwd, env=environment, capture_output=True,
                                text=True, encoding="utf-8", timeout=120)
        assert result.returncode == 0, f"{arguments}\n{result.stdout}\n{result.stderr}"
        commands.append([str(arg) for arg in arguments])
        return result.stdout.strip()

    quickstart = Path(__file__).resolve().parents[2] / "docs/installed_workflows.md"
    block = quickstart.read_text(encoding="utf-8").split("<!-- installed-quickstart -->", 1)[1].split("```bash", 1)[1].split("```", 1)[0]
    quickstart_checks = []
    for line in block.strip().splitlines():
        arguments = shlex.split(line)
        executable = arguments[0]
        arguments[0] = python if executable == "python" else scripts / (
            f"{executable}.exe" if os.name == "nt" else executable)
        output = run(arguments)
        quickstart_checks.append({"command": line, "stdout_sha256": hashlib.sha256(output.encode()).hexdigest()})

    project = work / "Pröjekt with spaces"
    run([tiny, "project", "init", project, "--name", "demo", "--vscode"])
    settings = json.loads((project / ".vscode/settings.json").read_text(encoding="utf-8"))
    assert Path(settings["tinylanguage.pythonPath"]).resolve() == python.resolve()
    assert settings["tinylanguage.runtimePath"] == ""
    program = project / "src/main.tiny"
    assert run([tiny, program]) == "Hello from demo!"
    (program.parent / "helper.tiny").write_text("fn value() { return 7; }\n", encoding="utf-8")
    program.write_text("import helper;\nimport stdlib.math as math;\nprint(helper.value() + math.sqrt(81));\n",
                       encoding="utf-8")
    assert run([tiny, program]) == "16"
    assert run([tiny, "--file", program, "--typecheck"]) == "16"
    run([tiny, "pkg", "init", project])
    run([tiny, "pkg", "resolve", "--manifest", project / "tiny.toml"])
    assert (project / "tiny.lock").is_file()

    simple = project / "backend.tiny"
    simple.write_text("print(1 + 2);\n", encoding="utf-8")
    for backend in ("interpreter", "python", "native", "native-python-bytecode"):
        assert run([tiny, simple, "--backend", backend]) == "3"
    c_source = run([python, "-m", "tinyc_cli", simple, "--emit-c"])
    assert "main(" in c_source
    assert run([tiny, "c", simple, "--emit-c"]) == c_source
    lsp = scripts / ("tiny-lsp.exe" if os.name == "nt" else "tiny-lsp")
    assert json.loads(run([lsp, "--file", simple, "diagnostics"])) == []
    assert "print" in json.loads(run([lsp, "--file", simple, "format"]))["source"]

    # Copy only the shipped extension payload; no neighboring repository src/.
    installed_extension = work / "installed extension"
    shutil.copytree(extension, installed_extension,
                    ignore=shutil.ignore_patterns("node_modules", "*.vsix", "__pycache__", ".vscode"))
    report["extension_files"] = {
        name: hashlib.sha256((installed_extension / name).read_bytes()).hexdigest()
        for name in ("extension.js", "package.json", "python/vscode_helpers.py", "python/tiny_debug_adapter.py")
    }
    helper = installed_extension / "python/vscode_helpers.py"
    formatted = run([python, helper, "format"], source="print(1+2);")
    assert "print" in formatted
    assert run([python, helper, "format"], source=formatted) == formatted
    assert json.loads(run([python, helper, "diagnostics"], source="print(1+);"))

    # Run the actual debug adapter handlers with the wheel's interpreter/hooks.
    # A separate process guarantees that repository imports cannot mask failures.
    driver = work / "debug_acceptance.py"
    driver.write_text('''import importlib.util, json, sys, time
from pathlib import Path
adapter, program = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("acceptance_adapter", adapter)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
server = module.DAPServer()
messages = []
server._send = messages.append
server.handle_initialize({"seq": 1, "command": "initialize"})
server.handle_set_breakpoints({"seq": 2, "command": "setBreakpoints", "arguments": {
    "source": {"path": str(program)}, "breakpoints": [{"line": 3}]}})
server.handle_launch({"seq": 3, "command": "launch", "arguments": {"program": str(program)}})
server.handle_configuration_done({"seq": 4, "command": "configurationDone"})
deadline = time.monotonic() + 10
try:
    while not any(m.get("event") == "stopped" for m in messages):
        assert time.monotonic() < deadline, messages
        time.sleep(0.01)
    server.handle_stack_trace({"seq": 5, "command": "stackTrace"})
    stack = next(m for m in messages if m.get("command") == "stackTrace")
    assert stack["body"]["stackFrames"][-1]["line"] == 3, stack
finally:
    server._command_queue.put("continue")
    server._thread.join(timeout=10)
assert not server._thread.is_alive()
assert any(m.get("event") == "terminated" for m in messages), messages
assert any(m.get("event") == "output" and "16" in m.get("body", {}).get("output", "") for m in messages), messages
print(json.dumps({"debug": "breakpoint-stack-continue-terminate", "runtime": module.compile_and_run.__module__}))
''', encoding="utf-8")
    debug = json.loads(run([python, driver, installed_extension / "python/tiny_debug_adapter.py", program]))
    report["checks"] += ["project-scaffolding", "unrelated-working-directory", "unicode-space-paths",
                         "local-and-stdlib-import", "typecheck", "package-init-resolve", "execution-backends",
                         "c-module-and-subcommand-emission", "lsp-format-diagnostics",
                         "extension-helper-format-diagnostics", debug["debug"]]
    report["commands"] = commands
    report["quickstart"] = quickstart_checks
    if editor:
        editor_report = work / "editor-acceptance.json"
        environment.update(TINY_EDITOR_PYTHON=str(python), TINY_EDITOR_REPORT=str(editor_report))
        # A dedicated profile keeps this test independent of personal extensions/settings.
        run([editor, "--wait", "--new-window", "--skip-welcome", "--skip-release-notes",
             "--disable-workspace-trust", "--user-data-dir", work / "editor-profile",
             "--extensions-dir", work / "editor-extensions",
             f"--extensionDevelopmentPath={installed_extension}",
             f"--extensionTestsPath={Path(__file__).with_name('editor_acceptance.cjs').resolve()}", project])
        report["editor"] = json.loads(editor_report.read_text(encoding="utf-8"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--extension", type=Path, default=Path(__file__).resolve().parents[2] / "vscode-extension")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--editor", type=Path, help="Optional VS Code executable for actual extension-host acceptance")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tiny-workflows-") as directory:
        report = verify(args.wheel.resolve(), args.extension.resolve(), Path(directory), editor=args.editor)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
