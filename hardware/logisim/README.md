# TinyCPU in Logisim-evolution

This directory contains the first three, deliberately small hardware milestones
for TinyCPU. Open `TinyCPU.circ` with Logisim-evolution 3.x.

## What is implemented

The project fixes the initial hardware profile at 16 data bits and 12 address
bits and splits the design into the same blocks as the hardware contract:

- `TinyCPU` is the top-level sheet and documents the block boundary;
- `Datapath` contains the synchronously loaded 16-bit accumulator and its
  mandatory valid bit; a signed comparator exports `ZERO` and `NEGATIVE`;
- `AddressPath` contains the synchronously loaded 12-bit address register and
  its valid bit, plus the combinational 12-bit offset adder and carry output;
- `Memory` connects a 4096 x 16 data RAM and a 4096 x 1 validity RAM to the
  same address, write-enable, and clock signals; and
- `ErrorFlags` implements the six set-dominant sticky error registers (`OVF`,
  `DIV0`, `ADDR`, `INV`, `ILL`, and `INPUT`) with a shared `CLEAR_ERROR`.

This is **not yet an executable CPU**: work packages 2 and 3 wire the data/address
paths, memory, and error flags, while fetch/decode and the top level remain
deliberate structural placeholders. The pins are exposed so each block can be
tested independently. In
particular, the project does not assign opcodes or claim to define a machine
code format; the symbolic Python ISA remains authoritative.

## Next milestone

1. Add a fetch/decode controller for the initial instruction subset:
   `LOAD_CONST`, `STORE_ADDRESS`, `ADD_ADDRESS`, `JUMP_NOT_ZERO`, `PRINT`, and
   `HALT`.
2. Compare every clock edge against `src/tiny_cpu_vm.py` before extending the
   instruction set.

Do not store program ROM images as an official interchange format until the
repository has a versioned encoder and target profile.

## Automated checks and simulation

The repository includes a dependency-free `.circ` netlist inspector. It parses
the XML, lists circuits and components, and returns a failing exit status when
sheets contain no wires or components have no wire at their anchor:

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py hardware/logisim/TinyCPU.circ
```

The complete-project check still deliberately fails because the AP 4 top-level
fetch/decode integration is not wired. It nevertheless reports `Datapath`, `AddressPath`, `Memory`, and `ErrorFlags` as
connected, making both completed and pending work explicit in CI. The inspector
is **not** a replacement for Logisim's
component simulator: faithfully emulating the complete Logisim library,
propagation rules, clocks, unknown values, and RAM would amount to maintaining a
second Logisim. Use Logisim-evolution's command-line simulation for electrical
tests once the schematic is wired, and compare clock-by-clock CPU state with
the executable reference model in `src/tiny_cpu_vm.py`.

The completed first work package also freezes the initial structural contract
in `tinycpu-16-12.json`. It can be checked before any wiring is complete:

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --profile hardware/logisim/tinycpu-16-12.json --contract-only \
  hardware/logisim/TinyCPU.circ
```

See `docs/tiny_cpu_roadmap.md` for the ordered implementation packages and
their acceptance criteria.
