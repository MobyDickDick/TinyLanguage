"""Execute the checked-in TinyCPU examples as output-based acceptance tests."""

from __future__ import annotations

from pathlib import Path
import shlex

import pytest

from tiny_cpu_cli import main
from tiny_cpu_assembler import assemble
from tiny_cpu_isa import INSTRUCTION_SET


EXAMPLES = Path(__file__).parents[2] / "examples" / "tiny_cpu"
PROGRAMS = sorted(EXAMPLES.glob("*.tcpu"))
OPERATION_EXAMPLES = {
    "load": {
        name
        for name in INSTRUCTION_SET
        if name.startswith("LOAD_")
        and name
        not in {"LOAD_ADDRESS_REGISTER_CONST", "LOAD_ADDRESS_REGISTER_ADDRESS"}
    },
    "load_address_register": {"LOAD_ADDRESS_REGISTER_CONST", "LOAD_ADDRESS_REGISTER_ADDRESS"},
    "store": {name for name in INSTRUCTION_SET if name.startswith("STORE_")},
    "add": {name for name in INSTRUCTION_SET if name.startswith("ADD_")},
    "sub": {name for name in INSTRUCTION_SET if name.startswith("SUB_")},
    "mul": {name for name in INSTRUCTION_SET if name.startswith("MUL_")},
    "div": {name for name in INSTRUCTION_SET if name.startswith("DIV_")},
    "and": {name for name in INSTRUCTION_SET if name.startswith("AND_")},
    "or": {name for name in INSTRUCTION_SET if name.startswith("OR_")},
    "xor": {name for name in INSTRUCTION_SET if name.startswith("XOR_")},
    **{
        operation.lower(): {operation}
        for operation in (
            "NOT",
            "JUMP_ADDRESS",
            "JUMP_ZERO",
            "JUMP_NOT_ZERO",
            "JUMP_NEGATIVE",
            "JUMP_ERROR",
            "JUMP_NOT_ERROR",
            "CLEAR_ERROR",
            "INPUT",
            "PRINT",
            "PRINT_ADDRESS",
            "HALT",
            "HALT_ERROR",
        )
    },
}


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda path: path.stem)
def test_tiny_cpu_example_matches_expected_output(program: Path, capsys) -> None:
    """Run each example through the public CLI and compare its complete output."""

    expected_output = program.with_suffix(".stdout")
    assert expected_output.is_file(), f"missing expected output: {expected_output}"

    arguments_file = program.with_suffix(".args")
    arguments = (
        shlex.split(arguments_file.read_text(encoding="utf-8"))
        if arguments_file.exists()
        else []
    )
    expected_exit_file = program.with_suffix(".exit")
    expected_exit = (
        int(expected_exit_file.read_text(encoding="utf-8"))
        if expected_exit_file.exists()
        else 0
    )

    exit_code = main([*arguments, str(program)])

    captured = capsys.readouterr()
    assert exit_code == expected_exit
    assert captured.out == expected_output.read_text(encoding="utf-8")
    assert captured.err == ""


def test_tiny_cpu_example_suite_is_not_empty() -> None:
    """Prevent an accidentally empty discovery set from silently passing."""

    assert PROGRAMS, f"no TinyCPU example programs found in {EXAMPLES}"


def test_every_tiny_cpu_operation_has_a_matching_example() -> None:
    """Keep one named example for every operation and all its address modes."""

    programs_by_name = {program.stem: program for program in PROGRAMS}
    assert programs_by_name.keys() == OPERATION_EXAMPLES.keys()

    for name, expected_opcodes in OPERATION_EXAMPLES.items():
        program = assemble(programs_by_name[name].read_text(encoding="utf-8"))
        actual_opcodes = {instruction.opcode for instruction in program.instructions}
        assert expected_opcodes <= actual_opcodes, (
            f"{name}.tcpu does not demonstrate: "
            f"{', '.join(sorted(expected_opcodes - actual_opcodes))}"
        )
