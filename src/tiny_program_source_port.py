"""Port statically approved quarantine sources into TinyLanguage.

This stage never executes the source.  It accepts only the byte-exact input
approved by the static scanner and uses the project's deliberately small
Python-to-Tiny transpiler for Python sources.  Native Tiny sources are copied
after the same gate so every published result has one audit record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from tiny_language_transpilers import PythonTranspiler, TinyLanguageTranspiler


PORTER_VERSION = "tiny-source-port-v1"
REQUIRED_SCAN_POLICY = "tiny-source-static-v1"


@dataclass(frozen=True)
class PortReport:
    policy: str
    source_file: str
    source_sha256: str
    scan_file: str
    output_file: str
    output_sha256: str
    language: str
    ported_at: str
    status: str = "ported-unexecuted"
    next_stage: str = "sandbox-test"


def _regular_file(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise ValueError(f"{label} does not exist: {path}") from exc
    if not stat.S_ISREG(mode):
        raise ValueError(f"{label} must be a regular file without symlinks")


def _read_object(path: Path, label: str) -> dict[str, object]:
    _regular_file(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _atomic_write(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".port-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def port_approved_source(
    source: Path, metadata: Path, scan_report: Path, destination_dir: Path
) -> tuple[Path, Path]:
    """Port one approved quarantine triple and return output and audit paths."""
    _regular_file(source, "quarantined source")
    provenance = _read_object(metadata, "provenance metadata")
    scan = _read_object(scan_report, "scan report")
    if source.parent != metadata.parent or source.parent != scan_report.parent:
        raise ValueError("source, metadata, and scan report must share a quarantine directory")
    if metadata.name != f"{source.stem}.json" or scan_report.name != f"{source.stem}.scan.json":
        raise ValueError("source, metadata, and scan report must be a matching quarantine triple")

    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if provenance.get("status") != "unreviewed":
        raise ValueError("provenance status must be unreviewed")
    if provenance.get("sha256") != digest or provenance.get("byte_size") != len(payload):
        raise ValueError("quarantined source does not match provenance")
    if (
        scan.get("policy") != REQUIRED_SCAN_POLICY
        or scan.get("verdict") != "passed"
        or scan.get("next_stage") != "automatic-porting"
        or scan.get("source_file") != source.name
        or scan.get("source_sha256") != digest
    ):
        raise ValueError("scan report does not approve this exact source for automatic porting")

    final_url = provenance.get("final_url")
    if not isinstance(final_url, str):
        raise ValueError("provenance final_url must be a string")
    suffix = Path(urlparse(final_url).path).suffix.casefold()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("approved source must be UTF-8 text") from exc
    if suffix == ".py":
        try:
            program = PythonTranspiler().from_source(text)
            output_text = TinyLanguageTranspiler().to_source(program) + "\n"
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"Python source is outside the automatic-porting subset: {exc}") from exc
        language = "python"
    elif suffix == ".tiny":
        output_text = text if text.endswith("\n") else text + "\n"
        language = "tiny"
    else:
        raise ValueError(f"approved source type cannot be ported: {suffix or '<none>'}")

    safe_stem = Path(urlparse(final_url).path).stem
    if not safe_stem or not safe_stem.replace("_", "").replace("-", "").isalnum():
        safe_stem = digest[:16]
    output = destination_dir / f"{digest[:16]}-{safe_stem}.tiny"
    output_bytes = output_text.encode("utf-8")
    report_path = output.with_suffix(".port.json")
    report = PortReport(
        policy=PORTER_VERSION,
        source_file=source.name,
        source_sha256=digest,
        scan_file=scan_report.name,
        output_file=output.name,
        output_sha256=hashlib.sha256(output_bytes).hexdigest(),
        language=language,
        ported_at=datetime.now(timezone.utc).isoformat(),
    )
    _atomic_write(output, output_bytes)
    _atomic_write(report_path, (json.dumps(asdict(report), indent=2, sort_keys=True) + "\n").encode())
    return output, report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("scan_report", type=Path)
    parser.add_argument("--destination", type=Path, default=Path("var/ported-sources"))
    args = parser.parse_args(argv)
    output, report = port_approved_source(
        args.source, args.metadata, args.scan_report, args.destination
    )
    print(f"ported source: {output}")
    print(f"port report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
