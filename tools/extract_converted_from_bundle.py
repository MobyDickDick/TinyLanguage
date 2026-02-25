#!/usr/bin/env python3
"""Extract converted files for references from a bundle zip.

By default, binary files are written as hex text files so repositories can avoid
committing binary blobs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile


def _bytes_to_hex_lines(data: bytes, width: int = 16) -> str:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        lines.append(" ".join(f"{b:02x}" for b in chunk))
    return "\n".join(lines) + ("\n" if lines else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refs", nargs="+", help="Reference IDs like AC0870 AR0102")
    parser.add_argument(
        "--bundle",
        default="artifacts/converted_symbols/wurzelformen_svgs_semantic_v1_with_script.zip",
        help="Path to bundle ZIP",
    )
    parser.add_argument(
        "--out",
        default="artifacts/converted_symbols",
        help="Output directory",
    )
    parser.add_argument(
        "--binary-as-hex",
        action="store_true",
        default=True,
        help="Write binary members as .hex.txt files (default: true)",
    )
    parser.add_argument(
        "--keep-binary",
        action="store_true",
        help="Keep binary members as their original file format",
    )
    args = parser.parse_args()

    refs = [r.upper() for r in args.refs]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with ZipFile(args.bundle) as zf:
        names = zf.namelist()
        extracted = 0
        for ref in refs:
            matched = [
                n
                for n in names
                if n in (f"svgs/{ref}.svg", f"previews/{ref}.jpg", f"diffs/{ref}_diff.jpg")
            ]
            print(f"{ref}:")
            if not matched:
                print("  (keine Treffer im Bundle)")
                continue

            for member in matched:
                source_name = Path(member).name
                data = zf.read(member)
                is_binary = source_name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))

                if is_binary and not args.keep_binary and args.binary_as_hex:
                    target_path = out_dir / f"{source_name}.hex.txt"
                    hex_text = (
                        f"# source: {source_name}\n"
                        f"# bytes: {len(data)}\n"
                        + _bytes_to_hex_lines(data)
                    )
                    target_path.write_text(hex_text, encoding="utf-8")
                else:
                    target_path = out_dir / source_name
                    target_path.write_bytes(data)
                extracted += 1
                print(f"  - {target_path.as_posix()}")

    print(f"\nExtrahiert: {extracted} Dateien")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
