"""Compare two Tiny source files by normalized Tiny program structure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tiny_program_repository_db_adapter import TinyProgramRepositoryDB


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Vergleicht zwei Tiny-Source-Dateien und prüft, ob sie dasselbe "
            "Tiny-Programm darstellen."
        )
    )
    parser.add_argument("source_a", type=Path, help="Pfad zur ersten Tiny-Datei")
    parser.add_argument("source_b", type=Path, help="Pfad zur zweiten Tiny-Datei")
    args = parser.parse_args()

    source_a = args.source_a.read_text(encoding="utf-8")
    source_b = args.source_b.read_text(encoding="utf-8")

    equivalent = TinyProgramRepositoryDB.are_sources_equivalent(source_a, source_b)
    if equivalent:
        print("EQUIVALENT")
        return 0

    print("DIFFERENT")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
