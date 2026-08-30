"""Strictly error-propagating simulator for TinyCPU."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from tiny_cpu_assembler import Program
from tiny_cpu_isa import (
    DEFAULT_ADDRESS_BITS,
    DEFAULT_DATA_BITS,
    DEFAULT_MEMORY_SIZE,
    Instruction,
    address_limit,
    signed_bounds,
)


@dataclass
class Cell:
    value: int = 0
    valid: bool = False


class ErrorFlag(Enum):
    OVERFLOW = "OVF"
    DIVISION_BY_ZERO = "DIV0"
    INVALID_ADDRESS = "ADDR"
    INVALID_OPERAND = "INV"
    INVALID_INSTRUCTION = "ILL"
    INVALID_INPUT = "INPUT"


class TinyCPU:
    """A width-parametric accumulator computer with validity tracking.

    Error flags are sticky. ``CLEAR_ERROR`` clears flags, but never repairs a
    register or memory cell; only writing a newly valid value does that.
    """

    def __init__(
        self,
        memory_size: int = DEFAULT_MEMORY_SIZE,
        inputs: Iterable[int] = (),
        output: Callable[[int], None] | None = None,
        *,
        data_bits: int = DEFAULT_DATA_BITS,
        address_bits: int = DEFAULT_ADDRESS_BITS,
    ) -> None:
        self.data_bits = data_bits
        self.address_bits = address_bits
        self.word_min, self.word_max = signed_bounds(data_bits)
        self.address_space = address_limit(address_bits)
        if memory_size <= 0:
            raise ValueError("memory_size must be positive")
        if memory_size > self.address_space:
            raise ValueError(
                f"memory_size {memory_size} exceeds {address_bits}-bit address space"
            )
        self.memory = [Cell() for _ in range(memory_size)]
        self.accumulator = Cell()
        self.address_register = Cell()
        self.pc = 0
        self.zero = True
        self.negative = False
        self.errors: set[ErrorFlag] = set()
        self.halted = False
        self.halted_with_error = False
        self._inputs = iter(inputs)
        self.output_values: list[int] = []
        self._output = output

    @property
    def error(self) -> bool:
        return bool(self.errors)

    def _set_accumulator(self, value: int, valid: bool = True) -> None:
        self.accumulator = Cell(value if valid else 0, valid)
        self.zero = self.accumulator.value == 0
        self.negative = valid and value < 0

    def _fail(self, flag: ErrorFlag, target: str = "accumulator") -> None:
        self.errors.add(flag)
        if target == "accumulator":
            self._set_accumulator(0, False)
        elif target == "address_register":
            self.address_register = Cell(0, False)

    def _checked(self, value: int) -> int | None:
        if value < self.word_min or value > self.word_max:
            self._fail(ErrorFlag.OVERFLOW)
            return None
        return value

    def _set_address_register(self, value: int) -> None:
        if not 0 <= value < self.address_space:
            self._fail(ErrorFlag.INVALID_ADDRESS, target="address_register")
            return
        self.address_register = Cell(value, True)

    def _cell(self, address: int) -> Cell | None:
        if not 0 <= address < len(self.memory):
            self._fail(ErrorFlag.INVALID_ADDRESS)
            return None
        return self.memory[address]

    def _effective_address(self, instruction: Instruction) -> int | None:
        if instruction.opcode.endswith("_ADDRESS_REGISTER"):
            if not self.address_register.valid:
                self._fail(ErrorFlag.INVALID_OPERAND)
                return None
            return self.address_register.value
        if instruction.opcode.endswith("_ADDRESS_REGISTER_PLUS_OFFSET"):
            if not self.address_register.valid:
                self._fail(ErrorFlag.INVALID_OPERAND)
                return None
            address = self.address_register.value + int(instruction.operand or 0)
            if not 0 <= address < self.address_space:
                self._fail(ErrorFlag.INVALID_ADDRESS)
                return None
            return address
        return instruction.operand

    def _read_operand(self, instruction: Instruction) -> int | None:
        if instruction.opcode.endswith("_CONST"):
            return self._checked(int(instruction.operand))
        address = self._effective_address(instruction)
        if address is None:
            return None
        cell = self._cell(address)
        if cell is None:
            return None
        if not cell.valid:
            self._fail(ErrorFlag.INVALID_OPERAND)
            return None
        return cell.value

    def _binary(self, opcode: str, operand: int) -> None:
        if not self.accumulator.valid:
            self._fail(ErrorFlag.INVALID_OPERAND)
            return
        left = self.accumulator.value
        operation = opcode.split("_", 1)[0]
        if operation == "ADD":
            result = left + operand
        elif operation == "SUB":
            result = left - operand
        elif operation == "MUL":
            result = left * operand
        elif operation == "DIV":
            if operand == 0:
                self._fail(ErrorFlag.DIVISION_BY_ZERO)
                return
            # TinyCPU division truncates toward zero.  Do this with integer
            # arithmetic: converting the operands to float first overflows for
            # otherwise valid wide-bus values and can lose precision even for
            # smaller values.
            quotient = abs(left) // abs(operand)
            result = -quotient if (left < 0) != (operand < 0) else quotient
        elif operation == "AND":
            result = left & operand
        elif operation == "OR":
            result = left | operand
        elif operation == "XOR":
            result = left ^ operand
        else:
            self._fail(ErrorFlag.INVALID_INSTRUCTION)
            return
        checked = self._checked(result)
        if checked is not None:
            self._set_accumulator(checked)

    def step(self, instructions: tuple[Instruction, ...]) -> None:
        if self.halted:
            return
        if not 0 <= self.pc < len(instructions):
            self._fail(ErrorFlag.INVALID_ADDRESS)
            self.halted = True
            self.halted_with_error = True
            return
        instruction = instructions[self.pc]
        self.pc += 1
        opcode = instruction.opcode

        if opcode == "LOAD_ADDRESS_REGISTER_CONST":
            self._set_address_register(int(instruction.operand))
        elif opcode == "LOAD_ADDRESS_REGISTER_ADDRESS":
            value = self._read_operand(
                Instruction("LOAD_ADDRESS", instruction.operand)
            )
            if value is None:
                self.address_register = Cell(0, False)
            else:
                self._set_address_register(value)
        elif opcode.startswith("LOAD_"):
            value = self._read_operand(instruction)
            if value is not None:
                self._set_accumulator(value)
        elif opcode.startswith("STORE_"):
            address = self._effective_address(instruction)
            cell = self._cell(address) if address is not None else None
            if cell is not None:
                if self.accumulator.valid:
                    cell.value, cell.valid = self.accumulator.value, True
                else:
                    cell.value, cell.valid = 0, False
                    self.errors.add(ErrorFlag.INVALID_OPERAND)
        elif opcode.startswith(("ADD_", "SUB_", "MUL_", "DIV_", "AND_", "OR_", "XOR_")):
            operand = self._read_operand(instruction)
            if operand is not None:
                self._binary(opcode, operand)
        elif opcode == "NOT":
            if not self.accumulator.valid:
                self._fail(ErrorFlag.INVALID_OPERAND)
            else:
                value = self._checked(~self.accumulator.value)
                if value is not None:
                    self._set_accumulator(value)
        elif opcode.startswith("JUMP_"):
            take = {
                "JUMP_ADDRESS": True,
                "JUMP_ZERO": self.accumulator.valid and self.zero,
                "JUMP_NOT_ZERO": self.accumulator.valid and not self.zero,
                "JUMP_NEGATIVE": self.accumulator.valid and self.negative,
                "JUMP_ERROR": self.error,
                "JUMP_NOT_ERROR": not self.error,
            }.get(opcode)
            if take is None:
                self._fail(ErrorFlag.INVALID_INSTRUCTION)
            elif take:
                target = int(instruction.operand)
                if 0 <= target < len(instructions):
                    self.pc = target
                else:
                    self._fail(ErrorFlag.INVALID_ADDRESS)
        elif opcode == "CLEAR_ERROR":
            self.errors.clear()
        elif opcode == "INPUT":
            try:
                value = next(self._inputs)
            except (StopIteration, TypeError, ValueError):
                self._fail(ErrorFlag.INVALID_INPUT)
            else:
                checked = self._checked(value)
                if checked is not None:
                    self._set_accumulator(checked)
        elif opcode in {"PRINT", "PRINT_ADDRESS"}:
            if opcode == "PRINT":
                cell = self.accumulator
            else:
                cell = self._cell(int(instruction.operand))
            if cell is None or not cell.valid:
                self._fail(ErrorFlag.INVALID_OPERAND)
            else:
                self.output_values.append(cell.value)
                if self._output is not None:
                    self._output(cell.value)
        elif opcode in {"HALT", "HALT_ERROR"}:
            self.halted = True
            self.halted_with_error = opcode == "HALT_ERROR" or self.error
        else:
            self._fail(ErrorFlag.INVALID_INSTRUCTION)

    def run(
        self,
        program: Program | tuple[Instruction, ...],
        max_steps: int = 100_000,
    ) -> None:
        instructions = program.instructions if isinstance(program, Program) else program
        if len(instructions) > self.address_space:
            self._fail(ErrorFlag.INVALID_ADDRESS)
            self.halted = True
            self.halted_with_error = True
            return
        for _ in range(max_steps):
            if self.halted:
                return
            self.step(instructions)
        raise RuntimeError(f"execution limit of {max_steps} steps exceeded")
