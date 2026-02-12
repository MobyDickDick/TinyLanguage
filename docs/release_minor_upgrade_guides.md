# Minor release upgrade guides

This document defines how TinyLanguage publishes **minor release upgrade
information** and **automated migration tooling**. Each minor release (X.Y.0)
gets its own upgrade guide in `docs/release_minor_guides/` plus a matching
migration recipe entry in `docs/release_minor_migration_recipes.json`.

## Current minor release guides

A draft guide exists for the first planned minor release. Finalize release-specific notes and validation evidence when cutting the release candidate.

| From → To | Guide | Migration recipe | Status |
| --- | --- | --- | --- |
| 1.0.0 → 1.1.0 | `docs/release_minor_guides/1_0_0_to_1_1_0.md` | `docs/release_minor_migration_recipes.json` | Drafted (pre-release) |

## Publishing workflow

1. **Create or update the migration recipe**
   - Add a `releases["X.Y.Z->X.Y+1.0"]` entry in
     `docs/release_minor_migration_recipes.json`.
   - Keep automated changes mechanical (renames, path changes, config updates).
   - Leave manual steps for the guide.
2. **Generate the upgrade guide skeleton**
   - Run:
     ```bash
     python tools/release/prepare_minor_upgrade.py \
       --from X.Y.Z --to X.Y+1.0 \
       --guide-dir docs/release_minor_guides
     ```
3. **Validate automated migrations**
   - Use `--apply --dry-run` to preview updates, then run without `--dry-run`.
4. **Finalize the guide**
   - Fill in version-specific notes, test steps, and any manual migration work.

## Automation entry point

`tools/release/prepare_minor_upgrade.py` reads migration recipes, generates the
upgrade guide template, and can apply recipe steps. See the script header for
supported actions and usage examples.
