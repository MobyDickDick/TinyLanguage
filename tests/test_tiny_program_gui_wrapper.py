import hashlib
import json
from pathlib import Path

import pytest

from tiny_program_gui_wrapper import generate_gui_wrapper


def approved_result(tmp_path: Path) -> tuple[Path, Path, Path]:
    program = tmp_path / "approved.tiny"
    program.write_text("print(7);\n")
    output = tmp_path / "approved.sandbox.out"
    output.write_bytes(b"7\n")
    report = tmp_path / "approved.sandbox.json"
    report.write_text(json.dumps({
        "policy": "tiny-source-sandbox-v1",
        "source_file": program.name,
        "source_sha256": hashlib.sha256(program.read_bytes()).hexdigest(),
        "verdict": "passed",
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "output_bytes": len(output.read_bytes()),
        "next_stage": "gui-wrapper",
    }))
    return program, report, output


def test_generates_read_only_wrapper_and_audit_report(tmp_path: Path):
    program, sandbox_report, output = approved_result(tmp_path)
    wrapper, report_path = generate_gui_wrapper(
        program, sandbox_report, output, tmp_path / "gui"
    )
    compile(wrapper.read_bytes(), str(wrapper), "exec")
    wrapper_text = wrapper.read_text()
    report = json.loads(report_path.read_text())
    assert "OUTPUT = base64.b64decode" in wrapper_text
    assert "subprocess" not in wrapper_text
    assert report["status"] == "generated-read-only"
    assert report["wrapper_sha256"] == hashlib.sha256(wrapper.read_bytes()).hexdigest()
    assert wrapper.stat().st_mode & 0o777 == 0o700


def test_rejects_failed_sandbox_assessment(tmp_path: Path):
    program, sandbox_report, output = approved_result(tmp_path)
    report = json.loads(sandbox_report.read_text())
    report["verdict"] = "failed"
    sandbox_report.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="does not approve"):
        generate_gui_wrapper(program, sandbox_report, output, tmp_path / "gui")


def test_rejects_output_tampering_after_sandbox_run(tmp_path: Path):
    program, sandbox_report, output = approved_result(tmp_path)
    output.write_text("substituted\n")
    with pytest.raises(ValueError, match="does not approve"):
        generate_gui_wrapper(program, sandbox_report, output, tmp_path / "gui")
