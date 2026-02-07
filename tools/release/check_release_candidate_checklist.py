#!/usr/bin/env python3
"""Validate the release-candidate checklist section enforced by CI."""

from __future__ import annotations

import sys
from pathlib import Path

CHECKLIST_PATH = Path("docs/release_candidate_checklist.md")
SECTION_HEADER = "## CI gate checklist"


def extract_section(lines: list[str]) -> list[str]:
    in_section = False
    section_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break
            in_section = stripped == SECTION_HEADER
            continue
        if in_section:
            section_lines.append(line)
    return section_lines


def main() -> int:
    if not CHECKLIST_PATH.exists():
        print(f"Checklist not found: {CHECKLIST_PATH}")
        return 1

    lines = CHECKLIST_PATH.read_text(encoding="utf-8").splitlines()
    section_lines = extract_section(lines)

    if not section_lines:
        print(f"Checklist section missing or empty: {SECTION_HEADER}")
        return 1

    unchecked = [
        line.strip()
        for line in section_lines
        if line.strip().startswith("- [ ]")
    ]

    if unchecked:
        print("Release-candidate checklist has unchecked CI items:")
        for item in unchecked:
            print(f"  {item}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
