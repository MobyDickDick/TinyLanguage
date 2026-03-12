"""Element-based image-to-SVG converter with random-search refinement.

Workflow:
1) Search image elements.
2) Re-draw every element as SVG primitives with random parameter variation.
3) Compare candidates to the source element.
4) Narrow search space until a plateau or best solution is reached.
"""

from __future__ import annotations

import argparse
import importlib
import random
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

@dataclass
class Element:
    pixels: list[list[int]]
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass
class Candidate:
    shape: str
    cx: float
    cy: float
    w: float
    h: float


def load_grayscale_image(path: Path) -> list[list[int]]:
    try:
        image_module = importlib.import_module("PIL.Image")
    except ModuleNotFoundError as exc:
        if exc.name in {"PIL", "PIL.Image"}:
            if path.suffix.lower() == ".bmp":
                return load_grayscale_bmp(path)
            raise ModuleNotFoundError(
                "Missing dependency 'Pillow' (module 'PIL'). Install it into the active interpreter with "
                "`python -m pip install Pillow` and ensure your IDE/debugger uses the same interpreter."
            ) from exc
        raise

    gray = image_module.open(path).convert("L")
    w, h = gray.size
    px = gray.load()
    return [[int(px[x, y]) for x in range(w)] for y in range(h)]


def load_grayscale_bmp(path: Path) -> list[list[int]]:
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise ValueError(f"Unsupported BMP file: {path}")

    pixel_offset = struct.unpack_from("<I", data, 10)[0]
    dib_size = struct.unpack_from("<I", data, 14)[0]
    if dib_size < 40:
        raise ValueError(f"Unsupported BMP DIB header size {dib_size} in {path}")

    width = struct.unpack_from("<i", data, 18)[0]
    height = struct.unpack_from("<i", data, 22)[0]
    planes = struct.unpack_from("<H", data, 26)[0]
    bpp = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]

    if width <= 0 or height == 0:
        raise ValueError(f"Unsupported BMP dimensions in {path}")
    if planes != 1 or bpp not in {24, 32} or compression != 0:
        raise ValueError(f"Unsupported BMP format in {path}: planes={planes} bpp={bpp} compression={compression}")

    top_down = height < 0
    out_h = abs(height)
    row_stride = ((width * bpp + 31) // 32) * 4

    gray = [[255 for _ in range(width)] for _ in range(out_h)]
    for row in range(out_h):
        src_row = row if top_down else (out_h - 1 - row)
        row_start = pixel_offset + src_row * row_stride
        for x in range(width):
            px_start = row_start + x * (bpp // 8)
            if px_start + 2 >= len(data):
                raise ValueError(f"Corrupt BMP pixel data in {path}")
            b = data[px_start]
            g = data[px_start + 1]
            r = data[px_start + 2]
            gray[row][x] = int(0.114 * b + 0.587 * g + 0.299 * r)

    return gray


def load_binary_image(path: Path, threshold: int = 220) -> list[list[int]]:
    grayscale = load_grayscale_image(path)
    return [[1 if value < threshold else 0 for value in row] for row in grayscale]


def find_elements(binary: list[list[int]], min_pixels: int = 25) -> list[Element]:
    h = len(binary)
    w = len(binary[0]) if h else 0
    visited = [[False] * w for _ in range(h)]
    elements: list[Element] = []

    for y in range(h):
        for x in range(w):
            if binary[y][x] == 0 or visited[y][x]:
                continue
            stack = [(x, y)]
            visited[y][x] = True
            coords: list[tuple[int, int]] = []

            while stack:
                cx, cy = stack.pop()
                coords.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and binary[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = True
                        stack.append((nx, ny))

            if len(coords) < min_pixels:
                continue

            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
            local = [[0] * (x1 - x0 + 1) for _ in range(y1 - y0 + 1)]
            for px, py in coords:
                local[py - y0][px - x0] = 1
            elements.append(Element(local, x0, y0, x1, y1))

    return elements


def estimate_initial_candidate(element: Element) -> Candidate:
    coords = [(x, y) for y, row in enumerate(element.pixels) for x, v in enumerate(row) if v]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    cx = sum(xs) / max(1, len(xs))
    cy = sum(ys) / max(1, len(ys))
    w = max(2.0, float(max(xs) - min(xs) + 1))
    h = max(2.0, float(max(ys) - min(ys) + 1))
    ratio = max(w, h) / max(1.0, min(w, h))
    shape = "circle" if ratio < 1.35 else "ellipse"
    return Candidate(shape=shape, cx=cx, cy=cy, w=w, h=h)


def render_candidate_mask(candidate: Candidate, width: int, height: int) -> list[list[int]]:
    mask = [[0 for _ in range(width)] for _ in range(height)]

    if candidate.shape == "circle":
        rx = max(1.0, (candidate.w + candidate.h) / 4.0)
        ry = rx
    else:
        rx = max(1.0, candidate.w / 2.0)
        ry = max(1.0, candidate.h / 2.0)

    inv_rx2 = 1.0 / (rx * rx)
    inv_ry2 = 1.0 / (ry * ry)

    for y in range(height):
        dy2 = (y - candidate.cy) ** 2 * inv_ry2
        if dy2 > 1.0:
            continue
        for x in range(width):
            dx2 = (x - candidate.cx) ** 2 * inv_rx2
            if dx2 + dy2 <= 1.0:
                mask[y][x] = 1

    return mask


def _iou(a: list[list[int]], b: list[list[int]]) -> float:
    inter = 0
    union = 0
    for y in range(len(a)):
        for x in range(len(a[0])):
            av = a[y][x]
            bv = b[y][x]
            if av and bv:
                inter += 1
            if av or bv:
                union += 1
    return inter / union if union else 0.0


def score_candidate(target: list[list[int]], candidate: Candidate) -> float:
    rendered = render_candidate_mask(candidate, len(target[0]), len(target))
    return _iou(target, rendered)


def random_neighbor(base: Candidate, scale: float, rng: random.Random) -> Candidate:
    return Candidate(
        shape=base.shape,
        cx=base.cx + rng.uniform(-scale, scale),
        cy=base.cy + rng.uniform(-scale, scale),
        w=max(1.0, base.w + rng.uniform(-scale, scale) * 1.4),
        h=max(1.0, base.h + rng.uniform(-scale, scale) * 1.4),
    )


def optimize_element(target: list[list[int]], init: Candidate, *, max_iter: int, plateau_limit: int, seed: int) -> tuple[Candidate, float]:
    rng = random.Random(seed)
    best = init
    best_score = score_candidate(target, best)
    scale = max(len(target), len(target[0])) * 0.25
    plateau = 0

    for _ in range(max_iter):
        cand = random_neighbor(best, scale, rng)
        score = score_candidate(target, cand)
        if score > best_score:
            best = cand
            best_score = score
            plateau = 0
            scale = max(0.8, scale * 0.9)
        else:
            plateau += 1
            if plateau % 8 == 0:
                scale = max(0.6, scale * 0.8)
        if plateau >= plateau_limit:
            break

    return best, best_score


def gray_to_hex(value: int) -> str:
    c = max(0, min(255, int(value)))
    return f"#{c:02x}{c:02x}{c:02x}"


def element_fill_color(grayscale: list[list[int]], element: Element) -> str:
    values: list[int] = []
    for y, row in enumerate(element.pixels):
        gy = y + element.y0
        for x, is_foreground in enumerate(row):
            if is_foreground:
                gx = x + element.x0
                values.append(grayscale[gy][gx])

    if not values:
        return "#000000"
    return gray_to_hex(sum(values) // len(values))


def estimate_stroke_style(grayscale: list[list[int]], element: Element, candidate: Candidate) -> tuple[str, str | None, float | None]:
    """Estimate fill/stroke from grayscale values.

    For near-circular components we check whether the outer radial band is
    significantly darker than the center. If yes, emit an explicit stroke so
    reconstructed symbols preserve visible borders.
    """
    fill_color = element_fill_color(grayscale, element)
    if candidate.shape != "circle":
        return fill_color, None, None

    cx = candidate.cx + element.x0
    cy = candidate.cy + element.y0
    radius = max(1.0, (candidate.w + candidate.h) / 4.0)
    inner_values: list[int] = []
    outer_values: list[int] = []

    for y, row in enumerate(element.pixels):
        gy = y + element.y0
        for x, is_foreground in enumerate(row):
            if not is_foreground:
                continue
            gx = x + element.x0
            d = ((gx - cx) ** 2 + (gy - cy) ** 2) ** 0.5
            rel = d / radius
            v = grayscale[gy][gx]
            if rel <= 0.72:
                inner_values.append(v)
            elif 0.75 <= rel <= 1.05:
                outer_values.append(v)

    if len(inner_values) < 12 or len(outer_values) < 12:
        return fill_color, None, None

    inner_avg = sum(inner_values) / len(inner_values)
    outer_avg = sum(outer_values) / len(outer_values)
    darkness_delta = inner_avg - outer_avg
    if darkness_delta < 16:
        return fill_color, None, None

    fill = gray_to_hex(round(inner_avg))
    stroke = gray_to_hex(round(outer_avg))
    stroke_width = max(1.0, radius * 0.16)
    return fill, stroke, stroke_width


def candidate_to_svg(candidate: Candidate, gx: int, gy: int, fill_color: str, stroke_color: str | None = None, stroke_width: float | None = None) -> str:
    cx = candidate.cx + gx
    cy = candidate.cy + gy
    if candidate.shape == "circle":
        r = max(1.0, (candidate.w + candidate.h) / 4.0)
        attrs = [f'cx="{cx:.2f}"', f'cy="{cy:.2f}"', f'r="{r:.2f}"', f'fill="{fill_color}"']
        if stroke_color and stroke_width is not None:
            attrs.append(f'stroke="{stroke_color}"')
            attrs.append(f'stroke-width="{stroke_width:.2f}"')
        return f"<circle {' '.join(attrs)} />"
    attrs = [f'cx="{cx:.2f}"', f'cy="{cy:.2f}"', f'rx="{candidate.w/2:.2f}"', f'ry="{candidate.h/2:.2f}"', f'fill="{fill_color}"']
    if stroke_color and stroke_width is not None:
        attrs.append(f'stroke="{stroke_color}"')
        attrs.append(f'stroke-width="{stroke_width:.2f}"')
    return f"<ellipse {' '.join(attrs)} />"


def convert_image(image_path: Path, output_svg: Path, *, max_iter: int, plateau_limit: int, seed: int) -> None:
    grayscale = load_grayscale_image(image_path)
    binary = [[1 if value < 220 else 0 for value in row] for row in grayscale]
    elements = find_elements(binary)
    parts: list[str] = []
    for idx, element in enumerate(elements):
        init = estimate_initial_candidate(element)
        best, _ = optimize_element(element.pixels, init, max_iter=max_iter, plateau_limit=plateau_limit, seed=seed + idx)
        fill_color, stroke_color, stroke_width = estimate_stroke_style(grayscale, element, best)
        parts.append(candidate_to_svg(best, element.x0, element.y0, fill_color, stroke_color, stroke_width))

    width, height = len(binary[0]), len(binary)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        *parts,
        "</svg>",
    ]
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    output_svg.write_text("\n".join(svg), encoding="utf-8")


def iter_images(folder: Path) -> Iterable[Path]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    if not folder.exists() or not folder.is_dir():
        return
    for item in folder.iterdir():
        if item.is_file() and item.suffix.lower() in exts:
            yield item


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Raster->SVG converter via random search and plateau narrowing")
    p.add_argument("input_dir", type=Path)
    p.add_argument("output_dir", type=Path, nargs="?", default=Path("artifacts/converted_symbols/svg"))
    p.add_argument("--max-iter", type=int, default=120)
    p.add_argument("--plateau-limit", type=int, default=36)
    p.add_argument("--seed", type=int, default=42)
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    images = sorted(iter_images(args.input_dir))
    if not images:
        print(f"No images found in {args.input_dir}")
        return 1

    for image in images:
        out = args.output_dir / f"{image.stem}.svg"
        convert_image(image, out, max_iter=args.max_iter, plateau_limit=args.plateau_limit, seed=args.seed)
        print(f"converted: {image.name} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
