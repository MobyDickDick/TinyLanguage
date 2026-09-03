# English documentation translation work packages

## Goal and scope

The repository documentation must use English prose while preserving commands,
identifiers, paths, links, tables, and technical meaning. The current inventory
covers 568 Markdown, reStructuredText, and plain-text files outside the
development environment. Most are already English; the files below contain
German prose or mixed German and English prose.

A keyword scan is only an inventory aid. Each work package must also be reviewed
manually because short headings and sentences may not contain German-specific
characters.

## Shared acceptance criteria

A package is complete only when:

- all narrative text and headings in its files are idiomatic English;
- fenced code, commands, paths, API names, version numbers, and links retain
  their exact technical meaning;
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

## WP-2: Program service and repository documentation — pending

Files:

- `docs/tiny_program_daemon.md`
- `docs/tiny_program_repository_db.md`

Translate the daemon and database documentation together. Preserve endpoint
paths, JSON and SQL field names, status values, schema terminology, and security
requirements exactly.

## Final repository-wide audit — pending

After the remaining work packages are complete:

1. rescan every tracked documentation file, not only the files in this list;
2. inspect every match and document intentional non-English fixture text;
3. review headings and link targets for stale German anchor references;
4. run the relevant documentation checks; and
5. mark this audit complete only when no undocumented German narrative prose
   remains.
