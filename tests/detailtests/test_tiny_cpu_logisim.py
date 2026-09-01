import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tiny_cpu_assembler import assemble
from tiny_cpu_circuit import FETCH_DECODE_SIGNAL_LANES, inspect_project
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


def test_fetch_decode_controls_drives_jump_not_zero_lane():
    """Opcode 36 must reach a dedicated decoder-control output."""
    controls = ET.parse(PROJECT).getroot().find(
        "circuit[@name='FetchDecodeControls']"
    )
    assert controls is not None

    output = next(
        component
        for component in controls.findall("comp[@name='Pin']")
        if _attributes(component).get("label") == "JUMP_NOT_ZERO"
    )
    adjacency = _electrical_adjacency(controls, {"(520,390)", output.get("loc")})
    assert output.get("loc") in _reachable(adjacency, "(520,390)")


def test_jump_not_zero_pin_follows_jump_opcode_order():
    """Keep the redrawn control symbol's jump outputs together in ISA order.

    Logisim derives generated-symbol ports from the physical pin coordinates.
    The top-level routes therefore have to follow this accepted ordering rather
    than relying on the former final-slot exception for JUMP_NOT_ZERO.
    """

    controls = ET.parse(PROJECT).getroot().find(
        "circuit[@name='FetchDecodeControls']"
    )
    assert controls is not None
    output_labels = [
        _attributes(component).get("label")
        for component in sorted(
            (
                component
                for component in controls.findall("comp[@name='Pin']")
                if _attributes(component).get("type") == "output"
            ),
            key=lambda component: tuple(
                int(value)
                for value in component.get("loc").strip("()").split(",")
            )[::-1],
        )
    ]

    first_jump = output_labels.index("JUMP_ADR")
    assert output_labels[first_jump : first_jump + 6] == [
        "JUMP_ADR", "JUMP_ZERO", "JUMP_NOT_ZERO", "JUMP_NEGATIVE",
        "JUMP_ERROR", "JUMP_NOT_ERROR",
    ]


def test_jump_not_zero_decode_reaches_fetch_decode():
    """The dedicated decoder output must drive FetchDecode's DEC_JUMP_NOT_ZERO."""
    root = ET.parse(PROJECT).getroot()
    top = _top_level(root)
    source = _subcircuit_output(root, "FetchDecodeControls", "JUMP_NOT_ZERO")
    destination = _subcircuit_input(root, "FetchDecode", "DEC_JUMP_NOT_ZERO")
    adjacency = _electrical_adjacency(top, {source, destination})
    assert destination in _reachable(adjacency, source)


def test_fetch_decode_lanes_match_the_versioned_machine_opcodes():
    """Do not let symbolic output names drift one lane from the decoder."""

    assert FETCH_DECODE_SIGNAL_LANES == {
        signal: OPCODES[signal] for signal in FETCH_DECODE_SIGNAL_LANES
    }


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


def test_top_level_has_no_abandoned_upper_left_wire_tail():
    """Keep the removed L-shaped stub from returning beside the clock input."""

    circuit = _top_level(ET.parse(PROJECT).getroot())
    wires = {
        frozenset((wire.get("from"), wire.get("to")))
        for wire in circuit.findall("wire")
    }

    assert frozenset(("(210,250)", "(960,250)")) not in wires
    assert frozenset(("(960,250)", "(960,590)")) not in wires


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


def test_top_level_clock_reaches_every_stateful_block_without_joining_acc_valid():
    """All state clocks must share CLK, never accumulator validity."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    clock = next(
        component.get("loc")
        for component in circuit.findall("comp[@name='Pin']")
        if _attributes(component).get("label") == "CLK"
    )
    state_clocks = {
        _subcircuit_input(root, name, "CLK")
        for name in ("FetchDecode", "Datapath", "AddressPath", "Memory", "ErrorFlags")
    }
    acc_valid = _subcircuit_output(root, "Datapath", "ACC_VALID_OUT")
    adjacency = _electrical_adjacency(circuit, {clock, acc_valid} | state_clocks)

    clock_net = _reachable(adjacency, clock)
    assert state_clocks <= clock_net
    assert acc_valid not in clock_net


def test_maintained_projects_use_only_portable_wiring_components():
    """Do not persist PowerOnReset, which older Logisim versions reject."""

    projects = [PROJECT, *(HARDWARE / "diagnostics").glob("*.circ")]
    for project in projects:
        root = ET.parse(project).getroot()
        assert not root.findall(".//comp[@name='PowerOnReset']"), project


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


def test_fetch_decode_external_reset_reaches_pc_reset_directly():
    """RESET must clear the PC without a decorative constant or logic gate."""

    root = ET.parse(PROJECT).getroot()
    fetch = root.find("circuit[@name='FetchDecode']")
    assert fetch is not None
    reset = next(
        component.get("loc")
        for component in fetch.findall("comp[@name='Pin']")
        if _attributes(component).get("label") == "RESET"
    )
    assert fetch.find("comp[@name='Constant'][@loc='(300,240)']") is None
    assert not any(
        _attributes(component).get("label") == "PC_RESET"
        for component in fetch.findall("comp[@name='OR Gate']")
    )
    contacts = {reset, "(580,280)"}
    adjacency = _electrical_adjacency(fetch, contacts)
    assert "(580,280)" in _reachable(adjacency, reset)


def test_fetch_decode_range_error_uses_comparator_greater_output():
    """PC overflow, rather than PC equality, must request an error halt."""

    fetch = ET.parse(PROJECT).getroot().find("circuit[@name='FetchDecode']")
    assert fetch is not None
    comparator = fetch.find("comp[@name='Comparator'][@loc='(740,420)']")
    assert comparator is not None
    error_halt = _labelled_component(fetch, "ERROR_HALT")
    error_x, error_y = (
        int(value) for value in error_halt.get("loc").strip("()").split(",")
    )
    greater_output = "(740,410)"
    range_error_input = f"({error_x - 50},{error_y - 20})"
    adjacency = _electrical_adjacency(
        fetch, {greater_output, range_error_input}
    )
    assert range_error_input in _reachable(adjacency, greater_output)
    assert "(740,420)" not in _reachable(adjacency, "(740,410)")

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
    assert reset_owners == {"TinyCPUMain", "FetchDecode", "IntegrationReset"}


def test_fetch_decode_program_counter_is_enabled_and_incremented():
    """The autonomous clock must advance the PC rather than reload its value."""

    fetch = ET.parse(PROJECT).getroot().find("circuit[@name='FetchDecode']")
    assert fetch is not None
    enable = fetch.find("comp[@name='Constant'][@loc='(540,240)']")
    increment = fetch.find("comp[@name='Constant'][@loc='(710,240)']")
    assert _attributes(enable).get("value") == "0x1"
    assert _attributes(enable).get("width", "1") == "1"
    assert _attributes(increment).get("value") == "0x1"
    assert _attributes(increment).get("width") == "16"
    adjacency = _electrical_adjacency(fetch, {"(710,240)", "(730,240)", "(770,230)"})
    assert "(730,240)" in _reachable(adjacency, increment.get("loc"))

def test_program_counter_address_branch_reaches_rom_address_input():
    """Keep the 12-bit splitter branch on the terminal used by the ROM."""

    root = ET.parse(PROJECT).getroot()
    fetch = root.find("circuit[@name='FetchDecode']")
    assert fetch is not None
    splitter = next(
        component
        for component in fetch.findall("comp[@name='Splitter']")
        if _attributes(component).get("incoming") == "16"
    )
    attributes = _attributes(splitter)
    assert attributes.get("appear") == "right"
    assert all(attributes.get(f"bit{bit}", "0") == "0" for bit in range(12))
    assert all(attributes.get(f"bit{bit}") == "1" for bit in range(12, 16))
    adjacency = _electrical_adjacency(fetch, {"(720,560)", "(790,650)"})
    assert "(790,650)" in _reachable(adjacency, "(720,560)")


def test_fetch_decode_rom_drives_instruction_output():
    """Decoded controls must observe the word read from the program ROM."""

    fetch = ET.parse(PROJECT).getroot().find("circuit[@name='FetchDecode']")
    rom = fetch.find("comp[@name='ROM']")
    opcode = next(component for component in fetch.findall("comp[@name='Pin']") if _attributes(component).get("label") == "OPCODE")
    rom_x, rom_y = (int(value) for value in rom.get("loc").strip("()").split(","))
    address_input = f"({rom_x},{rom_y + 10})"
    data_output = f"({rom_x + 240},{rom_y + 60})"
    adjacency = _electrical_adjacency(fetch, {address_input, data_output, opcode.get("loc")})
    assert address_input == "(790,650)"
    assert data_output == "(1030,700)"
    assert opcode.get("loc") in _reachable(adjacency, data_output)
    assert address_input not in _reachable(adjacency, data_output)

def test_taken_jump_selects_instruction_operand_as_next_pc():
    """A taken JUMP_NOT_ZERO must replace PC + 1 with the encoded target."""

    fetch = ET.parse(PROJECT).getroot().find("circuit[@name='FetchDecode']")
    mux = fetch.find("comp[@name='Multiplexer']")
    assert mux is not None
    assert mux.get("loc") == "(870,240)"
    assert _attributes(mux).get("width") == "16"
    wires = {
        frozenset((wire.get("from"), wire.get("to")))
        for wire in fetch.findall("wire")
    }
    # The instruction splitter's operand output is at y=610.  The old y=580
    # endpoint was empty drawing space and left the lower mux input floating.
    assert frozenset(("(1070,610)", "(1320,610)")) in wires
    assert frozenset(("(1320,120)", "(1320,610)")) in wires
    assert frozenset(("(1070,580)", "(1420,580)")) not in wires
    assert frozenset(("(1420,120)", "(1420,580)")) not in wires
    jump_taken = next(
        component.get("loc")
        for component in fetch.findall("comp[@name='Pin']")
        if _attributes(component).get("label") == "JUMP_NOT_ZERO"
    )
    adjacency = _electrical_adjacency(
        fetch,
        {
            "(770,230)",
            "(840,230)",
            "(1070,610)",
            "(840,250)",
            jump_taken,
            "(850,260)",
            "(870,240)",
            "(550,220)",
        },
    )
    assert "(840,230)" in _reachable(adjacency, "(770,230)")
    assert "(840,250)" in _reachable(adjacency, "(1070,610)")
    assert jump_taken in _reachable(adjacency, "(850,260)")
    assert "(550,220)" in _reachable(adjacency, "(870,240)")
    assert "(840,250)" not in _reachable(adjacency, "(840,230)")
    assert "(850,260)" not in _reachable(adjacency, "(840,230)")
    assert "(850,260)" not in _reachable(adjacency, "(840,250)")
    assert "(870,240)" not in _reachable(adjacency, "(840,230)")
    assert "(870,240)" not in _reachable(adjacency, "(840,250)")
    assert "(870,240)" not in _reachable(adjacency, "(850,260)")


def test_jump_not_zero_receives_the_inverted_accumulator_status():
    """The JNZ condition must not float independently of the accumulator."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    inverter = _labelled_component(circuit, "INVERT_ZERO_FOR_JNZ")
    assert inverter.get("name") == "NOT Gate"
    assert _attributes(inverter).get("facing", "east") == "east"
    inverter_x, inverter_y = (
        int(value) for value in inverter.get("loc").strip("()").split(",")
    )
    inverter_input = f"({inverter_x - 30},{inverter_y})"
    assert inverter_input in _reachable(
        adjacency, _subcircuit_output(root, "Datapath", "ZERO")
    )
    assert _subcircuit_input(root, "FetchDecode", "NOT_ZERO") in _reachable(
        adjacency, inverter.get("loc")
    )
    assert not [
        component for component in circuit.findall("comp[@name='Tunnel']")
        if _attributes(component).get("label") == "NOT_ZERO_STATUS"
    ]

def test_signed_arithmetic_splitters_do_not_short_15_and_16_bit_buses():
    """Sign-bit taps must branch off, never sit inline with word-sized data."""

    root = ET.parse(PROJECT).getroot()
    for name in ("AddArithmeticCircuit", "SubArithmeticCircuit", "MulArithmeticCircuit"):
        circuit = root.find(f"circuit[@name='{name}']")
        assert circuit is not None
        contacts = {
            "(300,120)", "(370,120)", "(490,150)",
            "(330,200)", "(370,200)", "(490,170)",
            "(530,160)", "(640,160)", "(930,160)",
        }
        adjacency = _electrical_adjacency(circuit, contacts)

        assert "(490,150)" in _reachable(adjacency, "(300,120)")
        assert "(370,120)" not in _reachable(adjacency, "(300,120)")
        assert "(490,170)" in _reachable(adjacency, "(330,200)")
        assert "(370,200)" not in _reachable(adjacency, "(330,200)")
        result = next(component.get("loc") for component in circuit.findall("comp[@name='Pin']") if _attributes(component).get("label") == "RESULT")
        assert result in _reachable(adjacency, "(530,160)")
        assert "(640,160)" not in _reachable(adjacency, "(530,160)")


def test_top_level_opcode_reaches_decode_controls_only():
    """Resolve the opcode route from named pins and the splitter mapping."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    opcode_source = _subcircuit_output(root, "FetchDecode", "OPCODE")
    opcode_branch = _instruction_field_output(root, range(16, 22))
    opcode_target = _subcircuit_input(root, "FetchDecodeControls", "OPCODE")
    adjacency = _electrical_adjacency(
        circuit, {opcode_source, opcode_branch, opcode_target}
    )

    source_net = _reachable(adjacency, opcode_source)
    decoder_net = _reachable(adjacency, opcode_branch)
    assert opcode_branch not in source_net  # the splitter separates the fields
    assert opcode_target in decoder_net
    assert _instruction_field_output(root, range(16)) not in decoder_net
    external_controls = {
        component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("label") in {"CLK", "RESET"}
    }
    assert source_net.isdisjoint(external_controls)
    assert decoder_net.isdisjoint(external_controls)

def test_top_level_clear_error_reaches_error_flags_only():
    """Route one decoded control without coupling it to clock or reset."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(
        item
        for item in root.findall("circuit")
        if item.get("name") == "TinyCPUMain"
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


@pytest.mark.parametrize(
    "name", ("SET_OVF", "SET_ILL", "SET_INPUT")
)
def test_top_level_error_controls_reach_only_the_matching_error_input(name):
    """Resolve every error route by pin name, independent of drawing coordinates."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    sources = {
        label: _control_output(root, label)
        for label in (
            "CLEAR_ERROR", "SET_OVF", "SET_DIV0", "SET_ADDR",
            "SET_INV", "SET_ILL", "SET_INPUT",
        )
    }
    targets = {
        label: _subcircuit_input(root, "ErrorFlags", label)
        for label in sources
    }
    adjacency = _electrical_adjacency(
        circuit, set(sources.values()) | set(targets.values())
    )
    reachable = _reachable(adjacency, sources[name])

    assert targets[name] in reachable
    assert reachable.isdisjoint(set(sources.values()) - {sources[name]})
    assert reachable.isdisjoint(set(targets.values()) - {targets[name]})
    external_controls = {
        component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("label") in {"CLK", "RESET"}
    }
    assert reachable.isdisjoint(external_controls)


def test_active_offset_carry_sets_the_address_error_flag():
    """Only an active register-plus-offset carry replaces decoded SET_ADDR.

    The hand-maintained drawing may face this gate in either direction.  Resolve
    its terminals from that declared orientation rather than forcing the older
    west-facing placement back onto the compact, counter-clockwise route.
    """

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    carry = _subcircuit_output(root, "AddressPath", "OFFSET_CARRY")
    offset_active = _subcircuit_output(
        root, "EffectiveAddress", "EFFECTIVE_OFFSET_MODE"
    )
    address_error = _subcircuit_input(root, "ErrorFlags", "SET_ADDR")
    decoded_address_error = _control_output(root, "SET_ADDR")
    range_fbox = next(
        item for item in root.findall("circuit")
        if item.get("name") == "AddressRangeFBox"
    )
    gate = _labelled_component(range_fbox, "ACTIVE_OFFSET_ADDRESS_ERROR")
    assert gate.get("name") == "AND Gate"

    x, y = (int(value) for value in gate.get("loc").strip("()").split(","))
    # Logisim's default narrow two-input AND symbol places the terminals twenty
    # pixels above and below its centre (the generic helper models the wider
    # ten-pixel-spacing symbols used elsewhere in this project).
    gate_inputs = {f"({x - 50},{y - 20})", f"({x - 50},{y + 20})"}
    adjacency = _electrical_adjacency(range_fbox, gate_inputs)

    fbox_pins = {
        _attributes(component).get("label"): component.get("loc")
        for component in range_fbox.findall("comp")
        if component.get("name") == "Pin"
    }
    carry_net = _reachable(adjacency, fbox_pins["OFFSET_CARRY"])
    active_net = _reachable(
        adjacency,
        fbox_pins["EFFECTIVE_OFFSET_MODE"],
    )
    assert len(gate_inputs & carry_net) == 1
    assert len(gate_inputs & active_net) == 1
    assert carry_net.isdisjoint(active_net)
    integrated_error = _labelled_component(range_fbox, "ACTIVE_ADDRESS_ERROR")
    assert integrated_error.get("name") == "OR Gate"
    integrated_x, integrated_y = (
        int(value) for value in integrated_error.get("loc").strip("()").split(",")
    )
    integrated_inputs = {
        f"({integrated_x - 50},{integrated_y - 20})",
        f"({integrated_x - 50},{integrated_y + 20})",
    }
    assert len(
        integrated_inputs & _reachable(adjacency, gate.get("loc"))
    ) == 1

    top_adjacency = _electrical_adjacency(circuit)
    assert carry in _reachable(
        top_adjacency,
        _subcircuit_input(root, "AddressRangeFBox", "OFFSET_CARRY"),
    )
    assert offset_active in _reachable(
        top_adjacency,
        _subcircuit_input(root, "AddressRangeFBox", "EFFECTIVE_OFFSET_MODE"),
    )
    fbox_error = _subcircuit_output(
        root, "AddressRangeFBox", "ACTIVE_ADDRESS_OUT_OF_RANGE"
    )
    assert address_error in _reachable(top_adjacency, fbox_error)
    assert address_error not in _reachable(top_adjacency, decoded_address_error)


def test_effective_address_range_error_covers_every_memory_address_mode():
    """Reject active 16-bit addresses that do not fit the 12-bit memory."""

    root = ET.parse(PROJECT).getroot()
    effective = next(
        circuit for circuit in root.findall("circuit")
        if circuit.get("name") == "EffectiveAddress"
    )
    # The manually compacted sheet intentionally leaves these two primitive
    # components unlabelled; their type, width and unique constant value form
    # the stable electrical contract.
    comparators = [c for c in effective.findall("comp") if c.get("name") == "Comparator"]
    limits = [
        c for c in effective.findall("comp")
        if c.get("name") == "Constant" and _attributes(c).get("value") == "0xfff"
    ]
    assert len(comparators) == len(limits) == 1
    assert _attributes(comparators[0])["width"] == "16"
    assert _attributes(limits[0]) == {"value": "0xfff", "width": "16"}

    fbox = next(
        circuit for circuit in root.findall("circuit")
        if circuit.get("name") == "AddressRangeFBox"
    )
    direct = _labelled_component(fbox, "DIRECT_MEMORY_ADDRESS_ACTIVE")
    active = _labelled_component(fbox, "MEMORY_ADDRESS_ACTIVE")
    range_gate = _labelled_component(fbox, "ACTIVE_ADDRESS_RANGE_GATE")
    assert _attributes(direct)["inputs"] == "8"
    assert _attributes(active)["inputs"] == "3"
    assert range_gate.get("name") == "AND Gate"

    top = _top_level(root)
    instance = _labelled_component(top, "ADDRESS_RANGE_FBOX")
    assert instance.get("name") == "AddressRangeFBox"
    adjacency = _electrical_adjacency(top)
    for operation in ("LOAD", "ADD", "SUB", "MUL", "DIV", "AND", "OR", "STORE"):
        assert _subcircuit_input(
            root, "AddressRangeFBox", f"{operation}_ADDRESS"
        ) in _reachable(adjacency, _control_output(root, f"{operation}_ADDRESS"))
    for mode in ("EFFECTIVE_REGISTER_MODE", "EFFECTIVE_OFFSET_MODE"):
        assert _subcircuit_input(root, "AddressRangeFBox", mode) in _reachable(
            adjacency, _subcircuit_output(root, "EffectiveAddress", mode)
        )
    assert _subcircuit_input(
        root, "AddressRangeFBox", "ADDRESS_OUT_OF_RANGE"
    ) in _reachable(
        adjacency,
        _subcircuit_output(root, "EffectiveAddress", "ADDRESS_OUT_OF_RANGE"),
    )
    assert _subcircuit_input(root, "ErrorFlags", "SET_ADDR") in _reachable(
        adjacency,
        _subcircuit_output(root, "AddressRangeFBox", "ACTIVE_ADDRESS_OUT_OF_RANGE"),
    )


def test_decoded_error_placeholders_are_inactive():
    """Unused decoded error outputs must not continuously set sticky flags."""

    root = ET.parse(PROJECT).getroot()
    controls = next(
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == "FetchDecodeControls"
    )
    components = {component.get("loc"): component for component in controls.findall("comp")}
    wires = {
        (wire.get("from"), wire.get("to"))
        for wire in controls.findall("wire")
    }

    for label in ("SET_OVF", "SET_DIV0", "SET_ADDR", "SET_INV", "SET_ILL", "SET_INPUT"):
        output = next(
            component
            for component in controls.findall("comp")
            if component.get("name") == "Pin"
            and _attributes(component).get("label") == label
        )
        output_x, output_y = (
            int(value) for value in output.get("loc").strip("()").split(",")
        )
        source_location = f"({output_x - 40},{output_y})"
        source = components[source_location]

        assert source.get("name") == "Constant"
        assert _attributes(source).get("value") == "0x0"
        assert (source_location, output.get("loc")) in wires


def test_invalid_arithmetic_result_sets_the_invalid_operand_flag():
    """SET_INV comes from active invalid arithmetic, not a decoded constant."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    operation_invalid = _subcircuit_output(root, "Operations", "INVALID_OPERAND")
    invalid_target = _subcircuit_input(root, "ErrorFlags", "SET_INV")
    decoded_invalid = _control_output(root, "SET_INV")
    adjacency = _electrical_adjacency(
        circuit, {operation_invalid, invalid_target, decoded_invalid}
    )

    assert invalid_target in _reachable(adjacency, operation_invalid)
    assert invalid_target not in _reachable(adjacency, decoded_invalid)

    operations = next(
        item for item in root.findall("circuit") if item.get("name") == "Operations"
    )
    labels = {
        _attributes(component).get("label"): component
        for component in operations.findall("comp")
        if _attributes(component).get("label")
    }
    assert labels["ACTIVE_INVALID_OPERATION"].get("name") == "AND Gate"
    assert labels["OPERATION_IS_ACTIVE"].get("name") == "OR Gate"
    assert labels["OPERATION_RESULT_VALID"].get("name") == "OR Gate"


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
        circuit
        for circuit in root.findall("circuit")
        if circuit.get("name") == "TinyCPUMain"
    )


def _labelled_component(circuit, label):
    """Resolve a component by its stable schematic label, not its position."""

    matches = [
        component
        for component in circuit.findall("comp")
        if _attributes(component).get("label") == label
    ]
    assert len(matches) == 1, label
    return matches[0]

def test_top_level_does_not_restore_the_obsolete_accumulator_selector_chain():
    """Keep regressions aligned with the maintained direct data routes."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    labels = {
        _attributes(component).get("label")
        for component in circuit.findall("comp")
    }
    obsolete = {
        "ACC_MEMORY_DATA_SELECT",
        "ACC_NOT_DATA_SELECT",
        "ACC_INPUT_DATA_SELECT",
        "ACC_NOT_VALUE",
    }
    assert labels.isdisjoint(obsolete)


def _accumulator_validity_selectors(circuit):
    """Return the named one-bit validity muxes in signal-flow order."""

    return tuple(
        _labelled_component(circuit, label)
        for label in (
            "ACC_MEMORY_VALID_SELECT",
            "ACC_NOT_VALID_SELECT",
            "ACC_ADD_VALID_SELECT",
            "ACC_INPUT_VALID_SELECT",
        )
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
    compact_label = (
        label.replace("ADDRESS_REGISTER_PLUS_OFFSET", "REG_OFF")
        .replace("ADDRESS_REGISTER", "ADR_REG")
        .replace("ADDRESS", "ADR")
    )
    index = next(
        index
        for index, component in enumerate(outputs)
        if _attributes(component).get("label") == compact_label
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
    if attributes.get("facing") == "south":
        return f"({x + 10 + 20 * (len(branches) - 1 - branch)},{y + 20})"
    if attributes.get("appear") == "right":
        return f"({x + 20},{y + 10 + 40 * branch})"
    return f"({x + 20},{y + 20 * branch})"


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


def test_top_level_has_visible_labels_on_wires_at_components():
    """Keep top-level tunnels limited to the documented status exception."""

    circuit = _top_level(ET.parse(PROJECT).getroot())
    top_level_tunnels = [
        c for c in circuit.findall("comp") if c.get("name") == "Tunnel"
    ]
    assert top_level_tunnels == []
    operations = next(
        c for c in ET.parse(PROJECT).getroot().findall("circuit")
        if c.get("name") == "Operations"
    )
    assert not [
        component
        for component in operations.findall("comp")
        if component.get("name") == "Tunnel"
    ]
    root = ET.parse(PROJECT).getroot()
    addition = next(
        item for item in root.findall("circuit")
        if item.get("name") == "AddSubCircuit"
    )
    assert {"MEMORY_VALID →", "ADD_VALID →", "CONST_VALID →"} <= {
        _attributes(component).get("text")
        for component in addition.findall("comp")
        if component.get("name") == "Text"
    }
    subtraction_validity = next(
        item for item in root.findall("circuit")
        if item.get("name") == "SubSubCircuit"
    )
    assert {"MEMORY_VALID →", "SUB_VALID →", "CONST_VALID →"} <= {
        _attributes(component).get("text")
        for component in subtraction_validity.findall("comp")
        if component.get("name") == "Text"
    }
    component_labels = [
        _attributes(component).get("label")
        for component in circuit.findall("comp")
        if _attributes(component).get("label") and component.get("name") != "Tunnel"
    ]
    assert len(component_labels) == len(set(component_labels))

def test_top_level_accumulator_family_controls_are_independent_connections():
    """Aggregate every value-producing control before the top-level boundary."""

    root = ET.parse(PROJECT).getroot()
    circuit = root.find("circuit[@name='DecodeSignals']")
    adjacency = _electrical_adjacency(circuit)
    family_gate = _labelled_component(circuit, "ACC_LOAD_REQUEST")
    # The expanded classic symbol reserves the lane immediately below its
    # output; these are its 28 actual contacts rather than a bounding-box guess.
    family_inputs = {
        f"(620,{y})"
        for y in (*range(230, 390, 10), *range(400, 520, 10))
    }
    decoder = circuit.find("comp[@name='FetchDecodeControls']")
    decoder_definition = root.find("circuit[@name='FetchDecodeControls']")
    decoder_outputs = {
        _attributes(component)["label"]: component.get("loc")
        for component in decoder_definition.findall("comp[@name='Pin']")
        if _attributes(component).get("type") == "output"
    }
    decoder_x, decoder_y = map(int, decoder.get("loc").strip("()").split(","))
    ordered_outputs = sorted(
        decoder_outputs,
        key=lambda label: tuple(
            map(int, decoder_outputs[label].strip("()").split(","))
        )[::-1],
    )
    sources = {
        name: f"({decoder_x},{decoder_y + 20 * ordered_outputs.index(compact_name)})"
        for name in ACCUMULATOR_FAMILY_CONTROLS
        for compact_name in (
            name.replace("ADDRESS_REGISTER_PLUS_OFFSET", "REG_OFF")
            .replace("ADDRESS_REGISTER", "ADR_REG")
            .replace("ADDRESS", "ADR"),
        )
    }

    connected_inputs = {}
    for name, source in sources.items():
        reachable = _reachable(adjacency, source)
        matches = reachable & family_inputs
        assert len(matches) == 1, name
        connected_inputs[name] = matches.pop()
        assert reachable.isdisjoint(set(sources.values()) - {source}), name

    assert len(set(connected_inputs.values())) == len(ACCUMULATOR_FAMILY_CONTROLS)
    assert set(connected_inputs.values()) <= family_inputs

    top_level = _top_level(root)
    top_level_adjacency = _electrical_adjacency(top_level)
    request = _subcircuit_output(root, "DecodeSignals", "ACC_WRITE_REQUEST")
    accumulator_load = _subcircuit_input(root, "Datapath", "ACC_LOAD")
    assert accumulator_load in _reachable(top_level_adjacency, request)


def test_decode_signals_exports_canonical_accumulator_request_names():
    """Keep the decode boundary free of misspelled public pin labels."""

    root = ET.parse(PROJECT).getroot()
    circuit = root.find("circuit[@name='DecodeSignals']")
    output_labels = {
        _attributes(component).get("label")
        for component in circuit.findall("comp[@name='Pin']")
        if _attributes(component).get("type") == "output"
    }
    assert output_labels == {"ACC_MEMORY_REQUEST", "ACC_WRITE_REQUEST"}
    assert (
        _labelled_component(circuit, "ACC_WRITE_AGGREGATOR").get("name")
        == "OR Gate"
    )


def test_decode_accumulator_family_request_excludes_store_and_register_loads():
    """Only value-producing families may enable the accumulator register."""

    root = ET.parse(PROJECT).getroot()
    circuit = root.find("circuit[@name='DecodeSignals']")
    gate = _labelled_component(circuit, "ACC_LOAD_REQUEST")
    assert _attributes(gate).get("inputs") == "28"
    output = gate.get("loc")
    # The expanded classic gate leaves the lane immediately below its output
    # unused; freeze the actual 28 contacts rather than a symbol-size guess.
    inputs = {
        f"(620,{y})"
        for y in (*range(230, 390, 10), *range(400, 520, 10))
    }

    adjacency = _electrical_adjacency(circuit, inputs | {output})
    family_outputs = {f"(460,{80 + 20 * index})" for index in range(28)}
    excluded_outputs = {f"(460,{80 + 20 * index})" for index in range(28, 33)}
    connected_inputs = {
        next(iter(_reachable(adjacency, source) & inputs))
        for source in family_outputs
    }

    assert connected_inputs == inputs
    assert all(_reachable(adjacency, source).isdisjoint(inputs) for source in excluded_outputs)
    assert output in _reachable(adjacency, "(750,390)")


def test_decode_write_request_causes_use_separate_gate_connections():
    """Keep the family request, NOT, and INPUT on three distinct named nets."""

    root = ET.parse(PROJECT).getroot()
    circuit = root.find("circuit[@name='DecodeSignals']")
    adjacency = _electrical_adjacency(circuit)
    family_gate = _labelled_component(circuit, "ACC_LOAD_REQUEST")
    write_gate = _labelled_component(circuit, "ACC_WRITE_AGGREGATOR")
    family_output, _ = _gate_ports(family_gate)
    write_output, write_inputs = _gate_ports(write_gate)
    causes = {
        "ACC_LOAD_REQUEST": family_output,
        "NOT": "(460,740)",
        "INPUT": "(460,880)",
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
    write_request = next(
        component.get("loc")
        for component in circuit.findall("comp[@name='Pin']")
        if _attributes(component).get("label") == "ACC_WRITE_REQUEST"
    )
    assert write_request in _reachable(adjacency, write_output)






def _assert_binary_validity_selector(root, circuit_name, operation):
    """Prove the named operand-validity path inside one arithmetic FBox."""

    circuit = next(c for c in root.findall("circuit") if c.get("name") == circuit_name)
    adjacency = _electrical_adjacency(circuit)
    pins = {
        _attributes(component).get("label"): component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
    }
    # The user's repaired drawing intentionally leaves routing primitives
    # unlabelled.  Identify the validity selector by its electrical role: it is
    # the only one-bit mux on this page (the operand-data mux is 16-bit).
    selectors = [
        component
        for component in circuit.findall("comp[@name='Multiplexer']")
        if _attributes(component).get("width", "1") == "1"
    ]
    assert len(selectors) == 1, f"{circuit_name} validity selector"
    selector = selectors[0]
    gate = _labelled_component(circuit, f"ACC_{operation}_VALID")
    x, y = map(int, selector.get("loc").strip("()").split(","))
    selector_inputs = {f"({x - 30},{y - 10})", f"({x - 30},{y + 10})"}
    assert len(_reachable(adjacency, pins["MEMORY_VALID"]) & selector_inputs) == 1
    assert len([
        component for component in circuit.findall("comp")
        if component.get("name") == "Constant"
        and _reachable(adjacency, component.get("loc")) & selector_inputs
    ]) == 1
    # The project inspector resolves the generated multi-input gate terminals;
    # requiring the complete sheet catches either validity source being open.
    report = next(item for item in inspect_project(PROJECT) if item.name == circuit_name)
    assert report.connected


def test_memory_validity_is_selected_for_binary_memory_operands():
    """Memory-backed ADD and SUB modes use the RAM validity bit."""

    root = ET.parse(PROJECT).getroot()
    _assert_binary_validity_selector(root, "AddSubCircuit", "ADD")
    _assert_binary_validity_selector(root, "SubSubCircuit", "SUB")


def test_immediate_arithmetic_uses_a_defined_valid_operand():
    """The non-memory side of each operand-validity mux is an explicit one."""

    root = ET.parse(PROJECT).getroot()
    for circuit_name, operation in (("AddSubCircuit", "ADD"), ("SubSubCircuit", "SUB")):
        circuit = next(c for c in root.findall("circuit") if c.get("name") == circuit_name)
        constants = [c for c in circuit.findall("comp") if c.get("name") == "Constant"]
        assert len(constants) == 1
        assert _attributes(constants[0]).get("value", "0x1") == "0x1"
        selectors = [
            component
            for component in circuit.findall("comp[@name='Multiplexer']")
            if _attributes(component).get("width", "1") == "1"
        ]
        assert len(selectors) == 1, f"{circuit_name} validity selector"


def test_not_propagates_accumulator_validity_only_while_active():
    """NOT gates ACC_VALID with its dedicated activation control."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(c for c in root.findall("circuit") if c.get("name") == "NotCircuit")
    adjacency = _electrical_adjacency(circuit)
    pins = {_attributes(c).get("label"): c.get("loc") for c in circuit.findall("comp") if c.get("name") == "Pin"}
    assert next(item for item in inspect_project(PROJECT) if item.name == "NotCircuit").connected
    assert pins["RESULT_VALID"] in _reachable(adjacency, _labelled_component(circuit, "ACTIVE_NOT_VALID").get("loc"))


def test_add_requires_accumulator_and_selected_operand_validity():
    root = ET.parse(PROJECT).getroot()
    _assert_binary_validity_selector(root, "AddSubCircuit", "ADD")


def test_sub_requires_accumulator_and_selected_operand_validity():
    root = ET.parse(PROJECT).getroot()
    _assert_binary_validity_selector(root, "SubSubCircuit", "SUB")


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






def test_ci_runs_the_fresh_checkout_hardware_verifier():
    """Keep the documented dependency-free acceptance command in the main gate."""

    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "Run TinyCPU hardware reproducibility gate" in workflow
    assert "PYTHONPATH=src python src/tiny_cpu_verify.py" in workflow


def test_tinycpu_sheet_uses_the_operations_sheet_as_its_only_operation_box():
    """Keep operation boxes encapsulated behind one explicit integration boundary."""

    root = ET.parse(PROJECT).getroot()
    top = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
    subcircuits = {
        component.get("name")
        for component in top.findall("comp")
        if component.get("lib") is None
    }
    assert {
        "Datapath", "AddressPath", "Memory", "ErrorFlags", "FetchDecode",
        "FetchDecodeControls", "DecodeSignals", "Operations",
    } <= subcircuits
    assert not {"AddSubCircuit", "SubSubCircuit", "NotCircuit"} & subcircuits

    operations = next(
        c for c in root.findall("circuit") if c.get("name") == "Operations"
    )
    operation_boxes = [
        component.get("name")
        for component in operations.findall("comp")
        if component.get("name") in {
            "AddSubCircuit", "SubSubCircuit", "MulSubCircuit", "DivSubCircuit", "AndSubCircuit", "NotCircuit"
        }
    ]
    assert sorted(operation_boxes) == [
        "AddSubCircuit", "AndSubCircuit", "DivSubCircuit", "MulSubCircuit", "NotCircuit", "SubSubCircuit"
    ]
    owners = {
        box: [
            circuit.get("name")
            for circuit in root.findall("circuit")
            for component in circuit.findall("comp")
            if component.get("name") == box
        ]
        for box in operation_boxes
    }
    assert owners == {
        "AddSubCircuit": ["Operations"],
        "SubSubCircuit": ["Operations"],
        "MulSubCircuit": ["Operations"],
        "DivSubCircuit": ["Operations"],
        "AndSubCircuit": ["Operations"],
        "NotCircuit": ["Operations"],
    }

def test_logisim_starter_matches_default_hardware_profile():
    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}

    assert root.find("main").get("name") == "TinyCPUMain"
    assert {
        "TinyCPUMain",
        "AddSubCircuit",
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

    address_splitter = next(
        component
        for component in circuits["Memory"].findall("comp")
        if component.get("name") == "Splitter"
    )
    splitter_attributes = _attributes(address_splitter)
    # Keep the low address bit explicit so a Logisim save cannot silently
    # move it away from the 12-bit RAM-address branch.
    assert splitter_attributes["bit0"] == "0"
    assert {
        bit
        for bit in range(int(splitter_attributes["incoming"]))
        if splitter_attributes.get(f"bit{bit}", "0") == "0"
    } == set(range(12))

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
    assert has_wire("(350,150)", "(450,150)")  # ADDRESS_IN -> AR.D
    assert has_wire("(390,170)", "(450,170)")  # AR_LOAD -> AR.WE
    assert has_wire("(430,190)", "(450,190)")  # CLK -> AR clock
    assert has_wire("(300,330)", "(450,330)")  # VALID_IN -> AR_VALID.D
    assert has_wire("(390,350)", "(450,350)")  # AR_LOAD -> AR_VALID.WE
    assert has_wire("(430,370)", "(450,370)")  # CLK -> AR_VALID clock

    # The address register output and OFFSET terminate at the adder's distinct
    # A and B pins. Neither input bus shares a segment with the other.
    assert has_wire("(510,150)", "(530,150)")  # AR.Q -> address net
    assert has_wire("(530,190)", "(590,190)")
    # OFFSET detours around AR's one-bit reset terminal at (480,210); a
    # straight bus here makes Logisim report incompatible 12/1-bit widths.
    assert has_wire("(300,240)", "(560,240)")
    assert has_wire("(560,210)", "(560,240)")
    assert has_wire("(560,210)", "(590,210)")
    assert has_wire("(630,200)", "(730,200)")
    # Carry-out is the one-bit terminal below the adder at (500,220), not a
    # point below its 12-bit sum output anchor.
    assert has_wire("(610,220)", "(610,240)")
    assert has_wire("(610,240)", "(730,240)")
    assert has_wire("(510,330)", "(740,330)")  # AR_VALID.Q -> output


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
    assert {"(380,140)", "(380,160)", "(380,180)"} <= endpoints
    assert {"(380,300)", "(380,320)", "(380,340)"} <= endpoints

    # The comparator receives ACC and the zero constant on separate 16-bit
    # inputs; neither is accidentally attached to a one-bit status output.
    assert {"(470,140)", "(470,180)", "(560,200)", "(590,200)"} <= endpoints


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
    assert pins["MEMORY_DATA"]["width"] == "16"
    assert {"VALID_IN", "WRITE_ENABLE", "CLK", "MEMORY_VALID"} <= pins.keys()

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
        "DIV0": ("(110,340)", "(500,380)", "(580,360)", "(750,330)", "(1000,360)"),
        "ADDR": ("(110,480)", "(510,520)", "(590,500)", "(750,470)", "(1000,500)"),
        "INV": ("(110,610)", "(500,650)", "(590,630)", "(750,600)", "(1000,630)"),
        "ILL": ("(110,750)", "(510,790)", "(600,770)", "(750,740)", "(1000,770)"),
        "INPUT": ("(120,890)", "(510,930)", "(610,910)", "(750,880)", "(1000,910)"),
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
    undirected_wires = {frozenset(wire) for wire in wires}

    # Feedback remains explicit wiring. The only tunnels are the deliberately
    # shared portable reset net for the six register clear terminals.
    tunnels = errors.findall("comp[@name='Tunnel']")
    assert tunnels
    assert {
        _attributes(component).get("label") for component in tunnels
    } == {"ERROR_FLAGS_STARTUP_RESET"}

    expected_feedback_routes = {
        "OVF": ("(420,230)", "(820,230)", 170),
        "DIV0": ("(420,360)", "(820,360)", 300),
        "ADDR": ("(420,500)", "(820,500)", 440),
        "INV": ("(430,630)", "(820,630)", 570),
        "ILL": ("(440,770)", "(820,770)", 710),
        "INPUT": ("(440,910)", "(830,910)", 850),
    }
    for start, end, lane_y in expected_feedback_routes.values():
        start_x = start.partition(",")[0] + ","
        end_x = end.partition(",")[0] + ","
        route = {
            (start, f"{start_x}{lane_y})"),
            (f"{start_x}{lane_y})", f"{end_x}{lane_y})"),
            (f"{end_x}{lane_y})", end),
        }
        assert {frozenset(wire) for wire in route} <= undirected_wires

    for register_y in (200, 330, 470, 600, 740, 880):
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
        "(750,400)",
        "(750,540)",
        "(750,670)",
        "(750,810)",
        "(750,950)",
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
        "named topology",
        "electrical attributes",
        "ROM and listing",
        "embedded ROM",
        "17-edge trace",
        "integration boundary trace",
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


@pytest.mark.parametrize(
    ("circuit_name", "component_name", "label", "attribute", "invalid"),
    (
        ("FetchDecode", "Constant", "PC_INCREMENT_ENABLE", "value", "0x0"),
        ("FetchDecode", "Constant", "PC_INCREMENT", "width", "1"),
        ("Operations", "Multiplexer", "RESULT_DATA_SELECT", "width", "1"),
    ),
)
def test_ap8_verification_rejects_incorrect_electrical_attributes(
    tmp_path, circuit_name, component_name, label, attribute, invalid
):
    """The required CI gate must catch effective electrical changes."""

    repository = tmp_path / "checkout"
    target = repository / "hardware" / "logisim"
    target.mkdir(parents=True)
    for artifact in HARDWARE.iterdir():
        if artifact.is_file():
            (target / artifact.name).write_bytes(artifact.read_bytes())

    project = target / "TinyCPU.circ"
    tree = ET.parse(project)
    circuit = tree.getroot().find(f"circuit[@name='{circuit_name}']")
    component = next(
        item for item in circuit.findall(f"comp[@name='{component_name}']")
        if _attributes(item).get("label") == label
    )
    item = next((item for item in component if item.get("name") == attribute), None)
    if item is None:
        item = ET.SubElement(component, "a", name=attribute)
    item.set("val", invalid)
    tree.write(project, encoding="utf-8", xml_declaration=True)

    with pytest.raises(
        VerificationError,
        match=rf"electrical attributes: .* requires {attribute}=",
    ):
        verify_checkout(repository)


def test_restored_arithmetic_boxes_are_tunnel_free():
    """Keep the restored independent ADD and SUB boxes directly traceable."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    for box, helper in (("AddSubCircuit", "AddArithmeticCircuit"), ("SubSubCircuit", "SubArithmeticCircuit")):
        components = circuits[box].findall("comp")
        assert not [c for c in components if c.get("name") == "Tunnel"]
        assert helper in {c.get("name") for c in components}

    extracted_operations = {
        "AddArithmeticCircuit": "Adder",
        "SubArithmeticCircuit": "Subtractor",
    }
    for circuit_name, primitive in extracted_operations.items():
        extracted = circuits[circuit_name]
        extracted_components = extracted.findall("comp")
        assert sum(
            component.get("name") == primitive
            for component in extracted_components
        ) == 1
        assert not [
            component
            for component in extracted_components
            if component.get("name") == "Tunnel"
        ]



def test_mul_box_exports_the_arithmetic_result_and_validity_contract():
    """Keep MUL ready for integration behind the same explicit FBox contract."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    multiply = circuits["MulSubCircuit"]
    inputs = {
        _attributes(component).get("label")
        for component in multiply.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") != "output"
    }
    outputs = {
        _attributes(component).get("label")
        for component in multiply.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") == "output"
    }

    assert {
        "MUL_CONST", "MUL_ADDRESS", "MUL_ADDRESS_REGISTER",
        "MUL_ADDRESS_REGISTER_PLUS_OFFSET", "ACC_VALUE", "ACC_VALID",
        "MEMORY_VALUE", "MEMORY_VALID", "IMMEDIATE_VALUE",
    } == inputs
    assert {"RESULT", "OVERFLOW", "RESULT_VALID", "RESULT_ACTIVE"} == outputs
    assert any(
        component.get("name") == "MulArithmeticCircuit"
        for component in multiply.findall("comp")
    )
    assert any(
        component.get("name") == "Multiplier"
        for component in circuits["MulArithmeticCircuit"].findall("comp")
    )
    assert not [
        component for name in ("MulSubCircuit", "MulArithmeticCircuit")
        for component in circuits[name].findall("comp")
        if component.get("name") == "Tunnel"
    ]


def test_and_box_exports_bitwise_result_and_validity_contract():
    """AND mirrors binary operand selection without inventing arithmetic status."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    bitwise_and = circuits["AndSubCircuit"]
    inputs = {
        _attributes(component).get("label")
        for component in bitwise_and.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") != "output"
    }
    outputs = {
        _attributes(component).get("label")
        for component in bitwise_and.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") == "output"
    }

    assert {
        "AND_CONST", "AND_ADDRESS", "AND_ADDRESS_REGISTER",
        "AND_ADDRESS_REGISTER_PLUS_OFFSET", "ACC_VALUE", "ACC_VALID",
        "MEMORY_VALUE", "MEMORY_VALID", "IMMEDIATE_VALUE",
    } == inputs
    assert {"RESULT", "RESULT_VALID", "RESULT_ACTIVE"} == outputs
    arithmetic = circuits["AndArithmeticCircuit"]
    labels = {_attributes(component).get("label") for component in arithmetic.findall("comp")}
    assert {"BITWISE_AND", "ACTIVE_AND_VALID"} <= labels
    assert any(
        component.get("name") == "Multiplexer"
        for component in arithmetic.findall("comp")
    )
    assert "INACTIVE_AND_DEFAULT" not in labels
    assert not [
        component for name in ("AndSubCircuit", "AndArithmeticCircuit")
        for component in circuits[name].findall("comp")
        if component.get("name") == "Tunnel"
    ]


def test_or_box_exports_bitwise_result_and_validity_contract():
    """OR mirrors the binary validity boundary without arithmetic status."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    bitwise_or = circuits["OrSubCircuit"]
    inputs = {
        _attributes(component).get("label")
        for component in bitwise_or.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") != "output"
    }
    outputs = {
        _attributes(component).get("label")
        for component in bitwise_or.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") == "output"
    }
    assert {
        "OR_CONST", "OR_ADDRESS", "OR_ADDRESS_REGISTER",
        "OR_ADDRESS_REGISTER_PLUS_OFFSET", "ACC_VALUE", "ACC_VALID",
        "MEMORY_VALUE", "MEMORY_VALID", "IMMEDIATE_VALUE",
    } == inputs
    assert {"RESULT", "RESULT_VALID", "RESULT_ACTIVE"} == outputs
    arithmetic = circuits["OrArithmeticCircuit"]
    labels = {_attributes(component).get("label") for component in arithmetic.findall("comp")}
    assert {"BITWISE_OR", "ACTIVE_OR_VALID"} <= labels
    assert "INACTIVE_OR_DEFAULT" not in labels
    assert _labelled_component(arithmetic, "BITWISE_OR").get("name") == "OR Gate"
    assert not [
        component for name in ("OrSubCircuit", "OrArithmeticCircuit")
        for component in circuits[name].findall("comp")
        if component.get("name") == "Tunnel"
    ]


def test_xor_box_exports_bitwise_result_and_validity_contract():
    """XOR mirrors the binary validity boundary without arithmetic status."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    bitwise_xor = circuits["XorSubCircuit"]
    inputs = {
        _attributes(component).get("label")
        for component in bitwise_xor.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") != "output"
    }
    outputs = {
        _attributes(component).get("label")
        for component in bitwise_xor.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") == "output"
    }
    assert {
        "XOR_CONST", "XOR_ADDRESS", "XOR_ADDRESS_REGISTER",
        "XOR_ADDRESS_REGISTER_PLUS_OFFSET", "ACC_VALUE", "ACC_VALID",
        "MEMORY_VALUE", "MEMORY_VALID", "IMMEDIATE_VALUE",
    } == inputs
    assert {"RESULT", "RESULT_VALID", "RESULT_ACTIVE"} == outputs
    arithmetic = circuits["XorArithmeticCircuit"]
    labels = {_attributes(component).get("label") for component in arithmetic.findall("comp")}
    assert {"BITWISE_XOR", "ACTIVE_XOR_VALID"} <= labels
    assert _labelled_component(arithmetic, "BITWISE_XOR").get("name") == "XOR Gate"
    assert not [
        component for name in ("XorSubCircuit", "XorArithmeticCircuit")
        for component in circuits[name].findall("comp")
        if component.get("name") == "Tunnel"
    ]


def test_arithmetic_fboxes_use_operation_specific_activation_and_validity_labels():
    """Prevent copy/paste labels from making the visible wiring misleading."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}

    for operation in ("ADD", "SUB", "MUL", "DIV", "AND"):
        selector = circuits[f"{operation.title()}SubCircuit"]
        arithmetic = circuits[f"{operation.title()}ArithmeticCircuit"]
        selector_labels = {
            _attributes(component).get("label")
            for component in selector.findall("comp")
        }
        arithmetic_pin_labels = {
            _attributes(component).get("label")
            for component in arithmetic.findall("comp")
            if component.get("name") == "Pin"
        }
        text = {
            _attributes(component).get("text")
            for component in selector.findall("comp")
            if component.get("name") == "Text"
        }

        assert f"ACC_{operation}_VALID" in selector_labels
        assert f"{operation}_ACTIVATED" in arithmetic_pin_labels
        assert f"{operation}_VALID →" in text



def test_div_box_exports_result_validity_and_divide_by_zero_contract():
    """DIV selects operands like MUL and reports its dedicated zero error."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    divide = circuits["DivSubCircuit"]
    inputs = {
        _attributes(component).get("label")
        for component in divide.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") != "output"
    }
    outputs = {
        _attributes(component).get("label")
        for component in divide.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") == "output"
    }
    assert {
        "DIV_CONST", "DIV_ADDRESS", "DIV_ADDRESS_REGISTER",
        "DIV_ADDRESS_REGISTER_PLUS_OFFSET", "ACC_VALUE", "ACC_VALID",
        "MEMORY_VALUE", "MEMORY_VALID", "IMMEDIATE_VALUE",
    } == inputs
    assert {"RESULT", "RESULT_VALID", "RESULT_ACTIVE", "DIVIDE_BY_ZERO"} == outputs
    arithmetic = circuits["DivArithmeticCircuit"]
    assert any(component.get("name") == "Divider" for component in arithmetic.findall("comp"))
    labels = {_attributes(component).get("label") for component in arithmetic.findall("comp")}
    assert {"DIVIDE_BY_ZERO", "NONZERO_DIVISOR"} <= labels
    assert "OVERFLOW" not in labels
    assert not [
        component for name in ("DivSubCircuit", "DivArithmeticCircuit")
        for component in circuits[name].findall("comp")
        if component.get("name") == "Tunnel"
    ]

def test_not_operation_gates_data_and_valid_with_activity():
    """An inactive NOT operation contributes neutral data and validity."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(c for c in root.findall("circuit") if c.get("name") == "NotCircuit")
    labels = {_attributes(c).get("label") for c in circuit.findall("comp")}
    assert "ACTIVE_NOT_VALID" in labels


def test_operation_data_and_validity_are_combined_by_explicit_or_trees():
    """Aggregate every FBox contract without duplicating its error checks."""

    circuit = next(
        c for c in ET.parse(PROJECT).getroot().findall("circuit")
        if c.get("name") == "Operations"
    )
    components = {
        _attributes(component).get("label"): component
        for component in circuit.findall("comp")
        if _attributes(component).get("label")
    }
    assert _attributes(components["RESULT"])["inputs"] == "8"
    assert _attributes(components["OPERATION_RESULT_VALID"])["inputs"] == "8"
    assert _attributes(components["OPERATION_IS_ACTIVE"])["inputs"] == "8"
    assert components["ACTIVE_INVALID_OPERATION"].get("name") == "AND Gate"
    assert "RESULT_VALID_WITHOUT_ERROR" not in components
    assert "NO_INVALID_OPERAND" not in components

def test_mul_operation_is_integrated_into_results_and_invalid_operand_detection():
    """MUL crosses Operations once and participates in every arithmetic merge."""

    root = ET.parse(PROJECT).getroot()
    top_adjacency = _electrical_adjacency(_top_level(root))
    for mode in ACCUMULATOR_ADDRESSING_MODES:
        label = f"MUL_{mode}"
        assert _subcircuit_input(root, "Operations", label) in _reachable(
            top_adjacency, _control_output(root, label)
        )

    operations = next(
        circuit for circuit in root.findall("circuit")
        if circuit.get("name") == "Operations"
    )
    labels = {
        _attributes(component).get("label"): component
        for component in operations.findall("comp")
        if _attributes(component).get("label")
    }
    assert labels["MUL_OPERATION"].get("name") == "MulSubCircuit"
    assert _attributes(labels["OPERATION_RESULT_VALID"])["inputs"] == "8"
    assert _attributes(labels["OPERATION_IS_ACTIVE"])["inputs"] == "8"
    assert _attributes(labels["OVERFLOW_SET"])["inputs"] == "3"


def test_unary_and_subtraction_boxes_export_a_uniform_operation_contract():
    """Each independently selectable operation reports data, status and activity."""

    root = ET.parse(PROJECT).getroot()
    circuits = {circuit.get("name"): circuit for circuit in root.findall("circuit")}
    expected_outputs = {
        "NotCircuit": {"RESULT", "RESULT_VALID", "RESULT_ACTIVE"},
        "SubSubCircuit": {"RESULT", "OVERFLOW", "RESULT_VALID", "RESULT_ACTIVE"},
    }
    for circuit_name, outputs in expected_outputs.items():
        circuit = circuits[circuit_name]
        actual_outputs = {
            _attributes(component)["label"]
            for component in circuit.findall("comp")
            if component.get("name") == "Pin"
            and _attributes(component).get("type") == "output"
        }
        assert actual_outputs == outputs
        assert not [
            component
            for component in circuit.findall("comp")
            if component.get("name") == "Tunnel"
        ]

    assert "OVERFLOW" not in expected_outputs["NotCircuit"]
    assert any(component.get("name") == "SubArithmeticCircuit"
               for component in circuits["SubSubCircuit"].findall("comp"))


def test_memory_address_selector_includes_indirect_addressing_modes():
    """Memory selects direct, register, and register-plus-offset addresses."""
    root = ET.parse(PROJECT).getroot()
    circuit = next(
        item for item in root.findall("circuit")
        if item.get("name") == "EffectiveAddress"
    )
    muxes = {
        component.get("loc"): component
        for component in circuit.findall("comp")
        if component.get("name") == "Multiplexer"
    }
    register_mux = muxes["(750,220)"]
    offset_mux = muxes["(750,580)"]
    def ports(component):
        x, y = (int(v) for v in component.get("loc").strip("()").split(","))
        return {f"({x-30},{y-10})", f"({x-30},{y+10})"}, f"({x},{y})"
    register_inputs, register_output = ports(register_mux)
    offset_inputs, offset_output = ports(offset_mux)
    pins = {
        _attributes(component).get("label"): component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
    }
    points = set(register_inputs | offset_inputs) | {
        pins["DIRECT_ADDR"],
        pins["REG_ADDR"],
        pins["REG_SELECTED"],
        pins["OFFSET_ADDR"],
    }
    adjacency = _electrical_adjacency(circuit, points)
    for source, target in (
        (pins["DIRECT_ADDR"], "(720,210)"),
        (pins["REG_ADDR"], "(720,230)"),
        (pins["REG_SELECTED"], "(720,590)"),
        (pins["OFFSET_ADDR"], "(720,570)"),
    ):
        assert target in _reachable(adjacency, source)
    assert register_output == "(750,220)"
    assert offset_output == "(750,580)"
    for label, suffix in (("MEMORY_ADDRESS_REGISTER_SELECT", "ADDRESS_REGISTER"), ("MEMORY_ADDRESS_OFFSET_SELECT", "ADDRESS_REGISTER_PLUS_OFFSET")):
        _labelled_component(circuit, label)
        connected = {
            pins[f"{family}_{'ADR_REG' if suffix == 'ADDRESS_REGISTER' else 'REG_OFF'}"]
            for family in ("LOAD", "ADD", "SUB", "MUL", "DIV", "AND", "OR", "STORE")
        }
        assert len(connected) == 8


def test_store_modes_write_the_accumulator_payload_to_memory():
    """Only STORE modes enable RAM and preserve accumulator validity."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    write_gate = _labelled_component(circuit, "MEMORY_WRITE_REQUEST")
    write_output, write_inputs = _gate_ports(write_gate)
    adjacency = _electrical_adjacency(circuit, write_inputs | {write_output})

    controls = {
        _control_output(root, "STORE_ADDRESS"),
        _control_output(root, "STORE_ADDRESS_REGISTER"),
        _control_output(root, "STORE_ADDRESS_REGISTER_PLUS_OFFSET"),
    }
    connected_inputs = {
        next(iter(_reachable(adjacency, control) & write_inputs))
        for control in controls
    }
    assert connected_inputs == write_inputs
    assert _subcircuit_input(root, "Memory", "WRITE_ENABLE") in _reachable(
        adjacency, write_output
    )
    assert _subcircuit_input(root, "Memory", "DATA_IN") in _reachable(
        adjacency, _subcircuit_output(root, "Datapath", "ACC_OUT")
    )
    assert _subcircuit_input(root, "Memory", "VALID_IN") in _reachable(
        adjacency, _subcircuit_output(root, "Datapath", "ACC_VALID_OUT")
    )


def test_print_controls_export_separate_validated_output_channels():
    """Keep accumulator and addressed-memory print events electrically distinct."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    output_pins = {
        _attributes(component).get("label"): component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") == "output"
    }

    channels = {
        "PRINT": {
            "enable": "PRINT_ENABLE",
            "value": "PRINT_VALUE",
            "valid": "PRINT_VALID",
            "value_source": _subcircuit_output(root, "Datapath", "ACC_OUT"),
            "valid_source": _subcircuit_output(root, "Datapath", "ACC_VALID_OUT"),
        },
        "PRINT_ADDRESS": {
            "enable": "PRINT_ADDRESS_ENABLE",
            "value": "PRINT_ADDRESS_VALUE",
            "valid": "PRINT_ADDRESS_VALID",
            "value_source": _subcircuit_output(root, "Memory", "MEMORY_DATA"),
            "valid_source": _subcircuit_output(root, "Memory", "MEMORY_VALID"),
        },
    }

    for control, channel in channels.items():
        assert output_pins[channel["enable"]] in _reachable(
            adjacency, _control_output(root, control)
        )
        assert output_pins[channel["value"]] in _reachable(
            adjacency, channel["value_source"]
        )
        assert output_pins[channel["valid"]] in _reachable(
            adjacency, channel["valid_source"]
        )

    for field in ("enable", "value", "valid"):
        left = output_pins[channels["PRINT"][field]]
        right = output_pins[channels["PRINT_ADDRESS"][field]]
        assert right not in _reachable(adjacency, left)


def test_halt_controls_export_distinct_observable_outcomes():
    """Normal and error halts must never share an external event net."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)
    output_pins = {
        _attributes(component).get("label"): component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("type") == "output"
    }

    normal_halt = output_pins["HALTED"]
    error_halt = output_pins["HALTED_WITH_ERROR"]
    assert normal_halt in _reachable(adjacency, _control_output(root, "HALT"))
    assert error_halt in _reachable(
        adjacency, _control_output(root, "HALT_ERROR")
    )
    assert error_halt not in _reachable(adjacency, normal_halt)

    # AP-5 terminates with a normal HALT.  Mirroring the two already valid
    # event nets avoids the erroneous extra OR gate that previously left the
    # tty harness running forever with HALTED=E.
    assert output_pins["HALTED"] in _reachable(adjacency, normal_halt)
    assert output_pins["HALTED_WITH_ERROR"] in _reachable(adjacency, error_halt)
    assert not any(
        component.get("name") == "OR Gate"
        and _attributes(component).get("label") == "HALTED_STATE"
        for component in circuit.findall("comp")
    )


def test_not_result_is_committed_by_the_accumulator_write_request():
    """NOT selects its operation result and enables the accumulator write."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    adjacency = _electrical_adjacency(circuit)

    not_control = _control_output(root, "NOT")
    assert _subcircuit_input(root, "Operations", "NOT_IS_ACTIVE") in _reachable(
        adjacency, not_control
    )
    assert _subcircuit_input(root, "Datapath", "DATA_IN") in _reachable(
        adjacency, _subcircuit_output(root, "Operations", "RESULT_VALUE")
    )
    assert _subcircuit_input(root, "Datapath", "VALID_IN") in _reachable(
        adjacency, _subcircuit_output(root, "Operations", "RESULT_IS_VALID")
    )
    assert _subcircuit_input(root, "Datapath", "ACC_LOAD") in _reachable(
        adjacency, _subcircuit_output(root, "DecodeSignals", "ACC_WRITE_REQUEST")
    )


def test_non_arithmetic_accumulator_results_are_explicitly_valid():
    """Immediate and selected load data must not inherit a zero default."""

    root = ET.parse(PROJECT).getroot()
    operations = next(
        circuit for circuit in root.findall("circuit")
        if circuit.get("name") == "Operations"
    )
    validity = _labelled_component(operations, "IMMEDIATE_RESULT_VALID")

    assert validity.get("name") == "Constant"
    assert _attributes(validity).get("value") == "0x1"
    adjacency = _electrical_adjacency(operations)
    assert "(1780,760)" in _reachable(adjacency, validity.get("loc"))


def test_datapath_startup_reset_is_explicitly_inactive():
    """The accumulator must not be held in reset by a default-valued constant."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    reset = _labelled_component(circuit, "DATAPATH_RESET_INACTIVE")

    assert reset.get("name") == "Constant"
    assert _attributes(reset).get("value") == "0x0"
    adjacency = _electrical_adjacency(circuit)
    assert _subcircuit_input(
        root, "Datapath", "DATAPATH_STARTUP_RESET"
    ) in _reachable(adjacency, reset.get("loc"))


def test_operations_preserve_immediate_load_values_outside_alu_cycles():
    """LOAD_CONST must not receive the inactive operation tree's zero value."""

    root = ET.parse(PROJECT).getroot()
    circuit = root.find("circuit[@name='Operations']")
    assert circuit is not None
    adjacency = _electrical_adjacency(circuit)

    data_selector = circuit.find("comp[@name='Multiplexer'][@loc='(1730,650)']")
    assert data_selector is not None
    data_x, data_y = map(int, data_selector.get("loc").strip("()").split(","))
    data_inputs = {f"({data_x - 30},{data_y - 10})", f"({data_x - 30},{data_y + 10})"}
    immediate = next(
        component.get("loc")
        for component in circuit.findall("comp[@name='Pin']")
        if _attributes(component).get("label") == "IMMEDIATE_VALUE"
    )
    operation_result = _labelled_component(circuit, "RESULT").get("loc")
    # Logisim numbers this east-facing mux from top (input 0) to bottom
    # (input 1).  An active operation must therefore select the lower input;
    # the upper input preserves IMMEDIATE_VALUE while the ALU is inactive.
    assert _reachable(adjacency, immediate) & data_inputs == {
        f"({data_x - 30},{data_y - 10})"
    }
    assert _reachable(adjacency, operation_result) & data_inputs == {
        f"({data_x - 30},{data_y + 10})"
    }

    active = _labelled_component(circuit, "OPERATION_IS_ACTIVE").get("loc")
    assert f"({data_x - 20},{data_y + 20})" in _reachable(adjacency, active)
    result_pin = next(
        component.get("loc")
        for component in circuit.findall("comp[@name='Pin']")
        if _attributes(component).get("label") == "RESULT_VALUE"
    )
    assert result_pin in _reachable(adjacency, data_selector.get("loc"))

    valid_selector = circuit.find("comp[@name='Multiplexer'][@loc='(1810,770)']")
    assert valid_selector is not None
    valid_x, valid_y = map(int, valid_selector.get("loc").strip("()").split(","))
    valid_inputs = {
        f"({valid_x - 30},{valid_y - 10})",
        f"({valid_x - 30},{valid_y + 10})",
    }
    immediate_valid_component = circuit.find("comp[@name='Constant'][@loc='(1760,760)']")
    assert immediate_valid_component is not None
    immediate_valid = immediate_valid_component.get("loc")
    operation_valid = _labelled_component(circuit, "OPERATION_RESULT_VALID").get("loc")
    assert _reachable(adjacency, immediate_valid) & valid_inputs == {
        f"({valid_x - 30},{valid_y - 10})"
    }
    assert _reachable(adjacency, operation_valid) & valid_inputs == {
        f"({valid_x - 30},{valid_y + 10})"
    }
    assert _attributes(immediate_valid_component).get("value", "0x1") == "0x1"
    assert f"({valid_x - 20},{valid_y + 20})" in _reachable(adjacency, active)


def test_effective_address_input_labels_are_compact_source_names():
    """Show each source signal on the fixed-width EffectiveAddress symbol."""

    root = ET.parse(PROJECT).getroot()
    effective_address = next(
        circuit for circuit in root.findall("circuit")
        if circuit.get("name") == "EffectiveAddress"
    )
    input_labels = {
        _attributes(pin).get("label")
        for pin in effective_address.findall("comp")
        if pin.get("name") == "Pin"
        and _attributes(pin).get("type", "input") == "input"
    }
    expected_control_labels = {
        f"{operation}_{mode}"
        for operation in ("LOAD", "ADD", "SUB", "MUL", "DIV", "AND", "OR", "STORE")
        for mode in ("ADR_REG", "REG_OFF")
    }

    assert expected_control_labels <= input_labels
    control_outputs = {
        _attributes(pin).get("label")
        for circuit in root.findall("circuit")
        if circuit.get("name") == "FetchDecodeControls"
        for pin in circuit.findall("comp")
        if pin.get("name") == "Pin"
        and _attributes(pin).get("type") == "output"
    }
    assert expected_control_labels <= control_outputs
    assert {"DIRECT_ADDR", "REG_ADDR", "OFFSET_ADDR", "REG_SELECTED"} <= input_labels
    assert all(len(label) <= 13 for label in input_labels)
    assert all(not label.startswith("EFFECTIVE_") for label in input_labels)


def test_effective_address_sheet_keeps_the_existing_selector_layout():
    """Keep only the documented status-wire exception at the top level."""
    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    tunnels = [
        component for component in circuit.findall("comp")
        if component.get("name") == "Tunnel"
    ]
    assert tunnels == []

    fbox = next(
        item for item in root.findall("circuit")
        if item.get("name") == "EffectiveAddress"
    )
    selector_parts = [
        component for component in fbox.findall("comp")
        if _attributes(component).get("label") in {
            "MEMORY_ADDRESS_REGISTER_SELECT",
            "MEMORY_ADDRESS_OFFSET_SELECT",
        }
    ]
    assert selector_parts
    assert {part.get("loc") for part in selector_parts} == {
        "(560,260)", "(570,620)",
    }
    assert {
        component.get("loc") for component in fbox.findall("comp")
        if component.get("name") == "Multiplexer"
    } == {"(750,220)", "(750,580)"}
    assert any(
        component.get("name") == "EffectiveAddress"
        for component in circuit.findall("comp")
    )


def test_top_level_follows_the_redrawn_effective_address_pin_order():
    """Keep integration wiring attached to signals, not obsolete pin positions."""

    root = ET.parse(PROJECT).getroot()
    circuit = _top_level(root)
    pairs = {
        "LOAD_ADDRESS_REGISTER": "LOAD_ADR_REG",
        "ADD_ADDRESS_REGISTER": "ADD_ADR_REG",
        "SUB_ADDRESS_REGISTER": "SUB_ADR_REG",
        "MUL_ADDRESS_REGISTER": "MUL_ADR_REG",
        "DIV_ADDRESS_REGISTER": "DIV_ADR_REG",
        "AND_ADDRESS_REGISTER": "AND_ADR_REG",
        "OR_ADDRESS_REGISTER": "OR_ADR_REG",
        "STORE_ADDRESS_REGISTER": "STORE_ADR_REG",
        "LOAD_ADDRESS_REGISTER_PLUS_OFFSET": "LOAD_REG_OFF",
        "ADD_ADDRESS_REGISTER_PLUS_OFFSET": "ADD_REG_OFF",
        "SUB_ADDRESS_REGISTER_PLUS_OFFSET": "SUB_REG_OFF",
        "MUL_ADDRESS_REGISTER_PLUS_OFFSET": "MUL_REG_OFF",
        "DIV_ADDRESS_REGISTER_PLUS_OFFSET": "DIV_REG_OFF",
        "AND_ADDRESS_REGISTER_PLUS_OFFSET": "AND_REG_OFF",
        "OR_ADDRESS_REGISTER_PLUS_OFFSET": "OR_REG_OFF",
        "STORE_ADDRESS_REGISTER_PLUS_OFFSET": "STORE_REG_OFF",
    }
    points = {
        point
        for source_label, target_label in pairs.items()
        for point in (
            _control_output(root, source_label),
            _subcircuit_input(root, "EffectiveAddress", target_label),
        )
    }
    adjacency = _electrical_adjacency(circuit, points)

    source_nets = []
    for source_label, target_label in pairs.items():
        source = _control_output(root, source_label)
        target = _subcircuit_input(root, "EffectiveAddress", target_label)
        reachable = _reachable(adjacency, source)
        assert target in reachable, (source_label, target_label)
        source_nets.append(reachable)

    for index, source_net in enumerate(source_nets):
        assert all(source_net.isdisjoint(other) for other in source_nets[index + 1:])


def test_effective_address_routes_use_separate_drawing_lanes():
    """Reject shorts without prescribing obsolete absolute routing lanes."""

    report = next(
        report for report in inspect_project(PROJECT)
        if report.name == "TinyCPUMain"
    )

    assert report.routing_conflicts == ()
    assert report.width_conflicts == ()


def test_div_operation_is_integrated_into_results_status_and_sticky_zero_error():
    """DIV crosses Operations once and owns the hardware divide-by-zero path."""
    root = ET.parse(PROJECT).getroot()
    top = _top_level(root)
    adjacency = _electrical_adjacency(top)
    for mode in ACCUMULATOR_ADDRESSING_MODES:
        label = f"DIV_{mode}"
        assert _subcircuit_input(root, "Operations", label) in _reachable(
            adjacency, _control_output(root, label)
        )
    zero = _subcircuit_output(root, "Operations", "DIVIDE_BY_ZERO")
    sticky = _subcircuit_input(root, "ErrorFlags", "SET_DIV0")
    assert sticky in _reachable(adjacency, zero)
    assert sticky not in _reachable(adjacency, _control_output(root, "SET_DIV0"))

    operations = next(c for c in root.findall("circuit") if c.get("name") == "Operations")
    labels = {_attributes(c).get("label"): c for c in operations.findall("comp")}
    assert labels["DIV_OPERATION"].get("name") == "DivSubCircuit"
    # Division joins the consolidated data/validity merges, but deliberately
    # has no overflow output: integer division can only fail for a zero divisor.
    assert _attributes(labels["RESULT"])["inputs"] == "8"
    assert "OVERFLOW_WITH_DIV" not in labels
    assert "OVERFLOW" not in {
        _attributes(pin).get("label")
        for pin in next(c for c in root.findall("circuit") if c.get("name") == "DivSubCircuit")
        .findall("comp")
    }


def test_and_operation_is_integrated_into_the_maintained_result_merge():
    """AND contributes its activity-neutral result to the shared tree."""

    root = ET.parse(PROJECT).getroot()
    top = _top_level(root)
    adjacency = _electrical_adjacency(top)
    for mode in ACCUMULATOR_ADDRESSING_MODES:
        label = f"AND_{mode}"
        assert _subcircuit_input(root, "Operations", label) in _reachable(
            adjacency, _control_output(root, label)
        )

    operations = next(
        circuit for circuit in root.findall("circuit")
        if circuit.get("name") == "Operations"
    )
    labels = {
        _attributes(component).get("label"): component
        for component in operations.findall("comp")
    }
    assert labels["AND_OPERATION"].get("name") == "AndSubCircuit"
    assert _attributes(labels["RESULT"])["inputs"] == "8"
    assert _attributes(labels["OPERATION_RESULT_VALID"])["inputs"] == "8"
    assert _attributes(labels["OPERATION_IS_ACTIVE"])["inputs"] == "8"
    arithmetic = next(c for c in root.findall("circuit") if c.get("name") == "AndArithmeticCircuit")
    assert not any(
        _attributes(component).get("label") == "INACTIVE_AND_DEFAULT"
        for component in arithmetic.findall("comp")
    )


def test_or_operation_is_integrated_into_results_and_invalid_operand_detection():
    """OR crosses Operations once and participates in every shared merge."""

    root = ET.parse(PROJECT).getroot()
    adjacency = _electrical_adjacency(_top_level(root))
    for mode in ACCUMULATOR_ADDRESSING_MODES:
        label = f"OR_{mode}"
        assert _subcircuit_input(root, "Operations", label) in _reachable(
            adjacency, _control_output(root, label)
        )

    operations = next(
        circuit for circuit in root.findall("circuit")
        if circuit.get("name") == "Operations"
    )
    labels = {
        _attributes(component).get("label"): component
        for component in operations.findall("comp")
    }
    assert labels["OR_OPERATION"].get("name") == "OrSubCircuit"
    assert _attributes(labels["RESULT"])["inputs"] == "8"
    assert _attributes(labels["OPERATION_RESULT_VALID"])["inputs"] == "8"
    assert _attributes(labels["OPERATION_IS_ACTIVE"])["inputs"] == "8"


def test_xor_operation_is_integrated_into_the_eight_way_merges():
    """XOR occupies the eighth input of every neutral shared output tree."""

    root = ET.parse(PROJECT).getroot()
    adjacency = _electrical_adjacency(_top_level(root))
    for mode in ACCUMULATOR_ADDRESSING_MODES:
        label = f"XOR_{mode}"
        assert _subcircuit_input(root, "Operations", label) in _reachable(
            adjacency, _control_output(root, label)
        )

    operations = next(
        circuit for circuit in root.findall("circuit")
        if circuit.get("name") == "Operations"
    )
    labels = {
        _attributes(component).get("label"): component
        for component in operations.findall("comp")
    }
    assert labels["XOR_OPERATION"].get("name") == "XorSubCircuit"
    assert _attributes(labels["RESULT"])["inputs"] == "8"
    assert _attributes(labels["OPERATION_RESULT_VALID"])["inputs"] == "8"
    assert _attributes(labels["OPERATION_IS_ACTIVE"])["inputs"] == "8"
    assert not {
        "RESULT_WITH_XOR", "RESULT_VALID_WITH_XOR",
        "OPERATION_ACTIVE_WITH_XOR",
    } & labels.keys()
