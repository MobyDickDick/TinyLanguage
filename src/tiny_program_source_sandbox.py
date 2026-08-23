"""Execute an approved TinyLanguage port under conservative OS limits.

The hand-off is accepted only when the porter's audit record still matches the
exact program bytes.  Execution happens in an empty temporary working
directory, in an isolated Python process with a short timeout and POSIX resource
ceilings.  The original port is never imported into the coordinator process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


SANDBOX_POLICY = "tiny-source-sandbox-v1"
REQUIRED_PORT_POLICY = "tiny-source-port-v1"
OUTPUT_LIMIT = 64 * 1024
FILE_SIZE_LIMIT = 16 * 1024 * 1024


@dataclass(frozen=True)
class SandboxReport:
    policy: str
    source_file: str
    source_sha256: str
    port_report_file: str
    verdict: str
    exit_code: int | None
    timed_out: bool
    output_sha256: str
    output_bytes: int
    tested_at: str
    duration_ms: int
    next_stage: str | None


def _load_port_report(program: Path, report_path: Path) -> tuple[dict[str, object], bytes]:
    if program.is_symlink() or report_path.is_symlink():
        raise ValueError("program and port report must be regular files without symlinks")
    if not program.is_file() or not report_path.is_file():
        raise ValueError("program and port report must exist")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("port report must be valid UTF-8 JSON") from exc
    payload = program.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if (
        not isinstance(report, dict)
        or report.get("policy") != REQUIRED_PORT_POLICY
        or report.get("status") != "ported-unexecuted"
        or report.get("next_stage") != "sandbox-test"
        or report.get("output_file") != program.name
        or report.get("output_sha256") != digest
    ):
        raise ValueError("port report does not approve this exact program for sandbox testing")
    return report, payload


def _limits() -> None:
    """Apply child-only ceilings before the TinyLanguage interpreter starts."""
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    # The interpreter stitches its modules into a temporary source file before
    # execution, so the filesystem ceiling must exceed that trusted bootstrap
    # artifact. Captured child output is still truncated to OUTPUT_LIMIT below.
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_SIZE_LIMIT,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))


def sandbox_test_port(
    program: Path, port_report: Path, destination_dir: Path, *, timeout: float = 3.0
) -> tuple[Path, Path]:
    """Run one byte-verified port and write captured output plus an assessment."""
    _report, payload = _load_port_report(program, port_report)
    digest = hashlib.sha256(payload).hexdigest()
    destination_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_path = destination_dir / f"{program.stem}.sandbox.out"
    report_path = destination_dir / f"{program.stem}.sandbox.json"
    source_root = Path(__file__).parent.resolve()
    cli = source_root / "tiny_language_cli.py"
    isolated_entrypoint = (
        "import runpy,sys;"
        f"sys.path.insert(0,{str(source_root)!r});"
        f"sys.argv=[{str(cli)!r},{str(program.resolve())!r}];"
        f"runpy.run_path({str(cli)!r},run_name='__main__')"
    )
    started = time.monotonic()
    timed_out = False
    exit_code: int | None
    with tempfile.TemporaryDirectory(prefix="tiny-source-sandbox-") as working_dir:
        try:
            result = subprocess.run(
                [sys.executable, "-I", "-c", isolated_entrypoint],
                cwd=working_dir,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
                preexec_fn=_limits,
            )
            exit_code = result.returncode
            captured = result.stdout[:OUTPUT_LIMIT]
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = None
            captured = (exc.stdout or b"")[:OUTPUT_LIMIT]
    duration_ms = round((time.monotonic() - started) * 1000)
    verdict = "passed" if exit_code == 0 and not timed_out else "failed"
    output_path.write_bytes(captured)
    os.chmod(output_path, 0o600)
    assessment = SandboxReport(
        policy=SANDBOX_POLICY,
        source_file=program.name,
        source_sha256=digest,
        port_report_file=port_report.name,
        verdict=verdict,
        exit_code=exit_code,
        timed_out=timed_out,
        output_sha256=hashlib.sha256(captured).hexdigest(),
        output_bytes=len(captured),
        tested_at=datetime.now(timezone.utc).isoformat(),
        duration_ms=duration_ms,
        next_stage="gui-wrapper" if verdict == "passed" else None,
    )
    report_path.write_text(json.dumps(asdict(assessment), indent=2, sort_keys=True) + "\n")
    os.chmod(report_path, 0o600)
    return output_path, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", type=Path)
    parser.add_argument("port_report", type=Path)
    parser.add_argument("--destination", type=Path, default=Path("var/sandbox-results"))
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args(argv)
    _output, report = sandbox_test_port(
        args.program, args.port_report, args.destination, timeout=args.timeout
    )
    assessment = json.loads(report.read_text(encoding="utf-8"))
    print(f"sandbox report: {report}")
    return 0 if assessment["verdict"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
