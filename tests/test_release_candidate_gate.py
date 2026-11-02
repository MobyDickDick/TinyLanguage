"""Release evidence must reject stale, empty, skipped and tampered results."""

import json
from pathlib import Path

import pytest

from tools.release import check_release_candidate_checklist as gate


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    """Make a complete synthetic CI run to exercise the verifier's failure paths."""
    root = tmp_path / "checkout"
    root.mkdir()
    monkeypatch.setattr(gate, "ROOT", root)
    (root / "VERSION").write_text("1.0.0\n")
    directory = tmp_path / "evidence"
    directory.mkdir()
    source = {"commit": "a" * 40, "files_sha256": "b" * 64, "clean": True}
    artifact_dir = root / "dist/release-ci"
    artifact_dir.mkdir(parents=True)
    archive = artifact_dir / "TinyLanguage-v1.0.0.tar.gz"
    archive.write_bytes(b"source payload")
    metadata = artifact_dir / "build-info.json"
    metadata.write_text(json.dumps({"git": {"commit": source["commit"]}, "version": "1.0.0",
                                    "artifacts": [{"name": archive.name, "sha256": gate.sha256(archive)}]}))
    checksums = artifact_dir / "SHA256SUMS"
    checksums.write_text(f"{gate.sha256(archive)}  {archive.name}\n")
    for name in gate.CHECKS:
        log = directory / f"{name}.log"
        log.write_text("check output\n")
        files = [log]
        if name in gate.TEST_CHECKS:
            xml = directory / f"{name}.xml"
            xml.write_text('<testsuites><testsuite><testcase name="passed"/></testsuite></testsuites>')
            files.append(xml)
        if name == "unsigned-source":
            files.extend([metadata, checksums, archive])
        record = {"schema": 1, "check": name, "source": source, "source_unchanged": True,
                  "command": gate.check_command(name, directory), "returncode": 0,
                  "files": {gate.evidence_key(path, directory): gate.sha256(path) for path in files}}
        (directory / f"{name}.json").write_text(json.dumps(record))
    return directory, source


def edit_record(directory, name, **updates):
    """Change a recorded result independently of the verifier."""
    path = directory / f"{name}.json"
    record = json.loads(path.read_text())
    record.update(updates)
    path.write_text(json.dumps(record))


def test_complete_evidence_passes(evidence):
    """All required evidence for the same source satisfies the regression gate."""
    directory, source = evidence
    errors, summaries = gate.validate(directory, source)
    assert errors == []
    assert summaries["interpreter-contract"]["tests"] == 1


@pytest.mark.parametrize("mutation", ["missing", "stale", "failed", "command", "tampered", "changed"])
def test_invalid_evidence_fails(evidence, mutation):
    """A Markdown checkbox cannot compensate for missing or invalid evidence."""
    directory, source = evidence
    if mutation == "missing":
        (directory / "lsp.json").unlink()
    elif mutation == "stale":
        edit_record(directory, "lsp", source={**source, "commit": "c" * 40})
    elif mutation == "failed":
        edit_record(directory, "lsp", returncode=1)
    elif mutation == "command":
        edit_record(directory, "lsp", command=["-c", "pass"])
    elif mutation == "tampered":
        (directory / "lsp.log").write_text("altered")
    else:
        edit_record(directory, "lsp", source_unchanged=False)
    errors, _ = gate.validate(directory, source)
    assert len(errors) == 1 and errors[0].startswith("lsp:")


@pytest.mark.parametrize("content", ["<testsuites/>", '<testsuite><testcase><skipped/></testcase></testsuite>',
                                     '<testsuite><testcase><failure/></testcase></testsuite>', "broken XML"])
def test_nonpassing_contract_report_fails_even_with_zero_exit(evidence, content):
    """Required semantics cannot pass with zero collected tests or skipped tests."""
    directory, source = evidence
    xml = directory / "interpreter-contract.xml"
    xml.write_text(content)
    path = directory / "interpreter-contract.json"
    record = json.loads(path.read_text())
    record["files"][gate.evidence_key(xml, directory)] = gate.sha256(xml)
    path.write_text(json.dumps(record))
    errors, _ = gate.validate(directory, source)
    assert len(errors) == 1 and errors[0].startswith("interpreter-contract:")


def test_dirty_candidate_cannot_qualify_head_archive(evidence):
    """A source archive excludes uncommitted runtime changes and cannot qualify them."""
    directory, original = evidence
    source = {**original, "clean": False}
    for name in gate.CHECKS:
        edit_record(directory, name, source=source)
    errors, _ = gate.validate(directory, source)
    assert len(errors) == 1 and "commit candidate changes" in errors[0]


def test_artifact_payload_is_verified(evidence):
    """A successful build log alone cannot hide a changed artifact."""
    directory, source = evidence
    (gate.ROOT / "dist/release-ci/TinyLanguage-v1.0.0.tar.gz").write_bytes(b"tampered")
    errors, _ = gate.validate(directory, source)
    assert len(errors) == 1 and "checksum mismatch" in errors[0]


@pytest.mark.parametrize("exit_code", [0, 7])
def test_recorder_retains_actual_process_result(tmp_path, monkeypatch, exit_code):
    """Execute a real child, with valid stdin and both output streams retained."""
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "CHECKS", {"probe": ["-c", (
        "import sys; assert sys.stdin.read() == ''; print('stdout'); "
        f"print('stderr', file=sys.stderr); sys.exit({exit_code})"
    )]})
    source = {"commit": "a" * 40, "files_sha256": "b" * 64, "clean": True}
    monkeypatch.setattr(gate, "source_identity", lambda: source)
    directory = tmp_path / "evidence"
    assert gate.run_check("probe", directory) == exit_code
    record = json.loads((directory / "probe.json").read_text())
    assert record["returncode"] == exit_code
    assert record["source_unchanged"] is True
    assert "stdout" in (directory / "probe.log").read_text()
    assert "stderr" in (directory / "probe.log").read_text()
    errors, _ = gate.validate(directory, source)
    assert bool(errors) == bool(exit_code)


def test_stale_junit_is_removed_before_failed_execution(tmp_path, monkeypatch):
    """An earlier successful report cannot survive a failed collection/run."""
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setitem(gate.CHECKS, "lsp", ["-c", "import sys; sys.exit(2)"])
    monkeypatch.setattr(gate, "source_identity", lambda: {"commit": "current"})
    directory = tmp_path / "evidence"
    directory.mkdir()
    (directory / "lsp.xml").write_text("old successful report")
    assert gate.run_check("lsp", directory) == 2
    assert not (directory / "lsp.xml").exists()


def test_changed_working_files_invalidate_source_identity(tmp_path, monkeypatch):
    """A changed file with the same HEAD must invalidate earlier passing evidence."""
    monkeypatch.setattr(gate.subprocess, "check_output", lambda command, **kwargs:
                        b"program.py\0artifacts/report.json\0" if "ls-files" in command
                        else "head\n" if "rev-parse" in command else "")
    program = tmp_path / "program.py"
    program.write_text("first")
    first = gate.source_identity(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "report.json").write_text("generated")
    assert gate.source_identity(tmp_path) == first
    program.write_text("second")
    assert gate.source_identity(tmp_path) != first
