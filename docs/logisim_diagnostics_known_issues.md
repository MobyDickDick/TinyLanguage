# Verification of the Logisim diagnostic circuits

The projects under `hardware/logisim/diagnostics/` are generated directly from
the integrated `hardware/logisim/TinyCPU.circ` circuit using
`tiny_cpu_circuit.py --split-output`. The individual sheets therefore use the
same components, bit widths, and connections as the reference circuit.

## Verification result

The previous, manually divergent `TinyCPU-FetchDecode.circ` connected 1-bit
control signals to a 16-bit datapath. In particular, `JUMP_NOT_ZERO` and
`HALT_ERROR` were not connected to their intended decoder lanes. That version
was replaced by the two current reference sheets, `TinyCPU-FetchDecode.circ`
and `TinyCPU-FetchDecodeControls.circ`. This keeps the PC/ROM path and control
signal decoding electrically separate so that they can be examined
independently.

Each of the six diagnostic projects consists of exactly one independently
loadable sheet and passes the structural connectivity check. An automated test
compares them byte for byte with files newly generated from `TinyCPU.circ`, so
future changes to the reference circuit cannot diverge unnoticed from the
diagnostic projects.

## Reproducible verification

```bash
PYTHONPATH=src python src/tiny_cpu_circuit.py \
  --split-output hardware/logisim/diagnostics \
  hardware/logisim/TinyCPU.circ

for project in hardware/logisim/diagnostics/*.circ; do
  PYTHONPATH=src python src/tiny_cpu_circuit.py "$project"
done
```

This check evaluates structure, port assignments, and bus widths. Electrical
runtime simulation of the Logisim component library remains the responsibility
of Logisim-evolution.

## Root-cause analysis of the repeated reversion

Logisim itself did not restore the faulty version. Instead, the Git history
shows that an older, automatically generated repair (`3e9ea7a`, `c5b8cd2`, and
`de63af2`) was reapplied to each explicitly restored user version (`ac06b29`,
and later `5f4d2ab`) and subsequently merged through a pull request. The repair
therefore used the wrong baseline: rather than correcting the latest user
commit each time, earlier agent commits served as a supposedly known “working”
reference.

Regression tests that fixed specific coordinates and component positions from
the older drawing contributed to this problem. A user solution with a
different electrical arrangement therefore failed even when its design was
functionally equivalent. Copying back the old drawing appeared to be the
easier way to make the tests pass—and that is precisely what repeatedly
displaced the user's change.

Commit `28d49cb` is therefore explicitly the baseline for the current repair.
The components and layout of that version remain intact; only faulty networks,
bus taps, and the corresponding diagnostic fixtures were corrected. Tests now
locate moved components using their labels or current interface instead of
indirectly restoring the old drawing through historical coordinates. The
diagnostic sheets generated from the main project remain reproducible byte for
byte.
