#!/usr/bin/env python3
"""List converted output files and matching diff files for specific references."""

from __future__ import annotations

import argparse
from pathlib import Path


def _find_matches(artifacts_dir: Path, ref: str) -> tuple[list[Path], list[Path]]:
    ref_upper = ref.upper()
    converted: list[Path] = []
    diffs: list[Path] = []

    for path in artifacts_dir.rglob("*"):
        if not path.is_file():
            continue
        name_upper = path.name.upper()
        stem_upper = path.stem.upper()

        if ref_upper in name_upper and "DIFF" not in name_upper:
            converted.append(path)
        if ref_upper in name_upper and "DIFF" in name_upper:
            diffs.append(path)
        elif stem_upper == f"{ref_upper}_DIFF":
            diffs.append(path)

    return sorted(set(converted)), sorted(set(diffs))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refs", nargs="+", help="Reference IDs, e.g. AC0870 AR0100")
    parser.add_argument("--artifacts", default="artifacts", help="Artifacts root directory")
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts)
    if not artifacts_dir.exists():
        print(f"Artifacts directory not found: {artifacts_dir}")
        return 1

    for ref in args.refs:
        converted, diffs = _find_matches(artifacts_dir, ref)
        print(f"\n{ref}:")
        if converted:
            print("  converted:")
            for path in converted:
                print(f"    - {path.as_posix()}")
        else:
            print("  converted: (none)")

        if diffs:
            print("  diffs:")
            for path in diffs:
                print(f"    - {path.as_posix()}")
        else:
            print("  diffs: (none)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
