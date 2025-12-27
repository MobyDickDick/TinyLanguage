"""Wrapper to expose the TinyLanguage compiler CLI as ``python -m tinyc_cli``."""
from __future__ import annotations

from tiny_language_compiler_cli import main


def run(argv: list[str] | None = None) -> int:
    return main(argv)


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    raise SystemExit(run())
