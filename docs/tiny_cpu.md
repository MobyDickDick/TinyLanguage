# TinyCPU: microcomputer, assembly language, and simulator

TinyCPU is a deliberately small, complete teaching machine for TinyLanguage. By
default, it is a **16-bit accumulator machine** with a 12-bit address bus and
4,096 memory cells. Data and address widths can be configured independently.
The machine has an address register, a program counter, input/output,
conditional jumps, and strict error semantics. The simulator is in
`src/tiny_cpu_vm.py`, the assembler is in `src/tiny_cpu_assembler.py`, and the
ISA is in `src/tiny_cpu_isa.py`.

## Circuit-simulation recommendation

**[Logisim-evolution](https://github.com/logisim-evolution/logisim-evolution)**
is recommended for recreating TinyCPU. It is cross-platform, makes educational
circuits easy to understand, and provides the registers, RAM/ROM, ALU,
splitters, and clock components that TinyCPU needs. Most importantly, it allows
the processor to be divided hierarchically into datapath, control unit, and
input/output. The included Python VM remains the reference: a Logisim test is
correct when registers, memory, output, and error flags match
`src/tiny_cpu_vm.py` after every clock tick.

**[Digital](https://github.com/hneemann/Digital)** is a suitable alternative,
particularly when automated circuit tests and a compact Java application are
more important. Logisim-evolution is preferred for collaboration and easily
accessible documentation. Browser-based tools are useful for demonstrations,
but make it more difficult to model precisely the validity bits and sticky
error flags described below.

The machine format is now versioned: an instruction word consists of 22 bits,
with a 6-bit opcode and a 16-bit operand. `assemble()` continues to return a
`Program` made up of symbolic `Instruction` objects; `src/tiny_cpu_machine.py`
then converts them into machine words, a ROM image readable by
Logisim-evolution, and a human-readable listing file. The opcode table is in
`hardware/logisim/tinycpu-machine-v1.json`. The AP-5 program, its ROM image, and
its listing serve as reproducible reference artifacts for the encoder and the
embedded Logisim ROM.

### Hardware contract for an implementation

The smallest compatible circuit consists of the following states and signals:

| Part | Required state / behavior |
|---|---|
| Program control | unsigned, `address_bits`-wide PC; increment to the next instruction before execution |
| Datapath | `data_bits`-wide two’s-complement accumulator plus zero and negative status |
| Addressing | `address_bits`-wide address register with its own validity bit |
| Data memory | one `data_bits`-wide value **and one validity bit** per cell |
| Error register | sticky bits `OVF`, `DIV0`, `ADDR`, `INV`, `ILL`, `INPUT`; their OR is `ERR` |
| Input/output | input queue to the accumulator; `PRINT` writes a valid value to the output channel |
| Halt | separate states for a normal halt and a halt with an error |

The validity bit is not an optional debugging signal: the specified error
propagation cannot be implemented without a validity bit for the accumulator,
the address register, and every memory cell. `CLEAR_ERROR()` clears only the
error register, never validity bits. Zero is set exactly when the value stored
in the accumulator is zero; conditional zero/not-zero jumps are taken only when
the accumulator is valid. Negative is set only for a valid negative
accumulator.

The following sequence is observable in a clock-synchronous implementation:

1. Read the instruction at `PC`; an invalid instruction address sets `ADDR`
   and halts with an error.
2. Increment `PC` to the next instruction.
3. Read operands and perform the operation and validity check.
4. Commit the result, flags, memory, or jump target together at the clock edge.

Jump targets are **instruction indices**, not byte addresses. A taken jump
outside the loaded program sets `ADDR`; a jump that is not taken does not
validate its target. Integer division truncates toward zero. `AND`, `OR`, and
`NOT` operate bitwise at the selected two’s-complement width. Arithmetic results
outside the signed data range set `OVF` and write `0 INVALID` to the
accumulator.

### Testing TinyCPU.circ

A short step-by-step guide for the stable electrical test, testing with an
existing Logisim JAR, and visual troubleshooting is available in
[`docs/tiny_cpu_test_guide.md`](tiny_cpu_test_guide.md). Run the required AP-5
test from the repository root with `scripts/test-logisim.sh`. The full matrix
remains available as a diagnostic run with
`TINYCPU_FULL_ACCEPTANCE=1 scripts/test-logisim.sh`.

### Accepted Logisim-evolution implementation

The project that runs in Logisim-evolution 4.1.x is located at
[`hardware/logisim/TinyCPU.circ`](../hardware/logisim/TinyCPU.circ). It defines
the 16/12-bit profile, subcircuits, and mandatory validity/error states. The
architecture and electrical AP-12 acceptance are documented in
[`hardware/logisim/README.md`](../hardware/logisim/README.md). The following
list describes the implementation and acceptance sequence already performed,
not missing wiring: the inspector reports `TinyCPUMain: connected`, and the
electrical AP-11 matrix covers all 50 opcodes in the versioned machine format,
including their success and error cases. Thus, every top-level pin and the
entire documented instruction set are implemented; visible wire crossings
without a junction point are deliberately not electrical connections in
Logisim.

The project can first be checked structurally without Logisim by running
`PYTHONPATH=src python src/tiny_cpu_circuit.py
hardware/logisim/TinyCPU.circ`. The checker reads the `.circ` XML, reports
missing connections, and exits with status 1 for contract violations. It
deliberately does not simulate the complete Logisim component library;
Logisim-evolution remains responsible for electrical simulation, while
`tiny_cpu_vm.py` supplies the expected CPU semantics. A successful structural
check therefore does not replace the full electrical test linked above.

If CPU or memory usage is unusually high, the five standalone projects under
[`hardware/logisim/diagnostics/`](../hardware/logisim/diagnostics/) can be
loaded individually. This allows fetch/decode, datapath, address path, memory,
and error flags to be examined without loading all other circuit sheets at the
same time. Generation, size comparison, and a recommended test sequence are
documented in the hardware
[README](../hardware/logisim/README.md#ressourcenverbrauch-eingrenzen).

1. The target profile was set to **16 data bits, 12 address bits, and 4,096
   memory cells**.
2. The datapath (accumulator, ALU, status), address path (address register,
   offset adder), memory, and control unit were built as separate subcircuits.
3. The validity RAM is parallel to the data RAM; both use the same address and
   write-enable signal.
4. The error flags are set-dominant registers; `CLEAR_ERROR` is the only shared
   clear line.
5. `LOAD_CONST`, `STORE_ADDRESS`, `ADD_ADDRESS`, `JUMP_NOT_ZERO`, `PRINT`, and
   `HALT` were accepted first using the loop example.
6. The remaining addressing modes and targeted error cases were then added and
   accepted in the full electrical matrix.

For reproducible comparisons, every circuit test should include the `.tcpu`
source file, the target profile used, the input sequence, and the expected
output and error flags in addition to the Logisim project.

## Guiding principle: errors are not modular arithmetic

Every register and memory cell logically consists of `(value, valid)`. An
operation produces a valid value only if all inputs are valid, the operation is
permitted, and the result is within the signed range of the configured data bus
(for 16 bits: -32768 to 32767). Otherwise, the destination becomes `0 INVALID`
and a specific error flag is set. Invalidity propagates when the value is used
again.

## Scale-invariant widths

The ISA and assembly language deliberately contain no hard-coded operand
width: numbers, addresses, offsets, and jump targets are represented
symbolically as integers. Only a concrete `TinyCPU` instance defines the
hardware limits through `data_bits` and `address_bits`. The same assembly
program can therefore run on an 8/8, 16/12, or 32/20 machine, for example,
provided that its values and addresses fit the selected ranges.

The data bus uses two’s complement and determines the accumulator, memory
cells, input/output values, and arithmetic overflow. The address bus is
unsigned and independently determines the address register, effective
addresses, program counter, and maximum addressable memory size. `memory_size`
may be smaller than the address space (partially populated memory), but never
larger.

```python
TinyCPU(data_bits=8, address_bits=8, memory_size=256)
TinyCPU(data_bits=32, address_bits=20, memory_size=65536)
```

This parameterization is semantically scale-invariant; a future binary
instruction format must likewise derive its encoding width from the target
profile and must not hard-code it in opcodes.

Error flags are **sticky**. `CLEAR_ERROR()` clears them but does not repair
invalid values. For example, only `LOAD_CONST(5)` makes the accumulator valid
again. Supported flags are `OVF`, `DIV0`, `ADDR`, `INV`, `ILL`, and `INPUT`;
`ERR` means “at least one error flag is set.”

## Syntax

Every instruction uses function-call syntax. Comments begin with `;` or `//`.
Direct operands are mandatory; consequently, `ADD_ADDRESS()` is an assembler
error, while `ADD_ADDRESS_REGISTER()` is correct.

```text
sum := 100
ADC := ADD_CONST

LOAD_CONST(7)
STORE_ADDRESS(sum)
LOAD_CONST(5)
ADC(3)
ADD_ADDRESS(sum)
PRINT()
HALT()
```

`name := 100` defines a value alias, and `ADC := ADD_CONST` defines an
instruction alias. Jump targets are defined with `name:`. Common abbreviations
(`LDC`, `LDA`, `STA`, `ADC`, `ADA`, `JMP`, `JZ`, `JNZ`, `JNEG`, `JER`, `CER`,
`HLT`) are built in; canonical names remain the documented interface.

## Instruction set

The `LOAD`, `ADD`, `SUB`, `MUL`, `DIV`, `AND`, `OR`, and `XOR` operations each
have four explicit sources:

```text
OP_CONST(value)
OP_ADDRESS(address)
OP_ADDRESS_REGISTER()
OP_ADDRESS_REGISTER_PLUS_OFFSET(offset)
```

`STORE` has the three writable destination variants (there is no
`STORE_CONST`). The address register is loaded by
`LOAD_ADDRESS_REGISTER_CONST(value)` or
`LOAD_ADDRESS_REGISTER_ADDRESS(address)`. In addition, there are:

| Group | Instructions |
|---|---|
| Logic | `NOT()` |
| Jumps | `JUMP_ADDRESS`, `JUMP_ZERO`, `JUMP_NOT_ZERO`, `JUMP_NEGATIVE`, `JUMP_ERROR`, `JUMP_NOT_ERROR` |
| Errors | `CLEAR_ERROR()`, `HALT_ERROR()` |
| I/O | `INPUT()`, `PRINT()`, `PRINT_ADDRESS(address)` |
| Control flow | `HALT()` |

Jump instructions expect a label or a numeric instruction address. `INPUT()`
reads the next number passed with `--input`. Missing or invalid input sets
`INPUT` and invalidates the accumulator.

## Example and invocation

Executable example programs are located under
[`examples/tiny_cpu/`](../examples/tiny_cpu/). There is a dedicated program for
each operation listed below; for operations with multiple addressing modes,
the program exercises all variants. Each `.tcpu` file has a same-named
`.stdout` file containing the complete expected output. Optional `.args` files
provide CLI arguments, and `.exit` files provide the expected nonzero exit
status. The `tests/detailtests/test_tiny_cpu_examples.py` test automatically
finds all these programs, runs them through the public CLI, and compares
standard output, standard error, and exit status. A new output example
therefore needs only its source file and output snapshot. An additional
coverage test ensures that no operation or addressing mode is missing. Run the
example suite specifically with:

```bash
python -m pytest tests/detailtests/test_tiny_cpu_examples.py
```

```text
counter := 20
LOAD_CONST(3)
STORE_ADDRESS(counter)

loop:
LOAD_ADDRESS(counter)
PRINT()
SUB_CONST(1)
STORE_ADDRESS(counter)
JUMP_NOT_ZERO(loop)
HALT()
```

```bash
python src/tiny_cpu_cli.py program.tcpu
python src/tiny_cpu_cli.py --disassemble program.tcpu
python src/tiny_cpu_cli.py --input 41 input_program.tcpu
python src/tiny_cpu_cli.py --data-bits 8 --address-bits 9 --memory-size 512 program.tcpu
```

`--data-bits` and `--address-bits` also select the target profile for a CLI
invocation. `--memory-size` must not exceed the address space determined by the
address bus; the defaults are 16, 12, and 4096.

The process exits with status 1 if `HALT_ERROR()` is executed or if an error
flag is still set at `HALT()`. A step limit protects against unintended infinite
loops.

## Cross-compiler direction

The stable boundary for a future backend is the canonical
`Instruction`/`Program` model. The intended direction is:

```text
TinyLanguage-Subset -> Native IR -> TinyCPU Program
TinyCPU Program -> Kontrollflussanalyse -> kanonisches TinyLanguage-Subset
```

The reverse direction is a decompiler and cannot generally reconstruct the
original names or control structures. It is therefore deliberately limited to
a canonical subset (numbers, variables, arithmetic, `if`, `while`, and simple
I/O); independently of that limitation, the simulator and assembler already
function as a complete small microcomputer.
