"""Versioned machine-code encoder and ROM tooling for TinyCPU.

Machine format version 1 stores a six-bit opcode in bits 21..16 and a
two's-complement or unsigned operand in bits 15..0.  The explicit opcode map is
part of the compatibility contract: it must never be reordered in place.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tiny_cpu_assembler import Program, assemble
from tiny_cpu_isa import INSTRUCTION_SET, Instruction, OperandKind, signed_bounds


FORMAT_VERSION = 1
OPCODE_BITS = 6
OPERAND_BITS = 16
WORD_BITS = OPCODE_BITS + OPERAND_BITS
ADDRESS_BITS = 12

# Append-only for format version 1.  Changing an assigned value requires a new
# format version, even when the symbolic instruction set remains unchanged.
OPCODES = {
    name: opcode
    for opcode, name in enumerate(
        (
            "LOAD_CONST", "LOAD_ADDRESS", "LOAD_ADDRESS_REGISTER",
            "LOAD_ADDRESS_REGISTER_PLUS_OFFSET", "ADD_CONST", "ADD_ADDRESS",
            "ADD_ADDRESS_REGISTER", "ADD_ADDRESS_REGISTER_PLUS_OFFSET",
            "SUB_CONST", "SUB_ADDRESS", "SUB_ADDRESS_REGISTER",
            "SUB_ADDRESS_REGISTER_PLUS_OFFSET", "MUL_CONST", "MUL_ADDRESS",
            "MUL_ADDRESS_REGISTER", "MUL_ADDRESS_REGISTER_PLUS_OFFSET",
            "DIV_CONST", "DIV_ADDRESS", "DIV_ADDRESS_REGISTER",
            "DIV_ADDRESS_REGISTER_PLUS_OFFSET", "AND_CONST", "AND_ADDRESS",
            "AND_ADDRESS_REGISTER", "AND_ADDRESS_REGISTER_PLUS_OFFSET",
            "OR_CONST", "OR_ADDRESS", "OR_ADDRESS_REGISTER",
            "OR_ADDRESS_REGISTER_PLUS_OFFSET", "STORE_ADDRESS",
            "STORE_ADDRESS_REGISTER", "STORE_ADDRESS_REGISTER_PLUS_OFFSET",
            "LOAD_ADDRESS_REGISTER_CONST", "LOAD_ADDRESS_REGISTER_ADDRESS", "NOT",
            "JUMP_ADDRESS", "JUMP_ZERO", "JUMP_NOT_ZERO", "JUMP_NEGATIVE",
            "JUMP_ERROR", "JUMP_NOT_ERROR", "CLEAR_ERROR", "INPUT", "PRINT",
            "PRINT_ADDRESS", "HALT", "HALT_ERROR",
        )
    )
}
OPCODE_NAMES = {value: name for name, value in OPCODES.items()}


class MachineCodeError(ValueError):
    """Raised when an instruction or ROM image violates format version 1."""


def _encoded_operand(instruction: Instruction) -> int:
    kind = INSTRUCTION_SET[instruction.opcode].operand
    operand = instruction.operand
    if kind is OperandKind.NONE:
        if operand is not None:
            raise MachineCodeError(f"{instruction.opcode} takes no operand")
        return 0
    if operand is None:
        raise MachineCodeError(f"{instruction.opcode} requires an operand")
    if kind in (OperandKind.ADDRESS, OperandKind.TARGET):
        if not 0 <= operand < 2**ADDRESS_BITS:
            raise MachineCodeError(f"{instruction.opcode} address is outside 12-bit range")
        return operand
    minimum, maximum = signed_bounds(OPERAND_BITS)
    if not minimum <= operand <= maximum:
        raise MachineCodeError(f"{instruction.opcode} operand is outside 16-bit range")
    return operand & ((1 << OPERAND_BITS) - 1)


def encode_instruction(instruction: Instruction) -> int:
    """Encode one symbolic instruction as a version-1 22-bit word."""

    try:
        opcode = OPCODES[instruction.opcode]
    except KeyError as error:
        raise MachineCodeError(f"unknown instruction {instruction.opcode!r}") from error
    return (opcode << OPERAND_BITS) | _encoded_operand(instruction)


def decode_word(word: int) -> Instruction:
    """Decode one version-1 word, rejecting reserved opcodes and stray bits."""

    if not 0 <= word < 2**WORD_BITS:
        raise MachineCodeError("machine word is outside 22-bit range")
    opcode = word >> OPERAND_BITS
    try:
        name = OPCODE_NAMES[opcode]
    except KeyError as error:
        raise MachineCodeError(f"reserved opcode 0x{opcode:02x}") from error
    raw_operand = word & ((1 << OPERAND_BITS) - 1)
    kind = INSTRUCTION_SET[name].operand
    if kind is OperandKind.NONE:
        if raw_operand:
            raise MachineCodeError(f"{name} has non-zero reserved operand bits")
        operand = None
    elif kind in (OperandKind.ADDRESS, OperandKind.TARGET):
        if raw_operand >= 2**ADDRESS_BITS:
            raise MachineCodeError(f"{name} address is outside 12-bit range")
        operand = raw_operand
    else:
        operand = raw_operand if raw_operand < 2**15 else raw_operand - 2**16
    return Instruction(name, operand)


def encode_program(program: Program | tuple[Instruction, ...]) -> tuple[int, ...]:
    """Encode every instruction in *program* in source order."""

    instructions = program.instructions if isinstance(program, Program) else program
    return tuple(encode_instruction(instruction) for instruction in instructions)


def rom_image(words: tuple[int, ...]) -> str:
    """Render words in Logisim's native address/data text format."""

    body = " ".join(f"{word:06x}" for word in words)
    return f"addr/data: 12 {WORD_BITS}\n{body}\n"


def listing(program: Program, words: tuple[int, ...]) -> str:
    """Render a stable address, word, and canonical-instruction listing."""

    rows = [f"; TinyCPU machine format v{FORMAT_VERSION} ({WORD_BITS}-bit words)"]
    for address, (word, instruction) in enumerate(zip(words, program.instructions)):
        operand = "" if instruction.operand is None else str(instruction.operand)
        rows.append(f"{address:03x}  {word:06x}  {instruction.opcode}({operand})")
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Encode TinyCPU assembly for Logisim")
    parser.add_argument("program", type=Path)
    parser.add_argument("--rom", type=Path, help="write the Logisim ROM image")
    parser.add_argument("--listing", type=Path, help="write an annotated listing")
    args = parser.parse_args(argv)
    program = assemble(args.program.read_text(encoding="utf-8"))
    words = encode_program(program)
    image = rom_image(words)
    if args.rom:
        args.rom.write_text(image, encoding="utf-8")
    else:
        print(image, end="")
    if args.listing:
        args.listing.write_text(listing(program, words), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
