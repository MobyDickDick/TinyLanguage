import hashlib
import json
from pathlib import Path

import pytest

from tiny_program_source_port import port_approved_source
from tiny_program_source_scan import scan_quarantined_source


def approved_source(tmp_path: Path, payload: bytes, suffix: str = ".py"):
    source = tmp_path / "item.quarantine"
    metadata = tmp_path / "item.json"
    url = f"https://raw.githubusercontent.com/o/r/main/demo{suffix}"
    source.write_bytes(payload)
    metadata.write_text(json.dumps({
        "source_url": url, "final_url": url, "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "fetched_at": "2026-08-22T00:00:00+00:00", "status": "unreviewed",
    }))
    return source, metadata, scan_quarantined_source(source, metadata)


def test_ports_approved_python_subset_and_records_unexecuted_handoff(tmp_path: Path):
    source, metadata, scan = approved_source(
        tmp_path, b"def add(a, b):\n    return a + b\n\nprint(add(2, 3))\n"
    )
    output, report_path = port_approved_source(source, metadata, scan, tmp_path / "published")
    assert output.read_text() == "fn add(a, b) {\n    return a + b;\n}\n\nprint(add(2, 3));\n"
    report = json.loads(report_path.read_text())
    assert report["status"] == "ported-unexecuted"
    assert report["next_stage"] == "sandbox-test"
    assert report["output_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert output.stat().st_mode & 0o777 == 0o600


def test_rejects_scan_report_for_different_bytes(tmp_path: Path):
    source, metadata, scan = approved_source(tmp_path, b"print(1)\n")
    report = json.loads(scan.read_text())
    report["source_sha256"] = "0" * 64
    scan.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="does not approve this exact source"):
        port_approved_source(source, metadata, scan, tmp_path / "published")
    assert not (tmp_path / "published").exists()


def test_rejects_python_outside_bounded_transpiler_subset(tmp_path: Path):
    source, metadata, scan = approved_source(tmp_path, b"import math\nprint(math.pi)\n")
    with pytest.raises(ValueError, match="outside the automatic-porting subset"):
        port_approved_source(source, metadata, scan, tmp_path / "published")


def test_copies_approved_tiny_without_running_it(tmp_path: Path):
    source, metadata, scan = approved_source(tmp_path, b"print(7);", ".tiny")
    output, report = port_approved_source(source, metadata, scan, tmp_path / "published")
    assert output.read_text() == "print(7);\n"
    assert json.loads(report.read_text())["language"] == "tiny"
