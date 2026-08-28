"""Validation for the frozen TinyCPU 1.x release contract."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

from tiny_cpu_logisim import JAVA_VERSION, LOGISIM_VERSION, MINIMUM_JAVA_FEATURE


RELEASE_CONTRACT = Path("hardware/logisim/tinycpu-release-v1.json")
SUPPORTED_SCHEMA = 1
PUBLIC_CLI_ENTRY_POINTS = [
    {
        "name": "circuit-inspector",
        "path": "src/tiny_cpu_circuit.py",
        "help_contains": "Check basic connectivity",
    },
    {
        "name": "logisim-acceptance",
        "path": "src/tiny_cpu_logisim.py",
        "help_contains": "pinned Logisim-evolution",
    },
    {
        "name": "simulator",
        "path": "src/tiny_cpu_cli.py",
        "help_contains": "Assemble and run TinyCPU programs",
    },
    {
        "name": "verifier",
        "path": "src/tiny_cpu_verify.py",
        "help_contains": "Verify a TinyCPU checkout",
    },
]


class ReleaseContractError(ValueError):
    """Raised when release metadata is incomplete or contradicts its sources."""


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ReleaseContractError(f"{label} must be an object")
    return value


def _load_json(path: Path, label: str) -> dict:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseContractError(f"could not read {label}: {error}") from error


def _repository_file(repository: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ReleaseContractError(
            f"{label} must be a repository-relative POSIX path"
        )
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != value:
        raise ReleaseContractError(f"unsafe {label}: {value!r}")
    path = repository.joinpath(*relative.parts)
    if not path.is_file():
        raise ReleaseContractError(f"{label} does not exist: {value}")
    return path


def validate_release_contract(
    repository: Path, *, check_cli_help: bool = True
) -> tuple[str, ...]:
    """Cross-check the versioned release contract against authoritative inputs."""

    repository = repository.resolve()
    contract = _load_json(repository / RELEASE_CONTRACT, "release contract")
    if contract.get("schema_version") != SUPPORTED_SCHEMA:
        raise ReleaseContractError("release contract must use schema version 1")
    if (
        contract.get("release_version") != "1.0.0"
        or contract.get("compatibility_series") != "1.x"
    ):
        raise ReleaseContractError(
            "release version and compatibility series must identify TinyCPU 1.0"
        )
    if contract.get("release_state") != "contract-frozen":
        raise ReleaseContractError("AP 13 must not describe a built or published release")

    hardware = _object(contract.get("hardware"), "hardware")
    profile = _load_json(
        _repository_file(repository, hardware.get("profile"), "hardware profile"),
        "hardware profile",
    )
    expected_hardware = {
        "profile": "hardware/logisim/tinycpu-16-12.json",
        "profile_schema_version": profile.get("schema_version"),
        "profile_name": profile.get("name"),
        "top_circuit": profile.get("top_circuit"),
    }
    if hardware != expected_hardware:
        raise ReleaseContractError(
            "release hardware metadata contradicts tinycpu-16-12.json"
        )

    machine_metadata = _object(contract.get("machine_format"), "machine_format")
    machine = _load_json(
        _repository_file(repository, machine_metadata.get("path"), "machine format"),
        "machine format",
    )
    expected_machine = {
        "path": "hardware/logisim/tinycpu-machine-v1.json",
        "schema_version": machine.get("schema_version"),
        "format": machine.get("format"),
        "word_bits": machine.get("word_bits"),
    }
    if machine_metadata != expected_machine:
        raise ReleaseContractError(
            "release machine metadata contradicts tinycpu-machine-v1.json"
        )

    runtime = _object(contract.get("runtime"), "runtime")
    if runtime != {
        "logisim_evolution": LOGISIM_VERSION,
        "java": JAVA_VERSION,
        "minimum_java_feature": MINIMUM_JAVA_FEATURE,
    }:
        raise ReleaseContractError(
            "release runtime metadata contradicts the pinned simulator constants"
        )

    acceptance = _object(contract.get("acceptance_report"), "acceptance_report")
    if acceptance != {
        "schema_version": 2,
        "status": "passed",
        "required_sections": ["reset_restart_runs", "matrix", "evidence"],
    }:
        raise ReleaseContractError(
            "release acceptance metadata does not identify the AP-12 schema"
        )

    entries = contract.get("public_cli_entry_points")
    if entries != PUBLIC_CLI_ENTRY_POINTS:
        raise ReleaseContractError(
            "public_cli_entry_points must contain the complete frozen CLI inventory"
        )
    names: list[str] = []
    for entry_value in entries:
        entry = _object(entry_value, "public CLI entry point")
        if set(entry) != {"name", "path", "help_contains"}:
            raise ReleaseContractError(
                "public CLI entries require name, path, and help_contains"
            )
        name, marker = entry.get("name"), entry.get("help_contains")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(marker, str)
            or not marker
        ):
            raise ReleaseContractError(
                "public CLI name and help marker must be non-empty strings"
            )
        script = _repository_file(repository, entry.get("path"), f"public CLI {name}")
        names.append(name)
        if check_cli_help:
            result = subprocess.run(
                [sys.executable, str(script), "--help"], cwd=repository,
                capture_output=True, text=True, check=False,
            )
            if result.returncode or marker not in result.stdout:
                raise ReleaseContractError(f"public CLI help contract failed for {name}")
    if names != sorted(set(names)):
        raise ReleaseContractError("public CLI names must be unique and sorted")
    return (
        "release metadata",
        "hardware profile",
        "machine format",
        "runtime versions",
        "acceptance schema",
        "public CLI help",
    )
