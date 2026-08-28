# TinyCPU 1.0.0 release notes

TinyCPU 1.0.0 is the first qualified release of the 12-bit-data/16-bit-address
Logisim CPU, its versioned 22-bit machine format, assembler, reference simulator,
and offline verification tools. The release tag is `tinycpu-v1.0.0`.

## Supported environment and interfaces

- Logisim-evolution 4.1.0 and Java 21 or newer are the electrical acceptance
  environment.
- The stable 1.x boundary comprises the hardware profile, machine format,
  top-level `TinyCPUMain` pins, opcode table, and documented CLI entry points.
- The source and simulator archives list every payload byte in
  `tinycpu-inventory-v1.json`; the simulator archive retains the passed AP-12
  evidence and can be checked without a repository or network connection.

## Limitations

- Logisim-evolution remains the normative electrical simulator. The Python VM
  is a convenient reference implementation, not electrical acceptance proof.
- Java versions below 21 and Logisim versions other than 4.1.0 are unsupported.
- Internal diagnostic JSON, circuit drawing coordinates, and implementation
  details not named by the compatibility policy are not stable interfaces.
- The release does not promise compatibility with third-party circuit forks or
  modified archive contents.

## Qualification and publication checklist

Run AP-12 on the exact commit, then invoke the single AP-15 gate with the full
commit object ID and the release signer's PEM private key:

```bash
python src/tiny_cpu_logisim.py --acceptance-output artifacts/tinycpu-ap12-acceptance
python tools/tiny_cpu_qualification.py qualify \
  --acceptance artifacts/tinycpu-ap12-acceptance \
  --output-dir dist/tinycpu-v1.0.0 \
  --commit "$(git rev-parse HEAD)" \
  --signing-key /secure/path/tinycpu-release-private.pem
```

The command first checks that `--commit` is the checkout's exact `HEAD`, runs
the complete checkout verifier, and validates the full AP-12 report rather than
accepting only its top-level status. It then records the offline archive checks,
clean-room `3, 2, 1` countdown, unchanged candidate-to-publication bytes,
commit, sizes, and digests in `tinycpu-v1.0.0-qualification.json`. It signs a
`SHA256SUMS` that covers both archives **and the qualification report** with
OpenSSL SHA-256 and stages only the qualified files under `published/`.

Before uploading, verify with the separately distributed public key:

```bash
python tools/tiny_cpu_qualification.py verify \
  dist/tinycpu-v1.0.0/published \
  --public-key /trusted/path/tinycpu-release-public.pem
git tag -s tinycpu-v1.0.0 "$(git rev-parse HEAD)" \
  -m "TinyCPU 1.0.0"
```

Upload the complete `published/` directory: the two archives, qualification
report, checksum list, and detached signature. Do not rebuild or rename any of
them. Download all five files into a fresh directory and rerun the verification
command before publishing the tag. This last comparison ensures the public
archives are byte-for-byte the qualified candidate.
