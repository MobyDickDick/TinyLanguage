"""Command-line assembler and simulator for TinyCPU."""

from __future__ import annotations

import argparse
from pathlib import Path

from tiny_cpu_assembler import AssemblyError, assemble, disassemble
from tiny_cpu_vm import TinyCPU


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble and run TinyCPU programs")
    parser.add_argument("program", type=Path)
    parser.add_argument("--disassemble", action="store_true")
    parser.add_argument("--memory-size", type=int, default=4096)
    parser.add_argument("--input", type=int, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        program = assemble(args.program.read_text(encoding="utf-8"))
    except (OSError, AssemblyError) as error:
        parser.error(str(error))
    if args.disassemble:
        print(disassemble(program))
        return 0
    cpu = TinyCPU(args.memory_size, args.input, print)
    cpu.run(program)
    if cpu.error:
        print("ERROR:", ", ".join(sorted(flag.value for flag in cpu.errors)))
    return 1 if cpu.halted_with_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
