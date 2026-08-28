# TinyCPU 1.0 release plan

The electrical acceptance of the circuit is complete, but that alone does not
constitute a TinyCPU 1.0 product release. AP 1 through AP 12 prove the hardware
and its simulator behaviour. The following bounded packages turn that accepted
baseline into a versioned, distributable, and independently verifiable release.

## Release definition of done

TinyCPU 1.0 is released only when all of the following are true:

1. the public hardware, ISA, machine-code, CLI, and artifact compatibility
   boundaries are explicitly versioned;
2. a source archive and a simulator-ready release bundle can be built twice
   from a clean checkout with identical file manifests and digests;
3. the AP-12 electrical acceptance passes for the exact release candidate and
   its evidence is included in the release bundle;
4. a clean environment can verify the bundle offline, assemble and run the
   countdown example, and reproduce its expected output; and
5. the release notes list supported versions, known limitations, upgrade rules,
   and every shipped file.

Passing the checkout-only Python verifier is necessary but not sufficient: the
real Logisim-evolution acceptance remains mandatory.

## AP 13 — Freeze the 1.0 release contract

**Deliverables**

- a machine-readable `tinycpu-release-v1.json` containing the release version,
  supported Logisim/Java versions, hardware profile, machine-format version,
  public CLI entry points, and required acceptance-report schema;
- a compatibility policy distinguishing stable 1.x interfaces from internal
  diagnostic files; and
- validation that rejects missing, contradictory, or unversioned release
  metadata.

**Acceptance criteria**

- focused tests cross-check the manifest against `tinycpu-16-12.json`,
  `tinycpu-machine-v1.json`, the pinned simulator constants, and CLI help;
- the normal TinyCPU verifier validates the release contract; and
- no release bundle is produced yet: AP 13 freezes inputs before packaging.

## AP 14 — Build a reproducible distribution

**Deliverables**

- one release command that creates a source archive and a simulator-ready
  bundle without modifying the checkout;
- a canonical inventory with relative paths, byte sizes, and SHA-256 digests;
- the circuit, profiles, machine format, assembler/simulator tools, example,
  documentation, license information, and AP-12 evidence in the bundle; and
- an offline verification command for the completed bundle.

**Acceptance criteria**

- two builds from clean checkouts have identical inventories and payload
  digests;
- undeclared, missing, symlinked, and digest-mismatched files are rejected; and
- extraction and verification work outside the repository tree.

## AP 15 — Qualify and publish TinyCPU 1.0

**Deliverables**

- a release-candidate checklist that runs the complete AP-12 electrical gate,
  builds AP-14 artifacts, verifies them offline, and performs the clean-room
  countdown smoke test;
- release notes and a support/limitations statement; and
- an authenticated checksum file plus documented tag naming
  (`tinycpu-v1.0.0`).

**Acceptance criteria**

- every mandatory check is recorded as passed for the same commit and artifact
  digests;
- the published archive is byte-for-byte the qualified release candidate; and
- only after this package is complete may documentation call TinyCPU 1.0
  released rather than release-ready or electrically accepted.

## Execution order

AP 13 is complete and its manifest is frozen. AP 14 is the next active package;
AP 15 depends on the reproducible artifacts from AP 14. Scope discovered while
executing a package must be added to that package's deliverables or recorded as
a separate unchecked task; completed AP 1 through AP 12 are not reopened.
