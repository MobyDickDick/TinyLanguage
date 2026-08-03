"""Instruction-set definition for TinyLanguage's educational TinyCPU.

TinyCPU deliberately uses explicit addressing modes.  This keeps both assembly
programs and the simulator easy to inspect: ``ADD_CONST`` cannot accidentally
be confused with ``ADD_ADDRESS``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


DEFAULT_DATA_BITS = 16
DEFAULT_ADDRESS_BITS = 12
WORD_MIN = -(2 ** (DEFAULT_DATA_BITS - 1))
WORD_MAX = 2 ** (DEFAULT_DATA_BITS - 1) - 1
DEFAULT_MEMORY_SIZE = 4096


def signed_bounds(bits: int) -> tuple[int, int]:
    """Return the two's-complement range for a data bus of *bits* bits."""

    if bits < 2:
        raise ValueError("data_bits must be at least 2")
    return -(2 ** (bits - 1)), 2 ** (bits - 1) - 1


def address_limit(bits: int) -> int:
    """Return the number of distinct addresses carried by *bits* bits."""

    if bits < 1:
        raise ValueError("address_bits must be at least 1")
    return 2**bits


class OperandKind(Enum):
    NONE = "none"
    VALUE = "value"
    ADDRESS = "address"
    OFFSET = "offset"
    TARGET = "target"


@dataclass(frozen=True)
class InstructionSpec:
    operand: OperandKind


@dataclass(frozen=True)
class Instruction:
    opcode: str
    operand: int | None = None


def _families() -> dict[str, InstructionSpec]:
    result: dict[str, InstructionSpec] = {}
    for operation in ("LOAD", "ADD", "SUB", "MUL", "DIV", "AND", "OR"):
        result[f"{operation}_CONST"] = InstructionSpec(OperandKind.VALUE)
        result[f"{operation}_ADDRESS"] = InstructionSpec(OperandKind.ADDRESS)
        result[f"{operation}_ADDRESS_REGISTER"] = InstructionSpec(OperandKind.NONE)
        result[f"{operation}_ADDRESS_REGISTER_PLUS_OFFSET"] = InstructionSpec(
            OperandKind.OFFSET
        )
    for operation in ("STORE",):
        result[f"{operation}_ADDRESS"] = InstructionSpec(OperandKind.ADDRESS)
        result[f"{operation}_ADDRESS_REGISTER"] = InstructionSpec(OperandKind.NONE)
        result[f"{operation}_ADDRESS_REGISTER_PLUS_OFFSET"] = InstructionSpec(
            OperandKind.OFFSET
        )
    return result


INSTRUCTION_SET = {
    **_families(),
    "LOAD_ADDRESS_REGISTER_CONST": InstructionSpec(OperandKind.VALUE),
    "LOAD_ADDRESS_REGISTER_ADDRESS": InstructionSpec(OperandKind.ADDRESS),
    "NOT": InstructionSpec(OperandKind.NONE),
    "JUMP_ADDRESS": InstructionSpec(OperandKind.TARGET),
    "JUMP_ZERO": InstructionSpec(OperandKind.TARGET),
    "JUMP_NOT_ZERO": InstructionSpec(OperandKind.TARGET),
    "JUMP_NEGATIVE": InstructionSpec(OperandKind.TARGET),
    "JUMP_ERROR": InstructionSpec(OperandKind.TARGET),
    "JUMP_NOT_ERROR": InstructionSpec(OperandKind.TARGET),
    "CLEAR_ERROR": InstructionSpec(OperandKind.NONE),
    "INPUT": InstructionSpec(OperandKind.NONE),
    "PRINT": InstructionSpec(OperandKind.NONE),
    "PRINT_ADDRESS": InstructionSpec(OperandKind.ADDRESS),
    "HALT": InstructionSpec(OperandKind.NONE),
    "HALT_ERROR": InstructionSpec(OperandKind.NONE),
}


DEFAULT_ALIASES = {
    "LDC": "LOAD_CONST",
    "LDA": "LOAD_ADDRESS",
    "LAR": "LOAD_ADDRESS_REGISTER",
    "LRO": "LOAD_ADDRESS_REGISTER_PLUS_OFFSET",
    "STA": "STORE_ADDRESS",
    "STAR": "STORE_ADDRESS_REGISTER",
    "STRO": "STORE_ADDRESS_REGISTER_PLUS_OFFSET",
    "ADC": "ADD_CONST",
    "ADA": "ADD_ADDRESS",
    "ADAR": "ADD_ADDRESS_REGISTER",
    "ADOR": "ADD_ADDRESS_REGISTER_PLUS_OFFSET",
    "SBC": "SUB_CONST",
    "SBA": "SUB_ADDRESS",
    "MUC": "MUL_CONST",
    "MUA": "MUL_ADDRESS",
    "DVC": "DIV_CONST",
    "DVA": "DIV_ADDRESS",
    "JMP": "JUMP_ADDRESS",
    "JZ": "JUMP_ZERO",
    "JNZ": "JUMP_NOT_ZERO",
    "JNEG": "JUMP_NEGATIVE",
    "JER": "JUMP_ERROR",
    "CER": "CLEAR_ERROR",
    "HLT": "HALT",
}
