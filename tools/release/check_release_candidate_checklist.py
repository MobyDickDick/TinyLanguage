#!/usr/bin/env python3
"""Execute and verify candidate checks, retaining source-bound evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE = ROOT / "artifacts/release-candidate"
CHECKS = {
    "docstrings": ["-m", "ruff", "check", "--select", "D", "src/language_server.py",
                   "src/language_server_cli.py", "src/tiny_language_cli.py",
                   "src/tiny_language_api.py", "src/tiny_errors.py"],
    "format-lint": ["tools/check_format_lint.py"],
    "lsp": ["-m", "pytest", "tests/detailtests/test_language_server.py",
            "tests/detailtests/test_language_server_cli.py",
            "tests/detailtests/test_tiny_language_server_cli_self_host.py"],
    "interpreter-contract": ["-m", "pytest", "tests/test_spec_conformance.py",
                             "tests/test_release_scope_contract.py",
                             "tests/detailtests/test_semantics_suite.py",
                             "tests/detailtests/test_stdlib_doc_examples.py"],
    "native-parity": ["-m", "pytest", "tests/test_parity_runner.py",
                      "tests/detailtests/test_native_backend_error_parity.py"],
    "regression": ["-m", "pytest", "--assert-no-heap-leaks", "-ra"],
    "unsigned-source": ["tools/release/build_release_artifacts.py",
                        "--output-dir", "dist/release-ci"],
}
TEST_CHECKS = {name for name, command in CHECKS.items() if command[:2] == ["-m", "pytest"]}


def sha256(path: Path) -> str:
    """Hash a retained log, result, or artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity(root: Path = ROOT) -> dict:
    """Identify HEAD and maintained working files, excluding generated evidence."""
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root,
    ).decode("utf-8").split("\0")
    digest = hashlib.sha256()
    for name in sorted(set(names)):
        if not name or name.split("/")[0] in {"artifacts", "build", "dist"}:
            continue
        path = root / name
        data = path.read_bytes() if path.is_file() else b"<missing>"
        digest.update(name.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root, text=True,
    )
    clean = all(line[3:].split("/")[0] in {"artifacts", "build", "dist"}
                for line in status.splitlines())
    return {"commit": commit, "files_sha256": digest.hexdigest(), "clean": clean}


def check_command(name: str, directory: Path) -> list[str]:
    """Use fixed commands so a successful unrelated command cannot satisfy a gate."""
    command = list(CHECKS[name])
    if name in TEST_CHECKS:
        result = directory / (name + ".xml")
        if result.is_relative_to(ROOT):
            result = result.relative_to(ROOT)
        command.append(f"--junitxml={result.as_posix()}")
    return command


def evidence_key(path: Path, directory: Path) -> str:
    """Keep retained report paths independent of the original CI workspace."""
    if path.is_relative_to(directory):
        return "evidence/" + path.relative_to(directory).as_posix()
    return "checkout/" + path.relative_to(ROOT).as_posix()


def run_check(name: str, directory: Path) -> int:
    """Record actual exit status, logs and result hashes, even for a failed check."""
    directory.mkdir(parents=True, exist_ok=True)
    before = source_identity()
    command = check_command(name, directory)
    log = directory / f"{name}.log"
    outputs = [log]
    if name in TEST_CHECKS:
        result_path = directory / f"{name}.xml"
        result_path.unlink(missing_ok=True)
        outputs.append(result_path)
    with log.open("wb") as handle:
        result = subprocess.run([sys.executable, *command], cwd=ROOT,
                                stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT)
    if name == "unsigned-source":
        artifact_dir = ROOT / "dist/release-ci"
        outputs.extend(artifact_dir / entry for entry in ("build-info.json", "SHA256SUMS"))
        if (artifact_dir / "build-info.json").is_file():
            metadata = json.loads((artifact_dir / "build-info.json").read_text(encoding="utf-8"))
            outputs.extend(artifact_dir / item["name"] for item in metadata["artifacts"])
    record = {
        "schema": 1, "check": name, "source": before,
        "source_unchanged": before == source_identity(),
        "command": command, "returncode": result.returncode,
        "environment": {"python": sys.version, "executable": sys.executable,
                        "platform": platform.platform()},
        "files": {evidence_key(path, directory): sha256(path) for path in outputs if path.is_file()},
    }
    (directory / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(log.read_text(encoding="utf-8", errors="replace"))
    return result.returncode if record["source_unchanged"] else 1


def test_summary(path: Path) -> dict:
    """Count actual test cases; failures and missing/empty results cannot pass."""
    cases = list(ET.parse(path).getroot().iter("testcase"))
    return {"tests": len(cases),
            "failures": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases)}


def validate(directory: Path, source: dict) -> tuple[list[str], dict]:
    """Verify results for this source; report optional regression skips separately."""
    errors = []
    summaries = {}
    for name in CHECKS:
        try:
            record = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
            if not isinstance(record, dict) or not isinstance(record.get("files"), dict):
                raise ValueError("malformed evidence record")
            if (record["schema"] != 1 or record["check"] != name or record["source"] != source
                    or record["source_unchanged"] is not True
                    or record["command"] != check_command(name, directory)
                    or type(record["returncode"]) is not int or record["returncode"] != 0):
                raise ValueError("failed check, changed source, or mismatched command/identity")
            required = [directory / f"{name}.log"]
            if name in TEST_CHECKS:
                required.append(directory / f"{name}.xml")
            if name == "unsigned-source":
                if not source["clean"]:
                    raise ValueError("source archive builds HEAD; commit candidate changes before qualification")
                artifact_dir = ROOT / "dist/release-ci"
                required.extend(artifact_dir / entry for entry in ("build-info.json", "SHA256SUMS"))
                metadata = json.loads((artifact_dir / "build-info.json").read_text(encoding="utf-8"))
                if metadata["git"]["commit"] != source["commit"]:
                    raise ValueError("source archive was built from another commit")
                if metadata["version"] != (ROOT / "VERSION").read_text().strip():
                    raise ValueError("artifact version differs from VERSION")
                if not metadata["artifacts"]:
                    raise ValueError("no artifacts built")
                for item in metadata["artifacts"]:
                    path = artifact_dir / item["name"]
                    if path.parent != artifact_dir or sha256(path) != item["sha256"]:
                        raise ValueError("artifact name or checksum mismatch")
                    required.append(path)
                expected_checksums = {item["name"]: item["sha256"] for item in metadata["artifacts"]}
                actual_checksums = {}
                for line in (artifact_dir / "SHA256SUMS").read_text().splitlines():
                    checksum, filename = line.split("  ", 1)
                    if filename in actual_checksums:
                        raise ValueError("duplicate checksum entry")
                    actual_checksums[filename] = checksum
                if actual_checksums != expected_checksums:
                    raise ValueError("SHA256SUMS differs from built artifact inventory")
            for path in required:
                if record["files"].get(evidence_key(path, directory)) != sha256(path):
                    raise ValueError(f"missing or modified evidence: {path.name}")
            if name in TEST_CHECKS:
                summary = test_summary(directory / f"{name}.xml")
                summaries[name] = summary
                if not summary["tests"] or summary["failures"] or summary["errors"]:
                    raise ValueError("empty or failing test report")
                if name != "regression" and summary["skipped"]:
                    raise ValueError("required contract/LSP/parity tests were skipped")
        except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
            errors.append(f"{name}: {exc}")
    return errors, summaries


def main(argv: list[str] | None = None) -> int:
    """Run a CI check or verify all retained candidate evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--run-check", choices=CHECKS)
    args = parser.parse_args(argv)
    directory = args.evidence_dir.resolve()
    if args.run_check:
        return run_check(args.run_check, directory)
    errors, summaries = validate(directory, source_identity())
    for name, summary in summaries.items():
        print(f"{name}: {summary}")
    for error in errors:
        print(error)
    if not errors:
        print("Candidate regression evidence verified. Delivery qualification (packages 1-3) remains separate.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
