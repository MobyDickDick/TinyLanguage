# Work package 5 checkpoint — 2026-11-02

Implementation and local verification are complete for this working-tree
checkpoint. **Release qualification and work package 5 remain open.** The
[candidate contract](../../docs/release_scope_v1.md) defines the scope,
exclusions, executable evidence map and outstanding delivery prerequisites.

The [machine-readable checkpoint](checkpoint.json) records HEAD, a digest of
the tested maintained working files, report hashes, summaries and limitations.
Every recorded command completed without changing that source identity.

| Check | Local result |
| --- | --- |
| Full suite with `--assert-no-heap-leaks` | 865 passed, 6 skipped; 4 existing JUnit-property warnings |
| Interpreter/spec/docs contract | 33 passed, no skips |
| LSP workflows | 38 passed, no skips |
| Experimental native parity | 16 passed, no skips |
| Required compiler C/LLVM subsets | 19 passed, no skips |
| Formatter/lint, CI YAML parsing, whitespace | Passed |
| CLI/API docstring lint | Failed: Ruff unavailable; local package lookup could not install it |
| Unsigned source archive | Build succeeds for HEAD; does not include uncommitted changes |
| Candidate evidence gate | Expected exit 1: docstring failure and dirty candidate/archive mismatch |

All checks used Windows CPython 3.12.14 and pytest 8.4.2. The test dependency
path was the repository's existing pure-Python development packages. C/LLVM
checks used the installed Clang toolchain. These are local execution results,
not a successful Linux/macOS matrix or independent-builder reproduction.

The six skips are optional llvmlite JIT, two POSIX executable-permission checks,
two Linux-only source-sandbox checks, and one Windows symlink-privilege check.
The passing full suite does not prove the open copy-on-call or interval
contracts correct; their existing tests are explicitly outside the frozen
stability target pending work packages 7–9.

The new regression checks include 17 evidence-gate cases and seven interpreter
contract cases, all included in the full suite. They exercise missing/stale/
modified results, failed processes, empty/skipped/invalid JUnit, real child
execution with valid stdin, source changes, payload integrity, a rational
arithmetic oracle and the actual Markdown encapsulation example.

Commit the candidate and run the recorded CI checks with Ruff available before
candidate regression approval. Complete delivery acceptance in packages 1–3
before release approval. The source archive and checksums are generated under
`dist/release-ci/`; CI retains them with the evidence. No tag, publication,
remote CI dispatch or release approval was performed in this checkpoint.
