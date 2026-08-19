"""Clock-edge trace fixtures for comparing TinyCPU hardware with the VM."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tiny_cpu_assembler import assemble
from tiny_cpu_vm import TinyCPU


INTEGRATION_TABLE_COLUMNS = (
    "PRINT_ENABLE",
    "PRINT_ADDRESS_ENABLE",
    "PRINT_VALUE",
    "PRINT_VALID",
    "PRINT_ADDRESS_VALUE",
    "PRINT_ADDRESS_VALID",
    "HALT_ENABLE",
    "HALT_ERROR_ENABLE",
    "ERROR_OVF",
    "ERROR_DIV0",
    "ERROR_ADDR",
    "ERROR_INV",
    "ERROR_ILL",
    "ERROR_INPUT",
    "HALTED",
    "HALTED_WITH_ERROR",
)


def _table_bit(value: str, column: str, row_number: int) -> bool:
    """Decode a single-bit Logisim table cell with a useful diagnostic."""

    normalized = value.strip().lower()
    if normalized in {"0", "false", "low"}:
        return False
    if normalized in {"1", "true", "high"}:
        return True
    raise ValueError(f"row {row_number}: {column} must be a defined bit (0 or 1)")


def integration_trace_from_table(table: str, instructions: list[str]) -> dict[str, Any]:
    """Convert a Logisim pin-table export into the integration trace schema.

    Logisim's table logger produces a flat CSV or tab-separated document.  The
    circuit pin labels form the header, while each subsequent row represents
    one rising edge.  Instruction names come from the matching assembly input
    because they are comparator metadata rather than electrical output pins.
    """

    lines = [
        line
        for line in table.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        raise ValueError("Logisim table is empty")
    delimiter = "\t" if "\t" in lines[0] else ","
    reader = csv.DictReader(lines, delimiter=delimiter)
    rows = list(reader)
    fieldnames = reader.fieldnames or []
    missing = [column for column in INTEGRATION_TABLE_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError("Logisim table is missing columns: " + ", ".join(missing))
    if len(rows) != len(instructions):
        raise ValueError(
            f"Logisim table has {len(rows)} rows but the program executes {len(instructions)} edges"
        )

    error_columns = {
        "ERROR_OVF": "OVF",
        "ERROR_DIV0": "DIV0",
        "ERROR_ADDR": "ADDR",
        "ERROR_INV": "INV",
        "ERROR_ILL": "ILL",
        "ERROR_INPUT": "INPUT",
    }
    edges: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        row_number = index + 2

        def bit(column: str) -> bool:
            return _table_bit(row[column], column, row_number)

        try:
            print_value = int(row["PRINT_VALUE"].strip(), 0)
            print_address_value = int(row["PRINT_ADDRESS_VALUE"].strip(), 0)
        except ValueError as error:
            raise ValueError(f"row {row_number}: output values must be integers") from error
        edges.append(
            {
                "edge": index + 1,
                "instruction": instructions[index],
                "boundary": {
                    "print_enable": bit("PRINT_ENABLE"),
                    "print_address_enable": bit("PRINT_ADDRESS_ENABLE"),
                    "print_value": print_value,
                    "print_valid": bit("PRINT_VALID"),
                    "print_address_value": print_address_value,
                    "print_address_valid": bit("PRINT_ADDRESS_VALID"),
                    "halt_enable": bit("HALT_ENABLE"),
                    "halt_error_enable": bit("HALT_ERROR_ENABLE"),
                },
                "errors": sorted(
                    name for column, name in error_columns.items() if bit(column)
                ),
                "halted": bit("HALTED"),
                "halted_with_error": bit("HALTED_WITH_ERROR"),
            }
        )
    return {"schema_version": 1, "edges": edges}


def capture_trace(source: str, *, watched_addresses: tuple[int, ...] = ()) -> dict[str, Any]:
    """Execute assembly *source* and return the observable state at every edge."""

    program = assemble(source)
    cpu = TinyCPU()
    edges: list[dict[str, Any]] = []
    while not cpu.halted:
        instruction = program.instructions[cpu.pc]
        cpu.step(program.instructions)
        edges.append(
            {
                "edge": len(edges) + 1,
                "instruction": instruction.opcode,
                "pc": cpu.pc,
                "accumulator": {
                    "value": cpu.accumulator.value,
                    "valid": cpu.accumulator.valid,
                },
                "zero": cpu.zero,
                "negative": cpu.negative,
                "memory": {
                    str(address): {
                        "value": cpu.memory[address].value,
                        "valid": cpu.memory[address].valid,
                    }
                    for address in watched_addresses
                },
                "outputs": list(cpu.output_values),
                "errors": sorted(flag.value for flag in cpu.errors),
                "halted": cpu.halted,
                "halted_with_error": cpu.halted_with_error,
            }
        )
    return {"schema_version": 1, "watched_addresses": list(watched_addresses), "edges": edges}


def capture_integration_trace(source: str) -> dict[str, Any]:
    """Capture the externally visible ``TinyCPUMain`` event boundary.

    Values and validity are sampled immediately before the rising edge, like
    the corresponding Logisim output pins.  Sticky errors and halt state are
    sampled immediately after the edge.  Keeping those phases explicit avoids
    treating an invalid ``PRINT`` as if it had emitted the VM's replacement
    accumulator value.
    """

    program = assemble(source)
    cpu = TinyCPU()
    edges: list[dict[str, Any]] = []
    while not cpu.halted:
        instruction = program.instructions[cpu.pc]
        opcode = instruction.opcode
        address = int(instruction.operand or 0)
        source_cell = cpu.memory[address] if 0 <= address < len(cpu.memory) else None
        boundary = {
            "print_enable": opcode == "PRINT",
            "print_address_enable": opcode == "PRINT_ADDRESS",
            "print_value": cpu.accumulator.value,
            "print_valid": cpu.accumulator.valid,
            "print_address_value": source_cell.value if source_cell is not None else 0,
            "print_address_valid": source_cell.valid if source_cell is not None else False,
            "halt_enable": opcode == "HALT",
            "halt_error_enable": opcode == "HALT_ERROR",
        }
        cpu.step(program.instructions)
        edges.append(
            {
                "edge": len(edges) + 1,
                "instruction": opcode,
                "boundary": boundary,
                "errors": sorted(flag.value for flag in cpu.errors),
                "halted": cpu.halted,
                "halted_with_error": cpu.halted_with_error,
            }
        )
    return {"schema_version": 1, "edges": edges}


def compare_trace(expected: dict[str, Any], observed: dict[str, Any]) -> tuple[str, ...]:
    """Return concise edge/field mismatches between two trace documents."""

    mismatches: list[str] = []
    if observed.get("schema_version") != expected.get("schema_version"):
        mismatches.append("schema_version differs")
    expected_edges = expected.get("edges", [])
    observed_edges = observed.get("edges", [])
    for index in range(max(len(expected_edges), len(observed_edges))):
        if index >= len(expected_edges):
            mismatches.append(f"unexpected edge {index + 1}")
            continue
        if index >= len(observed_edges):
            mismatches.append(f"missing edge {index + 1}")
            continue
        for field, value in expected_edges[index].items():
            if observed_edges[index].get(field) != value:
                mismatches.append(f"edge {index + 1}: {field} differs")
    return tuple(mismatches)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate or check a TinyCPU edge trace")
    parser.add_argument("program", type=Path)
    parser.add_argument("--watch", type=int, action="append", default=[])
    parser.add_argument(
        "--integration",
        action="store_true",
        help="sample the TinyCPUMain print/halt boundary instead of full VM state",
    )
    parser.add_argument("--check", type=Path, help="compare this observed JSON trace")
    parser.add_argument(
        "--check-logisim-table",
        type=Path,
        help="compare a CSV/TSV table exported by Logisim (integration mode only)",
    )
    args = parser.parse_args(argv)
    if args.check is not None and args.check_logisim_table is not None:
        parser.error("--check and --check-logisim-table are mutually exclusive")
    if args.check_logisim_table is not None and not args.integration:
        parser.error("--check-logisim-table requires --integration")
    source = args.program.read_text(encoding="utf-8")
    if args.integration:
        if args.watch:
            parser.error("--watch cannot be combined with --integration")
        expected = capture_integration_trace(source)
    else:
        expected = capture_trace(source, watched_addresses=tuple(args.watch))
    if args.check is None and args.check_logisim_table is None:
        print(json.dumps(expected, indent=2))
        return 0
    if args.check_logisim_table is not None:
        instructions = [edge["instruction"] for edge in expected["edges"]]
        try:
            observed = integration_trace_from_table(
                args.check_logisim_table.read_text(encoding="utf-8"), instructions
            )
        except ValueError as error:
            parser.error(str(error))
    else:
        observed = json.loads(args.check.read_text(encoding="utf-8"))
    mismatches = compare_trace(expected, observed)
    if mismatches:
        print("trace mismatch: " + "; ".join(mismatches))
        return 1
    print(f"trace matches across {len(expected['edges'])} clock edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
