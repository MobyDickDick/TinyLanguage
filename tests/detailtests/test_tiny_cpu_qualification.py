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
    evidence_files = {
        "reset-start.tsv": b"raw electrical evidence\n",
        "reset-start.normalized.tsv": b"edge\tvalue\n1\t3\n",
        "restart.tsv": b"raw electrical evidence\n",
        "restart.normalized.tsv": b"edge\tvalue\n1\t3\n",
        "isa-matrix/halt.tsv": b"matrix evidence\n",
    }
    for name, contents in evidence_files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    normalized_digest = hashlib.sha256(
        evidence_files["reset-start.normalized.tsv"]
    ).hexdigest()
    (path / "acceptance.json").write_text(json.dumps({
        "schema_version": 2,
        "status": "passed",
        "logisim_version": "4.1.0",
        "java_version": "21+",
        "reset_restart_runs": [
            {
                "name": name,
                "raw_table": f"{name}.tsv",
                "normalized_table": f"{name}.normalized.tsv",
                "sha256": normalized_digest,
                "clock_edges": 1,
            }
            for name in ("reset-start", "restart")
        ],
        "matrix": {"fixture_count": 1, "directory": "isa-matrix"},
        "evidence": [
            {
                "path": name,
                "size_bytes": len(evidence_files[name]),
                "sha256": hashlib.sha256(evidence_files[name]).hexdigest(),
            }
            for name in sorted(evidence_files)
        ],
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
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        check=True, capture_output=True,
    ).stdout.strip()
    published = qualification.qualify(
        ROOT, _acceptance(tmp_path / "acceptance"), tmp_path / "release",
        commit, private,
    )
    qualification.verify(published, public)
    report = json.loads((published / qualification.REPORT).read_text(encoding="utf-8"))
    assert report["commit"] == commit
    assert set(report["checks"].values()) == {"passed"}
    for artifact in report["artifacts"]:
        candidate = tmp_path / "release" / "candidate" / artifact["name"]
        assert candidate.read_bytes() == (published / artifact["name"]).read_bytes()


def test_publication_verifier_rejects_changed_archive(tmp_path):
    private, public = _keys(tmp_path)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        check=True, capture_output=True,
    ).stdout.strip()
    published = qualification.qualify(
        ROOT, _acceptance(tmp_path / "acceptance"), tmp_path / "release",
        commit, private,
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


def test_qualification_rejects_commit_other_than_checkout_head(tmp_path):
    private, _ = _keys(tmp_path)
    with pytest.raises(qualification.QualificationError, match="not checkout HEAD"):
        qualification.qualify(
            ROOT, _acceptance(tmp_path / "acceptance"), tmp_path / "release",
            "a" * 40, private,
        )


def test_publication_verifier_rejects_unsigned_qualification_report(tmp_path):
    private, public = _keys(tmp_path)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
        check=True, capture_output=True,
    ).stdout.strip()
    published = qualification.qualify(
        ROOT, _acceptance(tmp_path / "acceptance"), tmp_path / "release",
        commit, private,
    )
    report_path = published / qualification.REPORT
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["commit"] = "b" * 40
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(qualification.QualificationError, match="signed checksums"):
        qualification.verify(published, public)
