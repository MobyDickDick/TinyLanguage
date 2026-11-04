"""Qualify a complete installed JSON application with locked remote packages.

Run outside the checkout in a clean wheel environment. The controlled HTTP
registry serves fixture dependencies only; no public service is contacted.
An optional previous release wheel additionally qualifies runtime upgrades.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import threading

from verify_python_package import verify as verify_package

ROOT = Path(__file__).resolve().parents[2]


def _distribution(multiplier: int) -> bytes:
    """Publish a tiny deterministic dependency into the controlled registry."""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        source = f"fn apply(value) {{ return value * {multiplier}; }}\n".encode()
        info = tarfile.TarInfo("src/transform.tiny")
        info.size = len(source)
        archive.addfile(info, io.BytesIO(source))
    return output.getvalue()


@contextmanager
def _registry(payloads):
    """Serve only immutable distributions selected by this acceptance case."""
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            payload = payloads.get(self.path)
            if payload is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def verify(wheel: Path, work: Path, *, previous_wheel: Path | None = None) -> dict:
    """Install, process files, enforce boundaries, upgrade and reproduce offline."""
    report = verify_package(wheel, work)
    scripts = work / "environment" / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    tiny = scripts / ("tiny.exe" if os.name == "nt" else "tiny")
    project = work / "Application ü with spaces"
    shutil.copytree(ROOT / "examples/package_acceptance", project / "src")
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "PYTHONHOME", "TINYPATH"}
                   and not key.startswith("TINY")}
    input_file = work / "input ü.json"
    output_file = work / "output ü.json"
    input_file.write_text(json.dumps({"value": 21, "label": "Grüezi"}), encoding="utf-8")
    environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                       TINY_APP_INPUT=str(input_file), TINY_APP_OUTPUT=str(output_file),
                       TINY_PKG_CACHE=str(work / "cache"))
    commands = []

    def run(arguments, *, success=True):
        result = subprocess.run([str(arg) for arg in arguments], input="", cwd=work, env=environment,
                                capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert (result.returncode == 0) == success, f"{arguments}\n{result.stdout}\n{result.stderr}"
        commands.append({"arguments": [str(arg) for arg in arguments], "returncode": result.returncode,
                         "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
                         "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest()})
        return result

    def application(expected):
        result = run([tiny, project / "src/main.tiny"])
        assert result.stdout == f"true\ntrue {expected}\n", result.stdout
        actual = json.loads(output_file.read_text(encoding="utf-8"))
        assert actual == {"value": expected, "label": "Grüezi"}, actual
        # Use the installed public API to inspect heap state after the same
        # complete application has joined its worker and freed its arguments.
        driver = (
            "from pathlib import Path; import sys; "
            "from tiny_language import Runtime, compile_and_run; "
            "path = Path(sys.argv[1]); source = path.read_text(encoding='utf-8'); "
            "runtime = Runtime(source); compile_and_run(source, runtime=runtime, module_path=path); "
            "assert runtime.heap_leak_report()['count'] == 0, runtime.heap_leak_report()"
        )
        assert run([python, "-c", driver, project / "src/main.tiny"]).stdout == result.stdout

    manifest = project / "tiny.toml"

    def write_manifest(version):
        manifest.write_text('[package]\nname="application"\nversion="1.0.0"\n'
                            f'[dependencies]\npricing="{version}"\n'
                            '[registries]\ndefault="https://acceptance.invalid"\n', encoding="utf-8")

    payloads = {"/1.0.0.tar.gz": _distribution(2), "/1.1.0.tar.gz": _distribution(3)}
    with _registry(payloads) as (base, requests):
        versions = {version: {"dist": f"{base}/{version}.tar.gz",
                              "sha256": hashlib.sha256(payloads[f"/{version}.tar.gz"]).hexdigest()}
                    for version in ("1.0.0", "1.1.0")}
        index = project / "tiny_registry.json"
        index.write_text(json.dumps({"pricing": {"versions": versions}}), encoding="utf-8")
        write_manifest("1.0.0")
        run([tiny, "pkg", "resolve", "--manifest", manifest])
        original_lock = (project / "tiny.lock").read_bytes()
        run([tiny, "pkg", "vendor", "--manifest", manifest])
        application(42)
        # A changed manifest cannot silently install using stale lock contents.
        write_manifest("1.1.0")
        drift = run([tiny, "pkg", "vendor", "--manifest", manifest, "--force"], success=False)
        assert "manifest hash does not match" in drift.stderr
        run([tiny, "pkg", "update", "--manifest", manifest])
        run([tiny, "pkg", "vendor", "--manifest", manifest])
        application(63)
        assert requests == ["/1.0.0.tar.gz", "/1.1.0.tar.gz"], requests
    # Reproduce the original lock after the server has actually stopped.
    write_manifest("1.0.0")
    (project / "tiny.lock").write_bytes(original_lock)
    shutil.rmtree(project / "vendor")
    run([tiny, "pkg", "vendor", "--manifest", manifest])
    application(42)
    assert len(requests) == 2
    report["dependency_upgrade"] = {"from": "1.0.0", "to": "1.1.0", "rollback_offline": True}

    invalid = project / "invalid.tiny"
    invalid.write_text("print(1 + );\n", encoding="utf-8")
    assert run([tiny, invalid], success=False).stderr.strip()
    input_file.write_text("{invalid json", encoding="utf-8")
    before = output_file.read_bytes()
    assert "json" in run([tiny, project / "src/main.tiny"], success=False).stderr.lower()
    assert output_file.read_bytes() == before
    input_file.write_text(json.dumps({"value": 21, "label": "Grüezi"}), encoding="utf-8")
    boundaries = run([tiny, project / "src/boundaries.tiny"]).stdout
    for expected in ("E_PERMISSION:network capability not enabled", "E_PERMISSION:process capability not enabled",
                     "[PYSEC] module subprocess denied", "[PYDENY] attribute sqrt not allowed", "true true true"):
        assert expected in boundaries, boundaries

    report["runtime_upgrade"] = {"status": "not-run", "reason": "No previous release wheel supplied"}
    if previous_wheel:
        run([python, "-m", "pip", "install", "--no-index", "--no-deps", "--force-reinstall", previous_wheel])
        previous_version = run([tiny, "--version"]).stdout.strip()
        assert previous_version != f"TinyLanguage {report['version']}", "Upgrade requires distinct release versions"
        application(42)
        run([python, "-m", "pip", "install", "--no-index", "--no-deps", "--upgrade", wheel])
        assert run([tiny, "--version"]).stdout.strip() == f"TinyLanguage {report['version']}"
        application(42)
        report["runtime_upgrade"] = {
            "status": "passed", "from": previous_version, "to": report["version"],
            "previous_artifact": {"name": previous_wheel.name,
                                  "sha256": hashlib.sha256(previous_wheel.read_bytes()).hexdigest()},
        }
    report["checks"] += ["installed-multifile-json-application", "locked-http-dependency", "dependency-upgrade",
                         "offline-lock-reproduction", "cli-errors", "file-output-preserved-on-invalid-input",
                         "network-and-process-denial", "python-allowlist", "worker-join-and-cancel"]
    report["checks"].append("application-heap-cleanup")
    report["fixtures"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (ROOT / "examples/package_acceptance").glob("*.tiny")}
    report["commands"] = commands
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--previous-wheel", type=Path)
    parser.add_argument("--require-runtime-upgrade", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.require_runtime_upgrade and args.previous_wheel is None:
        parser.error("--require-runtime-upgrade requires --previous-wheel")
    with tempfile.TemporaryDirectory(prefix="tiny-application-") as directory:
        report = verify(args.wheel.resolve(), Path(directory),
                        previous_wheel=args.previous_wheel.resolve() if args.previous_wheel else None)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
