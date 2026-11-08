"""Install a wheel in a fresh environment and exercise it outside the checkout."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import csv
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import venv


@contextmanager
def read_only_installation(root: Path):
    """Deny writes to a disposable installation, restoring permissions afterward."""
    if os.name == "nt":
        # File read-only attributes do not protect directories on Windows. An
        # inheritable deny ACE protects existing files and creation of new ones.
        identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                  capture_output=True, text=True, check=True)
        sid = next(csv.reader(identity.stdout.splitlines()))[-1]
        principal = "*" + sid
        # Deny specific mutation rights. Generic W also includes SYNCHRONIZE,
        # which Windows file readers need and therefore must retain.
        subprocess.run(["icacls", str(root), "/deny", principal + ":(OI)(CI)(WD,AD,WEA,WA,DE,DC)"],
                       capture_output=True, text=True, check=True)
        try:
            yield
        finally:
            subprocess.run(["icacls", str(root), "/remove:d", principal],
                           capture_output=True, text=True, check=True)
    else:
        paths = [root, *root.rglob("*")]
        modes = {path: stat.S_IMODE(path.stat().st_mode) for path in paths}
        try:
            for path in paths:
                path.chmod(modes[path] & ~0o222)
            yield
        finally:
            for path, mode in modes.items():
                path.chmod(mode)


def verify_immutable_imports(python: Path, root: Path, work: Path, env: dict) -> dict:
    """Execute four fresh processes against the same OS-protected installation."""
    root, work = root.resolve(), work.resolve()
    if not root.is_relative_to(work) or root == work or root.is_symlink():
        raise ValueError("read-only acceptance requires an installation inside its disposable workspace")

    def snapshot():
        return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob("*") if path.is_file()}

    before = snapshot()
    worker = r'''
import importlib, inspect, json, sys, traceback
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
# Prove that the OS, rather than a Python mock, rejects both source rewrites
# and creation of a generated file. Retain a failure on privileged POSIX runs.
for path, mode in ((root / 'tiny_language.py', 'ab'), (root / 'write-probe', 'wb')):
    try:
        with path.open(mode):
            pass
    except PermissionError:
        pass
    else:
        raise AssertionError('installation is writable: ' + str(path))
for name in sys.argv[2].split(','):
    importlib.import_module(name)
import tiny_language as tiny
import tiny_language_api as api
import tiny_language_ast as nodes
import tiny_language_eval as evaluator
import tiny_language_runtime as runtime
assert Path(tiny.__file__).parent == root
assert tiny.compile_and_run is api.compile_and_run
assert tiny.Runtime is runtime.Runtime
assert tiny.Fn is nodes.Fn
assert runtime.Runtime.eval_stmt is evaluator.eval_stmt
assert tiny.compile_and_run('import stdlib.math as m; print(m.sqrt(81));', stream_output=False).strip() == '9'
assert tiny.run_with_native_backend('print(6 * 7);').strip() == '42'
assert tiny.run_with_python_backend('def x = 3; x = x + 4; print(x);').strip() == '7'
assert Path(inspect.getsourcefile(tiny.compile_and_run)).name == 'tiny_language_api.py'
assert Path(inspect.getsourcefile(runtime.Runtime.eval_stmt)).name == 'tiny_language_eval.py'
try:
    runtime.Runtime('').eval_expr(object(), tiny.Environment(parent=None))
except tiny.TinyLangError as error:
    filenames = [Path(frame.filename).name for frame in traceback.extract_tb(error.__traceback__)]
    assert 'tiny_language_eval.py' in filenames, filenames
    assert 'tiny_language_stitched.py' not in filenames
else:
    raise AssertionError('invalid expression did not raise')
assert not (root / 'tiny_language_stitched.py').exists()
print(json.dumps({'os_write_denied': True, 'stdlib': True, 'native': True, 'python': True,
                  'canonical_identity': True, 'maintained_traceback': True}))
'''
    orders = ["tiny_language_runtime,tiny_language_api", "tiny_language_eval,tiny_language_runtime",
              "tiny_language_codegen_native,tiny_language_codegen_py", "tiny_language_parser,tiny_language"]

    def run(order):
        result = subprocess.run([str(python), "-I", "-B", "-c", worker, str(root), order],
                                cwd=work, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return json.loads(result.stdout)

    with read_only_installation(root):
        with ThreadPoolExecutor(max_workers=4) as pool:
            reports = list(pool.map(run, orders))
    assert snapshot() == before, "installation changed during concurrent execution"
    return {"processes": reports, "files_unchanged": len(before), "permission_restored": True}


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
                                stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, encoding="utf-8", timeout=180)
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
    metadata["platform"] = {"system": platform.system(), "machine": platform.machine()}
    metadata["immutable_imports"] = verify_immutable_imports(
        python, Path(metadata["module"]).parent, work, clean_env)
    metadata["checks"].extend(["os-read-only-imports", "concurrent-fresh-processes",
                               "canonical-module-identity", "maintained-tracebacks"])
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
