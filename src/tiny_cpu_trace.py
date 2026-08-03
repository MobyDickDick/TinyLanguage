"""Clock-edge trace fixtures for comparing TinyCPU hardware with the VM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tiny_cpu_assembler import assemble
from tiny_cpu_vm import TinyCPU


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
    parser.add_argument("--check", type=Path, help="compare this observed JSON trace")
    args = parser.parse_args(argv)
    expected = capture_trace(
        args.program.read_text(encoding="utf-8"),
        watched_addresses=tuple(args.watch),
    )
    if args.check is None:
        print(json.dumps(expected, indent=2))
        return 0
    observed = json.loads(args.check.read_text(encoding="utf-8"))
    mismatches = compare_trace(expected, observed)
    if mismatches:
        print("trace mismatch: " + "; ".join(mismatches))
        return 1
    print(f"trace matches across {len(expected['edges'])} clock edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
