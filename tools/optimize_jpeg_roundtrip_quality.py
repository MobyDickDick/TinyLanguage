from __future__ import annotations

import argparse
import csv
import math
import random
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
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


@dataclass
class VariationResult:
    code: str
    source_file: str
    trial: int
    mae: float
    rmse: float
    exact_ratio: float
    improved: bool
    plateau_run: int


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
    per_param_trials: int,
    per_param_seed_step: int,
) -> tuple[ImageMetric, list[ImageMetric]]:
    h = len(rgb_source)
    w = len(rgb_source[0]) if h else 0
    metrics: list[ImageMetric] = []
    for p in params:
        for trial in range(per_param_trials):
            trial_seed = p.seed + trial * per_param_seed_step
            svg_path = work_svg_dir / p.name / f"{code}_trial{trial + 1:03d}_seed{trial_seed}.svg"
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            convert_image(source, svg_path, max_iter=p.max_iter, plateau_limit=p.plateau_limit, seed=trial_seed)
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
                    seed=trial_seed,
                    svg_path=svg_path,
                )
            )

    best = min(metrics, key=lambda m: (m.mae, m.rmse, -m.exact_ratio))
    return best, metrics


def clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def jitter_hex_color(hex_color: str, rng: random.Random, delta: int = 16) -> str:
    if not hex_color.startswith("#") or len(hex_color) != 7:
        return hex_color
    r = clamp_channel(int(hex_color[1:3], 16) + rng.randint(-delta, delta))
    g = clamp_channel(int(hex_color[3:5], 16) + rng.randint(-delta, delta))
    b = clamp_channel(int(hex_color[5:7], 16) + rng.randint(-delta, delta))
    return f"#{r:02x}{g:02x}{b:02x}"


def mutate_svg_tree(root: ET.Element, width: int, height: int, rng: random.Random, sigma: float) -> ET.Element:
    mutated = ET.fromstring(ET.tostring(root, encoding="unicode"))
    for node in mutated:
        tag = node.tag.rsplit("}", 1)[-1]

        if "stroke-width" in node.attrib:
            stroke = float(node.attrib["stroke-width"] or 0.0)
            node.attrib["stroke-width"] = f"{max(0.2, stroke + rng.gauss(0, sigma * 0.5)):.2f}"

        for key in ("fill", "stroke"):
            if key in node.attrib:
                node.attrib[key] = jitter_hex_color(node.attrib[key], rng)

        if tag == "rect":
            x = float(node.attrib.get("x", "0") or 0.0) + rng.gauss(0, sigma)
            y = float(node.attrib.get("y", "0") or 0.0) + rng.gauss(0, sigma)
            w = max(0.8, float(node.attrib.get("width", "0") or 0.0) + rng.gauss(0, sigma))
            h = max(0.8, float(node.attrib.get("height", "0") or 0.0) + rng.gauss(0, sigma))
            x = max(0.0, min(width - w, x))
            y = max(0.0, min(height - h, y))
            node.attrib["x"] = f"{x:.2f}"
            node.attrib["y"] = f"{y:.2f}"
            node.attrib["width"] = f"{w:.2f}"
            node.attrib["height"] = f"{h:.2f}"
        elif tag in {"circle", "ellipse"}:
            cx = float(node.attrib.get("cx", "0") or 0.0) + rng.gauss(0, sigma)
            cy = float(node.attrib.get("cy", "0") or 0.0) + rng.gauss(0, sigma)
            cx = max(0.0, min(float(width), cx))
            cy = max(0.0, min(float(height), cy))
            node.attrib["cx"] = f"{cx:.2f}"
            node.attrib["cy"] = f"{cy:.2f}"
            if tag == "circle":
                r = max(0.6, float(node.attrib.get("r", "0") or 0.0) + rng.gauss(0, sigma))
                node.attrib["r"] = f"{r:.2f}"
            else:
                rx = max(0.6, float(node.attrib.get("rx", "0") or 0.0) + rng.gauss(0, sigma))
                ry = max(0.6, float(node.attrib.get("ry", "0") or 0.0) + rng.gauss(0, sigma))
                node.attrib["rx"] = f"{rx:.2f}"
                node.attrib["ry"] = f"{ry:.2f}"
    return mutated


def stochastic_refine_svg(
    code: str,
    source_label: str,
    rgb_source: list[list[list[int]]],
    base_metric: ImageMetric,
    output_svg_dir: Path,
    variation_trials: int,
    variation_sigma: float,
    variation_seed: int,
    save_all_variations: bool,
    sigma_decay: float,
    min_sigma: float,
) -> tuple[ImageMetric, list[VariationResult]]:
    if variation_trials <= 0:
        return base_metric, []

    h = len(rgb_source)
    w = len(rgb_source[0]) if h else 0
    rng = random.Random(variation_seed)

    best_metric = base_metric
    current_tree = ET.fromstring(base_metric.svg_path.read_text(encoding="utf-8"))
    plateau_run = 0
    trace: list[VariationResult] = []
    sigma = max(min_sigma, variation_sigma)
    local_plateau_limit = max(4, variation_trials // 4)

    with tempfile.TemporaryDirectory(prefix="svg_variation_") as temp_dir:
        temp_dir_path = Path(temp_dir)
        for trial in range(1, variation_trials + 1):
            candidate_tree = mutate_svg_tree(current_tree, width=w, height=h, rng=rng, sigma=sigma)
            candidate_path = temp_dir_path / f"{code}_trial{trial:04d}.svg"
            candidate_path.write_text(ET.tostring(candidate_tree, encoding="unicode"), encoding="utf-8")

            reconv = rasterize_svg_shapes(candidate_path, width=w, height=h)
            mae, rmse, exact = compute_metrics(rgb_source, reconv)
            improved = (mae, rmse, -exact) < (best_metric.mae, best_metric.rmse, -best_metric.exact_ratio)
            if improved:
                if save_all_variations:
                    persisted_path = output_svg_dir / f"{code}_trial{trial:04d}.svg"
                else:
                    persisted_path = output_svg_dir / f"{code}_best_variation.svg"
                persisted_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate_path, persisted_path)
                best_metric = ImageMetric(
                    code=code,
                    source_file=source_label,
                    width=w,
                    height=h,
                    mae=mae,
                    rmse=rmse,
                    exact_ratio=exact,
                    max_iter=base_metric.max_iter,
                    plateau_limit=base_metric.plateau_limit,
                    seed=base_metric.seed,
                    svg_path=persisted_path,
                )
                current_tree = candidate_tree
                plateau_run = 0
            else:
                plateau_run += 1

            if plateau_run >= local_plateau_limit and sigma > min_sigma:
                sigma = max(min_sigma, sigma * sigma_decay)
                plateau_run = 0

            if save_all_variations and not improved:
                persisted_path = output_svg_dir / f"{code}_trial{trial:04d}.svg"
                persisted_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate_path, persisted_path)

            trace.append(
                VariationResult(
                    code=code,
                    source_file=source_label,
                    trial=trial,
                    mae=mae,
                    rmse=rmse,
                    exact_ratio=exact,
                    improved=improved,
                    plateau_run=plateau_run,
                )
            )

    return best_metric, trace


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


def write_variation_csv(path: Path, rows: list[VariationResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "source_file", "trial", "mae_rgb", "rmse_rgb", "exact_pixel_ratio", "improved", "plateau_run"])
        for r in rows:
            w.writerow([r.code, r.source_file, r.trial, f"{r.mae:.6f}", f"{r.rmse:.6f}", f"{r.exact_ratio:.6f}", int(r.improved), r.plateau_run])


def append_plateau_report(path: Path, traces: list[VariationResult], variation_trials: int) -> None:
    if not traces or variation_trials <= 0:
        return
    by_code: dict[str, list[VariationResult]] = {}
    for row in traces:
        by_code.setdefault(row.code, []).append(row)

    plateau_edges: list[int] = []
    lines = ["", "## Stochastic variation search (Rekonstruktion)", "", "| Code | Last improvement trial | Plateau edge trial | Best trial MAE |", "|---|---:|---:|---:|"]
    for code, rows in sorted(by_code.items()):
        ordered = sorted(rows, key=lambda r: r.trial)
        improving_trials = [r.trial for r in ordered if r.improved]
        last_improvement = max(improving_trials) if improving_trials else 0
        plateau_edge = min(variation_trials, last_improvement + max(3, variation_trials // 10))
        plateau_edges.append(plateau_edge)
        best_trial = min(ordered, key=lambda r: (r.mae, r.rmse, -r.exact_ratio))
        lines.append(f"| {code} | {last_improvement} | {plateau_edge} | {best_trial.mae:.3f} |")

    plateau_avg = sum(plateau_edges) / len(plateau_edges)
    lines.extend(["", f"Plateau edge mean trial: **{plateau_avg:.1f} / {variation_trials}** (higher = broader event-space plateau)."])
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


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
    p.add_argument(
        "--param-seed-trials",
        type=int,
        default=32,
        help="How many converter restarts to run per parameter set (recommended 32-64 for stability).",
    )
    p.add_argument(
        "--param-seed-step",
        type=int,
        default=997,
        help="Seed increment between restarts of the same parameter set.",
    )
    p.add_argument("--limit", type=int, default=0, help="Optional limit of codes from CSV (0 = all)")
    p.add_argument(
        "--variation-trials",
        type=int,
        default=64,
        help="Random reconstruction variations per chosen SVG (0 disables random local search).",
    )
    p.add_argument("--variation-sigma", type=float, default=0.9, help="Initial mutation strength in px for geometric reconstruction variation.")
    p.add_argument("--variation-min-sigma", type=float, default=0.2, help="Minimum mutation sigma after iterative narrowing.")
    p.add_argument("--variation-sigma-decay", type=float, default=0.55, help="Sigma multiplier when local search hits a plateau.")
    p.add_argument("--variation-seed", type=int, default=2026, help="Seed for stochastic reconstruction refinement.")
    p.add_argument(
        "--variation-save-all",
        action="store_true",
        help="Persist every mutation SVG trial (default only keeps the best variation per code).",
    )
    args = p.parse_args()

    if not args.param:
        args.param = ["120:36:42", "240:72:42", "360:108:42", "240:72:1337", "480:144:42"]

    param_sets = parse_params(args.param)
    args.param_seed_trials = max(1, args.param_seed_trials)
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
    variation_rows: list[VariationResult] = []

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

            best, rows = choose_best_for_code(
                code,
                source_for_conversion,
                source_label,
                rgb,
                param_sets,
                work_svg,
                per_param_trials=args.param_seed_trials,
                per_param_seed_step=args.param_seed_step,
            )
            template_result = evaluate_template_svg(code, source_label, rgb, args.template_svg_dir)
            if template_result is not None:
                rows.append(template_result)
                if (template_result.mae, template_result.rmse, -template_result.exact_ratio) < (
                    best.mae,
                    best.rmse,
                    -best.exact_ratio,
                ):
                    best = template_result

            best, local_variations = stochastic_refine_svg(
                code=code,
                source_label=source_label,
                rgb_source=rgb,
                base_metric=best,
                output_svg_dir=work_svg / "stochastic_refine",
                variation_trials=args.variation_trials,
                variation_sigma=args.variation_sigma,
                variation_seed=args.variation_seed + idx,
                save_all_variations=args.variation_save_all,
                sigma_decay=args.variation_sigma_decay,
                min_sigma=args.variation_min_sigma,
            )
            variation_rows.extend(local_variations)

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
                f"seed_trials={args.param_seed_trials} source={best.svg_path.name}"
            )

    write_csv(out_dir / "best_per_image.csv", best_rows)
    write_csv(out_dir / "all_results.csv", all_rows)
    write_variation_csv(out_dir / "stochastic_variations.csv", variation_rows)
    write_report(out_dir / "optimization_report.md", best_rows, all_rows, param_sets)
    append_plateau_report(out_dir / "optimization_report.md", variation_rows, args.variation_trials)

    print(f"done images={len(best_rows)} params={len(param_sets)} out={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
