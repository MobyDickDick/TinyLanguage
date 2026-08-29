"""Regression checks for the extracted TinyCPU addition subcircuit."""

from collections import defaultdict, deque
from pathlib import Path
import xml.etree.ElementTree as ET

PROJECT = Path(__file__).parents[2] / "hardware" / "logisim" / "TinyCPU.circ"


def _attributes(element):
    return {item.get("name"): item.get("val") for item in element.findall("a")}


def _point(value):
    return tuple(int(part) for part in value.strip("()").split(","))


def _on_segment(point, start, end):
    x, y = _point(point)
    x1, y1 = _point(start)
    x2, y2 = _point(end)
    return (x1 == x2 == x and min(y1, y2) <= y <= max(y1, y2)) or (
        y1 == y2 == y and min(x1, x2) <= x <= max(x1, x2)
    )


def _adjacency(circuit, extra_points=()):
    wires = [(wire.get("from"), wire.get("to")) for wire in circuit.findall("wire")]
    points = {point for wire in wires for point in wire} | set(extra_points)
    result = defaultdict(set)
    for start, end in wires:
        members = {point for point in points if _on_segment(point, start, end)}
        for point in members:
            result[point].update(members - {point})
    return result


def _reachable(adjacency, source):
    reached = {source}
    pending = deque([source])
    while pending:
        point = pending.popleft()
        for neighbour in adjacency[point] - reached:
            reached.add(neighbour)
            pending.append(neighbour)
    return reached


def test_extracted_addition_has_the_restored_operation_interface():
    root = ET.parse(PROJECT).getroot()
    operations = next(
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == "Operations"
    )
    addition = next(
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == "AddSubCircuit"
    )
    assert any(
        component.get("name") == "AddSubCircuit"
        for component in operations.findall("comp")
    )

    # The contract is the set of named ports.  Deliberately do not derive the
    # generated symbol terminals from pin order or drawing coordinates: moving
    # a pin in Logisim must not turn an electrically equivalent redraw into a
    # regression.
    terminals = {
        _attributes(pin)["label"]
        for pin in addition.findall("comp")
        if pin.get("name") == "Pin"
        and _attributes(pin).get("type", "input") == "input"
        and _attributes(pin).get("width", "1") == "1"
    }
    # This is the interface of the restored, hand-maintained operation box.
    # Older tests described the subsequently reverted validity-helper layout
    # and therefore required ports which no longer exist in this schematic.
    assert terminals == {
        "ADD_CONST",
        "ADD_ADDRESS",
        "ADD_ADDRESS_REGISTER",
        "ADD_ADDRESS_REGISTER_PLUS_OFFSET",
        "MEMORY_VALID",
        "ACC_VALID",
    }
    assert not [
        component
        for component in operations.findall("comp")
        if component.get("name") == "Tunnel"
    ]

    labels = {_attributes(component).get("label") for component in addition.findall("comp")}
    # Keep the labels from the hand-redrawn sheet authoritative.  The drawing
    # uses the ADD memory-mode selector and validity gate directly instead of
    # the older, subsequently removed helper labels.
    assert {"ACC_ADD_MEMORY_SELECT", "ACC_ADD_VALID"} <= labels
    assert sum(
        component.get("name") == "Constant"
        for component in addition.findall("comp")
    ) == 1
    assert any(
        _attributes(component).get("label") == "IMMEDIATE_VALUE"
        and _attributes(component).get("width") == "16"
        for component in addition.findall("comp")
    )
