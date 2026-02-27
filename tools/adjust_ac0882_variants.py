#!/usr/bin/env python3
"""Shrink AC0882 variant glyphs and generate an image-vs-svg comparison board."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TRANSFORM_RE = re.compile(
    r'translate\(([-0-9.]+),([-0-9.]+)\)\s*scale\(([-0-9.]+),([-0-9.]+)\)\s*translate\((-?\d+),(-?\d+)\)'
)
CIRCLE_RE = re.compile(r'<circle[^>]*cx="([0-9.]+)"[^>]*cy="([0-9.]+)"[^>]*>')


def adjust_svg(svg_path: Path, shrink_factor: float) -> tuple[float, float, float]:
    text = svg_path.read_text(encoding="utf-8")

    circle_match = CIRCLE_RE.search(text)
    if not circle_match:
        raise ValueError(f"Could not find circle center in {svg_path}")
    cx = float(circle_match.group(1))
    cy = float(circle_match.group(2))

    transform_match = TRANSFORM_RE.search(text)
    if not transform_match:
        raise ValueError(f"Could not find path transform in {svg_path}")

    old_scale = float(transform_match.group(3))
    scale = old_scale * shrink_factor

    # glyph bbox from path data + translate(-381,-1493)
    glyph_w = 1636 - 381
    glyph_h = 1493 - 0
    tx = cx - (glyph_w / 2) * scale
    ty = cy - (glyph_h / 2) * scale

    new_transform = (
        f'translate({tx:.4f},{ty:.4f}) scale({scale:.6f},{-scale:.6f}) '
        'translate(-381,-1493)'
    )

    new_text = (
        text[: transform_match.start()]
        + new_transform
        + text[transform_match.end() :]
    )
    svg_path.write_text(new_text, encoding="utf-8")
    return old_scale, scale, tx


def write_comparison_html(out_path: Path, variants: list[str]) -> None:
    rows = []
    for code in variants:
        rows.append(
            f"""
            <div class='card'>
              <h3>{code}</h3>
              <div class='pair'>
                <figure><figcaption>Original JPG</figcaption><img src='../images_to_convert/{code}.jpg' /></figure>
                <figure><figcaption>Konvertiertes SVG</figcaption><img src='{code}.svg' /></figure>
              </div>
            </div>
            """
        )

    html = f"""<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<title>AC0882 Varianten Vergleich</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #f7f7f7; }}
.card {{ background: white; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
.pair {{ display: flex; gap: 20px; align-items: flex-start; }}
figure {{ margin: 0; }}
figcaption {{ font-size: 13px; margin-bottom: 6px; color: #444; }}
img {{ border: 1px solid #ddd; background: #fff; max-width: 320px; image-rendering: auto; }}
</style>
</head>
<body>
<h1>AC0882_L / _M / _S – Original vs. SVG</h1>
{''.join(rows)}
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("artifacts/converted_symbols"),
        help="Directory containing AC0882 variants.",
    )
    parser.add_argument(
        "--factor",
        type=float,
        default=0.82,
        help="Scale multiplier applied to the glyph path.",
    )
    args = parser.parse_args()

    variants = ["AC0882_L", "AC0882_M", "AC0882_S"]
    for code in variants:
        svg = args.dir / f"{code}.svg"
        old_scale, new_scale, tx = adjust_svg(svg, args.factor)
        print(f"{svg}: scale {old_scale:.6f} -> {new_scale:.6f}, tx={tx:.4f}")

    compare_html = args.dir / "AC0882_variant_comparison.html"
    write_comparison_html(compare_html, variants)
    print(f"Wrote comparison board: {compare_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
