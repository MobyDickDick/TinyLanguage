#!/usr/bin/env python3
"""Validate formatter stability and lint cleanliness for curated fixtures."""

from __future__ import annotations

import pathlib
import sys
from typing import Iterable

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_ROOT))

from formatter import format_source  # noqa: E402
from language_server import TinyLanguageServer  # noqa: E402

FIXTURES = [
    PROJECT_ROOT / "tests" / "fixtures" / "formatter_lint_sample.tiny",
]


def _format_diff(path: pathlib.Path, source: str, formatted: str) -> str:
    """Format a diff-like snippet to show formatting drift."""
    return "\n".join(
        [
            f"--- {path}",
            "+++ formatted",
            "@@",
            *formatted.splitlines(),
            "@@",
            *source.splitlines(),
        ]
    )


def _diagnostic_summary(diagnostics: Iterable) -> str:
    """Summarize diagnostics into human-readable bullet points."""
    lines = []
    for diag in diagnostics:
        lines.append(f"- [{diag.code}] {diag.message}")
    return "\n".join(lines)


def check_fixture(path: pathlib.Path) -> list[str]:
    """Check formatter idempotence and lint diagnostics for one fixture."""
    errors: list[str] = []
    source = path.read_text(encoding="utf-8")
    formatted = format_source(source)
    if formatted != source:
        errors.append(
            "\n".join(
                [
                    f"Formatter output differs for {path}",
                    _format_diff(path, source, formatted),
                ]
            )
        )

    server = TinyLanguageServer(source, lint_profile="typing")
    diagnostics = server.diagnostics()
    if diagnostics:
        errors.append(
            "\n".join(
                [
                    f"Diagnostics emitted for {path}",
                    _diagnostic_summary(diagnostics),
                ]
            )
        )
    return errors


def main() -> int:
    """Run the module entry point."""
    failures: list[str] = []
    for fixture in FIXTURES:
        if not fixture.exists():
            failures.append(f"Missing fixture: {fixture}")
            continue
        failures.extend(check_fixture(fixture))

    if failures:
        joined = "\n\n".join(failures)
        sys.stderr.write(f"Formatter/lint checks failed:\n{joined}\n")
        return 1

    print("Formatter and lint checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
