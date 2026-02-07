"""Generate and apply minor release upgrade guides and migration recipes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import textwrap


def load_recipes(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "releases": {}}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def format_steps(steps: list[dict]) -> str:
    if not steps:
        return "- (No automated steps listed.)"
    lines = []
    for step in steps:
        description = step.get("description") or step.get("action", "step")
        target = step.get("path", "")
        lines.append(f"- {description} ({target})")
    return "\n".join(lines)


def format_manual_steps(manual_steps: list[str]) -> str:
    if not manual_steps:
        return "- (No manual steps listed.)"
    return "\n".join(f"- {step}" for step in manual_steps)


def build_guide(from_version: str, to_version: str, recipes: dict) -> str:
    release_key = f"{from_version}->{to_version}"
    release = recipes.get("releases", {}).get(release_key, {})
    summary = release.get("summary", "Describe the high-level upgrade impact.")
    steps = format_steps(release.get("steps", []))
    manual_steps = format_manual_steps(release.get("manual_steps", []))

    return textwrap.dedent(
        f"""\
        # Upgrade guide: {from_version} → {to_version}

        **Release date:** TBD
        **Scope:** Minor release upgrade guide for TinyLanguage {to_version}.

        ## Summary

        {summary}

        ## Automated migrations

        Run the migration tool (dry run first):

        ```bash
        python tools/release/prepare_minor_upgrade.py \
          --from {from_version} --to {to_version} \
          --apply --dry-run
        ```

        Planned automated steps:

        {steps}

        ## Manual migration steps

        {manual_steps}

        ## Validation checklist

        - Run the project test suite and linting workflow.
        - Verify TinyLanguage CLI commands in automation and CI.
        - Confirm package/module imports resolve correctly.

        ## Rollback plan

        - Revert the migration commit.
        - Pin TinyLanguage tooling to {from_version} until the blockers are resolved.
        """
    )


def apply_steps(steps: list[dict], repo_root: Path, dry_run: bool) -> list[str]:
    results = []
    for index, step in enumerate(steps, start=1):
        action = step.get("action")
        target_path = Path(step.get("path", ""))
        if not target_path.is_absolute():
            target_path = repo_root / target_path
        if not target_path.exists():
            results.append(f"{index}. SKIP missing file: {target_path}")
            continue

        content = target_path.read_text(encoding="utf-8")
        updated = content
        if action == "replace":
            search = step.get("search", "")
            replacement = step.get("replace", "")
            count = step.get("count", 0)
            updated = content.replace(search, replacement, count if count else -1)
        elif action == "regex_replace":
            pattern = step.get("pattern", "")
            replacement = step.get("replace", "")
            updated = re.sub(pattern, replacement, content, count=step.get("count", 0))
        else:
            results.append(f"{index}. SKIP unknown action '{action}'")
            continue

        if updated == content:
            results.append(f"{index}. NOOP {action} in {target_path}")
            continue

        if not dry_run:
            target_path.write_text(updated, encoding="utf-8")
        results.append(f"{index}. {'DRY-RUN' if dry_run else 'APPLIED'} {action} in {target_path}")

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate minor release upgrade guides and apply migration recipes."
    )
    parser.add_argument("--from", dest="from_version", required=True)
    parser.add_argument("--to", dest="to_version", required=True)
    parser.add_argument(
        "--guide-dir",
        default="docs/release_minor_guides",
        help="Directory for generated upgrade guides.",
    )
    parser.add_argument(
        "--recipes",
        default="docs/release_minor_migration_recipes.json",
        help="Path to migration recipe JSON.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply migration steps from the recipe.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    recipes_path = repo_root / args.recipes
    recipes = load_recipes(recipes_path)

    guide_dir = repo_root / args.guide_dir
    guide_dir.mkdir(parents=True, exist_ok=True)
    guide_name = f"{args.from_version}_to_{args.to_version}.md".replace(".", "_")
    guide_path = guide_dir / guide_name
    guide_content = build_guide(args.from_version, args.to_version, recipes)
    guide_path.write_text(guide_content, encoding="utf-8")

    if args.apply:
        release_key = f"{args.from_version}->{args.to_version}"
        steps = recipes.get("releases", {}).get(release_key, {}).get("steps", [])
        results = apply_steps(steps, repo_root, args.dry_run)
        for result in results:
            print(result)

    print(f"Generated guide: {guide_path}")


if __name__ == "__main__":
    main()
