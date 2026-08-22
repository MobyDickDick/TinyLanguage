import hashlib
import json
from pathlib import Path

import pytest

from tiny_program_source_scan import scan_quarantined_source


def quarantine_pair(tmp_path: Path, payload: bytes, url: str = "https://raw.githubusercontent.com/o/r/main/demo.py"):
    source = tmp_path / "item.quarantine"
    metadata = tmp_path / "item.json"
    source.write_bytes(payload)
    metadata.write_text(json.dumps({
        "source_url": url, "final_url": url, "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "fetched_at": "2026-08-22T00:00:00+00:00", "status": "unreviewed",
    }))
    return source, metadata


def test_safe_text_source_receives_porting_gate(tmp_path: Path):
    source, metadata = quarantine_pair(tmp_path, b"def add(a, b):\n    return a + b\n")
    report_path = scan_quarantined_source(source, metadata)
    report = json.loads(report_path.read_text())
    assert report["verdict"] == "passed"
    assert report["findings"] == []
    assert report["next_stage"] == "automatic-porting"
    assert report["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("payload, finding", [
    (b"#!/usr/bin/python\nprint(1)\n", "executable shebang"),
    (b"import subprocess\n", "external I/O API"),
    (b"value = eval(user_input)\n", "dynamic code execution"),
    (b"\x7fELFbinary", "ELF executable"),
])
def test_static_signatures_are_rejected(tmp_path: Path, payload: bytes, finding: str):
    source, metadata = quarantine_pair(tmp_path, payload)
    report = json.loads(scan_quarantined_source(source, metadata).read_text())
    assert report["verdict"] == "rejected"
    assert report["next_stage"] is None
    assert any(finding in item for item in report["findings"])


def test_non_allowlisted_source_type_is_rejected(tmp_path: Path):
    source, metadata = quarantine_pair(tmp_path, b"plain text\n", "https://rosettacode.org/wiki/Demo")
    report = json.loads(scan_quarantined_source(source, metadata).read_text())
    assert report["verdict"] == "rejected"
    assert "source type is not allowlisted: <none>" in report["findings"]


def test_tampered_quarantine_is_not_scanned(tmp_path: Path):
    source, metadata = quarantine_pair(tmp_path, b"print(1)\n")
    source.write_bytes(b"print(2)\n")
    with pytest.raises(ValueError, match="digest"):
        scan_quarantined_source(source, metadata)
    assert not (tmp_path / "item.scan.json").exists()


def test_symlinked_source_is_not_scanned(tmp_path: Path):
    target = tmp_path / "target"
    target.write_bytes(b"print(1)\n")
    source, metadata = quarantine_pair(tmp_path, target.read_bytes())
    source.unlink()
    source.symlink_to(target)
    with pytest.raises(ValueError, match="regular file"):
        scan_quarantined_source(source, metadata)
