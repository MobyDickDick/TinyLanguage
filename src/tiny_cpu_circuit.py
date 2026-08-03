"""Inspect Logisim-evolution ``.circ`` files used by TinyCPU.

This module intentionally does not emulate Logisim's component library. It
provides a dependency-free netlist reader so an incomplete schematic can be
checked in CI before the authoritative Logisim simulator is invoked.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


class CircuitError(ValueError):
    """Raised when a Logisim project cannot be read."""


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


def inspect_project(path: str | Path) -> tuple[CircuitReport, ...]:
    """Read *path* and return a connectivity report for every circuit.

    A component is considered connected when its anchor shares a wire endpoint.
    This conservative rule detects empty starter sheets; detailed pin geometry
    remains Logisim's job. Text annotations have no electrical terminals.
    """

    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise CircuitError(f"cannot read Logisim project {path}: {error}") from error
    if root.tag != "project":
        raise CircuitError(f"{path} is not a Logisim project")

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
    args = parser.parse_args(argv)
    try:
        reports = inspect_project(args.project)
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
    return 1 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
