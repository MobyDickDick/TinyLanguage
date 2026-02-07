#!/usr/bin/env python3
"""Run formatter + lint baseline checks over TinyLanguage sources."""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Iterable, List

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_ROOT))

from formatter import format_source  # noqa: E402
from language_server import TinyLanguageServer  # noqa: E402

DEFAULT_FIXTURES = [
    PROJECT_ROOT / "tests" / "fixtures" / "formatter_lint_sample.tiny",
]


def _iter_tiny_files(paths: Iterable[pathlib.Path]) -> List[pathlib.Path]:
    files: list[pathlib.Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.rglob("*.tiny")))
        else:
            files.append(path)
    return files


def _format_diff(path: pathlib.Path, source: str, formatted: str) -> str:
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
    lines = []
    for diag in diagnostics:
        lines.append(f"- [{diag.code}] {diag.message}")
    return "\n".join(lines)


def _format_and_lint(
    path: pathlib.Path,
    *,
    lint_profile: str,
    apply: bool,
) -> list[str]:
    errors: list[str] = []
    source = path.read_text(encoding="utf-8")
    formatted = format_source(source)

    if formatted != source:
        if apply:
            path.write_text(formatted, encoding="utf-8")
        else:
            errors.append(
                "\n".join(
                    [
                        f"Formatter output differs for {path}",
                        _format_diff(path, source, formatted),
                    ]
                )
            )

    server = TinyLanguageServer(formatted, lint_profile=lint_profile)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run TinyLanguage formatter + lint baseline checks",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=pathlib.Path,
        help="Files or directories to check (defaults to the curated fixtures)",
    )
    parser.add_argument(
        "--lint-profile",
        choices=["default", "typing"],
        default="default",
        help="Lint profile to apply during diagnostics",
    )
    apply_group = parser.add_mutually_exclusive_group()
    apply_group.add_argument(
        "--check",
        action="store_true",
        help="Only report formatting differences (default)",
    )
    apply_group.add_argument(
        "--apply",
        action="store_true",
        help="Write formatter output back to disk before linting",
    )

    args = parser.parse_args(argv)
    apply = args.apply

    targets = args.paths if args.paths else DEFAULT_FIXTURES
    files = _iter_tiny_files(targets)
    failures: list[str] = []

    for path in files:
        if not path.exists():
            failures.append(f"Missing file: {path}")
            continue
        failures.extend(
            _format_and_lint(path, lint_profile=args.lint_profile, apply=apply)
        )

    if failures:
        joined = "\n\n".join(failures)
        sys.stderr.write(f"Formatter/lint baseline failed:\n{joined}\n")
        return 1

    print("Formatter and lint baseline checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
