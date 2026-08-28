# TinyCPU 1.x compatibility policy

The machine-readable release boundary is
`hardware/logisim/tinycpu-release-v1.json`. During the 1.x series, the named
hardware profile and top-level circuit, machine-format encoding and assigned
opcodes, AP-12 acceptance-report schema, supported runtime range, and public
CLI names and documented options are stable interfaces. Additions must remain
backward compatible; removing or reinterpreting one of these interfaces
requires a new major release contract.

Patch releases may fix implementations without changing observable machine
behaviour. Minor releases may add opcodes or CLI options only where the v1
format has reserved capacity and existing programs and commands retain their
meaning. A newer Java patch/feature runtime remains supported when it satisfies
the recorded minimum; the pinned Logisim-evolution version changes only through
an explicit, tested contract update.

Source-module APIs, XML coordinates and cosmetic circuit layout, generated
diagnostic leaf projects, trace/debug fixtures, test helpers, cache paths, and
CI artifact locations are internal. They may change between 1.x releases and
must not be treated as distribution interfaces. AP-12 evidence remains required
release input, but AP 13 does not create a release archive; packaging begins in
AP 14.
