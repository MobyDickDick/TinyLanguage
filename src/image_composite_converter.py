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
import re
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


@dataclass
class SvgEmission:
    parts: list[str]
    defs: list[str]


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


def _compute_otsu_threshold(grayscale: list[list[int]]) -> int:
    hist = [0] * 256
    total = 0
    for row in grayscale:
        for value in row:
            hist[value] += 1
            total += 1

    if total == 0:
        return 220

    sum_total = sum(i * hist[i] for i in range(256))
    sum_bg = 0.0
    weight_bg = 0
    max_var = -1.0
    threshold = 220

    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break

        sum_bg += t * hist[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg
        between_var = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if between_var > max_var:
            max_var = between_var
            threshold = t

    return threshold


def _adaptive_threshold(grayscale: list[list[int]], block_size: int = 15, c: int = 5) -> list[list[int]]:
    h = len(grayscale)
    w = len(grayscale[0]) if h else 0
    if h == 0 or w == 0:
        return []

    if block_size % 2 == 0:
        block_size += 1
    radius = block_size // 2

    integral = [[0] * (w + 1) for _ in range(h + 1)]
    for y in range(h):
        row_sum = 0
        for x in range(w):
            row_sum += grayscale[y][x]
            integral[y + 1][x + 1] = integral[y][x + 1] + row_sum

    out = [[0] * w for _ in range(h)]
    for y in range(h):
        y0 = max(0, y - radius)
        y1 = min(h - 1, y + radius)
        for x in range(w):
            x0 = max(0, x - radius)
            x1 = min(w - 1, x + radius)
            area = (y1 - y0 + 1) * (x1 - x0 + 1)
            region_sum = (
                integral[y1 + 1][x1 + 1]
                - integral[y0][x1 + 1]
                - integral[y1 + 1][x0]
                + integral[y0][x0]
            )
            local_mean = region_sum / max(1, area)
            out[y][x] = 1 if grayscale[y][x] < (local_mean - c) else 0
    return out


def load_binary_image_with_mode(path: Path, *, threshold: int = 220, mode: str = "global") -> list[list[int]]:
    grayscale = load_grayscale_image(path)
    normalized_mode = mode.lower()
    if normalized_mode == "global":
        return [[1 if value < threshold else 0 for value in row] for row in grayscale]
    if normalized_mode == "otsu":
        otsu_threshold = _compute_otsu_threshold(grayscale)
        return [[1 if value < otsu_threshold else 0 for value in row] for row in grayscale]
    if normalized_mode == "adaptive":
        return _adaptive_threshold(grayscale)
    raise ValueError(f"Unknown threshold mode '{mode}'. Expected one of: global, otsu, adaptive")


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
    half_stroke = (stroke_width / 2.0) if (stroke_color and stroke_width is not None and stroke_width > 0) else 0.0

    if candidate.shape == "circle":
        outer_r = max(1.0, (candidate.w + candidate.h) / 4.0)
        r = max(0.5, outer_r - half_stroke)
        attrs = [f'cx="{cx:.2f}"', f'cy="{cy:.2f}"', f'r="{r:.2f}"', f'fill="{fill_color}"']
        if stroke_color and stroke_width is not None:
            attrs.append(f'stroke="{stroke_color}"')
            attrs.append(f'stroke-width="{stroke_width:.2f}"')
        return f"<circle {' '.join(attrs)} />"

    rx = max(0.5, candidate.w / 2.0 - half_stroke)
    ry = max(0.5, candidate.h / 2.0 - half_stroke)
    attrs = [f'cx="{cx:.2f}"', f'cy="{cy:.2f}"', f'rx="{rx:.2f}"', f'ry="{ry:.2f}"', f'fill="{fill_color}"']
    if stroke_color and stroke_width is not None:
        attrs.append(f'stroke="{stroke_color}"')
        attrs.append(f'stroke-width="{stroke_width:.2f}"')
    return f"<ellipse {' '.join(attrs)} />"


def detect_stemmed_circle(element: Element) -> tuple[Candidate, tuple[int, int, int, int], str] | None:
    """Detect circle+stem geometry in a merged connected component.

    Returns a circle candidate plus stem bounding box (local element coordinates)
    when one thin axis-aligned strip protrudes from a mostly circular body.
    """

    if not element.pixels or not element.pixels[0]:
        return None

    h = len(element.pixels)
    w = len(element.pixels[0])
    row_counts = [sum(row) for row in element.pixels]
    col_counts = [sum(element.pixels[y][x] for y in range(h)) for x in range(w)]
    max_row = max(row_counts) if row_counts else 0
    max_col = max(col_counts) if col_counts else 0
    if max_row == 0 or max_col == 0:
        return None

    def _extract(direction: str) -> tuple[int, int, int, int] | None:
        if direction in {"bottom", "top"}:
            threshold = max(2, int(max_row * 0.48))
            rows: list[int] = []
            indices = range(h - 1, -1, -1) if direction == "bottom" else range(h)
            for y in indices:
                c = row_counts[y]
                if c == 0:
                    if rows:
                        break
                    continue
                if c <= threshold:
                    rows.append(y)
                elif rows:
                    break
                else:
                    return None
            if len(rows) < 2 or len(rows) > max(2, int(h * 0.45)):
                return None
            min_count = min(row_counts[y] for y in rows)
            stem_rows = [y for y in rows if row_counts[y] <= max(2, int(min_count * 1.25))]
            if len(stem_rows) < 2:
                return None
            ys = sorted(stem_rows)
            xvals = [x for y in ys for x, v in enumerate(element.pixels[y]) if v]
            if not xvals:
                return None
            sx0, sx1 = min(xvals), max(xvals)
            if (sx1 - sx0 + 1) > w * 0.45:
                return None
            stem_cx = (sx0 + sx1) / 2.0
            if abs(stem_cx - (w - 1) / 2.0) > max(1.2, w * 0.2):
                return None
            return sx0, ys[0], sx1, ys[-1]

        threshold = max(2, int(max_col * 0.48))
        cols: list[int] = []
        indices = range(w - 1, -1, -1) if direction == "right" else range(w)
        for x in indices:
            c = col_counts[x]
            if c == 0:
                if cols:
                    break
                continue
            if c <= threshold:
                cols.append(x)
            elif cols:
                break
            else:
                return None
        if len(cols) < 2 or len(cols) > max(2, int(w * 0.45)):
            return None
        min_count = min(col_counts[x] for x in cols)
        stem_cols = [x for x in cols if col_counts[x] <= max(2, int(min_count * 1.25))]
        if len(stem_cols) < 2:
            return None
        xs = sorted(stem_cols)
        yvals = [y for x in xs for y in range(h) if element.pixels[y][x]]
        if not yvals:
            return None
        sy0, sy1 = min(yvals), max(yvals)
        if (sy1 - sy0 + 1) > h * 0.45:
            return None
        stem_cy = (sy0 + sy1) / 2.0
        if abs(stem_cy - (h - 1) / 2.0) > max(1.2, h * 0.2):
            return None
        return xs[0], sy0, xs[-1], sy1

    stem_bbox = None
    stem_direction = ""
    for direction in ("bottom", "top", "left", "right"):
        stem_bbox = _extract(direction)
        if stem_bbox is not None:
            stem_direction = direction
            break
    if stem_bbox is None:
        return None

    sx0, sy0, sx1, sy1 = stem_bbox
    body_coords: list[tuple[int, int]] = []
    for y, row in enumerate(element.pixels):
        for x, is_fg in enumerate(row):
            if not is_fg:
                continue
            if sx0 <= x <= sx1 and sy0 <= y <= sy1:
                continue
            body_coords.append((x, y))
    if len(body_coords) < 20:
        return None

    xs = [x for x, _ in body_coords]
    ys = [y for _, y in body_coords]
    bw = max(xs) - min(xs) + 1
    bh = max(ys) - min(ys) + 1
    ratio = max(bw, bh) / max(1.0, min(bw, bh))
    if ratio > 1.35:
        return None

    circle = Candidate(shape="circle", cx=sum(xs) / len(xs), cy=sum(ys) / len(ys), w=float(bw), h=float(bh))
    return circle, stem_bbox, stem_direction


def decompose_circle_with_stem(
    grayscale: list[list[int]], element: Element, candidate: Candidate
) -> list[str] | None:
    """Split merged components into stem + circle when geometry strongly suggests it.

    Some badges encode a circle with an attached straight stem ("Kelle"). During
    connected-component search these pixels form one component, which the random
    search otherwise approximates as a single ellipse. This heuristic keeps the
    conversion process primitive-based by emitting a rect (stem) behind a circle.
    """
    detected = detect_stemmed_circle(element)
    if detected is None:
        return None

    circle_candidate, (sx0, sy0, sx1, sy1), stem_direction = detected
    stem_w = sx1 - sx0 + 1
    stem_h = sy1 - sy0 + 1

    stem_values = [
        grayscale[element.y0 + y][element.x0 + x]
        for y in range(sy0, sy1 + 1)
        for x in range(sx0, sx1 + 1)
        if element.pixels[y][x]
    ]
    stem_color = gray_to_hex(round(sum(stem_values) / max(1, len(stem_values))))
    fill_color, stroke_color, stroke_width = estimate_stroke_style(grayscale, element, circle_candidate)

    stem_x = element.x0 + sx0
    stem_y = element.y0 + sy0
    stem_wf = float(stem_w)
    stem_hf = float(stem_h)

    if stem_direction in {"bottom", "top"}:
        circle_cx = element.x0 + circle_candidate.cx
        stem_x = circle_cx - stem_wf / 2.0

        radius = max(1.0, (circle_candidate.w + circle_candidate.h) / 4.0)
        circle_cy = element.y0 + circle_candidate.cy
        overlap = max(0.6, (stroke_width or 0.0) * 0.55)
        old_bottom = (element.y0 + sy0) + stem_hf

        if stem_direction == "bottom":
            stem_y = circle_cy + radius - overlap
            stem_hf = max(1.0, old_bottom - stem_y)
        else:
            old_top = element.y0 + sy0
            old_right = (element.x0 + sx0) + stem_wf
            stem_y = old_top
            stem_hf = max(1.0, (circle_cy - radius + overlap) - stem_y)
            stem_x = min(stem_x, old_right - stem_wf)

    parts: list[str] = []
    parts.append(
        f'<rect x="{stem_x:.2f}" y="{stem_y:.2f}" '
        f'width="{stem_wf:.2f}" height="{stem_hf:.2f}" fill="{stem_color}"/>'
    )
    parts.append(candidate_to_svg(circle_candidate, element.x0, element.y0, fill_color, stroke_color, stroke_width))
    return parts


def decompose_plus_shape(grayscale: list[list[int]], element: Element) -> list[str] | None:
    """Emit two rects for plus-like components instead of a blob ellipse."""
    h = len(element.pixels)
    w = len(element.pixels[0]) if h else 0
    if h < 5 or w < 5:
        return None

    row_counts = [sum(row) for row in element.pixels]
    col_counts = [sum(element.pixels[y][x] for y in range(h)) for x in range(w)]
    max_row = max(row_counts) if row_counts else 0
    max_col = max(col_counts) if col_counts else 0
    if max_row < int(w * 0.65) or max_col < int(h * 0.65):
        return None

    area = sum(sum(row) for row in element.pixels)
    if area <= 0:
        return None
    expected = max_row + max_col - 1
    if area > expected * 1.9:
        return None

    cy = row_counts.index(max_row)
    cx = col_counts.index(max_col)

    y0 = cy
    while y0 > 0 and element.pixels[y0 - 1][cx]:
        y0 -= 1
    y1 = cy
    while y1 < h - 1 and element.pixels[y1 + 1][cx]:
        y1 += 1

    x0 = cx
    while x0 > 0 and element.pixels[cy][x0 - 1]:
        x0 -= 1
    x1 = cx
    while x1 < w - 1 and element.pixels[cy][x1 + 1]:
        x1 += 1

    thickness = max(1, min(max_row, max_col) // 3)
    color = element_fill_color(grayscale, element)
    gx, gy = element.x0, element.y0

    return [
        f'<rect x="{gx + x0:.2f}" y="{gy + cy - thickness / 2:.2f}" width="{x1 - x0 + 1:.2f}" height="{thickness:.2f}" fill="{color}"/>',
        f'<rect x="{gx + cx - thickness / 2:.2f}" y="{gy + y0:.2f}" width="{thickness:.2f}" height="{y1 - y0 + 1:.2f}" fill="{color}"/>',
    ]


def decompose_rect_with_diagonal(grayscale: list[list[int]], element: Element, gradient_id: str) -> SvgEmission | None:
    """Detect tall rectangular badges with border+diagonal and emit dedicated primitives."""
    h = len(element.pixels)
    w = len(element.pixels[0]) if h else 0
    if h < 10 or w < 6:
        return None

    ratio = h / max(1.0, w)
    if ratio < 1.4:
        return None

    row_counts = [sum(row) for row in element.pixels]
    col_counts = [sum(element.pixels[y][x] for y in range(h)) for x in range(w)]
    if min(row_counts[0], row_counts[-1]) < int(w * 0.75):
        return None
    if min(col_counts[0], col_counts[-1]) < int(h * 0.75):
        return None

    border_band = max(1, min(w, h) // 10)
    interior_pixels = [
        (x, y)
        for y in range(border_band, h - border_band)
        for x in range(border_band, w - border_band)
        if element.pixels[y][x]
    ]
    if len(interior_pixels) < max(12, (w * h) // 20):
        return None

    filtered = [(x, y) for (x, y) in interior_pixels if not (x < w * 0.38 and y < h * 0.34)]
    fit_points = filtered if len(filtered) > 10 else interior_pixels
    n = len(fit_points)
    sum_y = sum(y for _, y in fit_points)
    sum_x = sum(x for x, _ in fit_points)
    sum_yy = sum(y * y for _, y in fit_points)
    sum_xy = sum(x * y for x, y in fit_points)
    denom = n * sum_yy - sum_y * sum_y
    if abs(denom) < 1e-6:
        return None
    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_x - a * sum_y) / n
    if a > -0.05:
        return None

    avg_dev = sum(abs(x - (a * y + b)) for x, y in fit_points) / n
    thickness = max(2.0, min(w * 0.45, avg_dev * 2.2))

    left_vals = [grayscale[element.y0 + y][element.x0 + x] for y in range(h) for x in range(0, max(1, w // 4)) if element.pixels[y][x]]
    center_vals = [
        grayscale[element.y0 + y][element.x0 + x]
        for y in range(h)
        for x in range(max(0, w // 3), min(w, (2 * w) // 3))
        if element.pixels[y][x]
    ]
    right_vals = [grayscale[element.y0 + y][element.x0 + x] for y in range(h) for x in range(max(0, (3 * w) // 4), w) if element.pixels[y][x]]
    if not left_vals or not center_vals or not right_vals:
        return None

    left_hex = gray_to_hex(round(sum(left_vals) / len(left_vals)))
    mid_hex = gray_to_hex(round(sum(center_vals) / len(center_vals)))
    right_hex = gray_to_hex(round(sum(right_vals) / len(right_vals)))
    border_val = round(
        (
            sum(grayscale[element.y0][element.x0 + x] for x in range(w))
            + sum(grayscale[element.y0 + h - 1][element.x0 + x] for x in range(w))
            + sum(grayscale[element.y0 + y][element.x0] for y in range(h))
            + sum(grayscale[element.y0 + y][element.x0 + w - 1] for y in range(h))
        )
        / max(1, 2 * (w + h))
    )
    border_hex = gray_to_hex(border_val)
    diag_hex = gray_to_hex(max(0, border_val - 4))

    y_start = h - 1 - border_band
    y_end = border_band
    x_start = a * y_start + b
    x_end = a * y_end + b
    dx = x_end - x_start
    dy = y_end - y_start
    length = max(1e-6, (dx * dx + dy * dy) ** 0.5)
    nx = -dy / length
    ny = dx / length
    half_t = thickness / 2.0
    p1 = (element.x0 + x_start + nx * half_t, element.y0 + y_start + ny * half_t)
    p2 = (element.x0 + x_end + nx * half_t, element.y0 + y_end + ny * half_t)
    p3 = (element.x0 + x_end - nx * half_t, element.y0 + y_end - ny * half_t)
    p4 = (element.x0 + x_start - nx * half_t, element.y0 + y_start - ny * half_t)

    defs = [
        (
            f'<linearGradient id="{gradient_id}" x1="{element.x0:.2f}" y1="{element.y0:.2f}" '
            f'x2="{element.x0 + w:.2f}" y2="{element.y0:.2f}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{left_hex}"/><stop offset="0.53" stop-color="{mid_hex}"/>'
            f'<stop offset="1" stop-color="{right_hex}"/></linearGradient>'
        )
    ]
    parts = [
        f'<rect x="{element.x0:.2f}" y="{element.y0:.2f}" width="{w:.2f}" height="{h:.2f}" fill="url(#{gradient_id})" stroke="{border_hex}" stroke-width="1.00"/>',
        f'<path d="M {p1[0]:.2f},{p1[1]:.2f} L {p2[0]:.2f},{p2[1]:.2f} L {p3[0]:.2f},{p3[1]:.2f} L {p4[0]:.2f},{p4[1]:.2f} Z" fill="{diag_hex}"/>',
    ]
    return SvgEmission(parts=parts, defs=defs)


def _rotate_matrix_90cw(matrix: list[list[int]]) -> list[list[int]]:
    h = len(matrix)
    w = len(matrix[0]) if h else 0
    return [[matrix[h - 1 - y][x] for y in range(h)] for x in range(w)]


def _rotate_grayscale_90cw(matrix: list[list[int]]) -> list[list[int]]:
    h = len(matrix)
    w = len(matrix[0]) if h else 0
    return [[matrix[h - 1 - y][x] for y in range(h)] for x in range(w)]


def _resize_nn(matrix: list[list[int]], out_w: int, out_h: int) -> list[list[int]]:
    in_h = len(matrix)
    in_w = len(matrix[0]) if in_h else 0
    if in_h == 0 or in_w == 0 or out_w <= 0 or out_h <= 0:
        return [[0 for _ in range(max(0, out_w))] for _ in range(max(0, out_h))]
    return [
        [matrix[min(in_h - 1, int(y * in_h / out_h))][min(in_w - 1, int(x * in_w / out_w))] for x in range(out_w)]
        for y in range(out_h)
    ]


def _merge_variants(
    binaries: list[list[list[int]]],
    grayscales: list[list[list[int]]],
    *,
    allow_quarter_turns: bool,
    preserve_text_orientation: bool,
) -> tuple[list[list[int]], list[list[int]]]:
    if not binaries:
        return [], []

    heights = [len(b) for b in binaries]
    widths = [len(b[0]) if b else 0 for b in binaries]
    best_idx = max(range(len(binaries)), key=lambda i: widths[i] * heights[i])
    out_w = widths[best_idx]
    out_h = heights[best_idx]

    union = [[0 for _ in range(out_w)] for _ in range(out_h)]
    composite_gray = [[255 for _ in range(out_w)] for _ in range(out_h)]

    for idx in range(len(binaries)):
        b0 = _resize_nn(binaries[idx], out_w, out_h)
        g0 = _resize_nn(grayscales[idx], out_w, out_h)

        variants = [(b0, g0)]
        if allow_quarter_turns and not preserve_text_orientation:
            rb, rg = b0, g0
            for _ in range(3):
                rb = _rotate_matrix_90cw(rb)
                rg = _rotate_grayscale_90cw(rg)
                variants.append((_resize_nn(rb, out_w, out_h), _resize_nn(rg, out_w, out_h)))

        base_iou = -1.0
        chosen_b, chosen_g = variants[0]
        if any(any(v for v in row) for row in union):
            for vb, vg in variants:
                score = _iou(union, vb)
                if score > base_iou:
                    base_iou = score
                    chosen_b, chosen_g = vb, vg

        for y in range(out_h):
            for x in range(out_w):
                if chosen_b[y][x]:
                    union[y][x] = 1
                    composite_gray[y][x] = min(composite_gray[y][x], chosen_g[y][x])

    return union, composite_gray


def _convert_from_binary_and_grayscale(
    binary: list[list[int]],
    grayscale: list[list[int]],
    output_svg: Path,
    *,
    max_iter: int,
    plateau_limit: int,
    seed: int,
) -> None:
    elements = find_elements(binary)
    parts: list[str] = []
    defs: list[str] = []
    for idx, element in enumerate(elements):
        frame = decompose_rect_with_diagonal(grayscale, element, f"autoGradient{idx}")
        if frame is not None:
            parts.extend(frame.parts)
            defs.extend(frame.defs)
            continue

        plus_parts = decompose_plus_shape(grayscale, element)
        if plus_parts is not None:
            parts.extend(plus_parts)
            continue

        init = estimate_initial_candidate(element)
        best, _ = optimize_element(element.pixels, init, max_iter=max_iter, plateau_limit=plateau_limit, seed=seed + idx)
        decomposed = decompose_circle_with_stem(grayscale, element, best)
        if decomposed is not None:
            parts.extend(decomposed)
        else:
            fill_color, stroke_color, stroke_width = estimate_stroke_style(grayscale, element, best)
            parts.append(candidate_to_svg(best, element.x0, element.y0, fill_color, stroke_color, stroke_width))

    width, height = len(binary[0]), len(binary)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>" if defs else "",
        *defs,
        "</defs>" if defs else "",
        *parts,
        "</svg>",
    ]
    svg = [line for line in svg if line]
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    output_svg.write_text("\n".join(svg), encoding="utf-8")


def convert_image_variants(
    image_paths: list[Path],
    output_svg: Path,
    *,
    max_iter: int,
    plateau_limit: int,
    seed: int,
    threshold_mode: str = "auto",
    threshold: int = 220,
    allow_quarter_turns: bool = False,
    preserve_text_orientation: bool = True,
) -> None:
    if not image_paths:
        raise ValueError("convert_image_variants requires at least one image path")

    binaries: list[list[list[int]]] = []
    grays: list[list[list[int]]] = []
    for image_path in image_paths:
        grayscale = load_grayscale_image(image_path)
        mode = threshold_mode.lower()
        if mode == "auto":
            mode = "otsu" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "global"
        if mode == "global":
            binary = [[1 if value < threshold else 0 for value in row] for row in grayscale]
        elif mode == "otsu":
            otsu_threshold = _compute_otsu_threshold(grayscale)
            binary = [[1 if value < otsu_threshold else 0 for value in row] for row in grayscale]
        elif mode == "adaptive":
            binary = _adaptive_threshold(grayscale)
        else:
            raise ValueError(f"Unknown threshold mode '{threshold_mode}'. Expected one of: auto, global, otsu, adaptive")
        binaries.append(binary)
        grays.append(grayscale)

    merged_binary, merged_gray = _merge_variants(
        binaries,
        grays,
        allow_quarter_turns=allow_quarter_turns,
        preserve_text_orientation=preserve_text_orientation,
    )
    _convert_from_binary_and_grayscale(
        merged_binary,
        merged_gray,
        output_svg,
        max_iter=max_iter,
        plateau_limit=plateau_limit,
        seed=seed,
    )


def convert_image(
    image_path: Path,
    output_svg: Path,
    *,
    max_iter: int,
    plateau_limit: int,
    seed: int,
    threshold_mode: str = "auto",
    threshold: int = 220,
) -> None:
    grayscale = load_grayscale_image(image_path)
    mode = threshold_mode.lower()
    if mode == "auto":
        mode = "otsu" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "global"
    if mode == "global":
        binary = [[1 if value < threshold else 0 for value in row] for row in grayscale]
    elif mode == "otsu":
        otsu_threshold = _compute_otsu_threshold(grayscale)
        binary = [[1 if value < otsu_threshold else 0 for value in row] for row in grayscale]
    elif mode == "adaptive":
        binary = _adaptive_threshold(grayscale)
    else:
        raise ValueError(f"Unknown threshold mode '{threshold_mode}'. Expected one of: auto, global, otsu, adaptive")

    _convert_from_binary_and_grayscale(
        binary,
        grayscale,
        output_svg,
        max_iter=max_iter,
        plateau_limit=plateau_limit,
        seed=seed,
    )


def iter_images(folder: Path) -> Iterable[Path]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    if not folder.exists() or not folder.is_dir():
        return
    for item in folder.iterdir():
        if item.is_file() and item.suffix.lower() in exts:
            yield item



def variant_group_key(path: Path) -> str:
    stem = path.stem
    m = re.match(r"^(.*?)(?:_(?:XXL|XL|L|M|S|XS|\d+))?$", stem, flags=re.IGNORECASE)
    return (m.group(1) if m else stem).lower()


def group_image_variants(images: list[Path]) -> list[list[Path]]:
    groups: dict[str, list[Path]] = {}
    for image in images:
        groups.setdefault(variant_group_key(image), []).append(image)
    return [sorted(v) for _, v in sorted(groups.items(), key=lambda item: item[0])]

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Raster->SVG converter via random search and plateau narrowing")
    p.add_argument("input_dir", type=Path)
    p.add_argument("output_dir", type=Path, nargs="?", default=Path("artifacts/converted_symbols/svg"))
    p.add_argument("--max-iter", type=int, default=120)
    p.add_argument("--plateau-limit", type=int, default=36)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--threshold-mode", choices=["auto", "global", "otsu", "adaptive"], default="auto")
    p.add_argument("--threshold", type=int, default=220)
    p.add_argument("--merge-variants", action="store_true", help="Merge similarly named image variants into one SVG")
    p.add_argument("--allow-quarter-turns", action="store_true", help="Allow 90° rotation matching while merging variants")
    p.add_argument("--preserve-text-orientation", action="store_true", default=True, help="Do not rotate variants while merging (default: true)")
    p.add_argument("--no-preserve-text-orientation", dest="preserve_text_orientation", action="store_false", help="Permit rotated alignment that may rotate text")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    images = sorted(iter_images(args.input_dir))
    if not images:
        print(f"No images found in {args.input_dir}")
        return 1

    if args.merge_variants:
        for group in group_image_variants(images):
            representative = max(group, key=lambda p: p.stat().st_size)
            out = args.output_dir / f"{variant_group_key(representative)}.svg"
            convert_image_variants(
                group,
                out,
                max_iter=args.max_iter,
                plateau_limit=args.plateau_limit,
                seed=args.seed,
                threshold_mode=args.threshold_mode,
                threshold=args.threshold,
                allow_quarter_turns=args.allow_quarter_turns,
                preserve_text_orientation=args.preserve_text_orientation,
            )
            print(f"converted-group: {', '.join(img.name for img in group)} -> {out}")
    else:
        for image in images:
            out = args.output_dir / f"{image.stem}.svg"
            convert_image(
                image,
                out,
                max_iter=args.max_iter,
                plateau_limit=args.plateau_limit,
                seed=args.seed,
                threshold_mode=args.threshold_mode,
                threshold=args.threshold,
            )
            print(f"converted: {image.name} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
