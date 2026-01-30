"""Shared helpers for stdlib module tests.

Standard fixture layout for stdlib tests:
    - Build TinyLanguage source with ``stdlib_program(...)`` so the import,
      optional setup, body, and cleanup are consistently ordered.
    - Execute the program via the ``run_tiny_source`` fixture for in-process
      runs.
    - Keep module-specific logic in the body string to minimize duplication
      across ``tests/detailtests/test_stdlib_*.py`` files.
"""

from __future__ import annotations

import textwrap
from typing import Callable


def stdlib_program(module: str, body: str, *, prelude: str | None = None, epilogue: str | None = None) -> str:
    """Return a TinyLanguage program string for stdlib module tests."""

    segments = [f"import stdlib.{module};"]
    if prelude:
        segments.append(textwrap.dedent(prelude).strip("\n"))
    if body:
        segments.append(textwrap.dedent(body).strip("\n"))
    if epilogue:
        segments.append(textwrap.dedent(epilogue).strip("\n"))
    return "\n".join(segments) + "\n"


def run_stdlib_module(
    run_tiny_source: Callable[[str], str],
    module: str,
    body: str,
    *,
    prelude: str | None = None,
    epilogue: str | None = None,
) -> str:
    """Build and run a stdlib module test program."""

    return run_tiny_source(
        stdlib_program(module, body, prelude=prelude, epilogue=epilogue),
    )
