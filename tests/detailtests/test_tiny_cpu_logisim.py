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
CI_WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"


def _attributes(component):
    return {attribute.get("name"): attribute.get("val") for attribute in component}


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
        "TinyCPU", "FetchDecode", "Datapath", "AddressPath", "Memory", "ErrorFlags"
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
    assert address_registers == {"AR": "12", "AR_VALID": "1"}


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

    datapath_parts = {
        _attributes(component).get("label"): component.get("name")
        for component in circuits["Datapath"].findall("comp")
    }
    address_parts = {
        _attributes(component).get("label"): component.get("name")
        for component in circuits["AddressPath"].findall("comp")
    }
    assert datapath_parts["ACC_STATUS"] == "Comparator"
    assert address_parts["OFFSET_ADDER"] == "Adder"


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
    assert has_wire("(240,150)", "(340,150)")      # ADDRESS_IN -> AR.D
    assert has_wire("(300,170)", "(340,170)")      # AR_LOAD -> AR.WE
    assert has_wire("(320,190)", "(340,190)")      # CLK -> AR clock
    assert has_wire("(240,330)", "(340,330)")      # VALID_IN -> AR_VALID.D
    assert has_wire("(280,350)", "(340,350)")      # AR_LOAD -> AR_VALID.WE
    assert has_wire("(320,370)", "(340,370)")      # CLK -> AR_VALID clock

    # The address register output and OFFSET terminate at the adder's distinct
    # A and B pins. Neither input bus shares a segment with the other.
    assert has_wire("(400,150)", "(420,150)")      # AR.Q -> address net
    assert has_wire("(420,190)", "(470,190)")
    # OFFSET detours around AR's one-bit reset terminal at (370,210); a
    # straight bus here makes Logisim report incompatible 12/1-bit widths.
    assert has_wire("(80,210)", "(200,210)")
    assert has_wire("(200,210)", "(200,240)")
    assert has_wire("(200,240)", "(450,240)")
    assert has_wire("(450,210)", "(450,240)")
    assert has_wire("(450,210)", "(470,210)")
    assert has_wire("(520,200)", "(620,200)")
    # Carry-out is the one-bit terminal below the adder at (500,220), not a
    # point below its 12-bit sum output anchor.
    assert has_wire("(500,220)", "(560,220)")
    assert has_wire("(400,330)", "(540,330)")      # AR_VALID.Q -> output


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
    assert {"(270,140)", "(270,160)", "(270,170)"} <= endpoints
    assert {"(270,220)", "(270,240)", "(270,250)"} <= endpoints

    # The comparator receives ACC and the zero constant on separate 16-bit
    # inputs; neither is accidentally attached to a one-bit status output.
    assert {"(360,260)", "(360,280)", "(400,270)", "(400,280)"} <= endpoints


def test_ap3_memory_shares_address_write_enable_and_clock():
    root = ET.parse(PROJECT).getroot()
    memory = next(c for c in root.findall("circuit") if c.get("name") == "Memory")
    pins = {
        _attributes(component).get("label"): _attributes(component)
        for component in memory.findall("comp")
        if component.get("name") == "Pin"
    }
    assert pins["ADDRESS"]["width"] == "12"
    assert pins["DATA_IN"]["width"] == "16"
    assert pins["DATA_OUT"]["width"] == "16"
    assert {"VALID_IN", "WRITE_ENABLE", "CLK", "VALID_OUT"} <= pins.keys()

    endpoints = {
        point
        for wire in memory.findall("wire")
        for point in (wire.get("from"), wire.get("to"))
    }
    # Both RAM control-port coordinates are present on their shared nets.
    assert {"(330,120)", "(330,200)"} <= endpoints
    assert {"(330,180)", "(330,260)"} <= endpoints
    assert {"(330,190)", "(330,270)"} <= endpoints


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


def test_ap3_error_flag_feedback_is_clocked_not_combinational():
    root = ET.parse(PROJECT).getroot()
    errors = next(c for c in root.findall("circuit") if c.get("name") == "ErrorFlags")
    wires = {
        (wire.get("from"), wire.get("to"))
        for wire in errors.findall("wire")
    }

    for register_y in (200, 270, 340, 410, 480, 550):
        # Q feeds the hold gate, while NOT_CLEAR_ERROR uses its other input.
        assert (f"(430,{register_y})", f"(430,{register_y + 50})") in wires
        assert (
            f"(210,{register_y + 10})",
            f"(220,{register_y + 10})",
        ) in wires
        assert (
            f"(190,{register_y + 30})",
            f"(220,{register_y + 30})",
        ) in wires

        # The OR result enters D and CLK reaches the clock terminal.  The only
        # feedback consequently crosses the register before returning to HOLD.
        assert (f"(330,{register_y})", f"(400,{register_y})") in wires
        clock_target = f"(400,{register_y + 20})"
        graph = {}
        for start, end in wires:
            graph.setdefault(start, set()).add(end)
            graph.setdefault(end, set()).add(start)
        reachable = {"(80,140)"}
        pending = ["(80,140)"]
        while pending:
            for endpoint in graph.get(pending.pop(), ()):
                if endpoint not in reachable:
                    reachable.add(endpoint)
                    pending.append(endpoint)
        assert clock_target in reachable


def test_ap4_fetch_decode_has_pc_rom_core_controls_and_error_halt():
    root = ET.parse(PROJECT).getroot()
    fetch = next(c for c in root.findall("circuit") if c.get("name") == "FetchDecode")
    parts = {
        _attributes(component).get("label"): (
            component.get("name"),
            _attributes(component),
        )
        for component in fetch.findall("comp")
        if _attributes(component).get("label")
    }

    assert parts["PC"] == ("Register", {"appearance": "logisim_evolution", "label": "PC", "width": "12"})
    assert parts["INSTRUCTION_ROM"][0] == "ROM"
    assert parts["INSTRUCTION_ROM"][1]["addrWidth"] == "12"
    assert parts["INSTRUCTION_ROM"][1]["dataWidth"] == str(WORD_BITS)
    assert parts["ISA_DECODER"][0] == "Decoder"
    assert parts["PC_INCREMENT"][0] == "Adder"
    assert parts["PC_SOURCE"][0] == "Multiplexer"
    assert parts["PC_RANGE"][0] == "Comparator"
    assert parts["JNZ_TAKEN"][0] == "AND Gate"
    controls = {
        "LOAD_CONST", "STORE_ADDRESS", "ADD_ADDRESS", "JUMP_NOT_ZERO",
        "PRINT", "HALT", "SET_ADDR", "HALT_ERROR",
    }
    assert controls <= parts.keys()


def test_ap6_fetch_decode_exposes_every_symbolic_isa_control():
    root = ET.parse(PROJECT).getroot()
    fetch = next(c for c in root.findall("circuit") if c.get("name") == "FetchDecode")
    parts = {
        _attributes(component).get("label"): (component.get("name"), _attributes(component))
        for component in fetch.findall("comp")
        if _attributes(component).get("label")
    }

    assert parts["ISA_DECODER"][1]["select"] == "6"
    assert set(INSTRUCTION_SET) <= parts.keys()
    assert {"ZERO", "NEGATIVE", "ERROR"} <= parts.keys()
    error_outputs = {
        "SET_OVF", "SET_DIV0", "SET_ADDR", "SET_INV", "SET_ILL", "SET_INPUT"
    }
    assert error_outputs <= parts.keys()


def test_ap5_rom_contains_the_countdown_fixture():
    root = ET.parse(PROJECT).getroot()
    fetch = next(c for c in root.findall("circuit") if c.get("name") == "FetchDecode")
    rom = next(
        component
        for component in fetch.findall("comp")
        if _attributes(component).get("label") == "INSTRUCTION_ROM"
    )

    contents_element = next(
        item for item in rom.findall("a") if item.get("name") == "contents"
    )
    contents = (contents_element.text or "").strip().splitlines()
    assert contents[0] == "addr/data: 12 22"
    assert " ".join(contents[1:]).split() == [
        "00ffff", "1c0065", "000003", "1c0064", "2a0000",
        "050065", "1c0064", "240004", "2c0000",
    ]


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


def test_ap7_encoder_generated_rom_is_loaded_in_logisim():
    program = assemble((HARDWARE / "ap5_countdown.tcpu").read_text())
    generated = rom_image(encode_program(program))
    assert (HARDWARE / "ap5_countdown.rom").read_text() == generated

    root = ET.parse(PROJECT).getroot()
    fetch = next(c for c in root.findall("circuit") if c.get("name") == "FetchDecode")
    rom = next(c for c in fetch.findall("comp") if _attributes(c).get("label") == "INSTRUCTION_ROM")
    embedded = next(a for a in rom.findall("a") if a.get("name") == "contents").text
    embedded_lines = embedded.strip().splitlines()
    generated_lines = generated.strip().splitlines()
    assert embedded_lines[0] == generated_lines[0]
    assert " ".join(embedded_lines[1:]).split() == " ".join(generated_lines[1:]).split()


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


@pytest.mark.parametrize("instruction", tuple(INSTRUCTION_SET))
def test_ap6_each_instruction_has_a_connected_decode_output(instruction):
    root = ET.parse(PROJECT).getroot()
    fetch = next(c for c in root.findall("circuit") if c.get("name") == "FetchDecode")
    pin = next(
        component
        for component in fetch.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("label") == instruction
    )
    endpoints = {
        endpoint
        for wire in fetch.findall("wire")
        for endpoint in (wire.get("from"), wire.get("to"))
    }
    assert _attributes(pin).get("type") == "output"
    assert pin.get("loc") in endpoints


@pytest.mark.parametrize(
    "signal",
    ("SET_OVF", "SET_DIV0", "SET_ADDR", "SET_INV", "SET_ILL", "SET_INPUT"),
)
def test_ap6_each_error_path_has_a_connected_output(signal):
    root = ET.parse(PROJECT).getroot()
    fetch = next(c for c in root.findall("circuit") if c.get("name") == "FetchDecode")
    pin = next(
        component
        for component in fetch.findall("comp")
        if component.get("name") == "Pin"
        and _attributes(component).get("label") == signal
    )
    endpoints = {
        endpoint
        for wire in fetch.findall("wire")
        for endpoint in (wire.get("from"), wire.get("to"))
    }
    assert pin.get("loc") in endpoints
