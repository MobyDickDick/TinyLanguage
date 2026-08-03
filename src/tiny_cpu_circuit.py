"""Inspect Logisim-evolution ``.circ`` files used by TinyCPU.

This module intentionally does not emulate Logisim's component library. It
provides a dependency-free netlist reader so an incomplete schematic can be
checked in CI before the authoritative Logisim simulator is invoked.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


class CircuitError(ValueError):
    """Raised when a Logisim project cannot be read."""


SUPPORTED_PROFILE_SCHEMA = 1


@dataclass(frozen=True)
class CircuitReport:
    name: str
    components: int
    wires: int
    unconnected: tuple[str, ...]

    @property
    def connected(self) -> bool:
        return self.wires > 0 and not self.unconnected


def _attributes(element: ET.Element) -> dict[str, str]:
    return {
        item.get("name", ""): item.get("val", "")
        for item in element.findall("a")
    }


def _read_project(path: str | Path) -> ET.Element:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise CircuitError(f"cannot read Logisim project {path}: {error}") from error
    if root.tag != "project":
        raise CircuitError(f"{path} is not a Logisim project")
    return root


def load_profile(path: str | Path) -> dict[str, Any]:
    """Load and minimally validate a versioned TinyCPU hardware profile."""

    try:
        profile = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CircuitError(f"cannot read hardware profile {path}: {error}") from error
    if not isinstance(profile, dict):
        raise CircuitError(f"hardware profile {path} must contain an object")
    if profile.get("schema_version") != SUPPORTED_PROFILE_SCHEMA:
        raise CircuitError(
            f"unsupported hardware profile schema {profile.get('schema_version')!r}"
        )
    for key in ("name", "top_circuit", "registers", "rams"):
        if key not in profile:
            raise CircuitError(f"hardware profile {path} is missing {key!r}")
    return profile


def validate_hardware_contract(
    project: str | Path, profile_path: str | Path
) -> tuple[str, ...]:
    """Return deviations between a Logisim project and a hardware profile."""

    root = _read_project(project)
    profile = load_profile(profile_path)
    circuits = {item.get("name", ""): item for item in root.findall("circuit")}
    violations: list[str] = []

    main = root.find("main")
    actual_top = main.get("name") if main is not None else None
    if actual_top != profile["top_circuit"]:
        violations.append(
            f"top circuit is {actual_top!r}, expected {profile['top_circuit']!r}"
        )

    def labelled_components(circuit_name: str, kind: str) -> dict[str, dict[str, str]]:
        circuit = circuits.get(circuit_name)
        if circuit is None:
            violations.append(f"missing circuit {circuit_name!r}")
            return {}
        return {
            attrs["label"]: attrs
            for component in circuit.findall("comp")
            if component.get("name") == kind
            and (attrs := _attributes(component)).get("label")
        }

    for circuit_name, expected in profile["registers"].items():
        actual = labelled_components(circuit_name, "Register")
        for label, width in expected.items():
            if label not in actual:
                violations.append(f"{circuit_name}: missing register {label}")
            elif int(actual[label].get("width", "1")) != width:
                violations.append(
                    f"{circuit_name}.{label}: width is "
                    f"{actual[label].get('width', '1')}, expected {width}"
                )

    for circuit_name, expected in profile["rams"].items():
        actual = labelled_components(circuit_name, "RAM")
        for label, dimensions in expected.items():
            if label not in actual:
                violations.append(f"{circuit_name}: missing RAM {label}")
                continue
            address_bits = int(actual[label].get("addrWidth", "0"))
            data_bits = int(actual[label].get("dataWidth", "0"))
            if address_bits != dimensions["address_bits"]:
                violations.append(
                    f"{circuit_name}.{label}: address width is {address_bits}, "
                    f"expected {dimensions['address_bits']}"
                )
            if data_bits != dimensions["data_bits"]:
                violations.append(
                    f"{circuit_name}.{label}: data width is {data_bits}, "
                    f"expected {dimensions['data_bits']}"
                )
    return tuple(violations)


def inspect_project(path: str | Path) -> tuple[CircuitReport, ...]:
    """Read *path* and return a connectivity report for every circuit.

    A component is considered connected when its anchor shares a wire endpoint.
    This conservative rule detects empty starter sheets; detailed pin geometry
    remains Logisim's job. Text annotations have no electrical terminals.
    """

    root = _read_project(path)

    reports: list[CircuitReport] = []
    for circuit in root.findall("circuit"):
        wires = circuit.findall("wire")
        endpoints = {
            point
            for wire in wires
            for point in (wire.get("from"), wire.get("to"))
            if point is not None
        }
        electrical = [
            component
            for component in circuit.findall("comp")
            if component.get("name") != "Text"
        ]
        unconnected = []
        for component in electrical:
            location = component.get("loc", "?")
            if location not in endpoints:
                attrs = _attributes(component)
                label = attrs.get("label") or component.get("name", "component")
                unconnected.append(f"{label}@{location}")
        reports.append(
            CircuitReport(
                circuit.get("name", "<unnamed>"),
                len(electrical),
                len(wires),
                tuple(unconnected),
            )
        )
    if not reports:
        raise CircuitError(f"{path} contains no circuits")
    return tuple(reports)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check basic connectivity of a Logisim-evolution project"
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--profile", type=Path, help="validate the project against this profile"
    )
    parser.add_argument(
        "--contract-only",
        action="store_true",
        help="check the profile contract without requiring complete wiring",
    )
    args = parser.parse_args(argv)
    if args.contract_only and args.profile is None:
        parser.error("--contract-only requires --profile")
    try:
        reports = inspect_project(args.project)
        violations = (
            validate_hardware_contract(args.project, args.profile)
            if args.profile is not None
            else ()
        )
    except CircuitError as error:
        parser.error(str(error))

    incomplete = False
    for report in reports:
        state = "connected" if report.connected else "INCOMPLETE"
        print(
            f"{report.name}: {state}; {report.components} components, "
            f"{report.wires} wires"
        )
        if report.unconnected:
            print("  unconnected: " + ", ".join(report.unconnected))
        incomplete |= not report.connected
    if args.profile is not None:
        if violations:
            print(f"contract {args.profile}: FAILED")
            for violation in violations:
                print(f"  {violation}")
        else:
            print(f"contract {args.profile}: valid")
    failed = bool(violations) or (incomplete and not args.contract_only)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
