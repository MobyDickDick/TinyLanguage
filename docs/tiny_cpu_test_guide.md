# Testing TinyCPU.circ yourself

This guide provides the short, recommended procedure for a complete test of
the committed circuit. Run all commands from the root of the TinyLanguage
checkout.

## Prerequisites

- **Java 21 or newer** (`java -version`)
- **Python 3** (`python3 --version`)
- an internet connection for the first run **or** the file
  `logisim-evolution-4.1.0-all.jar`

You do not need to install Logisim separately. The test script downloads the
exact supported Logisim-evolution version, 4.1.0, to the user cache. The JAR is
not committed to Git.

## Complete automated test

1. Open a terminal and change to the checkout:

   ```bash
   cd /pfad/zu/TinyLanguage
   ```

2. Check Java:

   ```bash
   java -version
   ```

   The output must report Java 21 or newer.

3. Start the test:

   ```bash
   scripts/test-logisim.sh
   ```

The script loads `hardware/logisim/TinyCPU.circ` in the real simulator and runs
the stable 17-tick counter test. A successful run exits with status 0. The full
opcode/error matrix, which currently still fails, is deliberately not part of
the required test run. It can be run for diagnostic purposes with
`TINYCPU_FULL_ACCEPTANCE=1 scripts/test-logisim.sh` and must become a mandatory
CI check again only after a successful repair.

The stable AP-5 test is part of the CI test run. A missing simulator or a
failure in this approved test causes the run to fail; there is no silent
fallback to a project-loading-only or Python test.

### If you already have the Logisim JAR

Place the exactly named file `logisim-evolution-4.1.0-all.jar` anywhere under
the checkout and run:

```bash
scripts/test-logisim-local.sh
```

If it is outside the checkout or there are multiple copies, specify the path
explicitly:

```bash
scripts/test-logisim-local.sh /pfad/zu/logisim-evolution-4.1.0-all.jar
```

## Verifying the result later without the simulator

An existing evidence bundle can be checked for completeness and unchanged
checksums using Python alone:

```bash
PYTHONPATH=src python3 src/tiny_cpu_logisim.py \
  --verify-acceptance artifacts/tinycpu-ap12-acceptance
```

This check does not simulate the CPU again. It confirms that the bundle
previously produced by the real simulator is complete and unchanged.

## Inspecting the circuit as well

For a visual inspection, start Logisim-evolution 4.1.0 and open
`hardware/logisim/TinyCPU.circ`. Select the `TinyCPUMain` sheet on the left. You
can inspect signals with the Poke tool; the automated test does not require
changes to the file.

If the large project does not load, first open
`hardware/logisim/smoke/PinPair-1bit.circ`, `PinPair-12bit.circ`, and
`PinPair-16bit.circ` in that order. If they work, use the standalone projects
under `hardware/logisim/diagnostics/` to narrow the problem down to the affected
circuit sheet.

## Common problems

| Message or symptom | Solution |
|---|---|
| `Java 21 or newer is required` | Install Java 21+ or use `JAVA=/pfad/zu/java scripts/test-logisim.sh`. |
| JAR download fails | Download the JAR manually and run `scripts/test-logisim-local.sh /pfad/zur/JAR`. |
| Multiple JAR files found | Pass the desired full path to `scripts/test-logisim-local.sh`. |
| Test fails | Check the first error message and `artifacts/tinycpu-ap12-acceptance/acceptance.json`; an aborted run does not count as passing. |

# Topological circuit tests

`hardware/logisim/TinyCPU.circ` is a manually maintained drawing. Its electrical
interface, not its arrangement on the canvas, is the test contract. Circuit
tests therefore always name the circuit sheet, component, source port, and
destination port. A test must neither compare fixed `loc` coordinates nor
calculate the connection coordinates of an automatically generated subcircuit
component from its position.

This rule applies to **every** circuit sheet and also to textual acceptance
tests: names, docstrings, and error messages describe, for example,
“`FetchDecode.PC_OUT` reaches `Datapath`” rather than “wire `(x1,y1)` reaches
`(x2,y2)`.” Absolute points are permitted only in synthetic, local XML fixtures
that test the netlist parser itself.

When making corrections, always use the latest user-maintained circuit as the
baseline. A failed historical layout test never justifies copying back an older
drawing. First reproduce the electrical fault at named ports; then correct the
circuit and test together against this topological contract.

The checkout gate `PYTHONPATH=src python3 src/tiny_cpu_verify.py` also enforces
this contract. It requires unique names for all sheet ports and subcircuit
instances, then checks open ports, multiple drivers, and bus widths on the
networks that are actually connected. Electrically relevant individual
components are identified by their `label`; their `loc` position is neither
their identity nor an expected value of the check.
