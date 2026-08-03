"""Assembler for the function-style TinyCPU assembly language."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tiny_cpu_isa import DEFAULT_ALIASES, INSTRUCTION_SET, Instruction, OperandKind


class AssemblyError(ValueError):
    """Raised for a source error with a stable line-oriented diagnostic."""


@dataclass(frozen=True)
class Program:
    instructions: tuple[Instruction, ...]
    labels: dict[str, int]
    values: dict[str, int]


_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_ALIAS_RE = re.compile(rf"^({_NAME})\s*:=\s*({_NAME}|[+-]?\d+)\s*$")
_LABEL_RE = re.compile(rf"^({_NAME})\s*:\s*(.*)$")
_CALL_RE = re.compile(rf"^({_NAME})\s*\((.*?)\)\s*$")


def _source_lines(source: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for number, raw in enumerate(source.splitlines(), 1):
        line = raw.split(";", 1)[0].split("//", 1)[0].strip()
        if line:
            lines.append((number, line))
    return lines


def assemble(source: str) -> Program:
    """Assemble *source*, resolving labels and instruction/value aliases."""

    aliases = dict(DEFAULT_ALIASES)
    values: dict[str, int] = {}
    labels: dict[str, int] = {}
    pending: list[tuple[int, str]] = []

    for line_number, original in _source_lines(source):
        line = original
        alias_match = _ALIAS_RE.fullmatch(line)
        if alias_match:
            name, target = alias_match.groups()
            if name in labels or name in values or name in INSTRUCTION_SET:
                raise AssemblyError(f"line {line_number}: duplicate name {name!r}")
            if re.fullmatch(r"[+-]?\d+", target):
                values[name] = int(target)
            else:
                resolved = aliases.get(target, target)
                if resolved not in INSTRUCTION_SET:
                    raise AssemblyError(
                        f"line {line_number}: unknown instruction alias target {target!r}"
                    )
                aliases[name] = resolved
            continue

        label_match = _LABEL_RE.fullmatch(line)
        if label_match:
            name, line = label_match.groups()
            if name in labels or name in values:
                raise AssemblyError(f"line {line_number}: duplicate name {name!r}")
            labels[name] = len(pending)
            line = line.strip()
            if not line:
                continue
        pending.append((line_number, line))

    instructions: list[Instruction] = []
    for line_number, line in pending:
        match = _CALL_RE.fullmatch(line)
        if not match:
            raise AssemblyError(
                f"line {line_number}: expected INSTRUCTION(operand), got {line!r}"
            )
        raw_opcode, raw_operand = match.groups()
        opcode = aliases.get(raw_opcode, raw_opcode)
        spec = INSTRUCTION_SET.get(opcode)
        if spec is None:
            raise AssemblyError(f"line {line_number}: unknown instruction {raw_opcode!r}")
        token = raw_operand.strip()
        if spec.operand is OperandKind.NONE:
            if token:
                raise AssemblyError(f"line {line_number}: {opcode} takes no operand")
            operand = None
        else:
            if not token:
                raise AssemblyError(f"line {line_number}: {opcode} requires an operand")
            if re.fullmatch(r"[+-]?\d+", token):
                operand = int(token)
            elif token in values:
                operand = values[token]
            elif spec.operand is OperandKind.TARGET and token in labels:
                operand = labels[token]
            else:
                raise AssemblyError(f"line {line_number}: unknown value or label {token!r}")
        instructions.append(Instruction(opcode, operand))

    return Program(tuple(instructions), labels, values)


def disassemble(program: Program | tuple[Instruction, ...]) -> str:
    """Return canonical, reassemblable TinyCPU source."""

    instructions = program.instructions if isinstance(program, Program) else program
    return "\n".join(
        f"{instruction.opcode}({'' if instruction.operand is None else instruction.operand})"
        for instruction in instructions
    )
