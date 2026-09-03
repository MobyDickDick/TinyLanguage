# English documentation translation work packages

## Goal and scope

The repository documentation must use English prose while preserving commands,
identifiers, paths, links, tables, and the meaning of hardware contracts. The
initial inventory covers all 578 tracked Markdown, reStructuredText, AsciiDoc,
and plain-text files. Most are already English; the files below contain German
prose or mixed German and English prose.

A keyword scan is only an inventory aid. Each work package must also be reviewed
manually because short headings and sentences may not contain German-specific
characters.

## Shared acceptance criteria

A package is complete only when:

- all narrative text and headings in its files are idiomatic English;
- fenced code, commands, paths, API names, signal names, opcodes, coordinates,
  version numbers, and links retain their exact technical meaning;
- Markdown structure, anchors, lists, tables, and task checkbox states remain
  intact;
- cross-references use the translated heading when they name a heading;
- the German-prose audit reports no unexplained matches; and
- relevant documentation or repository tests pass.

Names that are part of fixtures, user-facing compatibility examples, or quoted
external data may remain German, but the reviewer must record each intentional
exception in the completed package.

## WP-1: Standalone task list and isolated fragments — complete

Files:

- `documentation_tasks.md`
- `docs/open_tasks.md` (isolated WP 7 heading)
- `docs/python_interop.md` (isolated example label)
- `docs/rosetta_python_examples.md` (isolated heading)
- `imageCompositeConverterFs/mainFiles/README.md`

Translate the standalone German task list and the isolated fragments found in
documents that otherwise already use English. Preserve all completed checkbox
states and file paths.

## WP-2: TinyCPU overview and test documentation — complete

Files:

- `docs/tiny_cpu.md`
- `docs/tiny_cpu_test_guide.md`
- `docs/logisim_diagnostics_known_issues.md`

Translate user-facing architecture, testing, and troubleshooting prose. Verify
that commands and the distinction between static checks and real-simulator
checks remain unchanged.

Review note: path placeholders inside commands (such as
`/pfad/zu/TinyLanguage`) remain unchanged because commands are explicitly
preserved by the acceptance criteria. Commit hashes are likewise technical data
rather than narrative prose.

## WP-3: TinyCPU design and integration templates — pending

Files:

- `docs/tiny_cpu_alu_sketch.md`
- `docs/tiny_cpu_top_level_template.md`

Translate the ALU sketch and the fillable integration template together so that
shared signal terminology stays consistent. Do not translate literal signal,
pin, circuit-sheet, or component labels.

## WP-4: TinyCPU roadmap — pending

File:

- `docs/tiny_cpu_roadmap.md`

Translate the roadmap in one package to preserve dependencies, completion
states, acceptance boundaries, and work-package numbering. Do not reinterpret
historical status statements as open work.

## WP-5: Program service and repository documentation — pending

Files:

- `docs/tiny_program_daemon.md`
- `docs/tiny_program_repository_db.md`

Translate the daemon and database documentation together. Preserve endpoint
paths, JSON and SQL field names, status values, schema terminology, and security
requirements exactly.

## WP-6: Logisim maintainer README — pending

File:

- `hardware/logisim/README.md`

Translate all remaining German sections in this mixed-language maintainer guide.
Because it is the largest package and defines electrical contracts, review the
result section by section against `TinyCPU.circ`; preserve coordinates, signal
names, opcode numbers, commands, and the wording strength of normative rules.
Use the terminology established by WP-2 and WP-3.

## Final repository-wide audit — pending

After WP-2 through WP-6 are complete:

1. rescan every tracked documentation file, not only the files in this list;
2. inspect every match and document intentional non-English fixture text;
3. review headings and link targets for stale German anchor references;
4. run documentation checks and the relevant TinyCPU test suites; and
5. mark this audit complete only when no undocumented German narrative prose
   remains.
