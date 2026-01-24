"""Copy missing Rosetta Code Python scripts into a target directory.

The script was designed for quick local syncs while experimenting with the
Rosetta Code transpiler. It supports optional filtering, dry-run mode, and an
opt-in transpile step so workflows remain reproducible in CI.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

# Resolve repository paths once so every function can reference a single root.
ROOT = Path(__file__).resolve().parents[2]
# Default location of the upstream Rosetta Code Python samples.
DEFAULT_SOURCE = ROOT / "examples" / "rosetta" / "python"
# Default destination for transpiled TinyLanguage outputs.
DEFAULT_TINY_DEST = ROOT / "examples" / "rosetta" / "expected"


def list_missing(source_dir: Path, dest_dir: Path) -> list[Path]:
    """Return Python files present in ``source_dir`` but absent in ``dest_dir``.

    Files are compared by stem (filename without extension) so duplicates with
    other extensions are ignored when computing missing entries.
    """

    # Gather only regular Python source files.
    source_files = [path for path in source_dir.glob("*.py") if path.is_file()]
    # Compare by stem so we ignore different file extensions with the same base name.
    dest_stems = {path.stem for path in dest_dir.glob("*.py")}
    # Return the sorted list to keep output deterministic.
    return [path for path in sorted(source_files) if path.stem not in dest_stems]


def filter_missing(files: list[Path], includes: list[str] | None) -> list[Path]:
    """Keep only files whose stems match one of the ``includes`` filters."""

    if not includes:
        return files

    # Normalize filters by trimming whitespace and dropping empty strings.
    normalized = [pattern.strip() for pattern in includes if pattern.strip()]
    if not normalized:
        return files

    def _matches(path: Path) -> bool:
        """Check whether a file stem starts with any requested prefix."""
        return any(path.stem.startswith(pattern) for pattern in normalized)

    return [path for path in files if _matches(path)]


def copy_batch(
    files: list[Path], dest_dir: Path, limit: int, delay: float, *, dry_run: bool = False
) -> list[Path]:
    """Copy up to ``limit`` files into ``dest_dir`` with ``delay`` seconds between."""

    # Limit the copy set to avoid overwhelming large sample directories.
    to_copy = files[:limit]
    for index, source_path in enumerate(to_copy):
        # Build the destination filename next to the provided destination dir.
        destination = dest_dir / source_path.name
        if dry_run:
            print(f"[dry-run] would copy {source_path.name} -> {destination}")
        else:
            # Preserve timestamps/metadata to keep traceability to the source file.
            shutil.copy2(source_path, destination)
            print(f"copied {source_path.name} -> {destination}")
        if index + 1 < len(to_copy) and not dry_run:
            # Pause between copies to keep filesystem load predictable.
            time.sleep(delay)
    return to_copy


def run_transpiler(dest: Path, *, source_dir: Path) -> None:
    """Invoke the Rosetta transpiler with the provided destination."""

    # Add the repo src directory so the transpiler can be imported.
    sys.path.insert(0, str(ROOT / "src"))
    from transpile_rosetta import transpile_all

    # Transpile all Rosetta Python samples into TinyLanguage.
    transpile_all(dest, source_dir=source_dir)


def main(argv: list[str] | None = None) -> int:
    # Parse CLI arguments for copy and transpile operations.
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
        "--include",
        action="append",
        help="Optional stem prefixes to copy (can be passed multiple times).",
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the files that would be copied without writing to disk.",
    )
    parser.add_argument(
        "--transpile",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Transpile the Rosetta Python samples after copying them.",
    )
    parser.add_argument(
        "--transpile-dest",
        type=Path,
        default=DEFAULT_TINY_DEST,
        help="Where TinyLanguage outputs should be written when --transpile is set.",
    )
    args = parser.parse_args(argv)

    # Validate that the input directory exists before scanning.
    if not args.source.exists():
        parser.error(f"source directory does not exist: {args.source}")

    # Identify missing scripts and apply optional include filters.
    missing = filter_missing(list_missing(args.source, args.dest), args.include)

    if not missing:
        print("No missing Python scripts detected; nothing to copy.")
        return 0

    # Ensure the destination directory exists unless running a dry-run.
    if not args.dry_run:
        args.dest.mkdir(parents=True, exist_ok=True)

    # Copy files and report how many remain missing.
    copied = copy_batch(missing, args.dest, args.limit, args.delay, dry_run=args.dry_run)
    remaining = len(missing) - len(copied)
    summary_prefix = "Planned to copy" if args.dry_run else "Copied"
    print(f"{summary_prefix} {len(copied)} file(s); {remaining} still missing.")

    # Optionally transpile the copied samples into TinyLanguage.
    if args.transpile and not args.dry_run:
        run_transpiler(args.transpile_dest, source_dir=args.source)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
