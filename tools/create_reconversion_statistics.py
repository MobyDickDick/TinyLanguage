from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median


@dataclass
class Record:
    code: str
    source_file: str
    width: int
    height: int
    mae_rgb: float
    rmse_rgb: float
    exact_pixel_ratio: float
    max_iter: int
    plateau_limit: int
    seed: int


def load_records(path: Path) -> list[Record]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows: list[Record] = []
        for row in reader:
            rows.append(
                Record(
                    code=row["code"],
                    source_file=row["source_file"],
                    width=int(row["width"]),
                    height=int(row["height"]),
                    mae_rgb=float(row["mae_rgb"]),
                    rmse_rgb=float(row["rmse_rgb"]),
                    exact_pixel_ratio=float(row["exact_pixel_ratio"]),
                    max_iter=int(row["max_iter"]),
                    plateau_limit=int(row["plateau_limit"]),
                    seed=int(row["seed"]),
                )
            )
    return rows


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = (len(sorted_values) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def group_label(rec: Record) -> str:
    if rec.exact_pixel_ratio >= 0.45:
        return "Sehr gut (>=45% exakte Pixel)"
    if rec.exact_pixel_ratio >= 0.35:
        return "Mittel (35-45% exakte Pixel)"
    return "Schwach (<35% exakte Pixel)"


def build_report(records: list[Record]) -> str:
    count = len(records)
    mae_values = sorted(r.mae_rgb for r in records)
    rmse_values = sorted(r.rmse_rgb for r in records)
    exact_values = sorted(r.exact_pixel_ratio for r in records)

    best_exact = max(records, key=lambda r: r.exact_pixel_ratio)
    worst_exact = min(records, key=lambda r: r.exact_pixel_ratio)
    worst_mae = sorted(records, key=lambda r: r.mae_rgb, reverse=True)[:10]

    buckets = {
        "Sehr gut (>=45% exakte Pixel)": 0,
        "Mittel (35-45% exakte Pixel)": 0,
        "Schwach (<35% exakte Pixel)": 0,
    }
    for rec in records:
        buckets[group_label(rec)] += 1

    optimized = sum(1 for r in records if r.max_iter > 0)

    lines = [
        "# Statistik: Rekonvertierung Bild → SVG",
        "",
        "Datengrundlage: `artifacts/converted_symbols/optimized_roundtrip/best_per_image.csv`.",
        "",
        "## Gesamtüberblick",
        "",
        f"- Ausgewertete Bilder: **{count}**",
        f"- Optimierungs-Läufe genutzt (`max_iter > 0`): **{optimized}/{count}** ({optimized / count:.1%})",
        f"- Durchschnitt MAE (RGB): **{mean(mae_values):.3f}**",
        f"- Median MAE (RGB): **{median(mae_values):.3f}**",
        f"- Durchschnitt RMSE (RGB): **{mean(rmse_values):.3f}**",
        f"- Median RMSE (RGB): **{median(rmse_values):.3f}**",
        f"- Durchschnitt exakter Pixelanteil: **{mean(exact_values):.2%}**",
        f"- Median exakter Pixelanteil: **{median(exact_values):.2%}**",
        "",
        "## Verteilung exakter Pixel",
        "",
        "| Klasse | Anzahl | Anteil |",
        "|---|---:|---:|",
    ]

    for name in ["Sehr gut (>=45% exakte Pixel)", "Mittel (35-45% exakte Pixel)", "Schwach (<35% exakte Pixel)"]:
        n = buckets[name]
        lines.append(f"| {name} | {n} | {n / count:.1%} |")

    lines += [
        "",
        "## Quantile",
        "",
        "| Metrik | P10 | P50 | P90 |",
        "|---|---:|---:|---:|",
        f"| MAE | {percentile(mae_values, 0.10):.3f} | {percentile(mae_values, 0.50):.3f} | {percentile(mae_values, 0.90):.3f} |",
        f"| RMSE | {percentile(rmse_values, 0.10):.3f} | {percentile(rmse_values, 0.50):.3f} | {percentile(rmse_values, 0.90):.3f} |",
        f"| Exakte Pixel | {percentile(exact_values, 0.10):.2%} | {percentile(exact_values, 0.50):.2%} | {percentile(exact_values, 0.90):.2%} |",
        "",
        "## Beste und schwächste Rekonvertierung",
        "",
        f"- Beste Exaktquote: **{best_exact.code}** mit **{best_exact.exact_pixel_ratio:.2%}** exakten Pixeln.",
        f"- Schwächste Exaktquote: **{worst_exact.code}** mit **{worst_exact.exact_pixel_ratio:.2%}** exakten Pixeln.",
        "",
        "## 10 schwierigste Bilder (nach MAE)",
        "",
        "| Code | MAE | RMSE | Exakte Pixel | max_iter |",
        "|---|---:|---:|---:|---:|",
    ]

    for rec in worst_mae:
        lines.append(
            f"| {rec.code} | {rec.mae_rgb:.3f} | {rec.rmse_rgb:.3f} | {rec.exact_pixel_ratio:.2%} | {rec.max_iter} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Erzeugt eine Statistik zur Bild→SVG-Rekonvertierung.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("artifacts/converted_symbols/optimized_roundtrip/best_per_image.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/converted_symbols/optimized_roundtrip/reconversion_statistics.md"),
    )
    args = parser.parse_args()

    records = load_records(args.input)
    if not records:
        raise SystemExit(f"Keine Datensätze in {args.input}")

    report = build_report(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"created report: {args.output} (records={len(records)})")


if __name__ == "__main__":
    main()
