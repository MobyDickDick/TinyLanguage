<a id="tiny-program-daemon-30-minuten-generator"></a>
# Tiny Program Daemon (30-Minute Generator)

This document describes an initial building block for an "art project": a daemon
that generates TinyLanguage example programs at regular intervals.

<a id="ziel"></a>
## Goal

The daemon automatically generates `.tiny` files at regular intervals. Defaults:

- Interval: **1800 seconds (30 minutes)**
- Output directory: `generated_tiny_programs/`
- Idea catalog: locally curated templates (logic + mathematics + simulation)

Implementation: `src/tiny_program_daemon.py`.

<a id="starten-einmalig"></a>
## Run once

```bash
python src/tiny_program_daemon.py --count 1
```

<a id="als-laufender-dienst-daemon"></a>
## Run as a continuous service (daemon)

```bash
python src/tiny_program_daemon.py
```

<a id="wichtige-cli-optionen"></a>
## Key CLI options

- `--interval-seconds 1800`: set the interval
- `--count N`: generate a finite number of programs and exit
- `--idea <slug>`: force a specific program idea
- `--seed <int>`: make random selection reproducible
- `--db-path <sqlite.db>`: also store validated programs in SQLite
- `--deterministic`: reject time and randomness sources in the generated program

Example:

```bash
python src/tiny_program_daemon.py --interval-seconds 60 --count 3 --idea nand-gate
```

<a id="qualitätskriterien-für-den-programmgenerator"></a>
## Quality criteria for the program generator

The generator checks new programs with conservative heuristics before writing
or storing them:

1. **No dead stores**: variables must be read as well as written (except those
   explicitly named `_unused*`).
2. **No obvious infinite loops**: `while (true)` and `while (1)` are rejected.
3. **No obvious unhandled exceptions**: `throw` and obvious `... / 0` patterns
   are rejected.
4. **No database duplicates**: a normalized signature is checked when writing
   to SQLite; semantically identical programs are not stored more than once.
5. **Basic deadlock warning**: `spawn` without a detectable `join(...)` causes
   rejection.

<a id="weitere-sinnvolle-kriterien-als-nächste-aufgaben"></a>
### Additional useful criteria (follow-up tasks)

- **Deeper control-flow termination analysis (completed 2026-08-21)**:
  structured `while` blocks are fully captured as cyclic control-flow regions.
  The validator accepts only comparison-based loops whose induction variable
  can be shown to make progress in the loop body; literal infinite loops with
  alternative formatting are also rejected.
- **Type-safety and range checks (completed 2026-08-22)**: division is accepted
  only when a numeric literal, a local literal assignment, or a preceding zero
  check with a mandatory `return` proves that the denominator is nonzero. A
  later assignment invalidates that proof.
- **Resource limits (completed 2026-08-22)**: heap allocations require a fixed,
  nonnegative size of at most 4096 elements. Comparison-based loops require a
  locally provable integer starting value, a constant step size, and an upper
  bound of at most 10,000 iterations.
- **Determinism profile (completed 2026-08-22)**: `--deterministic` rejects
  calls to the Tiny standard library for the current time, monotonic time, and
  random values. Comments and strings do not trigger the check; without this
  option, the generator retains its existing behavior.
- **Style and readability rules (completed 2026-08-22)**: every generated
  program requires at least one nonempty, explanatory `//` comment;
  automatically generated metadata such as the idea, category, and description
  does not count. Declared function and variable names must use `snake_case`.
  The `logic` and `math` categories are limited to 80 lines;
  `physics-simulation` and unknown categories are limited to 100 lines.

## Systemd template

A unit template is available at:

- `tools/systemd/tiny-program-daemon.service`

Adjust the paths (`WorkingDirectory`, `ExecStart`) for your target system.

<a id="sicherheits--und-projekt-hinweise"></a>
## Security and project notes

This initial step deliberately uses **only local, predefined templates** and
does not execute third-party code.

For the next expansion stage (crawler, repository import, virus scanning, and
porting to Tiny), a pipeline with multiple stages is recommended:

1. **Fetch source into quarantine (completed 2026-08-22)** (e.g. from
   RosettaCode / Git repositories). `src/tiny_program_source_import.py` downloads
   only HTTPS sources from a narrow host allowlist, limits their size, and stores
   the unchanged bytes without an executable file extension, together with the
   URL, time, size, and SHA-256 checksum. Further processing is prohibited until
   step 2.
2. **Security scan (completed 2026-08-22)**: the separate scanner
   `src/tiny_program_source_scan.py` does not execute code. It first verifies the
   size and SHA-256 provenance. It then accepts only UTF-8 source files with
   `.py` or `.tiny` extensions and rejects binary signatures, executable
   shebangs, dynamic code execution, process launches, and external I/O APIs.
   Only a passing, versioned scan report authorizes automatic porting as the
   next stage.
3. **Automatic porting to TinyLanguage (completed 2026-08-22)**: the porter
   accepts only a matching set of quarantine, provenance, and passing scan
   files, and rechecks the SHA-256 association. Python is translated only within
   the limited, declarative transpiler subset; existing Tiny source is copied
   over. The result is explicitly left unexecuted and receives a versioned
   report with an output hash and `sandbox-test` as the only next step.
4. **Sandbox test run and result evaluation (completed 2026-08-23)**: only a
   program that matches the porter report byte for byte is launched in an empty
   working directory and an isolated Python process.
   `src/tiny_program_source_sandbox.py` limits runtime, memory, output file size,
   open files, and child processes, captures the combined output, and authorizes
   only successful runs for a GUI wrapper through a versioned report.
   Execution requires Linux with POSIX resource limits; Windows and macOS
   reject this step without launching the program or generating an approval.
   These resource limits do not isolate filesystem or network access. See the
   [platform contract](release_compatibility_matrix.md#source-program-service-platform-contract)
   for execution and file-permission limitations.
5. **Optional GUI wrapper (completed 2026-08-23)**: the generator
   `src/tiny_program_gui_wrapper.py` accepts only a passing sandbox result whose
   source and output hashes still match. The generated Tk wrapper displays only
   the verified, embedded output and does not rerun the imported source outside
   the sandbox. A separate report binds the wrapper, source, and sandbox output
   together using SHA-256 checksums.

This preserves the creative workflow without compromising safe default operation.
