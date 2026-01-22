# TinyLanguage 1.0.0 Release Notes (Draft)

These notes summarize the planned 1.0.0 release, with a focus on what is
considered stable, any breaking changes, and known limitations.

## Highlights

- Stable interpreter-first workflow (the interpreter is the 1.0.0 golden path).
- Core language syntax and semantics documented in `docs/language_spec.md`.
- Baseline standard library coverage documented in `docs/stdlib_compatibility.md`.
- CLI usage and tutorials updated in `README.md` and `docs/tutorial.md`.

## Breaking changes

- **None identified for 1.0.0.** The 1.0 line is intended to preserve
  compatibility with programs that follow the documented language spec.

## Known limitations

- LLVM and native/C backends remain experimental and are out of scope for 1.0.0.
- Performance guarantees and packaging/distribution workflows are not part of
  the 1.0.0 scope.

## Getting started

- See `README.md` for the quickstart.
- Follow `docs/tutorial.md` for a guided walkthrough.

## Feedback

If you encounter issues, please reference the known limitations and file a
report with a minimal repro case and expected vs. actual behavior.
