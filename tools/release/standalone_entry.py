"""Frozen interpreter entry point; data layout is defined in tinylanguage.spec."""

from tiny_language_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
