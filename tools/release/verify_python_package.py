"""Install a wheel in a fresh environment and exercise it outside the checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def verify(wheel: Path, work: Path) -> dict:
    environment = work / "environment"
    venv.EnvBuilder(with_pip=True).create(environment)
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    clean_env = {key: value for key, value in os.environ.items()
                 if key not in {"PYTHONPATH", "PYTHONHOME", "TINYPATH"}}
    clean_env["PYTHONNOUSERSITE"] = "1"
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"

    def run(arguments: list[str]) -> str:
        result = subprocess.run(arguments, cwd=work, env=clean_env,
                                capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise RuntimeError(f"Command failed: {arguments}\n{result.stdout}\n{result.stderr}")
        return result.stdout.strip()

    run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)])
    project = work / "separate project"
    project.mkdir()
    program = project / "main.tiny"
    program.write_text("import stdlib.math as math;\nprint(math.sqrt(81));\n", encoding="utf-8")
    tiny = scripts / ("tiny.exe" if os.name == "nt" else "tiny")
    cli_version = run([str(tiny), "--version"])
    assert run([str(tiny), str(program)]) == "9", "installed tiny stdlib import failed"
    assert run([str(python), "-m", "tiny_language", str(program)]) == "9"
    # The C CLI's module entry point must import successfully even without clang.
    run([str(python), "-m", "tinyc_cli", "--help"])
    for command in ("tiny-project", "tiny-pkg", "tinyc", "tiny-lsp"):
        executable = scripts / (f"{command}.exe" if os.name == "nt" else command)
        run([str(executable), "--help"])
    metadata = json.loads(run([str(python), "-c", """
import importlib.metadata as metadata
import json
from pathlib import Path
import tiny_language
root = Path(tiny_language.__file__).parent
assert (root / 'src_tiny' / 'tiny_language_parser.tiny').is_file()
assert (root / 'stdlib' / 'math.tiny').is_file()
assert not (root / 'tiny_language_stitched.py').exists()
print(json.dumps({'version': metadata.version('tinylanguage'),
                  'module': str(Path(tiny_language.__file__).resolve()),
                  'requires': metadata.requires('tinylanguage') or []}))
"""]))
    metadata["checks"] = ["clean-wheel-install", "stdlib-import", "python-module",
                          "console-entry-points", "bootstrap-assets", "no-source-write", "release-version"]
    metadata["artifact"] = {"name": wheel.name, "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}
    metadata["python"] = sys.version.split()[0]
    assert cli_version == f"TinyLanguage {metadata['version']}", "CLI and distribution versions differ"
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tiny-installed-") as directory:
        report = verify(args.wheel.resolve(), Path(directory))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
