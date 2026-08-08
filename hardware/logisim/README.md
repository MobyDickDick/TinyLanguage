# TinyCPU in Logisim-evolution

This directory contains the completed eight-package TinyCPU hardware baseline.
Open `TinyCPU.circ` with Logisim-evolution 3.x. Das Blatt **`TinyCPU` ist die
von Hand gepflegte Übersichtsseite**. Es ist keine generierte Verdrahtung und
darf beim Bearbeiten der Integration weder neu angeordnet noch durch eine
automatisch erzeugte Top-Level-Schaltung ersetzt werden. Generatoren in diesem
Repository dürfen ausschließlich die eigenständigen Dateien unter
`diagnostics/` aktualisieren; Ausgangspunkt bleibt immer die eingecheckte
`TinyCPU.circ` mit ihrer vorhandenen Übersichtsseite.

Eine ausfüllbare Schritt-für-Schritt-Vorlage für die weitere Integration steht
in [`docs/tiny_cpu_top_level_template.md`](../../docs/tiny_cpu_top_level_template.md).
Sie schreibt insbesondere vor, Leitungen in freien Korridoren **um** Symbole
herumzuführen und jeden neuen Signalverbund einzeln zu prüfen.

## TinyClock: erster Top-Level-Baustein

Die elektrische Integration beginnt bewusst mit dem gemeinsamen Takt. Das
isolierte Blatt `IntegrationClock` in `TinyCPU.circ` beschreibt die spätere
Verteilung eines einzigen `CLK`-Eingangs ohne Gatter auf Fetch/Decode,
Datenpfad, Adresspfad, Speicher und Fehlerflags. Sein Pinvertrag ist Teil von
`tinycpu-16-12.json`, sodass
fehlende, umbenannte oder falsch gerichtete Taktanschlüsse bereits in der
reproduzierbaren Hardwareprüfung auffallen.

Passend zur gewünschten Organisation liegt die eigenständig ladbare Ansicht
unter `diagnostics/TinyCPU-IntegrationClock.circ`. Sie wird wie die anderen
Diagnoseprojekte aus `TinyCPU.circ` erzeugt und bytegenau gegen das eingebettete
Blatt geprüft. Damit gibt es nur eine Schaltungsquelle, aber weiterhin eine
kleine Datei für die Poke-Prüfung in Logisim-evolution. Auf der manuell
wiederhergestellten Übersichtsseite erreicht die Taktleitung jetzt
Fetch/Decode, Datenpfad, Adresspfad, Speicher und Fehlerflags. Der neue Abzweig
verläuft oberhalb der Symbole im freien Korridor und trifft ausschließlich den
`CLK`-Anschluss von `ErrorFlags`.

## TinyReset: definierter Neustart des Befehlszählers

Das isolierte Blatt `IntegrationReset` führt den externen Eingang `RESET`
ohne kombinatorische Logik an den Reset-Anschluss von Fetch/Decode. Damit wird
der Programmzähler reproduzierbar auf den Startzustand gesetzt, ohne den
Inhalt der Daten- und Valid-RAMs oder die getrennte Fehlerlöschung durch
`CLEAR_ERROR` umzudeuten. Das Blatt `IntegrationReset` und das erzeugte
Diagnoseprojekt `diagnostics/TinyCPU-IntegrationReset.circ` frieren diesen
Pinvertrag unabhängig vom breiteren Top-Level ein. Auf der wiederhergestellten
Übersichtsseite erreicht `RESET` ausschließlich Fetch/Decode; Steuernetze,
Daten- und Halt-Netze bleiben davon getrennt.

## Ressourcenverbrauch eingrenzen

### Kleinstmögliche Verdrahtungsproben

Bevor eines der CPU-Blätter geöffnet wird, können die drei Projekte in
`smoke/` geprüft werden:

| Datei | Bauteile | Leitung | Zweck |
|---|---:|---:|---|
| `PinPair-1bit.circ` | 2 Pins | 1 | einfaches Steuersignal |
| `PinPair-12bit.circ` | 2 Pins | 1 | Adressbusbreite der TinyCPU |
| `PinPair-16bit.circ` | 2 Pins | 1 | Datenbusbreite der TinyCPU |

Jede Datei besitzt nur ein Eingangs- und ein Ausgangspin gleicher Breite. Die
beiden Anschlusskoordinaten liegen auf derselben Horizontalen und werden durch
genau ein gerades Leitungssegment verbunden. Es gibt weder Abzweigungen noch
Kreuzungen, Rückkopplungen, Speicher oder Unterblätter. Ein Repository-Test
prüft genau diese Invarianten sowie die XML-Lesbarkeit. Damit trennen die
Proben einen grundsätzlichen Ladefehler der verwendeten Logisim-Version von
Fehlern in der CPU-Verdrahtung.

Die Dateien bitte in der Reihenfolge 1, 12 und 16 Bit einzeln öffnen. Wenn
bereits `PinPair-1bit.circ` nicht ohne stark steigenden Speicherverbrauch lädt,
ist die CPU-Schaltung nicht die Ursache. Wenn alle drei Proben funktionieren,
aber eines der folgenden Diagnoseblätter nicht, ist der Fehler auf dieses
Blatt beziehungsweise dessen Bauteiltypen eingegrenzt.

Die statische Prüfung des Projekts findet 162 XML-Komponenten (davon sechs
reine Textfelder) und 280 rechtwinklige Leitungssegmente. Diagonale Leitungen
werden abgewiesen, weil Logisim sie beim Laden nicht als gültige Drähte
verarbeiten kann. `FetchDecode` ist mit 69 elektrischen
Komponenten der größte Block; `ErrorFlags` folgt mit 46. Die beiden 4096-Zellen-
RAMs liegen ausschließlich in `Memory`. In `ErrorFlags` läuft jede
Rückkopplung über ein getaktetes Register, daher ist dort im Schaltbild keine
rein kombinatorische Rückkopplung erkennbar. Eine Speicherbelegung von mehreren
Gigabyte lässt sich allein durch diese Projektgröße nicht erklären; sie sollte
blockweise in der tatsächlich verwendeten Simulatorversion reproduziert
werden.

Dafür enthält `diagnostics/` fünf eigenständig ladbare Projekte:

| Datei | Elektrische Komponenten | Leitungen | Isoliert insbesondere |
|---|---:|---:|---|
| `TinyCPU-FetchDecode.circ` | 69 | 109 | ROM, Decoder und PC-Steuerung |
| `TinyCPU-Datapath.circ` | 12 | 22 | Akkumulator und Vergleich |
| `TinyCPU-AddressPath.circ` | 12 | 25 | Adressregister und Addierer |
| `TinyCPU-Memory.circ` | 12 | 27 | Daten- und Validitäts-RAM |
| `TinyCPU-ErrorFlags.circ` | 46 | 92 | Sticky-Flag-Rückkopplungen |

Im Blatt `AddressPath` beziehen sich die XML-Koordinaten der Register auf die
linke obere Symbolecke und nicht auf einen Anschluss. D, WE und CLK werden
deshalb gezielt an ihren darunterliegenden Anschlusskoordinaten verdrahtet.
Adressbus und Offset enden getrennt an A und B des Addierers. Die
Offset-Leitung umfährt dabei den ein Bit breiten Reset-Anschluss des
Adressregisters; der Carry-Ausgang beginnt am separaten ein Bit breiten
Addiereranschluss. Die Leitungsführung besteht ausschließlich aus horizontalen und vertikalen
Segmenten, von denen sich keine zwei kollinear überdecken.

Dasselbe Anschlussprinzip gilt im Blatt `Datapath`: `DATA_IN`, `ACC_LOAD` und
`CLK` enden an D, WE und CLK beider Register statt an deren Symbolmitten. Der
16-Bit-Akkumulator und die Nullkonstante belegen außerdem getrennte Eingänge
des Komparators; die ein Bit breiten Statusausgänge bleiben davon isoliert.
`Memory` führt Adresse, Schreibfreigabe und Takt parallel zu beiden RAMs und
legt `VALID_IN` ausschließlich auf den Dateneingang des Validitäts-RAMs. Da
beide RAMs eigene Ausgangsleitungen haben und keinen gemeinsamen Bus treiben,
liegen ihre Output-Enable-Anschlüsse dauerhaft an logisch 1. Output-Enable ist
dabei unabhängig von `WRITE_ENABLE`.
`ErrorFlags` taktet die sechs Sticky-Register über einen segmentierten
gemeinsamen Taktbus; ein High-Pegel an WE sorgt dafür, dass jedes berechnete
Folgebit auf der steigenden Flanke übernommen wird. Paarweise benannte
`CURRENT_*`-Tunnel führen Q jeweils zum zugehörigen `HOLD_*`-Gatter zurück. So
kreuzt die Rückkopplung weder Reset-Anschlüsse noch Takt- oder WE-Bus.

Die Dateien nacheinander einzeln öffnen und CPU- sowie Speicherverbrauch nach
dem vollständigen Laden notieren. Tritt das Problem schon ohne Takten auf,
grenzt die erste auffällige Datei den verantwortlichen Baustein ein. Tritt es
nur beim Takten auf, zuerst `ErrorFlags`, dann `FetchDecode` prüfen. Bleibt jede
Einzeldatei unauffällig, liegt der Verdacht auf der Integration im Top-Level
oder auf einem Simulatorproblem. Die sechs Diagnoseprojekte enthalten
absichtlich nur je ein Blatt und ersetzen `TinyCPU.circ` nicht als integrierte
Schaltung. Fetch/Decode ist dabei in den Zustands- und ROM-Pfad (`FetchDecode`)
sowie die eigentliche Steuersignaldecodierung (`FetchDecodeControls`)
aufgeteilt.

Sie werden reproduzierbar aus dem Hauptprojekt erzeugt. Der Befehl liest
`TinyCPU.circ`, schreibt aber nur Dateien in das angegebene Diagnoseverzeichnis;
er ist ausdrücklich **kein** Weg, das Blatt `TinyCPU` wiederherzustellen oder
zu ersetzen:

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --split-output hardware/logisim/diagnostics \
  hardware/logisim/TinyCPU.circ
```

## What is implemented

The project fixes the initial hardware profile at 16 data bits and 12 address
bits and splits the design into the same blocks as the hardware contract:

The integrated top-level places every subcircuit anchor in its own 600-pixel
routing lane. This is intentionally much wider than the generated component
symbols: no terminals from adjacent subcircuits can be superimposed merely by
their placement. The dependency-free inspector enforces this clearance and
fails before a project with overlapping subcircuit symbols is checked in.

- `TinyCPU` is the top-level sheet and documents the block boundary;
- `Datapath` contains the synchronously loaded 16-bit accumulator and its
  mandatory valid bit; a signed comparator exports `ZERO` and `NEGATIVE`;
- `AddressPath` contains the synchronously loaded 12-bit address register and
  its valid bit, plus the combinational 12-bit offset adder and carry output;
- `Memory` connects a 4096 x 16 data RAM and a 4096 x 1 validity RAM to the
  same address, write-enable, and clock signals; and
- `ErrorFlags` implements the six set-dominant sticky error registers (`OVF`,
  `DIV0`, `ADDR`, `INV`, `ILL`, and `INPUT`) with a shared `CLEAR_ERROR`.
  Each hold path feeds the register output back through an AND gate and therefore
  crosses a clocked register; the feedback is not a combinational loop.
- `FetchDecode` contains the 12-bit `PC`, a 4096-word instruction ROM, the
  sequential/jump PC path, program-limit check, and control decode for the complete symbolic ISA. The expanded decoder
  exposes every addressing, arithmetic, logic, branch, and I/O control plus all six
  error-set paths.
- On the maintained `TinyCPU` overview, the 22-bit `FetchDecode.OPCODE` bus is
  the first decode-integration net and drives only the matching input of the
  separately placed `FetchDecodeControls` block. Its left-side route remains
  isolated from the already integrated clock and reset nets.
- The first decoded one-bit control, `CLEAR_ERROR`, leaves
  `FetchDecodeControls` through the free outer-right corridor and reaches only
  the matching `ErrorFlags` input. It remains isolated from clock, reset, and
  the opcode bus.
- The first sticky-error set control, `SET_OVF`, uses a separate outer-right
  lane between `FetchDecodeControls` and `ErrorFlags`. It remains isolated
  from `CLEAR_ERROR` and every earlier top-level net.
- The second sticky-error set control, `SET_DIV0`, runs through its own next
  outer-right lane and reaches only the matching `ErrorFlags` input. It stays
  isolated from `SET_OVF` and all earlier top-level nets.

The AP 5 countdown program is loaded into the instruction ROM and its
clock-edge reference trace is checked in as `ap5_countdown_trace.json`. AP 7
replaces the provisional ROM representation with the versioned machine format
described below.

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

## AP 6 complete symbolic control surface

`FetchDecode` now has a six-bit provisional decoder and exports one named
control for every instruction in `src/tiny_cpu_isa.py`. Its condition boundary
accepts `ZERO`, `NEGATIVE`, and aggregate `ERROR`; its error boundary exports
all six sticky-flag set controls. The hardware profile records the same
instruction, condition, and error sets, and parameterized structural tests
check every member rather than sampling individual controls.

This milestone completes the *symbolic* ISA control surface: constant, direct,
address-register, and address-register-plus-offset modes; arithmetic and logic;
all conditional and unconditional jumps; error clearing; and input/output are
present at the decode boundary. Arithmetic range, invalid operands and
addresses, division by zero, invalid instructions, and invalid input continue
to feed the AP 3 sticky error registers. The AP 5 countdown trace remains the
core behavioral regression.

## AP 7 machine format and encoder

`tinycpu-machine-v1.json` is the stable, machine-readable opcode table. A
machine word contains the six-bit opcode in bits 21..16 and its 16-bit operand
in bits 15..0. Direct addresses and jump targets must fit the unsigned 12-bit
address space; constants and offsets use signed 16-bit two's complement.
Operand-free instructions require zero in their reserved operand field, and
opcode values 46..63 are reserved. Existing assignments are append-only within
format version 1; incompatible changes require a new format version.

`src/tiny_cpu_machine.py` validates those ranges, encodes and decodes individual
instructions, and emits Logisim ROM images plus readable listings. Regenerate
the checked-in countdown artifacts with:

```bash
PYTHONPATH=src python src/tiny_cpu_machine.py \
  hardware/logisim/ap5_countdown.tcpu \
  --rom hardware/logisim/ap5_countdown.rom \
  --listing hardware/logisim/ap5_countdown.lst
```

`TinyCPU.circ` contains exactly this generated 22-bit ROM image. The test suite
roundtrips every symbolic instruction, validates the JSON allocation, and
compares the generated image with both the checked-in `.rom` file and the ROM
embedded in Logisim.

## AP 5 reproducible fixture

`ap5_countdown.tcpu` uses only the six core controls. It stores `-1` at address
101, counts down a value at address 100, prints `3`, `2`, and `1`, and halts
without an error after 17 rising edges. The ROM contents use the version-1 machine words generated by the AP 7 encoder.

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
and while single-stepping the circuit. AP 6 extends decode and execution
without changing this frozen core trace.

The `.rom` file is the supported Logisim interchange representation; the
`.lst` file is diagnostic output and is not consumed by the circuit.

## Automated checks and simulation

### Fresh-checkout acceptance

From the repository root, the supported dependency-free acceptance command is:

```bash
PYTHONPATH=src python src/tiny_cpu_verify.py
```

It checks that every sheet is connected, the schematic matches the versioned
hardware profile, the ROM and listing can be reproduced byte-for-byte, the ROM
embedded in `TinyCPU.circ` matches the encoder, and the VM still reproduces the
checked-in 17-edge trace. Then run the focused regression tests with:

```bash
PYTHONPATH=src python -m pytest -q tests/detailtests/test_tiny_cpu_logisim.py
```

Neither command modifies the checkout. A stale generated file is reported by
name; regenerate ROM/listing with the AP 7 command above. A trace mismatch is
reported by edge and field; regenerate the trace only after reviewing the VM or
schematic behavior as an intentional compatibility change.

### Architecture and simulation boundary

The clocked state is owned by `FetchDecode` (PC), `Datapath` (accumulator and
validity), `AddressPath` (address register and validity), `Memory` (parallel
value/validity RAM), and `ErrorFlags` (six sticky bits). `FetchDecode` reads the
22-bit instruction word and exposes symbolic controls; the other sheets commit
selected state on the rising edge. `TinyCPU` is the integration boundary for
the shared clock, reset, data/control paths, output, and halt state.

The repository includes a dependency-free `.circ` netlist inspector. It parses
the XML, lists circuits and components, and returns a failing exit status when
sheets contain no wires or components have no wire at their anchor. For
`FetchDecode`, the inspector also checks that each exported symbolic control is
wired to its exact six-bit decoder lane; this catches dangling output-pin stubs
or off-by-one-grid wires that would otherwise look connected from the pin alone:

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
