"""Lightweight intermediate representation for the native backend.

The native backend uses a compact stack-based IR to keep the code
generator and VM loosely coupled. This module centralises the opcode
definitions, container dataclasses, and a human-readable formatter so
tests can assert against the emitted instructions without parsing
private structures.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class Opcode(str, Enum):
    """Enumerate the stack-machine operations used by the VM."""

    PUSH_CONST = "PUSH_CONST"
    LOAD = "LOAD"
    STORE = "STORE"
    BINARY = "BINARY"
    PRINT = "PRINT"
    JUMP = "JUMP"
    JUMP_IF_FALSE = "JUMP_IF_FALSE"
    CALL = "CALL"
    POP = "POP"
    RETURN = "RETURN"


@dataclass
class Instruction:
    """Single opcode plus optional operand."""

    op: Opcode
    arg: Any = None


@dataclass
class FunctionIR:
    """Bytecode for a named function."""

    name: str
    params: List[str]
    instructions: List[Instruction]


@dataclass
class ProgramIR:
    """Entry sequence and function table for the VM."""

    entry: List[Instruction]
    functions: Dict[str, FunctionIR]


def format_program(program: ProgramIR) -> str:
    """Return a readable representation of the program's instructions."""

    def _fmt_block(label: str, instrs: List[Instruction]) -> List[str]:
        lines: List[str] = []
        for idx, instr in enumerate(instrs):
            suffix = f" {instr.arg}" if instr.arg is not None else ""
            lines.append(f"{label}[{idx:02d}]: {instr.op.value}{suffix}")
        return lines

    lines = _fmt_block("entry", program.entry)
    for func in program.functions.values():
        header = f"function {func.name}({', '.join(func.params)})"
        lines.append(header)
        lines.extend(_fmt_block(f"  {func.name}", func.instructions))
    return "\n".join(lines)
