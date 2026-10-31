import hashlib
import json
from pathlib import Path

import pytest

import tiny_program_source_sandbox as sandbox
from tiny_program_source_sandbox import sandbox_supported, sandbox_test_port


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


@pytest.mark.skipif(not sandbox_supported(), reason="source-port execution requires Linux resource limits")
def test_runs_approved_port_and_records_passing_assessment(tmp_path: Path):
    program, port_report = approved_port(tmp_path, "print(7);\n")
    output, report_path = sandbox_test_port(program, port_report, tmp_path / "results")
    assessment = json.loads(report_path.read_text())
    assert output.read_text() == "7\n"
    assert assessment["verdict"] == "passed"
    assert assessment["exit_code"] == 0
    assert assessment["next_stage"] == "gui-wrapper"
    assert output.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(not sandbox_supported(), reason="source-port execution requires Linux resource limits")
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


def test_unsupported_platform_never_starts_child_or_writes_assessment(tmp_path: Path, monkeypatch):
    program, report = approved_port(tmp_path, "print(1);\n")
    monkeypatch.setattr(sandbox, "resource", None)
    def forbidden(*args, **kwargs):
        pytest.fail("unsupported sandbox must not start a child process")
    monkeypatch.setattr(sandbox.subprocess, "run", forbidden)
    with pytest.raises(sandbox.SandboxUnavailableError, match="requires Linux"):
        sandbox_test_port(program, report, tmp_path / "results")
    assert not (tmp_path / "results").exists()


def test_unsupported_cli_reports_actionable_error(tmp_path: Path, monkeypatch, capsys):
    program, report = approved_port(tmp_path, "print(1);\n")
    monkeypatch.setattr(sandbox, "resource", None)
    with pytest.raises(SystemExit) as exc:
        sandbox.main([str(program), str(report)])
    assert exc.value.code == 2
    assert "requires Linux" in capsys.readouterr().err
