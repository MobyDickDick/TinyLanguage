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


def test_extracted_addition_inputs_reach_the_intended_symbol_ports():
    root = ET.parse(PROJECT).getroot()
    top = next(
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == "TinyCPU"
    )
    addition = next(
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == "AddSubCircuit"
    )
    instance = next(
        component
        for component in top.findall("comp")
        if component.get("name") == "AddSubCircuit"
    )

    inputs = sorted(
        (
            component
            for component in addition.findall("comp")
            if component.get("name") == "Pin"
            and _attributes(component).get("type", "input") == "input"
            and _attributes(component).get("width", "1") == "1"
        ),
        key=lambda component: _point(component.get("loc"))[::-1],
    )
    instance_x, instance_y = _point(instance.get("loc"))
    terminals = {
        _attributes(pin)["label"]: f"({instance_x - 220},{instance_y + 20 * index})"
        for index, pin in enumerate(inputs)
    }
    sources = {
        "DEFAULT_VALID": "(1260,410)",
        "MEMORY_VALID": "(1270,430)",
        "ACC_VALID": "(1420,450)",
        "NOT_VALID_SELECT": "(1430,590)",
        "ADD_ADDRESS": "(640,560)",
        "ADD_ADDRESS_REGISTER": "(640,580)",
        "ADD_ADDRESS_REGISTER_PLUS_OFFSET": "(640,600)",
        "ADD_CONST": "(640,540)",
    }
    adjacency = _adjacency(top, set(terminals.values()) | set(sources.values()))

    # The operation box also owns the two 16-bit arithmetic operands. This
    # regression test concerns the independently routed one-bit validity and
    # decoder inputs only.
    assert set(terminals) == set(sources)
    for label, source in sources.items():
        assert terminals[label] in _reachable(adjacency, source), label
