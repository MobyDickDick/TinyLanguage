from __future__ import annotations

import argparse
import csv
import math
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.image_composite_converter import convert_image
from tools.generate_badge_comparison_set import choose_reference_image, rasterize_svg_shapes, read_jpeg_size, save_bmp24


@dataclass
class ParamSet:
    max_iter: int
    plateau_limit: int
    seed: int

    @property
    def name(self) -> str:
        return f"iter{self.max_iter}_plat{self.plateau_limit}_seed{self.seed}"


@dataclass
class ImageMetric:
    code: str
    source_file: str
    width: int
    height: int
    mae: float
    rmse: float
    exact_ratio: float
    max_iter: int
    plateau_limit: int
    seed: int
    svg_path: Path


def read_codes(csv_path: Path) -> list[str]:
    if not csv_path.exists():
        return []

    rows = list(csv.reader(csv_path.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    codes: list[str] = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        code = row[1].strip()
        if code:
            codes.append(code)
    return codes


def discover_codes_from_images(images_dir: Path) -> list[str]:
    codes: set[str] = set()
    for image in list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.JPG")):
        stem = image.stem
        if not stem:
            continue
        code = stem.split("_")[0]
        if code:
            codes.add(code)
    return sorted(codes)


def load_rgb(path: Path) -> list[list[list[int]]]:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ModuleNotFoundError("Pillow is required to load JPEG files.") from exc

    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()
    return [[[int(px[x, y][0]), int(px[x, y][1]), int(px[x, y][2])] for x in range(w)] for y in range(h)]


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
            pixel_exact = True
            for c in range(3):
                d = a[y][x][c] - b[y][x][c]
                if d != 0:
                    pixel_exact = False
                abs_sum += abs(d)
                sq_sum += d * d
            if pixel_exact:
                exact += 1

    mae = abs_sum / count
    rmse = math.sqrt(sq_sum / count)
    exact_ratio = exact / (h * w)
    return mae, rmse, exact_ratio


def save_png(path: Path, rgb: list[list[list[int]]]) -> None:
    try:
        from PIL import Image
    except ModuleNotFoundError:
        return

    h = len(rgb)
    w = len(rgb[0]) if h else 0
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            r, g, b = rgb[y][x]
            px[x, y] = (r, g, b)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def parse_params(param_texts: list[str]) -> list[ParamSet]:
    params: list[ParamSet] = []
    for text in param_texts:
        parts = [p.strip() for p in text.split(":")]
        if len(parts) != 3:
            raise ValueError(f"Invalid --param '{text}', expected max_iter:plateau_limit:seed")
        params.append(ParamSet(max_iter=int(parts[0]), plateau_limit=int(parts[1]), seed=int(parts[2])))
    return params


def choose_best_for_code(
    code: str,
    source: Path,
    source_label: str,
    rgb_source: list[list[list[int]]],
    params: list[ParamSet],
    work_svg_dir: Path,
) -> tuple[ImageMetric, list[ImageMetric]]:
    h = len(rgb_source)
    w = len(rgb_source[0]) if h else 0
    metrics: list[ImageMetric] = []
    for p in params:
        svg_path = work_svg_dir / p.name / f"{code}.svg"
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        convert_image(source, svg_path, max_iter=p.max_iter, plateau_limit=p.plateau_limit, seed=p.seed)
        reconv = rasterize_svg_shapes(svg_path, width=w, height=h)
        mae, rmse, exact = compute_metrics(rgb_source, reconv)
        metrics.append(
            ImageMetric(
                code=code,
                source_file=source_label,
                width=w,
                height=h,
                mae=mae,
                rmse=rmse,
                exact_ratio=exact,
                max_iter=p.max_iter,
                plateau_limit=p.plateau_limit,
                seed=p.seed,
                svg_path=svg_path,
            )
        )

    best = min(metrics, key=lambda m: (m.mae, m.rmse, -m.exact_ratio))
    return best, metrics


def evaluate_template_svg(
    code: str,
    source_label: str,
    rgb_source: list[list[list[int]]],
    template_svg_dir: Path,
) -> ImageMetric | None:
    template_svg = template_svg_dir / f"{code}.svg"
    if not template_svg.exists():
        return None

    h = len(rgb_source)
    w = len(rgb_source[0]) if h else 0
    reconv = rasterize_svg_shapes(template_svg, width=w, height=h)
    mae, rmse, exact = compute_metrics(rgb_source, reconv)
    return ImageMetric(
        code=code,
        source_file=source_label,
        width=w,
        height=h,
        mae=mae,
        rmse=rmse,
        exact_ratio=exact,
        max_iter=0,
        plateau_limit=0,
        seed=0,
        svg_path=template_svg,
    )


def write_csv(path: Path, rows: list[ImageMetric]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "code",
                "source_file",
                "width",
                "height",
                "mae_rgb",
                "rmse_rgb",
                "exact_pixel_ratio",
                "max_iter",
                "plateau_limit",
                "seed",
                "svg_path",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.code,
                    r.source_file,
                    r.width,
                    r.height,
                    f"{r.mae:.6f}",
                    f"{r.rmse:.6f}",
                    f"{r.exact_ratio:.6f}",
                    r.max_iter,
                    r.plateau_limit,
                    r.seed,
                    r.svg_path.as_posix(),
                ]
            )


def write_report(path: Path, best_rows: list[ImageMetric], all_rows: list[ImageMetric], param_sets: list[ParamSet]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not best_rows:
        path.write_text("# JPEG→SVG Roundtrip Optimization\n\nNo rows generated.\n", encoding="utf-8")
        return

    avg_mae = sum(r.mae for r in best_rows) / len(best_rows)
    avg_rmse = sum(r.rmse for r in best_rows) / len(best_rows)
    avg_exact = sum(r.exact_ratio for r in best_rows) / len(best_rows)

    per_param: dict[str, list[ImageMetric]] = {p.name: [] for p in param_sets}
    per_param["template_svg"] = []
    for r in all_rows:
        key = f"iter{r.max_iter}_plat{r.plateau_limit}_seed{r.seed}"
        if key in per_param:
            per_param[key].append(r)
        elif r.max_iter == 0 and r.plateau_limit == 0 and r.seed == 0:
            per_param["template_svg"].append(r)

    param_summary: list[tuple[str, float, float, float]] = []
    report_param_order = [p.name for p in param_sets]
    if per_param["template_svg"]:
        report_param_order.append("template_svg")

    for name in report_param_order:
        rows = per_param[name]
        if not rows:
            continue
        mae = sum(r.mae for r in rows) / len(rows)
        rmse = sum(r.rmse for r in rows) / len(rows)
        exact = sum(r.exact_ratio for r in rows) / len(rows)
        param_summary.append((name, mae, rmse, exact))
    param_summary.sort(key=lambda t: (t[1], t[2], -t[3]))

    worst = sorted(best_rows, key=lambda r: r.mae, reverse=True)[:10]

    lines = [
        "# JPEG→SVG→Raster Roundtrip Optimization",
        "",
        f"- Images evaluated: **{len(best_rows)}**",
        f"- Parameter sets evaluated: **{len(param_sets)}**",
        f"- Best-per-image average MAE: **{avg_mae:.3f}**",
        f"- Best-per-image average RMSE: **{avg_rmse:.3f}**",
        f"- Best-per-image average exact pixel ratio: **{avg_exact:.2%}**",
        "",
        "## Parameter-set aggregate ranking",
        "",
        "| Param set | Avg MAE | Avg RMSE | Avg exact pixels |",
        "|---|---:|---:|---:|",
    ]
    for name, mae, rmse, exact in param_summary:
        lines.append(f"| {name} | {mae:.3f} | {rmse:.3f} | {exact:.2%} |")

    lines.extend(
        [
            "",
            "## Worst 10 images after optimization",
            "",
            "| Code | Source | MAE | RMSE | Exact pixels | Chosen params |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for r in worst:
        lines.append(
            f"| {r.code} | {r.source_file} | {r.mae:.3f} | {r.rmse:.3f} | {r.exact_ratio:.2%} | "
            f"iter={r.max_iter}, plateau={r.plateau_limit}, seed={r.seed} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Iteratively optimize JPEG->SVG roundtrip quality for selected symbols")
    p.add_argument("--csv", type=Path, default=Path("artifacts/images_to_convert/nonexistant.csv"))
    p.add_argument("--images-dir", type=Path, default=Path("artifacts/images_to_convert"))
    p.add_argument("--output-dir", type=Path, default=Path("artifacts/converted_symbols/optimized_roundtrip"))
    p.add_argument(
        "--template-svg-dir",
        type=Path,
        default=Path("artifacts/converted_symbols/svg"),
        help="Directory with existing SVG templates (code.svg) to be considered as baseline candidates.",
    )
    p.add_argument(
        "--param",
        action="append",
        default=[],
        help="Parameter set max_iter:plateau_limit:seed (repeatable)",
    )
    p.add_argument("--limit", type=int, default=0, help="Optional limit of codes from CSV (0 = all)")
    args = p.parse_args()

    if not args.param:
        args.param = ["120:36:42", "240:72:42", "360:108:42", "240:72:1337", "480:144:42"]

    param_sets = parse_params(args.param)
    codes = read_codes(args.csv)
    if not codes:
        codes = discover_codes_from_images(args.images_dir)
        print(
            f"warning: no usable CSV entries found in {args.csv}; "
            f"falling back to {len(codes)} code(s) discovered in {args.images_dir}"
        )
    if args.limit > 0:
        codes = codes[: args.limit]

    out_dir: Path = args.output_dir
    work_svg = out_dir / "all_candidates"
    best_svg = out_dir / "best_svg"
    reconv_png = out_dir / "best_reconverted_png"

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    best_rows: list[ImageMetric] = []
    all_rows: list[ImageMetric] = []

    jpg_mode = True
    try:
        import PIL  # noqa: F401
    except ModuleNotFoundError:
        jpg_mode = False
        print("warning: Pillow not available; using SVG proxy raster inputs instead of direct JPEG decoding")

    with tempfile.TemporaryDirectory(prefix="roundtrip_proxy_") as proxy_tmp:
        proxy_bmp_dir = Path(proxy_tmp)
        for idx, code in enumerate(codes, start=1):
            src = choose_reference_image(code, args.images_dir)

            if jpg_mode:
                source_for_conversion = src
                source_label = src.name
                rgb = load_rgb(src)
            else:
                w, h = read_jpeg_size(src)
                base_svg = Path("artifacts/converted_symbols/svg") / f"{code}.svg"
                if not base_svg.exists():
                    print(f"skip {code}: missing proxy svg {base_svg}")
                    continue
                rgb = rasterize_svg_shapes(base_svg, width=w, height=h)
                source_for_conversion = proxy_bmp_dir / f"{code}.bmp"
                save_bmp24(source_for_conversion, rgb)
                source_label = src.name

            best, rows = choose_best_for_code(code, source_for_conversion, source_label, rgb, param_sets, work_svg)
            template_result = evaluate_template_svg(code, source_label, rgb, args.template_svg_dir)
            if template_result is not None:
                rows.append(template_result)
                if (template_result.mae, template_result.rmse, -template_result.exact_ratio) < (
                    best.mae,
                    best.rmse,
                    -best.exact_ratio,
                ):
                    best = template_result

            all_rows.extend(rows)
            best_rows.append(best)

            final_svg = best_svg / f"{code}_reconverted.svg"
            final_svg.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best.svg_path, final_svg)

            reconv_rgb = rasterize_svg_shapes(final_svg, width=best.width, height=best.height)
            save_png(reconv_png / f"{code}_reconverted.png", reconv_rgb)

            print(
                f"[{idx}/{len(codes)}] {code}: mae={best.mae:.3f} rmse={best.rmse:.3f} "
                f"exact={best.exact_ratio:.2%} params=({best.max_iter},{best.plateau_limit},{best.seed}) "
                f"source={best.svg_path.name}"
            )

    write_csv(out_dir / "best_per_image.csv", best_rows)
    write_csv(out_dir / "all_results.csv", all_rows)
    write_report(out_dir / "optimization_report.md", best_rows, all_rows, param_sets)

    print(f"done images={len(best_rows)} params={len(param_sets)} out={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
