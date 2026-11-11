# Package hardening and application acceptance

Work package 6 covers distribution integrity, bounded transfers, safe extraction,
and complete installed application workflows. Its implementation is available;
release-to-release runtime upgrade qualification remains a separate open gate.

## Distribution contract

- Remote HTTP(S) archives require a valid SHA-256 `registry_checksum` persisted
  in `tiny.lock`. The resolver accepts index metadata named `sha256` or
  `checksum`. The old fallback hash of `name@version` is not an archive digest
  and cannot authorize a remote installation. Missing or malformed hashes fail
  before network access, including when an old cache file exists.
- Registry metadata is read beside the manifest, independently of the calling
  directory. A changed metadata digest cannot override the lock. Refresh an
  older lock with `tiny pkg resolve --manifest /path/to/tiny.toml` after reviewing
  its registry metadata. `--force` replaces an existing vendor directory; it
  does not bypass integrity or archive validation.
- Cache hits are verified again. Downloads use private temporary files and
  replace the cache only after hashing the complete response. Wrong checksums,
  invalid lengths, incomplete responses, timeout and size failures remove the
  temporary download and preserve any previous cache file.
- Each network I/O operation uses a 10-second timeout. The response-body loop
  also checks a 60-second elapsed budget between individual socket reads, so
  continually trickling data cannot extend a download indefinitely. The next
  budget check can be delayed by one I/O timeout; DNS and redirect/header work
  remain subject to the host networking implementation and urllib redirect
  limits. These are bounded transfer controls, not process-level preemption.
- Compressed distributions are limited to 64 MiB, individual extracted files
  to 32 MiB, aggregate payload to 256 MiB, and archives to 10,000 members.
  Decompressed tar bytes, including extended headers and padding, have a
  separate budget of 256 MiB plus 1,024 bytes per permitted member. Gzip footer
  and CRC validation finish before installation. Limits are fixed constants in
  `src/tiny_pkg_sources.py`.
- Only regular files and directories are extracted. Symbolic/hard links,
  devices, FIFOs and sparse files are rejected. Paths use component containment
  and reject parent traversal, absolute/drive/UNC paths, Windows alternate data
  streams/reserved names, backslashes, nonportable names, excessive depth,
  duplicates and case collisions. Archive owners, modes and timestamps are not
  restored. Conventional root directory entries are allowed.
- Extraction occurs in a private sibling directory. An invalid archive cannot
  expose a partially extracted vendor package or delete an existing installation.
  Replacement failures restore the previous directory. If the host also refuses
  rollback, the diagnostic identifies the retained backup rather than deleting
  it. Existing filesystem links/junctions in destination paths and links in
  local source trees are refused. Package/version names are single portable
  components; registry-file identities use hashed components shared by the
  installer and module resolver.
- HTTP URLs with inline credentials or control characters are rejected;
  redirects cannot downgrade HTTPS. Network diagnostics do not echo URLs,
  response text or credentials. Local registry fixtures may use directory or
  tar sources; archive checksums, when present, are verified. Remote Git fetching
  is explicitly unsupported. This does not implement registry publication or
  transitive dependency resolution (work package 4).

These checks assume that the project, configured cache directory and their
parents are controlled by the invoking user. They do not provide filesystem
isolation against a hostile process concurrently replacing those directories.
Installation is staged per package, not an all-dependency transaction. A hard
process kill can leave private staging/backup directories; it never promotes an
unverified download to a valid vendor package.

## Complete application workflow

Run the actual wheel acceptance helper:

```bash
python tools/release/verify_application_workflows.py dist/tinylanguage-1.0.0-py3-none-any.whl --report artifacts/application.json
```

It installs the wheel into a clean temporary environment outside the checkout,
removes inherited Tiny/Python search-path settings, copies only the maintained
`examples/package_acceptance` fixture, and executes from another directory.
The fixture imports a bundled stdlib module and a locked dependency served by a
controlled loopback HTTP registry. It reads a Unicode JSON file, computes in a
worker, calls an allowlisted Python function, writes JSON and releases its heap
allocations. The installed public API independently asserts zero live heap
allocations after the same application.

The helper upgrades the dependency from fixture version 1.0.0 to 1.1.0 and
checks the independently calculated results 42 and 63 for input 21. It rejects
manifest/lock drift, stops the test server, deletes vendored sources, restores
the original lock and reproduces the original result using the verified cache.
Invalid Tiny syntax and invalid JSON must return failing CLI status; invalid
input must preserve previous output. A second fixture checks network/process
stub denials, Python allowlist/denylist errors, and cancellation followed by a
completed worker join. CI invokes this helper on every platform matrix target
and retains `platform-application.json` with the other platform evidence.

The boundary tests also demonstrate what is **not** isolated: filesystem APIs
use host permissions; allowlisted Python code can read outside the working
directory; a timed-out Python thread can finish later and perform side effects.
These are documented limitations, not successful sandbox checks. See
[Python interop](python_interop.md#security-and-sandboxing). The strict profile
remains a proposal.

## Release upgrade gate

Dependency fixture versions are not TinyLanguage release versions. To qualify
a real runtime upgrade, supply an independently retained previous release wheel:

```bash
python tools/release/verify_application_workflows.py dist/current/tinylanguage-1.1.0-py3-none-any.whl --previous-wheel dist/previous/tinylanguage-1.0.0-py3-none-any.whl --require-runtime-upgrade --report artifacts/application-upgrade.json
```

This installs the previous runtime, executes the application, upgrades in the
same environment and executes it again. Both artifact hashes and the distinct
versions are retained. Without `--previous-wheel`, the report explicitly says
`runtime_upgrade.status = "not-run"`; `--require-runtime-upgrade` fails when the
previous artifact is missing. No synthetic version bump substitutes for a real
release artifact.

## Local evidence (2026-11-04)

Local test and installed-wheel results are retained under `artifacts/packaging`.
They describe the working-tree snapshot rather than a tagged release. The
release upgrade gate remains open because this checkout has no independently
qualified previous/current release pair. Cross-platform execution evidence
continues to belong to work package 3.

- The complete regression suite passes on native Windows CPython **3.12.14**:
  **932 passed, 7 skipped** (939 collected), with no failed/error cases. Four
  existing pytest warnings concern benchmark properties in xunit2 XML. The
  retained [JUnit report](../artifacts/packaging/package-hardening-full.xml) and
  [checkpoint](../artifacts/packaging/package-hardening-checkpoint.json) identify
  counts, skips, the base commit and the maintained implementation hashes.
- The seven skips are two Windows symlink-privilege checks, two POSIX permission
  checks, two Linux-only source sandbox checks and the optional llvmlite JIT.
  Archive link rejection is exercised using tar metadata without requiring the
  host to create links. Skipped host-link and Linux sandbox checks are not
  recorded as passing security evidence.
- A wheel built with setuptools 84.1.0 and wheel 0.48.0 passes the complete
  application helper outside the checkout. The [installed application report](
  ../artifacts/packaging/windows-application-workflows.json) retains its SHA-256,
  fixture hashes and command outcomes. Packaged implementation bytes were
  compared with the maintained files. The fixture dependency upgrade and offline
  rollback pass; the runtime upgrade is explicitly `not-run`.
- The development environment's pure pytest installation was loaded into native
  Windows Python, with pinned build tools from `dist/release-tools`. Test
  temporary files stayed in ignored checkout directories, and subprocesses had
  a valid standard-input handle. Loopback HTTP acceptance needed execution
  outside this session's network-restricted sandbox.
- `python tools/check_format_lint.py` and `git diff --check` pass. No release is
  published and no release version is changed by this qualification.
