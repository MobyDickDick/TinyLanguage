import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tiny_cpu_assembler import assemble
from tiny_cpu_isa import INSTRUCTION_SET, Instruction
from tiny_cpu_machine import (
    OPCODES,
    WORD_BITS,
    MachineCodeError,
    decode_word,
    encode_instruction,
    encode_program,
    rom_image,
)
from tiny_cpu_verify import VerificationError, verify_checkout

PROJECT = Path(__file__).parents[2] / "hardware" / "logisim" / "TinyCPU.circ"
HARDWARE = PROJECT.parent
INTEGRATION_CLOCK = HARDWARE / "diagnostics" / "TinyCPU-IntegrationClock.circ"
INTEGRATION_RESET = HARDWARE / "diagnostics" / "TinyCPU-IntegrationReset.circ"
CI_WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"


def _attributes(component):
    return {attribute.get("name"): attribute.get("val") for attribute in component}


def _electrical_adjacency(circuit, extra_points=()):
    """Return Logisim connectivity, including junctions and named tunnels.

    A wire endpoint that touches the middle of another wire creates a junction
    in Logisim.  Merely comparing the declared endpoint pairs misses those
    T-junctions and can therefore hide accidental wired-OR decoder outputs.
    """

    def coordinates(location):
        x, y = location.strip("()").split(",")
        return int(x), int(y)

    wires = [(wire.get("from"), wire.get("to")) for wire in circuit.findall("wire")]
    endpoints = {endpoint for wire in wires for endpoint in wire} | set(extra_points)
    adjacency = {endpoint: set() for endpoint in endpoints}
    for start, end in wires:
        start_x, start_y = coordinates(start)
        end_x, end_y = coordinates(end)
        points = []
        for endpoint in endpoints:
            x, y = coordinates(endpoint)
            if start_x == end_x == x and min(start_y, end_y) <= y <= max(start_y, end_y):
                points.append(endpoint)
            elif start_y == end_y == y and min(start_x, end_x) <= x <= max(start_x, end_x):
                points.append(endpoint)
        points.sort(key=coordinates)
        for left, right in zip(points, points[1:]):
            adjacency[left].add(right)
            adjacency[right].add(left)

    tunnels = {}
    for component in circuit.findall("comp"):
        if component.get("name") == "Tunnel":
            tunnels.setdefault(_attributes(component).get("label"), []).append(
                component.get("loc")
            )
    for locations in tunnels.values():
        for left, right in zip(locations, locations[1:]):
            adjacency.setdefault(left, set()).add(right)
            adjacency.setdefault(right, set()).add(left)
    return adjacency


def test_electrical_adjacency_splits_wires_at_component_contacts():
    """A component port can touch the middle of an unsplit Logisim wire."""

    circuit = ET.fromstring(
        '<circuit><wire from="(0,10)" to="(20,10)"/></circuit>'
    )
    adjacency = _electrical_adjacency(circuit, {"(10,10)"})

    assert "(10,10)" in _reachable(adjacency, "(0,10)")
    assert "(20,10)" in _reachable(adjacency, "(10,10)")


def test_integration_clock_fans_out_one_net_to_every_stateful_block():
    """Start top-level integration with a small, independently loadable net."""

    circuit = ET.parse(INTEGRATION_CLOCK).getroot().find("circuit")
    pins = {
        _attributes(component)["label"]: component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
    }
    assert set(pins) == {
        "CLK",
        "FETCH_CLK",
        "DATAPATH_CLK",
        "ADDRESS_CLK",
        "MEMORY_CLK",
        "ERROR_FLAGS_CLK",
    }

    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    reachable = {pins["CLK"]}
    pending = [pins["CLK"]]
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert set(pins.values()) <= reachable


def test_stateful_blocks_expose_named_clock_inputs():
    """Validate the clock contract without guessing automatic-symbol geometry."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    for name in ("FetchDecode", "Datapath", "AddressPath", "Memory", "ErrorFlags"):
        clocks = [
            component
            for component in circuits[name].findall("comp")
            if component.get("name") == "Pin"
            and _attributes(component).get("label") == "CLK"
            and _attributes(component).get("type", "input") == "input"
        ]
        assert len(clocks) == 1, name


def test_integration_reset_connects_external_reset_to_fetch_only():
    """Reset restarts the PC without implicitly clearing RAM or error flags."""

    circuit = ET.parse(INTEGRATION_RESET).getroot().find("circuit")
    pins = {
        _attributes(component)["label"]: component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
    }
    assert pins == {"RESET": "(120,140)", "FETCH_RESET": "(420,140)"}
    assert {
        frozenset((wire.get("from"), wire.get("to")))
        for wire in circuit.findall("wire")
    } == {frozenset(pins.values())}


def test_fetch_decode_alone_exposes_named_reset_input():
    """Keep reset ownership explicit without inferring a rendered terminal."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    reset_owners = {
        name
        for name, circuit in circuits.items()
        if any(
            component.get("name") == "Pin"
            and _attributes(component).get("label") == "RESET"
            for component in circuit.findall("comp")
        )
    }
    assert reset_owners == {"TinyCPU", "FetchDecode", "IntegrationReset"}


def test_top_level_opcode_reaches_decode_controls_only():
    """Start decode integration with the independently named opcode bus."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(item for item in root.findall("circuit") if item.get("name") == "TinyCPU")
    controls = [
        component
        for component in circuit.findall("comp")
        if component.get("name") == "FetchDecodeControls"
    ]
    assert [component.get("loc") for component in controls] == ["(650,480)"]

    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    # The 22-bit machine word is split before the six opcode bits reach the
    # controls block. Bits 21..16 form the decoder input; the operand remains
    # deliberately unconnected until the data-bus integration steps.
    opcode_source = "(340,150)"
    splitter_input = "(350,150)"
    reachable = {opcode_source}
    pending = list(reachable)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert splitter_input in reachable
    decoder_side = {"(370,140)"}
    pending = list(decoder_side)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in decoder_side:
                decoder_side.add(endpoint)
                pending.append(endpoint)
    assert "(430,480)" in decoder_side
    splitter = next(
        component
        for component in circuit.findall("comp")
        if component.get("name") == "Splitter"
    )
    splitter_attributes = _attributes(splitter)
    assert splitter_attributes["incoming"] == "22"
    assert {
        bit for bit in range(22) if splitter_attributes.get(f"bit{bit}") == "1"
    } == set(range(16, 22))
    assert reachable.isdisjoint({"(80,70)", "(80,160)"})


def test_top_level_clear_error_reaches_error_flags_only():
    """Route one decoded control without coupling it to clock or reset."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(
        item for item in root.findall("circuit") if item.get("name") == "TinyCPU"
    )
    clear_source = _control_output(root, "CLEAR_ERROR")
    clear_target = _subcircuit_input(root, "ErrorFlags", "CLEAR_ERROR")
    adjacency = _electrical_adjacency(circuit, {clear_source, clear_target})
    reachable = {clear_source}
    pending = list(reachable)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert clear_target in reachable
    forbidden = {
        component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("label") in {"CLK", "RESET"}
    } | {
        _subcircuit_input(root, "Datapath", "DATA_IN"),
    }
    assert reachable.isdisjoint(forbidden)


def test_top_level_set_ovf_reaches_error_flags_only():
    """Route one sticky-error set control without joining existing nets."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(
        item for item in root.findall("circuit") if item.get("name") == "TinyCPU"
    )
    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    # SET_OVF is output 46 on the automatic FetchDecodeControls symbol; the
    # matching ErrorFlags input follows CLK and CLEAR_ERROR on its symbol.
    set_ovf_source = "(650,1380)"
    set_ovf_target = "(1530,120)"
    reachable = {set_ovf_source}
    pending = list(reachable)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert set_ovf_target in reachable
    assert reachable.isdisjoint(
        {
            "(80,70)",  # CLK
            "(80,160)",  # RESET
            "(430,370)",  # FetchDecodeControls.OPCODE
            "(650,1150)",  # FetchDecodeControls.CLEAR_ERROR
            "(1350,100)",  # ErrorFlags.CLK
            "(1350,80)",  # ErrorFlags.CLEAR_ERROR
        }
    )


def test_top_level_set_div0_reaches_error_flags_only():
    """Route the divide-by-zero set control on an isolated top-level net."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(
        item for item in root.findall("circuit") if item.get("name") == "TinyCPU"
    )
    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    # SET_DIV0 immediately follows SET_OVF on both automatic symbols.
    set_div0_source = "(650,1400)"
    set_div0_target = "(1530,140)"
    reachable = {set_div0_source}
    pending = list(reachable)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert set_div0_target in reachable
    assert reachable.isdisjoint(
        {
            "(80,70)",  # CLK
            "(80,160)",  # RESET
            "(430,370)",  # FetchDecodeControls.OPCODE
            "(650,1150)",  # FetchDecodeControls.CLEAR_ERROR
            "(650,1270)",  # FetchDecodeControls.SET_OVF
            "(1350,100)",  # ErrorFlags.CLK
            "(1350,80)",  # ErrorFlags.CLEAR_ERROR
            "(1350,120)",  # ErrorFlags.SET_OVF
        }
    )


@pytest.mark.parametrize(
    ("name", "source", "target"),
    [
        ("SET_ADDR", "(650,1420)", "(1530,160)"),
        ("SET_INV", "(650,1440)", "(1530,180)"),
        ("SET_ILL", "(650,1460)", "(1530,200)"),
        ("SET_INPUT", "(650,1480)", "(1530,220)"),
    ],
)
def test_remaining_error_controls_reach_matching_error_flags_only(
    name, source, target
):
    """Every remaining error control has one dedicated top-level net."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(
        item for item in root.findall("circuit") if item.get("name") == "TinyCPU"
    )
    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    reachable = {source}
    pending = list(reachable)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert target in reachable, name
    all_control_terminals = {
        "(650,1150)",
        "(650,1270)",
        "(650,1290)",
        "(650,1310)",
        "(650,1330)",
        "(650,1350)",
        "(650,1370)",
        "(1350,80)",
        "(1350,120)",
        "(1350,140)",
        "(1350,160)",
        "(1350,180)",
        "(1350,200)",
        "(1350,220)",
    }
    assert reachable.isdisjoint(
        {"(80,70)", "(80,160)", "(430,370)", "(1350,100)"}
        | (all_control_terminals - {source, target})
    ), name


ACCUMULATOR_FAMILIES = ("LOAD", "ADD", "SUB", "MUL", "DIV", "AND", "OR")
ACCUMULATOR_ADDRESSING_MODES = (
    "CONST",
    "ADDRESS",
    "ADDRESS_REGISTER",
    "ADDRESS_REGISTER_PLUS_OFFSET",
)
ACCUMULATOR_FAMILY_CONTROLS = tuple(
    f"{family}_{mode}"
    for family in ACCUMULATOR_FAMILIES
    for mode in ACCUMULATOR_ADDRESSING_MODES
)


def _top_level(root):
    return next(
        circuit for circuit in root.findall("circuit") if circuit.get("name") == "TinyCPU"
    )


def _labelled_component(circuit, label):
    matches = [
        component
        for component in circuit.findall("comp")
        if _attributes(component).get("label") == label
    ]
    assert len(matches) == 1, label
    return matches[0]


def _accumulator_selectors(circuit):
    """Return the three 16-bit accumulator muxes in signal-flow order.

    Logisim may omit cosmetic component labels when a hand-edited project is
    saved.  The mux identity must therefore not depend on those labels alone.
    """

    muxes = [
        component
        for component in circuit.findall("comp")
        if component.get("name") == "Multiplexer"
        and _attributes(component).get("width") == "16"
    ]
    assert len(muxes) == 3
    return sorted(
        muxes,
        key=lambda component: int(component.get("loc").strip("()").split(",")[0]),
    )


def _accumulator_validity_selectors(circuit):
    """Return the one-bit validity muxes in signal-flow order."""

    muxes = [
        component
        for component in circuit.findall("comp")
        if component.get("name") == "Multiplexer"
        and _attributes(component).get("width", "1") == "1"
        and int(component.get("loc").strip("()").split(",")[0]) < 1000
    ]
    assert len(muxes) == 4
    return sorted(
        muxes,
        key=lambda component: int(component.get("loc").strip("()").split(",")[0]),
    )


def _control_output(root, label):
    """Resolve a generated-symbol output by its pin name, not a fixed point."""

    definition = next(
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == "FetchDecodeControls"
    )
    outputs = sorted(
        (
            component
            for component in definition.findall("comp")
            if component.get("name") == "Pin"
            and _attributes(component).get("type") == "output"
        ),
        key=lambda component: tuple(
            int(value) for value in component.get("loc").strip("()").split(",")
        )[::-1],
    )
    index = next(
        index
        for index, component in enumerate(outputs)
        if _attributes(component).get("label") == label
    )
    instance = next(
        component
        for component in _top_level(root).findall("comp")
        if component.get("name") == "FetchDecodeControls"
    )
    x, y = (int(value) for value in instance.get("loc").strip("()").split(","))
    return f"({x},{y + 20 * index})"


def _instruction_field_output(root, bits):
    """Resolve an instruction-splitter branch from its declared bit mapping."""

    splitter = next(
        component
        for component in _top_level(root).findall("comp")
        if component.get("name") == "Splitter"
    )
    attributes = _attributes(splitter)
    branches = {}
    for bit in range(int(attributes["incoming"])):
        branch = int(attributes.get(f"bit{bit}", "0"))
        branches.setdefault(branch, set()).add(bit)
    branch = next(
        index
        for index, mapped_bits in branches.items()
        if mapped_bits == set(bits)
    )
    x, y = (int(value) for value in splitter.get("loc").strip("()").split(","))
    return f"({x + 20},{y - 10 * len(branches) + 10 * branch})"


def _subcircuit_input(root, circuit_name, pin_label):
    """Resolve an automatic-symbol input from the named subcircuit pin."""

    definition = next(
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == circuit_name
    )
    inputs = sorted(
        (
            component
            for component in definition.findall("comp")
            if component.get("name") == "Pin"
            and _attributes(component).get("type", "input") == "input"
        ),
        key=lambda component: tuple(
            int(value) for value in component.get("loc").strip("()").split(",")
        )[::-1],
    )
    index = next(
        index
        for index, component in enumerate(inputs)
        if _attributes(component).get("label") == pin_label
    )
    instance = next(
        component
        for component in _top_level(root).findall("comp")
        if component.get("name") == circuit_name
    )
    x, y = (int(value) for value in instance.get("loc").strip("()").split(","))
    return f"({x - 220},{y + 20 * index})"


def _subcircuit_output(root, circuit_name, pin_label):
    """Resolve an automatic-symbol output from the named subcircuit pin."""

    definition = next(
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == circuit_name
    )
    outputs = sorted(
        (
            component
            for component in definition.findall("comp")
            if component.get("name") == "Pin"
            and _attributes(component).get("type") == "output"
        ),
        key=lambda component: tuple(
            int(value) for value in component.get("loc").strip("()").split(",")
        )[::-1],
    )
    index = next(
        index
        for index, component in enumerate(outputs)
        if _attributes(component).get("label") == pin_label
    )
    instance = next(
        component
        for component in _top_level(root).findall("comp")
        if component.get("name") == circuit_name
    )
    x, y = (int(value) for value in instance.get("loc").strip("()").split(","))
    return f"({x},{y + 20 * index})"


def _gate_ports(component):
    """Resolve an OR gate's output and inputs from its declared fan-in."""

    x, y = (int(value) for value in component.get("loc").strip("()").split(","))
    count = int(_attributes(component).get("inputs", "2"))
    if count > 8:
        offsets = range(-(count // 2) * 10, (count // 2) * 10, 10)
    else:
        offsets = ((index - (count - 1) / 2) * 20 for index in range(count))
    inputs = {f"({x - 50},{int(y + offset)})" for offset in offsets}
    return f"({x},{y})", inputs


def _reachable(adjacency, start):
    result = {start}
    pending = [start]
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in result:
                result.add(endpoint)
                pending.append(endpoint)
    return result


def test_top_level_accumulator_family_controls_are_independent_connections():
    """Connect every family control by name without freezing drawing coordinates."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    family_gate = _labelled_component(circuit, "ACC_LOAD_REQUEST")
    _, family_inputs = _gate_ports(family_gate)
    sources = {name: _control_output(root, name) for name in ACCUMULATOR_FAMILY_CONTROLS}

    connected_inputs = {}
    for name, source in sources.items():
        reachable = _reachable(adjacency, source)
        matches = reachable & family_inputs
        assert len(matches) == 1, name
        connected_inputs[name] = matches.pop()
        assert reachable.isdisjoint(set(sources.values()) - {source}), name

    assert len(set(connected_inputs.values())) == len(ACCUMULATOR_FAMILY_CONTROLS)
    assert set(connected_inputs.values()) <= family_inputs


def test_top_level_non_family_write_controls_use_separate_gate_connections():
    """Keep the family request, NOT, and INPUT on three distinct named nets."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    family_gate = _labelled_component(circuit, "ACC_LOAD_REQUEST")
    write_gate = _labelled_component(circuit, "ACC_WRITE_REQUEST")
    family_output, _ = _gate_ports(family_gate)
    write_output, write_inputs = _gate_ports(write_gate)
    causes = {
        "ACC_LOAD_REQUEST": family_output,
        "NOT": _control_output(root, "NOT"),
        "INPUT": _control_output(root, "INPUT"),
    }

    connected_inputs = {}
    for name, source in causes.items():
        reachable = _reachable(adjacency, source)
        matches = reachable & write_inputs
        assert len(matches) == 1, name
        connected_inputs[name] = matches.pop()
        assert reachable.isdisjoint(set(causes.values()) - {source}), name
        assert write_output not in reachable, name

    assert len(set(connected_inputs.values())) == 3
    assert set(connected_inputs.values()) == write_inputs
    assert len(_reachable(adjacency, write_output)) > 1


def test_top_level_accumulator_data_selector_keeps_sources_isolated():
    """Select memory for three load modes without shorting data or controls."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    mux, not_mux, input_mux = _accumulator_selectors(circuit)
    memory_select_gate = _labelled_component(circuit, "ACC_MEMORY_SELECT")
    assert mux.get("name") == "Multiplexer"
    assert _attributes(mux).get("width") == "16"
    assert memory_select_gate.get("name") == "OR Gate"

    x, y = (int(value) for value in mux.get("loc").strip("()").split(","))
    mux_output = f"({x},{y})"
    mux_inputs = {f"({x - 30},{y - 10})", f"({x - 30},{y + 10})"}
    mux_select = f"({x - 20},{y + 20})"
    operand = _instruction_field_output(root, range(16))
    memory_data = _subcircuit_output(root, "Memory", "DATA_OUT")
    data_in = _subcircuit_input(root, "Datapath", "DATA_IN")
    not_mux_x, not_mux_y = (
        int(value) for value in not_mux.get("loc").strip("()").split(",")
    )
    not_mux_inputs = {
        f"({not_mux_x - 30},{not_mux_y - 10})",
        f"({not_mux_x - 30},{not_mux_y + 10})",
    }
    not_mux_output = f"({not_mux_x},{not_mux_y})"
    adjacency = _electrical_adjacency(
        circuit,
        mux_inputs
        | {mux_output, mux_select, data_in, not_mux_output}
        | not_mux_inputs,
    )

    operand_reachable = _reachable(adjacency, operand)
    memory_reachable = _reachable(adjacency, memory_data)
    assert len(operand_reachable & mux_inputs) == 1
    assert len(memory_reachable & mux_inputs) == 1
    assert (operand_reachable & mux_inputs) != (memory_reachable & mux_inputs)
    assert memory_data not in operand_reachable
    assert len(_reachable(adjacency, mux_output) & not_mux_inputs) == 1
    input_mux_x, input_mux_y = (
        int(value) for value in input_mux.get("loc").strip("()").split(",")
    )
    input_mux_inputs = {
        f"({input_mux_x - 30},{input_mux_y - 10})",
        f"({input_mux_x - 30},{input_mux_y + 10})",
    }
    assert len(_reachable(adjacency, not_mux_output) & input_mux_inputs) == 1
    assert data_in in _reachable(adjacency, f"({input_mux_x},{input_mux_y})")

    select_output, select_inputs = _gate_ports(memory_select_gate)
    select_causes = {
        name: _control_output(root, name)
        for name in (
            "LOAD_ADDRESS",
            "LOAD_ADDRESS_REGISTER",
            "LOAD_ADDRESS_REGISTER_PLUS_OFFSET",
        )
    }
    connected_inputs = {}
    for name, source in select_causes.items():
        reachable = _reachable(adjacency, source)
        matches = reachable & select_inputs
        assert len(matches) == 1, name
        connected_inputs[name] = matches.pop()
        assert reachable.isdisjoint(set(select_causes.values()) - {source}), name
        assert reachable.isdisjoint(mux_inputs | {mux_output, data_in}), name
    assert len(set(connected_inputs.values())) == len(select_causes)
    assert set(connected_inputs.values()) == select_inputs
    assert mux_select in _reachable(adjacency, select_output)
    assert _instruction_field_output(root, range(16, 22)) not in operand_reachable
    assert _subcircuit_input(root, "Datapath", "ACC_LOAD") not in operand_reachable
    assert _subcircuit_input(root, "Datapath", "VALID_IN") not in operand_reachable

    address_outputs = {
        _subcircuit_output(root, "AddressPath", label)
        for label in ("ADDRESS", "ADDRESS_PLUS_OFFSET")
    }
    data_nets = operand_reachable | memory_reachable | _reachable(adjacency, data_in)
    assert data_nets.isdisjoint(address_outputs)


def test_top_level_input_value_is_selected_only_for_input():
    """Route the external 16-bit value through a dedicated final selector."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    _, not_mux, input_mux = _accumulator_selectors(circuit)
    x, y = (int(value) for value in input_mux.get("loc").strip("()").split(","))
    inputs = {f"({x - 30},{y - 10})", f"({x - 30},{y + 10})"}
    select = f"({x - 20},{y + 20})"
    output = f"({x},{y})"
    not_output = not_mux.get("loc")
    input_pin = _labelled_component(circuit, "INPUT_VALUE")
    assert _attributes(input_pin).get("width") == "16"
    prior_matches = _reachable(adjacency, not_output) & inputs
    external_matches = _reachable(adjacency, input_pin.get("loc")) & inputs
    assert len(prior_matches) == 1
    assert len(external_matches) == 1
    assert prior_matches != external_matches
    assert select in _reachable(adjacency, _control_output(root, "INPUT"))
    assert _subcircuit_input(root, "Datapath", "DATA_IN") in _reachable(
        adjacency, output
    )
    assert _control_output(root, "NOT") not in _reachable(
        adjacency, input_pin.get("loc")
    )


def test_top_level_input_validity_is_selected_only_for_input():
    """Propagate external validity only while INPUT writes the accumulator."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    _, _, _, selector = _accumulator_validity_selectors(circuit)
    assert selector.get("name") == "Multiplexer"
    assert _attributes(selector).get("width", "1") == "1"

    x, y = (int(value) for value in selector.get("loc").strip("()").split(","))
    inputs = {f"({x - 30},{y - 10})", f"({x - 30},{y + 10})"}
    select = f"({x - 20},{y + 20})"
    output = f"({x},{y})"
    input_valid = _labelled_component(circuit, "INPUT_VALID")
    memory_selector, not_selector, add_selector, _ = _accumulator_validity_selectors(circuit)
    adjacency = _electrical_adjacency(
        circuit, inputs | {select, output, input_valid.get("loc")}
    )

    default_matches = _reachable(adjacency, add_selector.get("loc")) & inputs
    external_matches = _reachable(adjacency, input_valid.get("loc")) & inputs
    assert len(default_matches) == len(external_matches) == 1
    assert default_matches != external_matches
    assert select in _reachable(adjacency, _control_output(root, "INPUT"))
    assert _subcircuit_input(root, "Datapath", "VALID_IN") in _reachable(
        adjacency, output
    )
    assert _subcircuit_input(root, "Datapath", "DATA_IN") not in _reachable(
        adjacency, input_valid.get("loc")
    )


def test_top_level_memory_validity_is_selected_for_memory_loads():
    """Use memory validity exactly when the matching data selector uses RAM."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    selector, not_selector, add_selector, input_selector = _accumulator_validity_selectors(circuit)
    assert selector.get("name") == "Multiplexer"
    assert _attributes(selector).get("width", "1") == "1"

    x, y = (int(value) for value in selector.get("loc").strip("()").split(","))
    inputs = {f"({x - 30},{y - 10})", f"({x - 30},{y + 10})"}
    select = f"({x - 20},{y + 20})"
    output = f"({x},{y})"
    default_valid = next(
        component
        for component in circuit.findall("comp")
        if component.get("name") == "Constant"
        and _attributes(component).get("value") == "0x1"
    )
    memory_valid = _subcircuit_output(root, "Memory", "VALID_OUT")
    adjacency = _electrical_adjacency(
        circuit,
        inputs
        | {
            select,
            output,
            default_valid.get("loc"),
            memory_valid,
            not_selector.get("loc"),
        },
    )

    default_matches = _reachable(adjacency, default_valid.get("loc")) & inputs
    memory_matches = _reachable(adjacency, memory_valid) & inputs
    assert len(default_matches) == len(memory_matches) == 1
    assert default_matches != memory_matches
    memory_select_gate = _labelled_component(circuit, "ACC_MEMORY_SELECT")
    memory_select_output, _ = _gate_ports(memory_select_gate)
    assert select in _reachable(adjacency, memory_select_output)
    not_x, not_y = (
        int(value) for value in not_selector.get("loc").strip("()").split(",")
    )
    not_selector_inputs = {
        f"({not_x - 30},{not_y - 10})",
        f"({not_x - 30},{not_y + 10})",
    }
    assert len(_reachable(adjacency, output) & not_selector_inputs) == 1
    assert _subcircuit_input(root, "Datapath", "DATA_IN") not in _reachable(
        adjacency, memory_valid
    )


def test_top_level_not_propagates_accumulator_validity():
    """Select the current accumulator validity for the unary NOT result."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    memory_selector, selector, add_selector, input_selector = _accumulator_validity_selectors(
        circuit
    )
    x, y = (int(value) for value in selector.get("loc").strip("()").split(","))
    inputs = {f"({x - 30},{y - 10})", f"({x - 30},{y + 10})"}
    select = f"({x - 20},{y + 20})"
    output = selector.get("loc")
    accumulator_valid = _subcircuit_output(root, "Datapath", "ACC_VALID_OUT")
    adjacency = _electrical_adjacency(circuit, inputs | {select, output})

    prior_matches = _reachable(adjacency, memory_selector.get("loc")) & inputs
    accumulator_matches = _reachable(adjacency, accumulator_valid) & inputs
    assert len(prior_matches) == len(accumulator_matches) == 1
    assert prior_matches != accumulator_matches
    assert select in _reachable(adjacency, _control_output(root, "NOT"))

    input_x, input_y = (
        int(value) for value in input_selector.get("loc").strip("()").split(",")
    )
    input_selector_inputs = {
        f"({input_x - 30},{input_y - 10})",
        f"({input_x - 30},{input_y + 10})",
    }
    add_x, add_y = (int(value) for value in add_selector.get("loc").strip("()").split(","))
    add_inputs = {f"({add_x - 30},{add_y - 10})", f"({add_x - 30},{add_y + 10})"}
    assert len(_reachable(adjacency, output) & add_inputs) == 1
    assert len(_reachable(adjacency, add_selector.get("loc")) & input_selector_inputs) == 1
    assert _subcircuit_input(root, "Datapath", "VALID_IN") in _reachable(
        adjacency, input_selector.get("loc")
    )


def test_top_level_add_propagates_both_operand_validities():
    """ADD is valid only when the accumulator and selected operand are valid."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    memory_gate = _labelled_component(circuit, "ACC_ADD_MEMORY_SELECT")
    family_gate = _labelled_component(circuit, "ACC_ADD_SELECT")
    operand_selector = _labelled_component(circuit, "ACC_ADD_OPERAND_VALID_SELECT")
    valid_gate = _labelled_component(circuit, "ACC_ADD_VALID")
    _, memory_inputs = _gate_ports(memory_gate)
    _, family_inputs = _gate_ports(family_gate)

    controls = {name: _control_output(root, name) for name in (
        "ADD_CONST", "ADD_ADDRESS", "ADD_ADDRESS_REGISTER",
        "ADD_ADDRESS_REGISTER_PLUS_OFFSET",
    )}
    for name, source in controls.items():
        reachable = _reachable(adjacency, source)
        assert len(reachable & family_inputs) == 1
        if name != "ADD_CONST":
            assert len(reachable & memory_inputs) == 1

    mux_x, mux_y = (int(value) for value in operand_selector.get("loc").strip("()").split(","))
    mux_inputs = {f"({mux_x - 30},{mux_y - 10})", f"({mux_x - 30},{mux_y + 10})"}
    assert len(_reachable(adjacency, _subcircuit_output(root, "Memory", "VALID_OUT")) & mux_inputs) == 1
    gate_output, gate_inputs = _gate_ports(valid_gate)
    assert len(_reachable(adjacency, operand_selector.get("loc")) & gate_inputs) == 1
    assert len(_reachable(adjacency, _subcircuit_output(root, "Datapath", "ACC_VALID_OUT")) & gate_inputs) == 1
    _, _, add_selector, _ = _accumulator_validity_selectors(circuit)
    add_x, add_y = (int(value) for value in add_selector.get("loc").strip("()").split(","))
    assert len(_reachable(adjacency, gate_output) & {f"({add_x - 30},{add_y - 10})", f"({add_x - 30},{add_y + 10})"}) == 1

def test_top_level_uses_the_corrected_direct_data_routes():
    """Do not reintroduce the obsolete tunnel endpoints from the old drawing."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    obsolete_labels = {"INPUT_VALUE_NET", "ACC_DATA_BUS", "INPUT_SELECT_NET"}
    actual = {
        _attributes(component).get("label")
        for component in circuit.findall("comp")
        if component.get("name") == "Tunnel"
    }
    assert actual.isdisjoint(obsolete_labels)


def test_top_level_accumulator_data_bus_reaches_the_corrected_terminal():
    """Follow the hand-corrected direct route to the visible data terminal."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    data_input = _subcircuit_input(root, "Datapath", "DATA_IN")
    _, _, input_mux = _accumulator_selectors(circuit)
    assert data_input in _reachable(adjacency, input_mux.get("loc"))


def test_top_level_not_data_selector_uses_inverted_accumulator():
    """Select an isolated, bitwise-inverted accumulator only for ``NOT``."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    inverter = _labelled_component(circuit, "ACC_NOT_VALUE")
    _, mux, _ = _accumulator_selectors(circuit)
    assert inverter.get("name") == "NOT Gate"
    assert _attributes(inverter).get("width") == "16"
    assert mux.get("name") == "Multiplexer"
    assert _attributes(mux).get("width") == "16"

    inverter_x, inverter_y = (
        int(value) for value in inverter.get("loc").strip("()").split(",")
    )
    inverter_input = f"({inverter_x - 30},{inverter_y})"
    inverter_output = f"({inverter_x},{inverter_y})"
    mux_x, mux_y = (int(value) for value in mux.get("loc").strip("()").split(","))
    mux_inputs = {f"({mux_x - 30},{mux_y - 10})", f"({mux_x - 30},{mux_y + 10})"}
    mux_select = f"({mux_x - 20},{mux_y + 20})"
    acc_out = _subcircuit_output(root, "Datapath", "ACC_OUT")
    not_control = _control_output(root, "NOT")
    data_in = _subcircuit_input(root, "Datapath", "DATA_IN")

    assert inverter_input in _reachable(adjacency, acc_out)
    inverted_reachable = _reachable(adjacency, inverter_output)
    assert len(inverted_reachable & mux_inputs) == 1
    assert mux_select in _reachable(adjacency, not_control)
    input_mux = _accumulator_selectors(circuit)[2]
    input_x, input_y = (
        int(value) for value in input_mux.get("loc").strip("()").split(",")
    )
    input_ports = {f"({input_x - 30},{input_y - 10})", f"({input_x - 30},{input_y + 10})"}
    assert len(_reachable(adjacency, f"({mux_x},{mux_y})") & input_ports) == 1
    assert data_in in _reachable(adjacency, f"({input_x},{input_y})")
    assert _control_output(root, "INPUT") not in _reachable(adjacency, not_control)


def test_ci_runs_the_fresh_checkout_hardware_verifier():
    """Keep the documented dependency-free acceptance command in the main gate."""

    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "Run TinyCPU hardware reproducibility gate" in workflow
    assert "PYTHONPATH=src python src/tiny_cpu_verify.py" in workflow


def test_logisim_starter_matches_default_hardware_profile():
    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}

    assert root.find("main").get("name") == "TinyCPU"
    assert {
        "TinyCPU",
        "Datapath",
        "AddressPath",
        "Memory",
        "ErrorFlags",
    } <= circuits.keys()

    datapath_registers = {
        _attributes(component).get("label"): _attributes(component).get("width", "1")
        for component in circuits["Datapath"].findall("comp")
        if component.get("name") == "Register"
    }
    address_registers = {
        _attributes(component).get("label"): _attributes(component).get("width", "1")
        for component in circuits["AddressPath"].findall("comp")
        if component.get("name") == "Register"
    }
    assert datapath_registers == {"ACC": "16", "ACC_VALID": "1"}
    assert address_registers == {"AR": "16", "AR_VALID": "1"}


def test_logisim_starter_has_parallel_valid_ram_and_all_error_flags():
    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}

    rams = {
        _attributes(component)["label"]: _attributes(component)
        for component in circuits["Memory"].findall("comp")
        if component.get("name") == "RAM"
    }
    assert rams["DATA_RAM"]["addrWidth"] == "12"
    assert rams["DATA_RAM"]["dataWidth"] == "16"
    assert rams["VALID_RAM"]["addrWidth"] == "12"
    assert rams["VALID_RAM"]["dataWidth"] == "1"

    labels = {
        _attributes(component).get("label")
        for component in circuits["ErrorFlags"].findall("comp")
        if component.get("name") == "Register"
    }
    assert labels == {"OVF", "DIV0", "ADDR", "INV", "ILL", "INPUT"}


def test_ap2_datapaths_are_wired_and_expose_status_and_offset_results():
    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}

    expected_outputs = {
        "Datapath": {"ACC_OUT", "ACC_VALID_OUT", "ZERO", "NEGATIVE"},
        "AddressPath": {
            "ADDRESS",
            "ADDRESS_VALID",
            "ADDRESS_PLUS_OFFSET",
            "OFFSET_CARRY",
        },
    }
    for circuit_name, labels in expected_outputs.items():
        circuit = circuits[circuit_name]
        output_labels = {
            _attributes(component).get("label")
            for component in circuit.findall("comp")
            if component.get("name") == "Pin"
            and _attributes(component).get("type") == "output"
        }
        assert labels <= output_labels
        assert circuit.findall("wire")

    assert any(
        component.get("name") == "Comparator"
        and _attributes(component).get("width") == "16"
        for component in circuits["Datapath"].findall("comp")
    )
    assert any(
        component.get("name") == "Adder"
        and _attributes(component).get("width") == "16"
        for component in circuits["AddressPath"].findall("comp")
    )


def test_address_path_uses_component_terminals_without_shorting_buses():
    """Pin coordinates, not symbol centres, define Logisim connections."""

    root = ET.parse(PROJECT).getroot()
    address = next(c for c in root.findall("circuit") if c.get("name") == "AddressPath")
    wires = {
        frozenset((wire.get("from"), wire.get("to")))
        for wire in address.findall("wire")
    }

    def has_wire(first, second):
        return frozenset((first, second)) in wires

    # With the logisim_evolution appearance, a register's ``loc`` is the
    # symbol's top-left corner, not a terminal.  D/Q are 30 px below it, WE is
    # 50 px below it and CLK is 70 px below it; Q is 60 px to the right.
    assert has_wire("(240,150)", "(340,150)")  # ADDRESS_IN -> AR.D
    assert has_wire("(280,170)", "(340,170)")  # AR_LOAD -> AR.WE
    assert has_wire("(320,190)", "(340,190)")  # CLK -> AR clock
    assert has_wire("(190,330)", "(340,330)")  # VALID_IN -> AR_VALID.D
    assert has_wire("(280,350)", "(340,350)")  # AR_LOAD -> AR_VALID.WE
    assert has_wire("(320,370)", "(340,370)")  # CLK -> AR_VALID clock

    # The address register output and OFFSET terminate at the adder's distinct
    # A and B pins. Neither input bus shares a segment with the other.
    assert has_wire("(400,150)", "(420,150)")  # AR.Q -> address net
    assert has_wire("(420,190)", "(480,190)")
    # OFFSET detours around AR's one-bit reset terminal at (370,210); a
    # straight bus here makes Logisim report incompatible 12/1-bit widths.
    assert has_wire("(190,240)", "(450,240)")
    assert has_wire("(450,210)", "(450,240)")
    assert has_wire("(450,210)", "(480,210)")
    assert has_wire("(520,200)", "(620,200)")
    # Carry-out is the one-bit terminal below the adder at (500,220), not a
    # point below its 12-bit sum output anchor.
    assert has_wire("(500,220)", "(500,250)")
    assert has_wire("(500,250)", "(620,250)")
    assert has_wire("(400,330)", "(630,330)")  # AR_VALID.Q -> output


def test_datapath_uses_register_terminals_instead_of_symbol_centres():
    """Both accumulator registers are wired at their actual left-side ports."""

    root = ET.parse(PROJECT).getroot()
    datapath = next(c for c in root.findall("circuit") if c.get("name") == "Datapath")
    endpoints = {
        point
        for wire in datapath.findall("wire")
        for point in (wire.get("from"), wire.get("to"))
    }

    # For east-facing registers, D, WE and CLK are 30 px left of Q, with
    # WE and CLK respectively 20 and 30 px below the Q coordinate.
    assert {"(270,130)", "(270,150)", "(270,170)"} <= endpoints
    assert {"(270,250)", "(270,270)", "(270,290)"} <= endpoints

    # The comparator receives ACC and the zero constant on separate 16-bit
    # inputs; neither is accidentally attached to a one-bit status output.
    assert {"(360,130)", "(360,170)", "(450,190)", "(480,190)"} <= endpoints


def test_ap3_memory_shares_address_write_enable_and_clock():
    root = ET.parse(PROJECT).getroot()
    memory = next(c for c in root.findall("circuit") if c.get("name") == "Memory")
    pins = {
        _attributes(component).get("label"): _attributes(component)
        for component in memory.findall("comp")
        if component.get("name") == "Pin"
    }
    assert pins["ADDRESS"]["width"] == "16"
    assert pins["DATA_IN"]["width"] == "16"
    assert pins["DATA_OUT"]["width"] == "16"
    assert {"VALID_IN", "WRITE_ENABLE", "CLK", "VALID_OUT"} <= pins.keys()

    endpoints = {
        point
        for wire in memory.findall("wire")
        for point in (wire.get("from"), wire.get("to"))
    }
    # Both RAMs receive the shared address, write-enable, and clock nets.
    assert {"(340,100)", "(340,240)"} <= endpoints
    assert {"(340,160)", "(340,320)"} <= endpoints
    assert {"(340,180)", "(340,300)"} <= endpoints
    # The validity value has its own one-bit input and output path.
    assert {"(330,290)", "(580,320)", "(600,320)"} <= endpoints


def test_ap3_error_flags_have_set_dominant_sticky_logic():
    root = ET.parse(PROJECT).getroot()
    errors = next(c for c in root.findall("circuit") if c.get("name") == "ErrorFlags")
    parts = {
        _attributes(component).get("label"): component.get("name")
        for component in errors.findall("comp")
        if _attributes(component).get("label")
    }
    flags = {"OVF", "DIV0", "ADDR", "INV", "ILL", "INPUT"}
    assert parts["NOT_CLEAR_ERROR"] == "NOT Gate"
    for flag in flags:
        assert parts[f"SET_{flag}"] == "Pin"
        assert parts[f"HOLD_{flag}"] == "AND Gate"
        assert parts[f"NEXT_{flag}"] == "OR Gate"
        assert parts[flag] == "Register"
        assert parts[f"{flag}_OUT"] == "Pin"


def test_ap3_error_flags_have_readable_lane_layout():
    root = ET.parse(PROJECT).getroot()
    errors = next(c for c in root.findall("circuit") if c.get("name") == "ErrorFlags")
    locations = {
        _attributes(component).get("label"): component.get("loc")
        for component in errors.findall("comp")
        if _attributes(component).get("label")
    }

    expected = {
        "OVF": ("(100,210)", "(500,250)", "(600,230)", "(750,200)", "(1000,230)"),
        "DIV0": ("(110,320)", "(500,360)", "(580,340)", "(750,310)", "(1000,340)"),
        "ADDR": ("(110,430)", "(510,470)", "(590,450)", "(750,420)", "(1000,450)"),
        "INV": ("(110,540)", "(500,580)", "(590,560)", "(750,530)", "(1000,560)"),
        "ILL": ("(110,650)", "(510,690)", "(600,670)", "(750,640)", "(1000,670)"),
        "INPUT": ("(120,760)", "(510,800)", "(610,780)", "(750,750)", "(1000,780)"),
    }
    for flag, (set_pin, hold, next_gate, register, output) in expected.items():
        assert locations[f"SET_{flag}"] == set_pin
        assert locations[f"HOLD_{flag}"] == hold
        assert locations[f"NEXT_{flag}"] == next_gate
        assert locations[flag] == register
        assert locations[f"{flag}_OUT"] == output


def test_ap3_error_flag_feedback_is_clocked_not_combinational():
    root = ET.parse(PROJECT).getroot()
    errors = next(c for c in root.findall("circuit") if c.get("name") == "ErrorFlags")
    wires = {(wire.get("from"), wire.get("to")) for wire in errors.findall("wire")}

    tunnels = {}
    for component in errors.findall("comp"):
        if component.get("name") == "Tunnel":
            label = _attributes(component).get("label")
            tunnels.setdefault(label, set()).add(component.get("loc"))

    expected_tunnels = {
        "OVF": {"(420,230)", "(830,270)"},
        "DIV0": {"(420,340)", "(830,370)"},
        "ADDR": {"(430,450)", "(840,470)"},
        "INV": {"(430,560)", "(830,580)"},
        "ILL": {"(440,680)", "(840,700)"},
        "INPUT": {"(440,780)", "(840,810)"},
    }
    for flag, locations in expected_tunnels.items():
        assert tunnels[f"CURRENT_{flag}"] == locations

    for register_y in (200, 310, 420, 530, 640, 750):
        assert (f"(730,{register_y + 50})", f"(750,{register_y + 50})") in wires

    graph = {}
    for start, end in wires:
        graph.setdefault(start, set()).add(end)
        graph.setdefault(end, set()).add(start)
    reachable = {"(100,160)"}
    pending = ["(100,160)"]
    while pending:
        for endpoint in graph.get(pending.pop(), ()):  # shared clock bus
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)
    assert {
        "(750,270)",
        "(750,380)",
        "(750,490)",
        "(750,600)",
        "(750,710)",
        "(750,820)",
    } <= reachable


def test_ap7_versioned_opcode_table_covers_the_symbolic_isa():
    table = json.loads((HARDWARE / "tinycpu-machine-v1.json").read_text())
    assert table["schema_version"] == 1
    assert table["word_bits"] == WORD_BITS
    assert {row["mnemonic"]: row["code"] for row in table["opcodes"]} == OPCODES
    assert set(OPCODES) == set(INSTRUCTION_SET)
    assert len(set(OPCODES.values())) == len(OPCODES)


def test_ap7_every_instruction_roundtrips_through_machine_code():
    examples = {"none": None, "value": -7, "address": 123, "offset": -3, "target": 17}
    for opcode, spec in INSTRUCTION_SET.items():
        instruction = Instruction(opcode, examples[spec.operand.value])
        assert decode_word(encode_instruction(instruction)) == instruction



@pytest.mark.parametrize("word", (0x3F0000, 0x2C0001, 1 << WORD_BITS))
def test_ap7_decoder_rejects_reserved_or_noncanonical_words(word):
    with pytest.raises(MachineCodeError):
        decode_word(word)


def test_ap8_fresh_checkout_verification_covers_all_deliverables():
    repository = PROJECT.parents[2]
    assert verify_checkout(repository) == (
        "hardware contract",
        "ROM and listing",
        "embedded ROM",
        "17-edge trace",
    )


def test_ap8_verification_reports_a_stale_generated_artifact(tmp_path):
    repository = tmp_path / "checkout"
    target = repository / "hardware" / "logisim"
    target.mkdir(parents=True)
    for artifact in HARDWARE.iterdir():
        if artifact.is_file():
            (target / artifact.name).write_bytes(artifact.read_bytes())
    (target / "ap5_countdown.rom").write_text("addr/data: 12 22\n", encoding="utf-8")

    with pytest.raises(VerificationError, match="ap5_countdown[.]rom"):
        verify_checkout(repository)
