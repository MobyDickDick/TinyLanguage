#!/usr/bin/env python3
"""Rank converted symbol quality by per-pixel squared RGB deltas."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import cv2

from src.image_composite_converter import Action


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--images", default="artifacts/images_to_convert")
    p.add_argument("--svg", default="artifacts/converted_symbols/svg")
    p.add_argument("--out", default="artifacts/converted_symbols/reports/pixel_delta2_ranking_manual.csv")
    p.add_argument("--threshold", type=float, default=18.0)
    p.add_argument("--top", type=int, default=20)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    images_dir = Path(args.images)
    svg_dir = Path(args.svg)

    rows: list[dict[str, float | str]] = []
    for svg_path in sorted(svg_dir.glob("*.svg")):
        stem = svg_path.stem
        src = None
        for ext in (".jpg", ".png", ".bmp"):
            cand = images_dir / f"{stem}{ext}"
            if cand.exists():
                src = cand
                break
        if src is None:
            continue

        img = cv2.imread(str(src))
        if img is None:
            continue

        svg_content = svg_path.read_text(encoding="utf-8")
        h, w = img.shape[:2]
        rendered = Action.render_svg_to_numpy(svg_content, w, h)
        if rendered is None:
            continue

        mean_delta2, std_delta2 = Action.calculate_delta2_stats(img, rendered)
        rows.append({"image": src.name, "mean_delta2": mean_delta2, "std_delta2": std_delta2})

    rows.sort(key=lambda r: float(r["mean_delta2"]), reverse=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["image", "mean_delta2", "std_delta2"])
        for row in rows:
            writer.writerow([row["image"], f"{float(row['mean_delta2']):.6f}", f"{float(row['std_delta2']):.6f}"])

    ok_count = sum(1 for r in rows if float(r["mean_delta2"]) <= args.threshold)
    print(f"images_total={len(rows)}")
    print(f"threshold_mean_delta2={args.threshold:.3f}")
    print(f"images_with_mean_delta2_le_threshold={ok_count}")
    print("top_worst:")
    for row in rows[: max(0, args.top)]:
        print(f"  {row['image']}: mean_delta2={float(row['mean_delta2']):.3f}, std_delta2={float(row['std_delta2']):.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
