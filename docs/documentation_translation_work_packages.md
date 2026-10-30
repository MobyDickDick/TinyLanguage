# English documentation translation work packages

## Goal and scope

The repository documentation must use English prose while preserving commands,
identifiers, paths, links, tables, and technical meaning. The initial inventory
covered the tracked Markdown, reStructuredText, AsciiDoc, and plain-text files
at the time of review. Most are already English; the files below contain German
prose or mixed German and English prose.

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

## WP-5: Program service and repository documentation — complete

Files:

- `docs/tiny_program_daemon.md`
- `docs/tiny_program_repository_db.md`

Translate the daemon and database documentation together. Preserve endpoint
paths, JSON and SQL field names, status values, schema terminology, and security
requirements exactly.

Acceptance record (2026-10-30):

- Manually reviewed and translated all narrative text and headings in both
  files, including the validation criteria and security pipeline requirements.
- Compared against the previous Git revision: fenced code blocks and the
  multiset of inline code spans are unchanged. Heading levels and list structure
  are preserved. Existing heading anchors remain available through explicit
  legacy IDs where the English heading generates a different anchor.
- The German-prose scan of both files has no unexplained matches. Intentional
  exceptions are the legacy German anchor IDs and the unchanged command
  placeholders `<datei_a.tiny>` / `<datei_b.tiny>`. No incoming references to
  translated heading names or fragments required updating.
- `git diff --check` passes. The focused regression suites
  `tests/test_tiny_program_daemon.py` and
  `tests/test_tiny_program_repository_db_adapter.py` pass: **26 passed** on
  Windows with Python 3.14. The runner supplied a valid Windows standard-input
  handle for the comparison CLI subprocess; the default tool environment's
  invalid handle otherwise causes `WinError 6` before the CLI starts.
- Additional source-import, scan, port, and GUI-wrapper tests were attempted:
  the initial combined run had **42 passed, 6 failed**. One failure was the CLI
  handle issue resolved in the focused run; four assert POSIX permission bits
  unavailable on Windows, and one requires symlink privileges unavailable in
  this environment. Sandbox tests cannot collect because `resource` is
  POSIX-only. These are platform-validation limitations, not passing security
  checks; platform verification remains open in
  [work package 3](open_tasks.md#3-supported-platform-verification).

## Final repository-wide audit — complete

Audit checklist:

1. rescan every tracked documentation file, not only the files in this list;
2. inspect every match and document intentional non-English fixture text;
3. review headings and link targets for stale German anchor references;
4. run documentation checks and the relevant TinyLanguage test suites; and
5. mark this audit complete only when no undocumented German narrative prose
   remains.

Acceptance record (2026-10-30):

- Rescanned all **103 tracked documentation files** selected by
  `git ls-files '*.md' '*.rst' '*.adoc' '*.txt'`: 99 Markdown files and four
  plain-text files; no reStructuredText or AsciiDoc files are tracked. The scan
  includes archived tasks, retained performance logs, extension documentation,
  and requirement files, rather than only the original translation inventory.
- Reviewed German-character and German-word matches in context, including
  words without umlauts, and reviewed all **991 headings outside fenced code**.
  Corrected four remaining German text fragments in `docs/language_spec.md`
  and `docs/native_ir.md`: two headings, an example label, and a code comment.
  No unexplained German narrative text remains in the tracked documentation.
- Intentional exceptions: the **15 explicit legacy anchor IDs** in
  `docs/language_spec.md`, `docs/native_ir.md`, `docs/tiny_program_daemon.md`,
  and `docs/tiny_program_repository_db.md` preserve existing links;
  `<datei_a.tiny>` / `<datei_b.tiny>` remain unchanged command placeholders;
  and `Pröjekt with spaces` in `docs/installed_workflows_acceptance.md` is a
  deliberate Unicode path fixture. Mentions of these exceptions in this
  work-package record are intentional too.
- Updated the internal argument-encapsulation reference to the English anchor
  and retained both translated headings' old anchors. Checked all **15 local
  Markdown links with documentation fragments** against heading and explicit
  IDs. Repaired the extension README's stale `6-codegen--interop` reference
  by linking directly to the Python interop examples; all 15 now resolve,
  including the new example-defect follow-up link in open-task package 9.
- Compared the newly translated documents with `HEAD`: fenced code and inline
  code retain their contents except for the translated comment; heading levels
  and task checkbox states are unchanged. Commands, identifiers, and language
  behavior are unchanged.
- `git diff --check` and `python tools/check_format_lint.py` pass. The focused
  suites below pass with **49 passed** on Windows using the repository's
  `.venv/bin/python.exe` (Python 3.14.5). CLI subprocesses were given a valid
  standard-input handle, as in the WP-5 acceptance run.

  ```text
  tests/test_language_spec_grammar.py
  tests/test_spec_conformance.py
  tests/detailtests/test_native_ir.py
  tests/detailtests/test_copy_on_call.py
  tests/detailtests/test_stdlib_doc_examples.py
  tests/detailtests/test_semantics_suite.py
  ```

- An additional direct run of the argument-encapsulation snippet exposed a
  pre-existing example defect: `_unused3` is a discard binding, so the
  `heap_set` call triggers `E001`. The snippet from `HEAD` and the translated
  snippet produce the same diagnostic. Replacing the three `_unused` binding
  names with ordinary `ignored` names in the verification harness makes both
  versions run and preserve the caller's buffer value of `1`. The translation
  retains the original identifiers; correcting and testing that example is
  tracked under open-task package 9. The 49-test result above does not imply
  that every documentation snippet executes verbatim.

This closes the documentation translation audit. The platform-verification
limitations recorded under WP-5 remain tracked by open-task package 3; this
audit does not claim a passing full-suite or cross-platform release run.
