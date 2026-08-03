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


PROJECT = Path(__file__).parents[2] / "hardware" / "logisim" / "TinyCPU.circ"
HARDWARE = PROJECT.parent


def _attributes(component):
    return {attribute.get("name"): attribute.get("val") for attribute in component}


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
