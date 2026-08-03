# TinyCPU in Logisim-evolution

This directory contains the first five, deliberately small hardware milestones
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
- `FetchDecode` contains the 12-bit `PC`, a 4096-word instruction ROM, the
  sequential/jump PC path, program-limit check, and control decode for the six
  core instructions.

The AP 5 countdown program is loaded into the instruction ROM and its
clock-edge reference trace is checked in as `ap5_countdown_trace.json`. The
internal ROM word
is deliberately provisional: bits 18..16 select one of the six core controls
and bits 15..0 carry the operand. It is a control-store detail, not a supported
machine-code format; the symbolic Python ISA remains authoritative.

## AP 4 clock sequences

All instructions are fetched combinationally at the current `PC`. On the next
rising edge the selected operation commits and `PC` takes `PC + 1`, except for
a taken `JUMP_NOT_ZERO`, which selects its 12-bit target. The exposed controls
have these sequences:

| Instruction | Decode/execute before edge | Commit at edge |
|---|---|---|
| `LOAD_CONST value` | drive operand to the accumulator and assert load/valid | load `ACC`; increment `PC` |
| `STORE_ADDRESS address` | select memory address, drive `ACC` and validity, assert write | write both RAMs; increment `PC` |
| `ADD_ADDRESS address` | read value/validity and select the adder result | load result/validity into `ACC`; increment `PC` |
| `JUMP_NOT_ZERO target` | combine decode with `!ZERO` and select the target when true | load target or `PC + 1` |
| `PRINT` | present the valid accumulator to the output boundary | emit once; increment `PC` |
| `HALT` | assert the normal halt output | retain halted state and `PC` |

Before decode, `PC_RANGE` compares `PC` with the exclusive `PROGRAM_LIMIT`.
An invalid fetch asserts both `SET_ADDR` and `HALT_ERROR`; no instruction is
committed and the error halt retains the failing PC for diagnosis.

## AP 5 reproducible fixture

`ap5_countdown.tcpu` uses only the six core controls. It stores `-1` at address
101, counts down a value at address 100, prints `3`, `2`, and `1`, and halts
without an error after 17 rising edges. The ROM contents use the provisional
AP 4 control word described above.

The checked-in JSON records the PC, accumulator and validity, status bits,
watched memory cells, cumulative output, error flags, and halt state after every
edge. Regenerate it from the VM or compare an exported Logisim trace with:

```bash
PYTHONPATH=src python src/tiny_cpu_trace.py \
  hardware/logisim/ap5_countdown.tcpu --watch 100 --watch 101
PYTHONPATH=src python src/tiny_cpu_trace.py \
  hardware/logisim/ap5_countdown.tcpu --watch 100 --watch 101 \
  --check hardware/logisim/ap5_countdown_trace.json
```

The comparison is deliberately field-oriented: a failure names the clock edge
and observable field that diverged. This makes the fixture usable both in CI
and while single-stepping the circuit. AP 6 can now extend decode and execution
without changing this frozen core trace.

Do not store program ROM images as an official interchange format until the
repository has a versioned encoder and target profile.

## Automated checks and simulation

The repository includes a dependency-free `.circ` netlist inspector. It parses
the XML, lists circuits and components, and returns a failing exit status when
sheets contain no wires or components have no wire at their anchor:

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py hardware/logisim/TinyCPU.circ
```

The complete-project structural check succeeds and reports all six sheets
as connected. The inspector
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
