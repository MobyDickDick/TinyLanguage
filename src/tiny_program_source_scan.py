"""Perform the non-executing security gate for quarantined program sources.

The scanner deliberately works on bytes and text only.  It never imports,
parses, or executes the untrusted source.  A passing report merely permits the
next pipeline stage (porting); it does not declare the source safe to run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


POLICY_VERSION = "tiny-source-static-v1"
ALLOWED_SOURCE_SUFFIXES = frozenset({".py", ".tiny"})
_REQUIRED_METADATA = {
    "source_url", "final_url", "byte_size", "sha256", "fetched_at", "status"
}
_BINARY_SIGNATURES = (
    (b"\x7fELF", "ELF executable"),
    (b"MZ", "PE executable"),
    (b"PK\x03\x04", "ZIP archive"),
    (b"\x1f\x8b", "gzip archive"),
)
_DANGEROUS_TEXT = (
    (re.compile(r"(?m)^\s*#!"), "executable shebang"),
    (re.compile(r"\b(?:eval|exec|compile|__import__)\s*\("), "dynamic code execution"),
    (re.compile(r"\b(?:subprocess|socket|requests|urllib)\b"), "external I/O API"),
    (re.compile(r"\bos\s*\.\s*(?:system|popen|exec\w*|spawn\w*)\s*\("), "process execution"),
)


@dataclass(frozen=True)
class ScanReport:
    """Auditable outcome of one static quarantine scan."""

    policy: str
    source_file: str
    source_sha256: str
    scanned_at: str
    verdict: str
    findings: tuple[str, ...]
    next_stage: str | None


def _regular_file(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise ValueError(f"{label} does not exist: {path}") from exc
    if not stat.S_ISREG(mode):
        raise ValueError(f"{label} must be a regular file without symlinks")


def _load_provenance(source: Path, metadata: Path) -> tuple[bytes, dict[str, object]]:
    _regular_file(source, "quarantined source")
    _regular_file(metadata, "provenance metadata")
    if source.parent != metadata.parent or source.stem != metadata.stem:
        raise ValueError("source and provenance metadata must be a matching quarantine pair")
    try:
        record = json.loads(metadata.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("provenance metadata must be valid UTF-8 JSON") from exc
    if not isinstance(record, dict) or not _REQUIRED_METADATA.issubset(record):
        raise ValueError("provenance metadata is incomplete")
    if record["status"] != "unreviewed":
        raise ValueError("only unreviewed quarantine records may be scanned")

    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if type(record["byte_size"]) is not int or record["byte_size"] != len(payload):
        raise ValueError("quarantined source size does not match provenance")
    if not isinstance(record["sha256"], str) or record["sha256"] != digest:
        raise ValueError("quarantined source digest does not match provenance")
    return payload, record


def scan_quarantined_source(source: Path, metadata: Path) -> Path:
    """Scan a quarantine pair and atomically write a separate verdict report."""
    payload, record = _load_provenance(source, metadata)
    findings: list[str] = []
    suffix = Path(urlparse(str(record["final_url"])).path).suffix.casefold()
    if suffix not in ALLOWED_SOURCE_SUFFIXES:
        findings.append(f"source type is not allowlisted: {suffix or '<none>'}")
    if b"\x00" in payload:
        findings.append("NUL byte indicates non-text content")
    for signature, description in _BINARY_SIGNATURES:
        if payload.startswith(signature):
            findings.append(f"blocked binary signature: {description}")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        findings.append("source is not valid UTF-8 text")
        text = ""
    for pattern, description in _DANGEROUS_TEXT:
        if pattern.search(text):
            findings.append(f"blocked static pattern: {description}")

    verdict = "passed" if not findings else "rejected"
    report = ScanReport(
        policy=POLICY_VERSION,
        source_file=source.name,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        verdict=verdict,
        findings=tuple(findings),
        next_stage="automatic-porting" if verdict == "passed" else None,
    )
    destination = source.with_suffix(".scan.json")
    content = (json.dumps(asdict(report), indent=2, sort_keys=True) + "\n").encode()
    fd, temporary = tempfile.mkstemp(dir=source.parent, prefix=".scan-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("metadata", type=Path)
    args = parser.parse_args(argv)
    report_path = scan_quarantined_source(args.source, args.metadata)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(f"security report: {report_path}")
    return 0 if report["verdict"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
