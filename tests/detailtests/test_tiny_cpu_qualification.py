"""Acceptance coverage for the AP-15 qualification and publication gate."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tiny_cpu_qualification", ROOT / "tools" / "tiny_cpu_qualification.py"
)
qualification = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(qualification)


def _acceptance(path: Path) -> Path:
    path.mkdir()
    evidence = b"electrical evidence\n"
    (path / "trace.tsv").write_bytes(evidence)
    (path / "acceptance.json").write_text(json.dumps({
        "schema_version": 2,
        "status": "passed",
        "reset_restart_runs": [{"name": "reset-start"}, {"name": "restart"}],
        "matrix": {"fixture_count": 1, "directory": "isa-matrix"},
        "evidence": [{
            "path": "trace.tsv",
            "size_bytes": len(evidence),
            "sha256": hashlib.sha256(evidence).hexdigest(),
        }],
    }), encoding="utf-8")
    return path


def _keys(path: Path) -> tuple[Path, Path]:
    private = path / "private.pem"
    public = path / "public.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", private], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", private, "-pubout", "-out", public], check=True, capture_output=True)
    return private, public


def test_qualification_stages_signed_unchanged_candidate(tmp_path):
    private, public = _keys(tmp_path)
    published = qualification.qualify(
        ROOT, _acceptance(tmp_path / "acceptance"), tmp_path / "release",
        "a" * 40, private,
    )
    qualification.verify(published, public)
    report = json.loads((published / qualification.REPORT).read_text(encoding="utf-8"))
    assert report["commit"] == "a" * 40
    assert set(report["checks"].values()) == {"passed"}
    for artifact in report["artifacts"]:
        candidate = tmp_path / "release" / "candidate" / artifact["name"]
        assert candidate.read_bytes() == (published / artifact["name"]).read_bytes()


def test_publication_verifier_rejects_changed_archive(tmp_path):
    private, public = _keys(tmp_path)
    published = qualification.qualify(
        ROOT, _acceptance(tmp_path / "acceptance"), tmp_path / "release",
        "b" * 40, private,
    )
    archive = published / "TinyCPU-1.0.0-source.tar.gz"
    archive.write_bytes(archive.read_bytes() + b"changed")
    with pytest.raises(qualification.QualificationError, match="digest mismatch"):
        qualification.verify(published, public)


def test_qualification_requires_full_commit_id(tmp_path):
    private, _ = _keys(tmp_path)
    with pytest.raises(qualification.QualificationError, match="full lowercase"):
        qualification.qualify(
            ROOT, _acceptance(tmp_path / "acceptance"), tmp_path / "release",
            "deadbeef", private,
        )
