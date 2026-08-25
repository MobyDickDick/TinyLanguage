"""Inspect Logisim-evolution ``.circ`` files used by TinyCPU.

This module intentionally does not emulate Logisim's component library. It
provides a dependency-free netlist reader so an incomplete schematic can be
checked in CI before the authoritative Logisim simulator is invoked.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any
import xml.etree.ElementTree as ET


class CircuitError(ValueError):
    """Raised when a Logisim project cannot be read."""


SUPPORTED_PROFILE_SCHEMA = 1
# Top-level instances in the hand-maintained overview are placed roughly 300
# grid units apart.  Keep a smaller guard around their anchors to catch true
# accidental overlays without imposing the obsolete generated 600-unit lanes.
SUBCIRCUIT_ANCHOR_CLEARANCE = 200
FETCH_DECODE_DECODER_PITCH = 10


def hardware_control_label(signal: str) -> str:
    """Return the compact label printed on a control-pin symbol."""

    special_labels = {
        "LOAD_ADDRESS_REGISTER_CONST": "LD_REG_CONST",
        "LOAD_ADDRESS_REGISTER_ADDRESS": "LD_REG_ADR",
    }
    if signal in special_labels:
        return special_labels[signal]
    return (
        signal.replace("ADDRESS_REGISTER_PLUS_OFFSET", "REG_OFF")
        .replace("ADDRESS_REGISTER", "ADR_REG")
        .replace("ADDRESS", "ADR")
    )


FETCH_DECODE_SIGNAL_LANES = {
    "LOAD_CONST": 0,
    "LOAD_ADDRESS": 1,
    "LOAD_ADDRESS_REGISTER": 2,
    "LOAD_ADDRESS_REGISTER_PLUS_OFFSET": 3,
    "ADD_CONST": 4,
    "ADD_ADDRESS": 5,
    "ADD_ADDRESS_REGISTER": 6,
    "ADD_ADDRESS_REGISTER_PLUS_OFFSET": 7,
    "SUB_CONST": 8,
    "SUB_ADDRESS": 9,
    "SUB_ADDRESS_REGISTER": 10,
    "SUB_ADDRESS_REGISTER_PLUS_OFFSET": 11,
    "MUL_CONST": 12,
    "MUL_ADDRESS": 13,
    "MUL_ADDRESS_REGISTER": 14,
    "MUL_ADDRESS_REGISTER_PLUS_OFFSET": 15,
    "DIV_CONST": 16,
    "DIV_ADDRESS": 17,
    "DIV_ADDRESS_REGISTER": 18,
    "DIV_ADDRESS_REGISTER_PLUS_OFFSET": 19,
    "AND_CONST": 20,
    "AND_ADDRESS": 21,
    "AND_ADDRESS_REGISTER": 22,
    "AND_ADDRESS_REGISTER_PLUS_OFFSET": 23,
    "OR_CONST": 24,
    "OR_ADDRESS": 25,
    "OR_ADDRESS_REGISTER": 26,
    "OR_ADDRESS_REGISTER_PLUS_OFFSET": 27,
    "STORE_ADDRESS": 28,
    "STORE_ADDRESS_REGISTER": 29,
    "STORE_ADDRESS_REGISTER_PLUS_OFFSET": 30,
    "LOAD_ADDRESS_REGISTER_CONST": 31,
    "LOAD_ADDRESS_REGISTER_ADDRESS": 32,
    "NOT": 33,
    "JUMP_ADDRESS": 34,
    "JUMP_ZERO": 35,
    "JUMP_NOT_ZERO": 36,
    "JUMP_NEGATIVE": 37,
    "JUMP_ERROR": 38,
    "JUMP_NOT_ERROR": 39,
    "CLEAR_ERROR": 40,
    "INPUT": 41,
    "PRINT": 42,
    "PRINT_ADDRESS": 43,
    "HALT": 44,
    "HALT_ERROR": 45,
    "XOR_CONST": 46,
    "XOR_ADDRESS": 47,
    "XOR_ADDRESS_REGISTER": 48,
    "XOR_ADDRESS_REGISTER_PLUS_OFFSET": 49,
}


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
            and not self.routing_conflicts
            and not self.width_conflicts
        )


def _wire_overlap(first: ET.Element, second: ET.Element) -> bool:
    """Return whether two collinear wires overlap for a non-zero distance."""

    first_from = _location(first.get("from", ""))
    first_to = _location(first.get("to", ""))
    second_from = _location(second.get("from", ""))
    second_to = _location(second.get("to", ""))
    if {first_from, first_to} & {second_from, second_to}:
        return False
    if first_from[1] == first_to[1] == second_from[1] == second_to[1]:
        first_span = sorted((first_from[0], first_to[0]))
        second_span = sorted((second_from[0], second_to[0]))
    elif first_from[0] == first_to[0] == second_from[0] == second_to[0]:
        first_span = sorted((first_from[1], first_to[1]))
        second_span = sorted((second_from[1], second_to[1]))
    else:
        return False
    return max(first_span[0], second_span[0]) < min(first_span[1], second_span[1])


def _norm_loc(value: str) -> str:
    """Normalize Logisim coordinate strings for stable comparisons."""

    x, y = _location(value)
    return f"({x},{y})"


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


def _fetch_decode_lane_conflicts(circuit: ET.Element) -> tuple[str, ...]:
    """Return FetchDecode outputs that do not touch their decoder lane.

    The generic connectivity pass only proves that a pin is on some wire.  A
    decode output can therefore look connected while the wire is one grid step
    above or below the six-bit decoder terminal.  These AP 7 lanes are fixed by
    the machine-format opcode table, so check the exact decoder-port endpoint.
    """

    decoder = next(
        (
            component
            for component in circuit.findall("comp")
            if component.get("name") == "Decoder"
            and _attributes(component).get("select") == "6"
        ),
        None,
    )
    if decoder is None:
        return ()
    decoder_x, decoder_y = _location(decoder.get("loc", ""))
    decoder_outputs = min(1 << int(_attributes(decoder)["select"]), 64)
    decoder_output_x = decoder_x + 20
    decoder_output0_y = decoder_y - FETCH_DECODE_DECODER_PITCH * decoder_outputs
    output_pins = {
        attrs["label"]: _norm_loc(component.get("loc", "?"))
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
        and (attrs := _attributes(component)).get("type") == "output"
        and attrs.get("label")
        in {hardware_control_label(signal) for signal in FETCH_DECODE_SIGNAL_LANES}
    }
    wire_neighbors: dict[str, set[str]] = {}
    for wire in circuit.findall("wire"):
        start = _norm_loc(wire.get("from", ""))
        end = _norm_loc(wire.get("to", ""))
        wire_neighbors.setdefault(start, set()).add(end)
        wire_neighbors.setdefault(end, set()).add(start)
    conflicts = []
    for signal, lane in FETCH_DECODE_SIGNAL_LANES.items():
        pin = output_pins.get(hardware_control_label(signal))
        if pin is None:
            continue
        target = pin
        if signal == "JUMP_NOT_ZERO":
            gate = next(
                (
                    component
                    for component in circuit.findall("comp")
                    if component.get("name") == "AND Gate"
                    and _attributes(component).get("label") == "JNZ_TAKEN"
                ),
                None,
            )
            if gate is not None:
                gate_x, gate_y = _location(gate.get("loc", ""))
                target = f"({gate_x - 50},{gate_y - 20})"
        elif signal == "HALT_ERROR":
            gate = next(
                (
                    component
                    for component in circuit.findall("comp")
                    if component.get("name") == "OR Gate"
                    and _attributes(component).get("label") == "ERROR_HALT"
                ),
                None,
            )
            if gate is not None:
                gate_x, gate_y = _location(gate.get("loc", ""))
                target = f"({gate_x - 50},{gate_y - 20})"
        decoder_output = (
            f"({decoder_output_x},"
            f"{decoder_output0_y + FETCH_DECODE_DECODER_PITCH * lane})"
        )
        pending = [decoder_output]
        seen = {decoder_output}
        while pending and target not in seen:
            current = pending.pop()
            for neighbor in wire_neighbors.get(current, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    pending.append(neighbor)
        if target not in seen:
            conflicts.append(
                f"{circuit.get('name')}.{signal}: output pin {pin} is not wired to "
                f"decoder lane {lane} at {decoder_output}"
            )
    return tuple(conflicts)


def _component_identity(
    component: ET.Element,
) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Return a stable identity for duplicate/overlay detection."""

    attrs = tuple(sorted(_attributes(component).items()))
    return (component.get("name", ""), component.get("lib", ""), attrs)


def _component_terminals(component: ET.Element) -> set[str]:
    """Return conservative Logisim-evolution terminal coordinates."""

    location = _norm_loc(component.get("loc", "?"))
    terminals = {location}
    x, y = _location(location)
    attrs = _attributes(component)
    if component.get("name") == "Decoder":
        select = int(attrs.get("select", "1"))
        outputs = min(1 << select, 64)
        terminals.update(
            f"({x + 20},{y - 10 * outputs + 10 * lane})" for lane in range(outputs)
        )
        return terminals
    if component.get("name") == "Splitter":
        fanout = int(attrs.get("fanout", "2"))
        if attrs.get("appear") == "right" or attrs.get("label") == "PC_ADDRESS":
            # Logisim's right-hand splitter symbol places branch zero one grid
            # step below its anchor.  Using y-20 here made real wires at y+10
            # look like decorative stubs (notably FetchDecode's operand bus).
            start = y + 10
            terminals.update(
                f"({x + 20},{start + 40 * index})" for index in range(fanout)
            )
        else:
            terminals.update(f"({x + 20},{y + 20 * index})" for index in range(fanout))
        return terminals
    if component.get("name") in {"AND Gate", "OR Gate", "XOR Gate"}:
        inputs = int(attrs.get("inputs", "2"))
        offsets = (
            (-20, 20)
            if inputs == 2
            else tuple(range(-(inputs // 2) * 10, 0, 10))
            + tuple(range(10, (inputs // 2 + 1) * 10, 10))
            if inputs % 2 == 0
            else tuple(range(-(inputs // 2) * 20, (inputs // 2 + 1) * 20, 20))
        )
        terminals.update(
            f"({x - 50},{y + offset})" for offset in offsets
        )
    elif component.get("name") == "NOT Gate":
        terminals.add(f"({x - 30},{y})")
    elif component.get("name") in {
        "Adder", "Subtractor", "Multiplier", "Divider", "Comparator"
    }:
        terminals.update({f"({x - 40},{y - 10})", f"({x - 40},{y + 10})"})
        if component.get("name") in {"Adder", "Subtractor", "Multiplier", "Divider"}:
            terminals.update({f"({x - 20},{y - 20})", f"({x - 20},{y + 20})"})
        else:
            terminals.update({f"({x},{y - 10})", f"({x},{y + 10})"})
    elif component.get("name") == "Multiplexer":
        terminals.update(
            {
                f"({x - 30},{y - 10})",
                f"({x - 30},{y + 10})",
                f"({x - 20},{y + 20})",
            }
        )
    if attrs.get("appearance") != "logisim_evolution":
        return terminals
    if component.get("name") == "Register":
        terminals.update(
            {
                f"({x},{y + 30})",  # D
                f"({x + 60},{y + 30})",  # Q
                f"({x},{y + 50})",  # WE
                f"({x},{y + 70})",  # clock
                f"({x + 30},{y + 90})",  # reset
            }
        )
    elif component.get("name") == "RAM":
        data_width = int(
            attrs.get("dataWidth", attrs.get("data", str(attrs.get("width", "1"))))
        )
        data_offset = 100 if data_width == 1 else 90
        address_offset = -10 if data_width == 1 else 10
        terminals.update(
            {
                f"({x},{y + address_offset})",
                f"({x},{y + 50})",
                f"({x},{y + 60})",
                f"({x},{y + 70})",
                f"({x},{y + data_offset})",
                f"({x + 240},{y + data_offset})",
            }
        )
    elif component.get("name") == "ROM":
        terminals.update({f"({x},{y + 10})", f"({x + 240},{y + 60})"})
    return terminals


def _component_terminal_widths(component: ET.Element) -> dict[str, int]:
    """Return conservative bit widths for known Logisim terminals."""

    attrs = _attributes(component)
    width = int(attrs.get("width", "1"))
    location = _norm_loc(component.get("loc", "?"))
    x, y = _location(location)
    name = component.get("name")
    if name == "Pin":
        return {location: width}
    if name == "Decoder":
        select = int(attrs.get("select", "1"))
        outputs = min(1 << select, 64)
        result = {location: select}
        result.update(
            {f"({x + 20},{y - 10 * outputs + 10 * lane})": 1 for lane in range(outputs)}
        )
        return result
    if name == "Splitter":
        incoming = int(attrs.get("incoming", attrs.get("fanout", "1")))
        fanout = int(attrs.get("fanout", "2"))
        output_widths = {index: 0 for index in range(fanout)}
        for bit in range(incoming):
            output = int(
                attrs.get(f"bit{bit}", str(bit if bit < fanout else fanout - 1))
            )
            if output >= 0:
                output_widths[output] = output_widths.get(output, 0) + 1
        result = {location: incoming}
        if attrs.get("appear") == "right" or attrs.get("label") == "PC_ADDRESS":
            start = y + 10
            result.update(
                {
                    f"({x + 20},{start + 40 * index})": max(width, 1)
                    for index, width in output_widths.items()
                }
            )
        else:
            result.update(
                {
                    f"({x + 20},{y + 20 * index})": max(width, 1)
                    for index, width in output_widths.items()
                }
            )
        return result
    if name in {"AND Gate", "OR Gate", "XOR Gate"}:
        inputs = int(attrs.get("inputs", "2"))
        offsets = (
            (-20, 20)
            if inputs == 2
            else tuple(range(-(inputs // 2) * 10, 0, 10))
            + tuple(range(10, (inputs // 2 + 1) * 10, 10))
            if inputs % 2 == 0
            else tuple(range(-(inputs // 2) * 20, (inputs // 2 + 1) * 20, 20))
        )
        result = {location: width}
        result.update(
            {
                f"({x - 50},{y + offset})": width
                for offset in offsets
            }
        )
        return result
    if name == "NOT Gate":
        return {location: width, f"({x - 30},{y})": width}
    if name in {"Adder", "Subtractor", "Multiplier", "Divider"}:
        return {
            location: width,
            f"({x - 40},{y - 10})": width,
            f"({x - 40},{y + 10})": width,
            f"({x - 20},{y - 20})": 1,
            f"({x - 20},{y + 20})": 1,
        }
    if name == "Multiplexer":
        return {
            location: width,
            f"({x - 30},{y - 10})": width,
            f"({x - 30},{y + 10})": width,
            f"({x - 20},{y + 20})": 1,
        }
    if name == "Comparator":
        return {
            f"({x - 40},{y - 10})": width,
            f"({x - 40},{y + 10})": width,
            f"({x},{y - 10})": 1,
            location: 1,
            f"({x},{y + 10})": 1,
        }
    if attrs.get("appearance") == "logisim_evolution":
        if name == "Register":
            return {
                f"({x},{y + 30})": width,
                f"({x + 60},{y + 30})": width,
                f"({x},{y + 50})": 1,
                f"({x},{y + 70})": 1,
                f"({x + 30},{y + 90})": 1,
            }
        if name == "RAM":
            addr_width = int(attrs.get("addrWidth", attrs.get("addr", "1")))
            data_width = int(attrs.get("dataWidth", attrs.get("data", str(width))))
            data_offset = 100 if data_width == 1 else 90
            address_offset = -10 if data_width == 1 else 10
            return {
                f"({x},{y + address_offset})": addr_width,
                f"({x},{y + 50})": 1,
                f"({x},{y + 60})": 1,
                f"({x},{y + 70})": 1,
                f"({x},{y + data_offset})": data_width,
                f"({x + 240},{y + data_offset})": data_width,
            }
        if name == "ROM":
            addr_width = int(attrs.get("addrWidth", attrs.get("addr", "1")))
            data_width = int(attrs.get("dataWidth", attrs.get("data", str(width))))
            return {f"({x},{y + 10})": addr_width, f"({x + 240},{y + 60})": data_width}
    return {terminal: width for terminal in _component_terminals(component)}


def _component_output_terminals(
    component: ET.Element, circuit_interfaces: dict[str, tuple[str, ...]]
) -> set[str]:
    """Return terminals that actively drive their net.

    Logisim does not store a netlist in ``.circ`` files, only drawing geometry.
    In particular, treating a component as a driver without identifying its
    output terminal produces both false positives and missed output-to-output
    shorts.  Keep this deliberately conservative list in step with
    :func:`_component_terminals` and resolve generated subcircuit ports from
    their declared output pins.
    """

    location = _norm_loc(component.get("loc", "?"))
    name = component.get("name", "")
    attrs = _attributes(component)
    x, y = _location(location)
    if name == "Pin":
        # An input pin is a source when viewed from inside its circuit.
        return {location} if attrs.get("type", "input") != "output" else set()
    if name in circuit_interfaces:
        return {
            f"({x},{y + 20 * index})"
            for index, _label in enumerate(circuit_interfaces[name])
        }
    if name == "Decoder":
        select = int(attrs.get("select", "1"))
        outputs = min(1 << select, 64)
        return {
            f"({x + 20},{y - 10 * outputs + 10 * lane})"
            for lane in range(outputs)
        }
    if name == "Splitter":
        # A splitter is passive: its branches are separate nets connected to
        # slices of the incoming bus, not independent voltage sources.
        return set()
    if name == "Register" and attrs.get("appearance") == "logisim_evolution":
        return {f"({x + 60},{y + 30})"}
    if name in {"RAM", "ROM"} and attrs.get("appearance") == "logisim_evolution":
        data_width = int(
            attrs.get("dataWidth", attrs.get("data", attrs.get("width", "1")))
        )
        data_offset = 100 if data_width == 1 else (60 if name == "ROM" else 90)
        return {f"({x + 240},{y + data_offset})"}
    # These Logisim primitives all expose their result at the component anchor.
    if name in {
        "AND Gate", "OR Gate", "XOR Gate", "NOT Gate", "Adder", "Subtractor",
        "Multiplier", "Divider", "Comparator", "Multiplexer", "Constant",
    }:
        return {location}
    return set()


def _required_terminal_names(component: ET.Element) -> dict[str, str]:
    """Return terminals that must each reach another component.

    Most primitives have optional control/status pins, so the general
    connectivity check deliberately remains conservative.  A multiplexer is
    different: both data inputs and its select input are fundamental to the
    operation.  In particular, a floating select pin must not be hidden by
    wires attached to the data terminals.
    """

    if component.get("name") != "Multiplexer":
        return {}
    x, y = _location(component.get("loc", ""))
    return {
        f"({x - 30},{y - 10})": "data input 0",
        f"({x - 30},{y + 10})": "data input 1",
        f"({x - 20},{y + 20})": "select input",
        f"({x},{y})": "output",
    }


def _location(value: str) -> tuple[int, int]:
    """Return the integer coordinates used by Logisim's ``loc`` attribute."""

    try:
        x, y = value.strip().strip("()").split(",")
        return int(x), int(y)
    except (AttributeError, TypeError, ValueError) as error:
        raise CircuitError(f"invalid Logisim component location {value!r}") from error


def _attributes(element: ET.Element) -> dict[str, str]:
    return {
        item.get("name", "").strip(): item.get("val", "").strip()
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

    # Logisim expands subcircuit symbols while loading a project.  A recursive
    # reference can therefore exhaust memory before the schematic becomes
    # interactive, so reject hierarchy cycles as part of the checkout gate.
    dependencies = {
        name: tuple(
            component.get("name", "")
            for component in circuit.findall("comp")
            if component.get("lib") is None
            and component.get("name", "") in circuits
        )
        for name, circuit in circuits.items()
    }
    visiting: list[str] = []
    visited: set[str] = set()

    def check_hierarchy(circuit_name: str) -> None:
        if circuit_name in visiting:
            start = visiting.index(circuit_name)
            cycle = visiting[start:] + [circuit_name]
            violation = "recursive subcircuit hierarchy: " + " -> ".join(cycle)
            if violation not in violations:
                violations.append(violation)
            return
        if circuit_name in visited:
            return
        visiting.append(circuit_name)
        for dependency in dependencies[circuit_name]:
            check_hierarchy(dependency)
        visiting.pop()
        visited.add(circuit_name)

    for circuit_name in circuits:
        check_hierarchy(circuit_name)

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
        for kind, spec in expected.get("component_kinds", {}).items():
            matches = [
                _attributes(component)
                for component in circuit.findall("comp")
                if component.get("name") == kind
            ]
            if len(matches) != spec["count"]:
                violations.append(
                    f"{circuit_name}: {kind} count is {len(matches)}, "
                    f"expected {spec['count']}"
                )
            for attribute, value in spec.get("attributes", {}).items():
                if any(attrs.get(attribute) != value for attrs in matches):
                    violations.append(
                        f"{circuit_name}: {kind} has unexpected {attribute}; "
                        f"expected {value}"
                    )
        pins = labelled_components(circuit_name, "Pin")
        expected_pin_directions = profile.get("pin_directions", {}).get(
            circuit_name, {}
        )
        for label, width in expected.get("pins", {}).items():
            if label not in pins:
                violations.append(f"{circuit_name}: missing pin {label}")
                continue
            if int(pins[label].get("width", "1")) != width:
                violations.append(
                    f"{circuit_name}.{label}: width is "
                    f"{pins[label].get('width', '1')}, expected {width}"
                )
            expected_type = expected_pin_directions.get(label)
            if expected_type is not None:
                actual_type = pins[label].get("type", "input")
                if actual_type != expected_type:
                    violations.append(
                        f"{circuit_name}.{label}: pin type is {actual_type}, "
                        f"expected {expected_type}"
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
    circuit_names = {circuit.get("name", "") for circuit in root.findall("circuit")}
    circuit_definitions = {
        circuit.get("name", ""): circuit for circuit in root.findall("circuit")
    }

    def interface_pins(name: str, pin_type: str) -> tuple[ET.Element, ...]:
        definition = circuit_definitions[name]
        return tuple(
            sorted(
                (
                    component
                    for component in definition.findall("comp")
                    if component.get("name") == "Pin"
                    and _attributes(component).get("type", "input") == pin_type
                ),
                key=lambda component: _location(component.get("loc", ""))[::-1],
            )
        )

    circuit_outputs = {
        name: tuple(
            _attributes(pin).get("label", f"output {index}")
            for index, pin in enumerate(interface_pins(name, "output"))
        )
        for name in circuit_names
    }

    reports: list[CircuitReport] = []
    for circuit in root.findall("circuit"):
        wires = circuit.findall("wire")
        endpoints = {
            _norm_loc(point)
            for wire in wires
            for point in (wire.get("from"), wire.get("to"))
            if point is not None
        }
        electrical = [
            component
            for component in circuit.findall("comp")
            if component.get("name") != "Text"
        ]

        def component_terminals(component: ET.Element) -> set[str]:
            terminals = _component_terminals(component)
            if component.get("name", "") not in circuit_names:
                return terminals
            x, y = _location(component.get("loc", ""))
            inputs = interface_pins(component.get("name", ""), "input")
            outputs = interface_pins(component.get("name", ""), "output")
            return {
                *(f"({x - 220},{y + 20 * index})" for index in range(len(inputs))),
                *(f"({x},{y + 20 * index})" for index in range(len(outputs))),
            }

        terminal_to_component: dict[str, list[ET.Element]] = {}
        for component in electrical:
            for terminal in component_terminals(component):
                terminal_to_component.setdefault(terminal, []).append(component)
        wire_neighbors: dict[str, set[str]] = {}
        tunnel_locations: dict[str, list[str]] = {}
        for component in electrical:
            if component.get("name") == "Tunnel":
                tunnel_locations.setdefault(
                    _attributes(component).get("label", ""), []
                ).append(_norm_loc(component.get("loc", "")))
        for locations in tunnel_locations.values():
            for first, second in zip(locations, locations[1:]):
                wire_neighbors.setdefault(first, set()).add(second)
                wire_neighbors.setdefault(second, set()).add(first)
        for wire in wires:
            start = _norm_loc(wire.get("from", ""))
            end = _norm_loc(wire.get("to", ""))
            # Every endpoint is a potential Logisim junction, including the
            # endpoint of a *different* wire that lands midway on this one.
            # Omitting these T-junctions was the reason wired-OR faults escaped
            # the old checker.
            points_on_wire = {
                point for point in endpoints if _point_on_wire(point, wire)
            }
            points_on_wire.update(
                terminal
                for terminal in terminal_to_component
                if _point_on_wire(terminal, wire)
            )
            if _location(start)[0] == _location(end)[0]:
                ordered = sorted(points_on_wire, key=lambda point: _location(point)[1])
            else:
                ordered = sorted(points_on_wire, key=lambda point: _location(point)[0])
            for first, second in zip(ordered, ordered[1:]):
                wire_neighbors.setdefault(first, set()).add(second)
                wire_neighbors.setdefault(second, set()).add(first)

        def reachable_wire_points(start_points: set[str]) -> set[str]:
            seen = set(start_points)
            pending = list(start_points)
            while pending:
                current = pending.pop()
                for neighbor in wire_neighbors.get(current, ()):
                    if neighbor not in seen:
                        seen.add(neighbor)
                        pending.append(neighbor)
            return seen

        unconnected = []
        for component in electrical:
            if component.get("name") == "Tunnel":
                continue
            location = _norm_loc(component.get("loc", "?"))
            terminals = component_terminals(component)
            attrs = _attributes(component)
            label = attrs.get("label") or component.get("name", "component")
            missing_required = []
            for terminal, terminal_name in _required_terminal_names(component).items():
                terminal_net = reachable_wire_points({terminal})
                terminal_peers = {
                    id(other)
                    for point in terminal_net
                    for other in terminal_to_component.get(point, ())
                    if other is not component
                }
                if not terminal_peers:
                    missing_required.append(f"{terminal_name} {terminal}")
            if missing_required:
                unconnected.extend(
                    f"{label}.{terminal_name}@{location}"
                    for terminal_name in missing_required
                )
            reachable = reachable_wire_points(terminals)
            connected_components = {
                id(other)
                for point in reachable
                for other in terminal_to_component.get(point, ())
            }
            connected_components.discard(id(component))
            wire_connected = bool(terminals & endpoints) or any(
                _point_on_wire(terminal, wire)
                for terminal in terminals
                for wire in wires
            )
            # A wire stub is not an electrical connection.  Pins are the public
            # circuit contract, so every input and output pin must reach at
            # least one other component terminal on its net.  Earlier versions
            # treated a pin as connected when any wire merely touched it; that
            # let broken Logisim sheets pass with input pins ending in stubs
            # or with output pins connected only to decorative wires.
            requires_peer = component.get("name") == "Pin" or len(terminals) > 1
            connected = bool(connected_components) if requires_peer else wire_connected
            if not connected:
                unconnected.append(f"{label}@{location}")
        placement_conflicts: list[str] = []
        components_by_location: dict[str, list[ET.Element]] = {}
        duplicate_components: dict[
            tuple[str, tuple[int, int], str, tuple[tuple[str, str], ...]], int
        ] = {}
        for component in electrical:
            if component.get("name") == "Tunnel":
                continue
            location = _norm_loc(component.get("loc", "?"))
            components_by_location.setdefault(location, []).append(component)
            name, lib, attrs = _component_identity(component)
            key = (name, _location(location), lib, attrs)
            duplicate_components[key] = duplicate_components.get(key, 0) + 1
        for location, components_at_location in sorted(components_by_location.items()):
            if len(components_at_location) > 1:
                labels = []
                for component in components_at_location:
                    attrs = _attributes(component)
                    labels.append(
                        attrs.get("label") or component.get("name", "component")
                    )
                placement_conflicts.append(
                    f"multiple components share {location}: "
                    + ", ".join(sorted(labels))
                )
        for (name, (x, y), _lib, attrs), count in sorted(duplicate_components.items()):
            if count > 1:
                label = dict(attrs).get("label") or name or "component"
                placement_conflicts.append(
                    f"possible overlaid circuit: {count} identical {label} "
                    f"components at ({x},{y})"
                )
        routing_conflicts: list[str] = []
        width_conflicts: list[str] = []
        visited_nets: set[frozenset[str]] = set()
        for point in set(wire_neighbors) | set(terminal_to_component):
            net = frozenset(reachable_wire_points({point}))
            if not net or net in visited_nets:
                continue
            visited_nets.add(net)
            # A labelled and an unlabelled serialization of the same primitive
            # can occupy one Logisim anchor after a three-way XML merge.  That
            # is an overlay/placement problem, not two distinct output
            # terminals on the net.  Key drivers by primitive and terminal;
            # keep the most descriptive label for diagnostics.
            drivers: dict[tuple[str, str], str] = {}
            for net_point in net:
                for component in terminal_to_component.get(net_point, ()):
                    attrs = _attributes(component)
                    if net_point in _component_output_terminals(
                        component, circuit_outputs
                    ):
                        label = attrs.get("label") or component.get("name", "component")
                        if component.get("name", "") in circuit_outputs:
                            index = (
                                _location(net_point)[1]
                                - _location(component.get("loc", ""))[1]
                            ) // 20
                            outputs = circuit_outputs[component.get("name", "")]
                            if 0 <= index < len(outputs):
                                label = f"{label}.{outputs[index]}"
                        key = (component.get("name", "component"), net_point)
                        description = f"{label}@{net_point}"
                        previous = drivers.get(key)
                        if previous is None or (
                            previous.startswith(f"{key[0]}@")
                            and not description.startswith(f"{key[0]}@")
                        ):
                            drivers[key] = description
            if len(drivers) > 1:
                routing_conflicts.append(
                    "multiple outputs drive one net (wired-OR is forbidden): "
                    + ", ".join(sorted(drivers.values()))
                )
        terminal_widths: dict[str, list[tuple[str, int]]] = {}
        for component in electrical:
            attrs = _attributes(component)
            label = attrs.get("label") or component.get("name", "component")
            if component.get("name", "") in circuit_names:
                x, y = _location(component.get("loc", ""))
                inputs = interface_pins(component.get("name", ""), "input")
                outputs = interface_pins(component.get("name", ""), "output")
                widths = {
                    **{
                        f"({x - 220},{y + 20 * index})": int(
                            _attributes(pin).get("width", "1")
                        )
                        for index, pin in enumerate(inputs)
                    },
                    **{
                        f"({x},{y + 20 * index})": int(
                            _attributes(pin).get("width", "1")
                        )
                        for index, pin in enumerate(outputs)
                    },
                }
            else:
                widths = _component_terminal_widths(component)
            for terminal, width in widths.items():
                terminal_widths.setdefault(terminal, []).append((label, width))
        for net in visited_nets:
            widths = {
                width
                for point in net
                for _label, width in terminal_widths.get(point, ())
            }
            if len(widths) > 1:
                members = sorted(
                    {
                        f"{label}@{point}:{width}"
                        for point in net
                        for label, width in terminal_widths.get(point, ())
                    }
                )
                width_conflicts.append(
                    "incompatible bus widths on one net: " + ", ".join(members)
                )
        for wire in wires:
            start = _location(wire.get("from", ""))
            end = _location(wire.get("to", ""))
            if start[0] != end[0] and start[1] != end[1]:
                routing_conflicts.append(
                    f"{wire.get('from')}->{wire.get('to')} is diagonal; "
                    "Logisim wires must be horizontal or vertical"
                )
        routing_conflicts.extend(_fetch_decode_lane_conflicts(circuit))
        for index, first in enumerate(wires):
            for second in wires[index + 1 :]:
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
            for second in instances[index + 1 :]:
                second_location = _location(second.get("loc", ""))
                horizontal = abs(first_location[0] - second_location[0])
                vertical = abs(first_location[1] - second_location[1])
                # The overview is hand-maintained and routes around the
                # generated symbols.  This guard catches accidental near-
                # duplicate anchors; it does not prescribe generated lanes.
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
                tuple(width_conflicts),
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
    # ElementTree inserts a space before self-closing tags whereas Logisim's
    # own writer does not.  Keep generated diagnostics in Logisim's stable
    # spelling so regenerating them does not create formatting-only churn.
    data = data.replace(b" />", b"/>")
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    data = data.replace(b"\n", b"\r\n")
    return data if data.endswith(b"\r\n") else data + b"\r\n"


def _project_element_signature(element: ET.Element) -> tuple[Any, ...]:
    """Return the complete XML content used by extraction postconditions."""

    return (
        element.tag,
        tuple(sorted(element.attrib.items())),
        element.text,
        element.tail,
        tuple(_project_element_signature(child) for child in element),
    )


def _copy_project_element(element: ET.Element) -> ET.Element:
    """Deep-copy one project element and verify that no content was lost.

    Component configuration is stored in child ``a`` elements rather than in
    the component's XML attributes.  Keeping the copy operation explicit here
    prevents an extractor refactor from retaining only ``lib``, ``loc``, and
    ``name`` while silently turning constants, buses, and labelled components
    back into their library defaults.
    """

    copied = deepcopy(element)
    if _project_element_signature(copied) != _project_element_signature(element):
        raise CircuitError("Logisim project element changed while being copied")
    return copied


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
    root = _read_project(project_path)
    circuits = {circuit.get("name", ""): circuit for circuit in root.findall("circuit")}
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

    main = root.find("main")
    if main is None:
        raise CircuitError(f"{project_path} has no main circuit declaration")

    destination = Path(output_directory)
    destination.mkdir(parents=True, exist_ok=True)
    prefix = project_path.stem
    written: list[Path] = []
    for name in leaf_names:
        # Build a fresh project instead of deleting circuit byte ranges from
        # the source document.  This prevents root text, comments, processing
        # instructions, or unknown tool output from leaking into a diagnostic
        # project.  Only library declarations, one main declaration, and the
        # selected circuit belong in a standalone diagnostic.  In particular,
        # do not carry root text or optional/unknown project sections across.
        standalone = ET.Element("project", root.attrib)
        for library in root.findall("lib"):
            standalone.append(_copy_project_element(library))
        standalone_main = _copy_project_element(main)
        standalone_main.set("name", name)
        standalone.append(standalone_main)
        standalone.append(_copy_project_element(circuits[name]))
        ET.indent(standalone, space="  ")
        xml = ET.tostring(
            standalone,
            encoding="utf-8",
            xml_declaration=True,
            short_empty_elements=True,
        )
        target = destination / f"{prefix}-{name}.circ"
        target.write_bytes(_serialize_standalone_logisim_project(xml))
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
