"""Acceptance tests for the reproducible TinyCPU AP-14 distribution."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tiny_cpu_distribution", ROOT / "tools" / "tiny_cpu_distribution.py"
)
distribution = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(distribution)


def _acceptance(path: Path) -> Path:
    path.mkdir()
    trace = b"edge\tvalue\n1\t0\n"
    (path / "trace.tsv").write_bytes(trace)
    report = {
        "schema_version": 2,
        "status": "passed",
        "reset_restart_runs": [{"name": "reset-start"}, {"name": "restart"}],
        "matrix": {"fixture_count": 1, "directory": "isa-matrix"},
        "evidence": [{
            "path": "trace.tsv", "size_bytes": len(trace),
            "sha256": hashlib.sha256(trace).hexdigest(),
        }],
    }
    (path / "acceptance.json").write_text(json.dumps(report), encoding="utf-8")
    return path


def _extract(archive: Path, target: Path) -> Path:
    with tarfile.open(archive) as handle:
        handle.extractall(target, filter="data")
    return next(target.iterdir())


def test_two_builds_are_byte_identical_and_verify_outside_checkout(tmp_path):
    acceptance = _acceptance(tmp_path / "acceptance")
    first = distribution.build(ROOT, tmp_path / "first", acceptance)
    second = distribution.build(ROOT, tmp_path / "second", acceptance)
    assert [path.read_bytes() for path in first] == [path.read_bytes() for path in second]

    extracted_source = _extract(first[0], tmp_path / "extracted-source")
    distribution.verify_directory(extracted_source)
    extracted = _extract(first[1], tmp_path / "extracted-bundle")
    distribution.verify_directory(extracted)
    assert (extracted / "verify.py").is_file()


@pytest.mark.parametrize("mutation", ["missing", "extra", "digest", "symlink"])
def test_verifier_rejects_invalid_payloads(tmp_path, mutation):
    archive = distribution.build(
        ROOT, tmp_path / "dist", _acceptance(tmp_path / "acceptance")
    )[1]
    extracted = _extract(archive, tmp_path / "extracted")
    circuit = extracted / "hardware/logisim/TinyCPU.circ"
    if mutation == "missing":
        circuit.unlink()
    elif mutation == "extra":
        (extracted / "undeclared.txt").write_text("extra", encoding="utf-8")
    elif mutation == "digest":
        circuit.write_bytes(circuit.read_bytes() + b"changed")
    else:
        circuit.unlink()
        circuit.symlink_to(extracted / "LICENSE-TinyCPU.md")
    with pytest.raises(distribution.DistributionError):
        distribution.verify_directory(extracted)


def test_build_rejects_unpassed_acceptance_report(tmp_path):
    acceptance = _acceptance(tmp_path / "acceptance")
    report_path = acceptance / "acceptance.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["status"] = "failed"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(distribution.DistributionError, match="not a passed"):
        distribution.build(ROOT, tmp_path / "dist", acceptance)
