from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.generate_badge_comparison_set import rasterize_svg_shapes


@dataclass
class Metric:
    code: str
    width: int
    height: int
    mae: float
    rmse: float
    exact_ratio: float


def compute_metrics(a: list[list[list[int]]], b: list[list[list[int]]]) -> tuple[float, float, float]:
    h = len(a)
    w = len(a[0]) if h else 0
    count = h * w * 3
    if count == 0:
        return 0.0, 0.0, 1.0

    abs_sum = 0.0
    sq_sum = 0.0
    exact = 0
    for y in range(h):
        for x in range(w):
            px_eq = True
            for c in range(3):
                d = a[y][x][c] - b[y][x][c]
                if d != 0:
                    px_eq = False
                abs_sum += abs(d)
                sq_sum += d * d
            if px_eq:
                exact += 1

    mae = abs_sum / count
    rmse = (sq_sum / count) ** 0.5
    exact_ratio = exact / (h * w)
    return mae, rmse, exact_ratio


def evaluate(svg_dir: Path) -> list[Metric]:
    metrics: list[Metric] = []
    originals = sorted(p for p in svg_dir.glob('*.svg') if not p.stem.endswith('_reconverted'))
    for original in originals:
        code = original.stem
        reconverted = svg_dir / f'{code}_reconverted.svg'
        if not reconverted.exists():
            continue

        base_img = rasterize_svg_shapes(original, width=64, height=64)
        h = len(base_img)
        w = len(base_img[0]) if h else 0
        reconv_img = rasterize_svg_shapes(reconverted, width=w, height=h)
        mae, rmse, exact = compute_metrics(base_img, reconv_img)
        metrics.append(Metric(code=code, width=w, height=h, mae=mae, rmse=rmse, exact_ratio=exact))

    return metrics


def write_csv(path: Path, metrics: list[Metric]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['code', 'width', 'height', 'mae_rgb', 'rmse_rgb', 'exact_pixel_ratio'])
        for m in metrics:
            writer.writerow([m.code, m.width, m.height, f'{m.mae:.6f}', f'{m.rmse:.6f}', f'{m.exact_ratio:.6f}'])


def write_markdown(path: Path, metrics: list[Metric]) -> None:
    if not metrics:
        text = '# Rekonvertierungs-Qualität\n\nKeine SVG-Paare gefunden.\n'
        path.write_text(text, encoding='utf-8')
        return

    avg_mae = sum(m.mae for m in metrics) / len(metrics)
    avg_rmse = sum(m.rmse for m in metrics) / len(metrics)
    avg_exact = sum(m.exact_ratio for m in metrics) / len(metrics)
    worst = sorted(metrics, key=lambda m: m.mae, reverse=True)[:5]

    lines = [
        '# Rekonvertierungs-Qualität (SVG → Raster → SVG)',
        '',
        'Hinweis: In dieser Umgebung fehlten JPEG-Bibliotheken/Tools, daher wurde die bestehende SVG-Rückkonvertierung bewertet.',
        '',
        f'- Ausgewertete Symbole: **{len(metrics)}**',
        f'- Durchschnitt MAE (RGB 0..255): **{avg_mae:.3f}**',
        f'- Durchschnitt RMSE (RGB 0..255): **{avg_rmse:.3f}**',
        f'- Durchschnitt exakter Pixelanteil: **{avg_exact:.2%}**',
        '',
        '## Schlechteste 5 nach MAE',
        '',
        '| Code | MAE | RMSE | Exakte Pixel |',
        '|---|---:|---:|---:|',
    ]
    for m in worst:
        lines.append(f'| {m.code} | {m.mae:.3f} | {m.rmse:.3f} | {m.exact_ratio:.2%} |')

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    p = argparse.ArgumentParser(description='Evaluate quality between original and *_reconverted SVG files.')
    p.add_argument('--svg-dir', type=Path, default=Path('artifacts/converted_symbols/svg'))
    p.add_argument('--csv', type=Path, default=Path('artifacts/converted_symbols/roundtrip_quality.csv'))
    p.add_argument('--report', type=Path, default=Path('artifacts/converted_symbols/roundtrip_quality_report.md'))
    args = p.parse_args()

    metrics = evaluate(args.svg_dir)
    write_csv(args.csv, metrics)
    write_markdown(args.report, metrics)
    print(f'evaluated={len(metrics)} csv={args.csv} report={args.report}')


if __name__ == '__main__':
    main()
