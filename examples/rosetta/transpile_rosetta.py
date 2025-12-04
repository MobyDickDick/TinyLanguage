"""Convert Python Rosetta samples to TinyLanguage snapshots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = ROOT / "examples" / "rosetta" / "python"
DEFAULT_DEST = ROOT / "examples" / "rosetta" / "expected"


def transpile_all(destination: Path) -> None:
    """Translate every Python sample under ``examples/rosetta/python``."""

    sys.path.insert(0, str(ROOT / "src"))
    from tiny_language_transpilers import PythonTranspiler, TinyLanguageTranspiler

    destination.mkdir(parents=True, exist_ok=True)
    python_transpiler = PythonTranspiler()
    tiny_transpiler = TinyLanguageTranspiler()

    for source_path in sorted(PYTHON_DIR.glob("*.py")):
        program_ir = python_transpiler.from_source(source_path.read_text())
        tiny_source = tiny_transpiler.to_source(program_ir) + "\n"
        dest_path = destination / f"{source_path.stem}.tiny"
        dest_path.write_text(tiny_source)
        rel_dest = dest_path.relative_to(ROOT)
        print(f"wrote {rel_dest}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help="Where to write translated TinyLanguage files (default: expected snapshots).",
    )
    args = parser.parse_args(argv)
    transpile_all(args.dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
