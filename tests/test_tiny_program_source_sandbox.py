import hashlib
import json
from pathlib import Path

import pytest

from tiny_program_source_sandbox import sandbox_test_port


def approved_port(tmp_path: Path, source: str) -> tuple[Path, Path]:
    program = tmp_path / "approved.tiny"
    program.write_text(source)
    report = tmp_path / "approved.port.json"
    report.write_text(json.dumps({
        "policy": "tiny-source-port-v1",
        "status": "ported-unexecuted",
        "next_stage": "sandbox-test",
        "output_file": program.name,
        "output_sha256": hashlib.sha256(program.read_bytes()).hexdigest(),
    }))
    return program, report


def test_runs_approved_port_and_records_passing_assessment(tmp_path: Path):
    program, port_report = approved_port(tmp_path, "print(7);\n")
    output, report_path = sandbox_test_port(program, port_report, tmp_path / "results")
    assessment = json.loads(report_path.read_text())
    assert output.read_text() == "7\n"
    assert assessment["verdict"] == "passed"
    assert assessment["exit_code"] == 0
    assert assessment["next_stage"] == "gui-wrapper"
    assert output.stat().st_mode & 0o777 == 0o600


def test_records_runtime_failure_without_promoting_program(tmp_path: Path):
    program, port_report = approved_port(tmp_path, "print(missing_name);\n")
    _output, report_path = sandbox_test_port(program, port_report, tmp_path / "results")
    assessment = json.loads(report_path.read_text())
    assert assessment["verdict"] == "failed"
    assert assessment["exit_code"] != 0
    assert assessment["next_stage"] is None


def test_rejects_tampered_port_after_approval(tmp_path: Path):
    program, port_report = approved_port(tmp_path, "print(1);\n")
    program.write_text("print(2);\n")
    with pytest.raises(ValueError, match="does not approve this exact program"):
        sandbox_test_port(program, port_report, tmp_path / "results")
