"""Copy missing Rosetta Code Python scripts into a target directory."""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "examples" / "rosetta" / "python"


def list_missing(source_dir: Path, dest_dir: Path) -> list[Path]:
    """Return Python files present in ``source_dir`` but absent in ``dest_dir``.

    Files are compared by stem (filename without extension) so duplicates with
    other extensions are ignored when computing missing entries.
    """

    source_files = [path for path in source_dir.glob("*.py") if path.is_file()]
    dest_stems = {path.stem for path in dest_dir.glob("*.py")}
    return [path for path in sorted(source_files) if path.stem not in dest_stems]


def copy_batch(files: list[Path], dest_dir: Path, limit: int, delay: float) -> list[Path]:
    """Copy up to ``limit`` files into ``dest_dir`` with ``delay`` seconds between."""

    to_copy = files[:limit]
    for index, source_path in enumerate(to_copy):
        destination = dest_dir / source_path.name
        shutil.copy2(source_path, destination)
        print(f"copied {source_path.name} -> {destination}")
        if index + 1 < len(to_copy):
            time.sleep(delay)
    return to_copy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dest",
        type=Path,
        help="Directory where Rosetta Code Python scripts should be copied.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Location of the Rosetta Code Python scripts (default: examples/rosetta/python).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of missing files to copy (default: 10).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=10.0,
        help="Seconds to wait between copy operations (default: 10).",
    )
    args = parser.parse_args(argv)

    if not args.source.exists():
        parser.error(f"source directory does not exist: {args.source}")

    args.dest.mkdir(parents=True, exist_ok=True)
    missing = list_missing(args.source, args.dest)

    if not missing:
        print("No missing Python scripts detected; nothing to copy.")
        return 0

    copied = copy_batch(missing, args.dest, args.limit, args.delay)
    remaining = len(missing) - len(copied)
    print(f"Copied {len(copied)} file(s); {remaining} still missing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
