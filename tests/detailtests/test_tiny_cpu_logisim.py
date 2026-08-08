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


def test_top_level_clock_reaches_every_stateful_block():
    """Follow the real symbol terminals instead of treating anchors as pins."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(item for item in root.findall("circuit") if item.get("name") == "TinyCPU")
    # These are the visible CLK terminals of the five stateful blocks on the
    # restored overview.  A subcircuit's ``loc`` is its symbol anchor, not an
    # electrical terminal, so anchor reachability would test the wrong points.
    clock_terminals = {
        "FetchDecode": "(430,160)",
        "Datapath": "(720,170)",
        "AddressPath": "(1020,130)",
        "Memory": "(1310,100)",
        "ErrorFlags": "(1610,20)",
    }
    clock = next(
        component.get("loc")
        for component in circuit.findall("comp")
        if component.get("name") == "Pin" and _attributes(component).get("label") == "CLK"
    )
    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    reachable = {clock}
    pending = [clock]
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert set(clock_terminals.values()) <= reachable


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


def test_top_level_reset_reaches_fetch_decode_only():
    """Reset the PC without coupling reset to any other top-level block."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(item for item in root.findall("circuit") if item.get("name") == "TinyCPU")
    reset_pins = [
        component
        for component in circuit.findall("comp")
        if component.get("name") == "Pin" and _attributes(component).get("label") == "RESET"
    ]
    assert len(reset_pins) == 1

    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    reachable = {reset_pins[0].get("loc")}
    pending = list(reachable)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert "(430,170)" in reachable  # FetchDecode.RESET
    assert reachable.isdisjoint(
        {
            "(720,180)",  # Datapath reset-shaped terminal
            "(1020,140)",  # AddressPath reset-shaped terminal
            "(1310,110)",  # Memory control terminal
            "(1610,30)",  # ErrorFlags control terminal
        }
    )


def test_top_level_opcode_reaches_decode_controls_only():
    """Start decode integration with the independently named opcode bus."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(item for item in root.findall("circuit") if item.get("name") == "TinyCPU")
    controls = [
        component
        for component in circuit.findall("comp")
        if component.get("name") == "FetchDecodeControls"
    ]
    assert [component.get("loc") for component in controls] == ["(330,400)"]

    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    # Automatic Logisim symbols place FetchDecode.OPCODE at the second output
    # terminal and the sole FetchDecodeControls.OPCODE input after its 51
    # output terminals.
    opcode_source = "(330,110)"
    opcode_target = "(430,910)"
    reachable = {opcode_source}
    pending = list(reachable)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert opcode_target in reachable
    assert reachable.isdisjoint({"(80,70)", "(80,210)"})


def test_top_level_clear_error_reaches_error_flags_only():
    """Route one decoded control without coupling it to clock or reset."""

    root = ET.parse(PROJECT).getroot()
    circuit = next(
        item for item in root.findall("circuit") if item.get("name") == "TinyCPU"
    )
    adjacency = {}
    for wire in circuit.findall("wire"):
        start, end = wire.get("from"), wire.get("to")
        adjacency.setdefault(start, set()).add(end)
        adjacency.setdefault(end, set()).add(start)

    # CLEAR_ERROR is output 40 on the automatic FetchDecodeControls symbol;
    # the matching ErrorFlags input is its second automatic-symbol terminal.
    clear_source = "(430,790)"
    clear_target = "(1610,30)"
    reachable = {clear_source}
    pending = list(reachable)
    while pending:
        for endpoint in adjacency.get(pending.pop(), ()):
            if endpoint not in reachable:
                reachable.add(endpoint)
                pending.append(endpoint)

    assert clear_target in reachable
    assert reachable.isdisjoint(
        {
            "(80,70)",  # CLK
            "(80,210)",  # RESET
            "(430,910)",  # FetchDecodeControls.OPCODE
            "(1610,20)",  # ErrorFlags.CLK
        }
    )


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
    set_ovf_source = "(430,850)"
    set_ovf_target = "(1610,40)"
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
            "(80,210)",  # RESET
            "(430,910)",  # FetchDecodeControls.OPCODE
            "(430,790)",  # FetchDecodeControls.CLEAR_ERROR
            "(1610,20)",  # ErrorFlags.CLK
            "(1610,30)",  # ErrorFlags.CLEAR_ERROR
        }
    )


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
        "connectivity",
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
