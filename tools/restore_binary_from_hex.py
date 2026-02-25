#!/usr/bin/env python3
"""Restore binary files from .hex.txt dumps.

Expected input format (as produced by tools/extract_converted_from_bundle.py):
  # source: <original_filename>
  # bytes: <N>
  <hex bytes separated by spaces>

The script also accepts plain hex-only files without headers.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _parse_hex_dump(path: Path) -> tuple[bytes, str | None, int | None]:
    source_name: str | None = None
    expected_size: int | None = None
    hex_tokens: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            lower = line.lower()
            if lower.startswith("# source:"):
                source_name = line.split(":", 1)[1].strip() or None
            elif lower.startswith("# bytes:"):
                value = line.split(":", 1)[1].strip()
                expected_size = int(value) if value else None
            continue

        hex_tokens.extend(line.split())

    data = bytes.fromhex("".join(hex_tokens))

    if expected_size is not None and len(data) != expected_size:
        raise ValueError(
            f"Byte length mismatch for {path}: expected {expected_size}, got {len(data)}"
        )

    return data, source_name, expected_size


def _default_output_name(input_path: Path, source_name: str | None) -> str:
    if source_name:
        return source_name
    name = input_path.name
    if name.endswith(".hex.txt"):
        return name[: -len(".hex.txt")]
    return f"{name}.bin"


def restore_file(input_path: Path, out_dir: Path | None, overwrite: bool) -> Path:
    data, source_name, _ = _parse_hex_dump(input_path)
    output_name = _default_output_name(input_path, source_name)
    target_dir = out_dir if out_dir is not None else input_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / output_name

    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Target already exists: {output_path}")

    output_path.write_bytes(data)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "hex_files",
        nargs="+",
        help="Input .hex.txt files (or shell-expanded patterns)",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Optional output directory (default: beside each input file)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite target files if they already exist",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir) if args.out_dir else None

    restored = 0
    for file_name in args.hex_files:
        input_path = Path(file_name)
        output_path = restore_file(input_path, out_dir, args.overwrite)
        restored += 1
        print(f"{input_path.as_posix()} -> {output_path.as_posix()}")

    print(f"Restored files: {restored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
