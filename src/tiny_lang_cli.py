"""Small wrapper that exposes the TinyLanguage CLI as ``python -m tiny_lang_cli``.

The implementation simply forwards to :mod:`tiny_language_cli` so both
``python -m tiny_language_cli`` and ``python -m tiny_lang_cli`` work with the
same options.
"""
from __future__ import annotations

from tiny_language_cli import main


def run(argv: list[str] | None = None) -> int:
    return main(argv)


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    raise SystemExit(run())
