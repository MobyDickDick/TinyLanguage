# TinyCPU in Logisim-evolution

This directory contains the first, deliberately small hardware milestone for
TinyCPU. Open `TinyCPU.circ` with Logisim-evolution 3.x.

## What is implemented

The project fixes the initial hardware profile at 16 data bits and 12 address
bits and splits the design into the same blocks as the hardware contract:

- `TinyCPU` is the top-level sheet and documents the block boundary;
- `Datapath` contains the 16-bit accumulator and its mandatory valid bit;
- `AddressPath` contains the 12-bit address register and its valid bit;
- `Memory` places a 4096 x 16 data RAM beside a 4096 x 1 validity RAM; and
- `ErrorFlags` reserves the six sticky error registers (`OVF`, `DIV0`, `ADDR`,
  `INV`, `ILL`, and `INPUT`).

This is a **structural starting point**, not yet an executable CPU. The pins are
intentionally exposed so each block can be wired and tested independently. In
particular, the project does not assign opcodes or claim to define a machine
code format; the symbolic Python ISA remains authoritative.

## Next milestone

1. Wire accumulator load/valid control and derive zero/negative status.
2. Give both RAMs a shared address and write-enable signal.
3. Make each error bit set-dominant, with `CLEAR_ERROR` as the only clear.
4. Add a fetch/decode controller for the initial instruction subset:
   `LOAD_CONST`, `STORE_ADDRESS`, `ADD_ADDRESS`, `JUMP_NOT_ZERO`, `PRINT`, and
   `HALT`.
5. Compare every clock edge against `src/tiny_cpu_vm.py` before extending the
   instruction set.

Do not store program ROM images as an official interchange format until the
repository has a versioned encoder and target profile.
