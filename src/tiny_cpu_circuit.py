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
import re
from typing import Any
import xml.etree.ElementTree as ET


class CircuitError(ValueError):
    """Raised when a Logisim project cannot be read."""


SUPPORTED_PROFILE_SCHEMA = 1
SUBCIRCUIT_ANCHOR_CLEARANCE = 600


@dataclass(frozen=True)
class CircuitReport:
    name: str
    components: int
    wires: int
    unconnected: tuple[str, ...]
    placement_conflicts: tuple[str, ...] = ()
    routing_conflicts: tuple[str, ...] = ()
    width_conflicts: tuple[str, ...] = ()

    @property
    def connected(self) -> bool:
        return (
            self.wires > 0
            and not self.unconnected
            and not self.placement_conflicts
            and not self.routing_conflicts
            and not self.width_conflicts
        )


def _wire_overlap(first: ET.Element, second: ET.Element) -> bool:
    """Return whether two collinear wires overlap for a non-zero distance."""

    first_from = _location(first.get("from", ""))
    first_to = _location(first.get("to", ""))
    second_from = _location(second.get("from", ""))
    second_to = _location(second.get("to", ""))
    if first_from[1] == first_to[1] == second_from[1] == second_to[1]:
        first_span = sorted((first_from[0], first_to[0]))
        second_span = sorted((second_from[0], second_to[0]))
    elif first_from[0] == first_to[0] == second_from[0] == second_to[0]:
        first_span = sorted((first_from[1], first_to[1]))
        second_span = sorted((second_from[1], second_to[1]))
    else:
        return False
    return max(first_span[0], second_span[0]) < min(first_span[1], second_span[1])



def _point_on_wire(point: str, wire: ET.Element) -> bool:
    """Return whether *point* lies on a horizontal or vertical wire segment."""

    px, py = _location(point)
    start = _location(wire.get("from", ""))
    end = _location(wire.get("to", ""))
    if start[0] == end[0] == px:
        low, high = sorted((start[1], end[1]))
        return low <= py <= high
    if start[1] == end[1] == py:
        low, high = sorted((start[0], end[0]))
        return low <= px <= high
    return False


def _component_terminals(component: ET.Element) -> set[str]:
    """Return conservative Logisim-evolution terminal coordinates."""

    location = component.get("loc", "?")
    terminals = {location}
    x, y = _location(location)
    attrs = _attributes(component)
    if attrs.get("appearance") != "logisim_evolution":
        return terminals
    if component.get("name") == "Register":
        terminals.update({
            f"({x},{y + 30})",       # D
            f"({x + 60},{y + 30})",  # Q
            f"({x},{y + 50})",       # WE
            f"({x},{y + 70})",       # clock
            f"({x + 30},{y + 90})",  # reset
        })
    elif component.get("name") in {"RAM", "ROM"}:
        terminals.update({
            f"({x},{y + 10})",
            f"({x},{y + 50})",
            f"({x},{y + 60})",
            f"({x},{y + 70})",
            f"({x},{y + 100})",
            f"({x + 240},{y + 100})",
        })
    return terminals

def _location(value: str) -> tuple[int, int]:
    """Return the integer coordinates used by Logisim's ``loc`` attribute."""

    try:
        x, y = value.strip("()").split(",")
        return int(x), int(y)
    except (AttributeError, TypeError, ValueError) as error:
        raise CircuitError(f"invalid Logisim component location {value!r}") from error


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

    for circuit_name, expected in profile.get("datapaths", {}).items():
        circuit = circuits.get(circuit_name)
        if circuit is None:
            violations.append(f"missing circuit {circuit_name!r}")
            continue
        by_label = {
            attrs["label"]: (component.get("name", ""), attrs)
            for component in circuit.findall("comp")
            if (attrs := _attributes(component)).get("label")
        }
        for label, spec in expected.get("components", {}).items():
            if label not in by_label:
                violations.append(f"{circuit_name}: missing component {label}")
                continue
            kind, attrs = by_label[label]
            if kind != spec["kind"]:
                violations.append(
                    f"{circuit_name}.{label}: kind is {kind}, expected {spec['kind']}"
                )
            if int(attrs.get("width", "1")) != spec["width"]:
                violations.append(
                    f"{circuit_name}.{label}: width is {attrs.get('width', '1')}, "
                    f"expected {spec['width']}"
                )
        pins = labelled_components(circuit_name, "Pin")
        for label, width in expected.get("pins", {}).items():
            if label not in pins:
                violations.append(f"{circuit_name}: missing pin {label}")
            elif int(pins[label].get("width", "1")) != width:
                violations.append(
                    f"{circuit_name}.{label}: width is "
                    f"{pins[label].get('width', '1')}, expected {width}"
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

    for circuit_name, expected in profile.get("roms", {}).items():
        actual = labelled_components(circuit_name, "ROM")
        for label, dimensions in expected.items():
            if label not in actual:
                violations.append(f"{circuit_name}: missing ROM {label}")
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
    Registers using Logisim-evolution's appearance are the exception: their
    location is the symbol's top-left corner, so their five electrical
    terminals are derived from that location.  This conservative rule detects
    empty starter sheets without mistaking the register's drawing origin for a
    pin. Text annotations have no electrical terminals.
    """

    root = _read_project(path)
    circuit_names = {
        circuit.get("name", "") for circuit in root.findall("circuit")
    }

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
            terminals = _component_terminals(component)
            connected = bool(terminals & endpoints) or any(
                _point_on_wire(terminal, wire)
                for terminal in terminals
                for wire in wires
            )
            if not connected:
                attrs = _attributes(component)
                label = attrs.get("label") or component.get("name", "component")
                unconnected.append(f"{label}@{location}")
        placement_conflicts: list[str] = []
        routing_conflicts: list[str] = []
        for wire in wires:
            start = _location(wire.get("from", ""))
            end = _location(wire.get("to", ""))
            if start[0] != end[0] and start[1] != end[1]:
                routing_conflicts.append(
                    f"{wire.get('from')}->{wire.get('to')} is diagonal; "
                    "Logisim wires must be horizontal or vertical"
                )
        for index, first in enumerate(wires):
            for second in wires[index + 1:]:
                if _wire_overlap(first, second):
                    routing_conflicts.append(
                        f"{first.get('from')}->{first.get('to')} overlaps "
                        f"{second.get('from')}->{second.get('to')}"
                    )
        instances = [
            component
            for component in electrical
            if component.get("name", "") in circuit_names
        ]
        for index, first in enumerate(instances):
            first_location = _location(first.get("loc", ""))
            for second in instances[index + 1:]:
                second_location = _location(second.get("loc", ""))
                horizontal = abs(first_location[0] - second_location[0])
                vertical = abs(first_location[1] - second_location[1])
                # Large subcircuits have a symbol derived from all their pins.
                # Reserve a full routing lane in either axis so those symbols
                # and their terminals can never be superimposed accidentally.
                if (
                    horizontal < SUBCIRCUIT_ANCHOR_CLEARANCE
                    and vertical < SUBCIRCUIT_ANCHOR_CLEARANCE
                ):
                    placement_conflicts.append(
                        f"{first.get('name')}@{first.get('loc')} overlaps the "
                        f"reserved lane of {second.get('name')}@{second.get('loc')}"
                    )
        reports.append(
            CircuitReport(
                circuit.get("name", "<unnamed>"),
                len(electrical),
                len(wires),
                tuple(unconnected),
                tuple(placement_conflicts),
                tuple(routing_conflicts),
                (),
            )
        )
    if not reports:
        raise CircuitError(f"{path} contains no circuits")
    return tuple(reports)



def _serialize_standalone_logisim_project(data: bytes) -> bytes:
    """Normalize extracted Logisim leaf projects for checked-in diagnostics."""

    declaration = (
        rb"^<\?xml\s+version=(['\"])1\.0\1\s+"
        rb"encoding=(['\"])(?:utf-8|UTF-8)\2"
        rb"(?:\s+standalone=(['\"])(?:yes|no)\3)?\s*\?>"
    )
    data = re.sub(
        declaration,
        b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        data,
        count=1,
    )
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return data.replace(b"\n", b"\r\n")


def split_leaf_circuits(
    project: str | Path, output_directory: str | Path
) -> tuple[Path, ...]:
    """Write independently loadable leaf circuits to *output_directory*.

    Logisim keeps every sheet of an opened project available to its simulator.
    Standalone leaf projects make it possible to isolate excessive CPU or
    memory use without loading the complete CPU. Sheets which instantiate
    another project circuit are skipped because they would contain unresolved
    components after extraction.
    """

    project_path = Path(project)
    source = project_path.read_bytes()
    root = _read_project(project_path)
    circuits = {
        circuit.get("name", ""): circuit for circuit in root.findall("circuit")
    }
    leaf_names = [
        name
        for name, circuit in circuits.items()
        if name
        and not any(
            component.get("name") in circuits for component in circuit.findall("comp")
        )
    ]
    if not leaf_names:
        raise CircuitError(
            f"{project_path} contains no independently loadable leaf circuits"
        )

    circuit_pattern = re.compile(
        rb"<circuit\b[^>]*\bname=(?P<quote>['\"])(?P<name>.*?)"
        rb"(?P=quote)[^>]*>.*?</circuit>",
        re.DOTALL,
    )
    circuit_matches = list(circuit_pattern.finditer(source))
    source_names = {
        match.group("name").decode("utf-8", errors="surrogateescape")
        for match in circuit_matches
    }
    if source_names != set(circuits):
        raise CircuitError(f"cannot locate every circuit byte range in {project_path}")

    main_pattern = re.compile(
        rb"(?P<prefix><main\b[^>]*\bname=)(?P<quote>['\"])(?P<name>.*?)"
        rb"(?P=quote)",
        re.DOTALL,
    )
    if main_pattern.search(source) is None:
        raise CircuitError(f"{project_path} has no main circuit declaration")

    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    prefix = project_path.stem
    written: list[Path] = []
    for name in leaf_names:
        encoded_name = name.encode("utf-8", errors="surrogateescape")
        standalone = bytearray(source)
        # Delete from the end so the original byte offsets remain valid.  The
        # selected circuit itself is never parsed and re-serialized: attribute
        # order, whitespace, coordinates, and line endings stay byte-exact.
        for match in reversed(circuit_matches):
            if match.group("name") != encoded_name:
                start = source.rfind(b"\n", 0, match.start()) + 1
                if source[start : match.start()].strip():
                    start = match.start()
                end = match.end()
                if source[end : end + 2] == b"\r\n":
                    end += 2
                elif source[end : end + 1] == b"\n":
                    end += 1
                del standalone[start:end]
        standalone = bytearray(
            main_pattern.sub(
                lambda match: (
                    match.group("prefix")
                    + match.group("quote")
                    + encoded_name
                    + match.group("quote")
                ),
                bytes(standalone),
                count=1,
            )
        )
        target = destination / f"{prefix}-{name}.circ"
        target.write_bytes(_serialize_standalone_logisim_project(bytes(standalone)))
        written.append(target)
    return tuple(written)


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
    parser.add_argument(
        "--split-output",
        type=Path,
        help="write standalone leaf-circuit projects to this directory",
    )
    args = parser.parse_args(argv)
    if args.contract_only and args.profile is None:
        parser.error("--contract-only requires --profile")
    try:
        reports = inspect_project(args.project)
        split_files = (
            split_leaf_circuits(args.project, args.split_output)
            if args.split_output is not None
            else ()
        )
        violations = (
            validate_hardware_contract(args.project, args.profile)
            if args.profile is not None
            else ()
        )
    except CircuitError as error:
        parser.error(str(error))

    for split_file in split_files:
        print(f"wrote {split_file}")

    incomplete = False
    for report in reports:
        state = "connected" if report.connected else "INCOMPLETE"
        print(
            f"{report.name}: {state}; {report.components} components, "
            f"{report.wires} wires"
        )
        if report.unconnected:
            print("  unconnected: " + ", ".join(report.unconnected))
        if report.placement_conflicts:
            print("  placement: " + ", ".join(report.placement_conflicts))
        if report.routing_conflicts:
            print("  routing: " + ", ".join(report.routing_conflicts))
        if report.width_conflicts:
            print("  widths: " + ", ".join(report.width_conflicts))
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
