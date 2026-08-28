#!/usr/bin/env python3
"""Qualify, sign, and verify the immutable TinyCPU 1.0 release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import stat


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import tiny_cpu_distribution as distribution  # noqa: E402
from tiny_cpu_logisim import verify_acceptance_bundle  # noqa: E402
from tiny_cpu_verify import verify_checkout  # noqa: E402

TAG = "tinycpu-v1.0.0"
CHECKSUMS = "SHA256SUMS"
SIGNATURE = "SHA256SUMS.sig"
REPORT = "tinycpu-v1.0.0-qualification.json"


class QualificationError(ValueError):
    """Raised when a candidate cannot satisfy the AP-15 publication gate."""


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode:
        raise QualificationError(
            f"command failed ({' '.join(command)}): {result.stderr.strip()}"
        )
    return result


def _sha256(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise QualificationError(f"missing publication file: {path.name}") from exc
    if not stat.S_ISREG(mode):
        raise QualificationError(f"publication path is not a regular file: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract(archive: Path, target: Path) -> Path:
    with tarfile.open(archive, "r:gz") as handle:
        handle.extractall(target, filter="data")
    children = list(target.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise QualificationError(f"archive has no single release root: {archive.name}")
    return children[0]


def qualify(repository: Path, acceptance: Path, output: Path, commit: str, signing_key: Path) -> Path:
    """Build once, verify outside the checkout, smoke test, sign, and stage unchanged bytes."""
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise QualificationError("commit must be a full lowercase Git object id")
    actual_commit = _run(["git", "rev-parse", "HEAD"], cwd=repository).stdout.strip()
    if actual_commit != commit:
        raise QualificationError(
            f"requested commit {commit} is not checkout HEAD {actual_commit}"
        )
    # AP-15 consumes the complete AP-12 contract.  The distribution builder's
    # lightweight nested-inventory check is deliberately not a substitute for
    # either the checkout verifier or the strict AP-12 metadata verifier.
    verify_checkout(repository)
    verify_acceptance_bundle(acceptance)
    output.mkdir(parents=True, exist_ok=False)
    candidate = output / "candidate"
    published = output / "published"
    candidate.mkdir()
    published.mkdir()
    artifacts = distribution.build(repository, candidate, acceptance)

    with tempfile.TemporaryDirectory(prefix="tinycpu-clean-room-") as temporary:
        clean_room = Path(temporary)
        roots = [_extract(archive, clean_room / archive.stem) for archive in artifacts]
        for root in roots:
            distribution.verify_directory(root)
        bundle = roots[1]
        smoke = _run(
            [sys.executable, "src/tiny_cpu_cli.py", "hardware/logisim/ap5_countdown.tcpu"],
            cwd=bundle,
        )
        if smoke.stdout != "3\n2\n1\n" or smoke.stderr:
            raise QualificationError("clean-room countdown output did not equal 3, 2, 1")

    artifact_rows = []
    for artifact in artifacts:
        digest = _sha256(artifact)
        artifact_rows.append({"name": artifact.name, "sha256": digest, "size_bytes": artifact.stat().st_size})
        shutil.copyfile(artifact, published / artifact.name)
        if (published / artifact.name).read_bytes() != artifact.read_bytes():
            raise QualificationError(f"published bytes changed: {artifact.name}")
    report = {
        "schema_version": 1,
        "release_version": distribution.RELEASE,
        "tag": TAG,
        "commit": commit,
        "status": "passed",
        "artifacts": artifact_rows,
        "checks": {
            "ap12_electrical_gate": "passed",
            "offline_inventory": "passed",
            "clean_room_countdown": "passed",
            "published_bytes_unchanged": "passed",
            "authenticated_checksums": "passed",
        },
    }
    (published / REPORT).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    signed_rows = artifact_rows + [{
        "name": REPORT,
        "sha256": _sha256(published / REPORT),
        "size_bytes": (published / REPORT).stat().st_size,
    }]
    checksums = "".join(f"{row['sha256']}  {row['name']}\n" for row in signed_rows)
    (published / CHECKSUMS).write_text(checksums, encoding="ascii")
    _run([
        "openssl", "dgst", "-sha256", "-sign", str(signing_key),
        "-out", str(published / SIGNATURE), str(published / CHECKSUMS),
    ])
    return published


def verify(directory: Path, public_key: Path) -> None:
    """Verify a published AP-15 directory, including signature and exact artifact bytes."""
    _run([
        "openssl", "dgst", "-sha256", "-verify", str(public_key),
        "-signature", str(directory / SIGNATURE), str(directory / CHECKSUMS),
    ])
    report = json.loads((directory / REPORT).read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise QualificationError("publication qualification report must be an object")
    if report.get("status") != "passed" or report.get("tag") != TAG:
        raise QualificationError("publication has no passed AP-15 report")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list) or any(
        not isinstance(row, dict)
        or not isinstance(row.get("name"), str)
        or not isinstance(row.get("sha256"), str)
        for row in artifacts
    ):
        raise QualificationError("publication has an invalid artifact inventory")
    expected = {row["name"]: row["sha256"] for row in artifacts}
    if len(expected) != len(artifacts):
        raise QualificationError("publication artifact names must be unique")
    expected[REPORT] = _sha256(directory / REPORT)
    lines = (directory / CHECKSUMS).read_text(encoding="ascii").splitlines()
    pairs = [line.split("  ", 1) for line in lines]
    if any(len(pair) != 2 or not pair[0] or not pair[1] for pair in pairs):
        raise QualificationError("signed checksum file is malformed")
    recorded = {name: digest for digest, name in pairs}
    if len(recorded) != len(pairs):
        raise QualificationError("signed checksum paths must be unique")
    if recorded != expected:
        raise QualificationError("signed checksums differ from qualification report")
    allowed = set(expected) | {CHECKSUMS, SIGNATURE}
    actual = {path.name for path in directory.iterdir()}
    if actual != allowed:
        raise QualificationError("publication contains missing or additional files")
    for name, digest in expected.items():
        if _sha256(directory / name) != digest:
            raise QualificationError(f"published artifact digest mismatch: {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    qualify_parser = commands.add_parser("qualify")
    qualify_parser.add_argument("--repository", type=Path, default=ROOT)
    qualify_parser.add_argument("--acceptance", type=Path, required=True)
    qualify_parser.add_argument("--output-dir", type=Path, required=True)
    qualify_parser.add_argument("--commit", required=True)
    qualify_parser.add_argument("--signing-key", type=Path, required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("directory", type=Path)
    verify_parser.add_argument("--public-key", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "qualify":
            print(qualify(args.repository.resolve(), args.acceptance.resolve(), args.output_dir.resolve(), args.commit, args.signing_key.resolve()))
        else:
            verify(args.directory.resolve(), args.public_key.resolve())
            print("TinyCPU 1.0 publication verification passed")
    except (OSError, json.JSONDecodeError, QualificationError, distribution.DistributionError) as exc:
        print(f"TinyCPU qualification FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
