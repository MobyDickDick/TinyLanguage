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
import xml.etree.ElementTree as ET
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




def _clip(value, low, high):
    """Clip scalar/array values without hard-requiring numpy at runtime."""
    if np is not None:
        return np.clip(value, low, high)
    if isinstance(value, (int, float)):
        # Match numpy semantics for inverted bounds (`a_min > a_max`):
        # values collapse to the upper bound.
        if low > high:
            return high
        return low if value < low else high if value > high else value
    raise RuntimeError("numpy is required for non-scalar clip operations")


def _isfinite(value: float) -> bool:
    """Finite check that works even when numpy is unavailable."""
    if np is not None:
        return bool(np.isfinite(value))
    return math.isfinite(float(value))

def _missing_required_image_dependencies() -> list[str]:
    missing: list[str] = []
    if cv2 is None:
        missing.append("opencv-python-headless")
    if np is None:
        missing.append("numpy")
    return missing


@dataclass
class QualityRow:
    image: str
    svg: str
    width: int
    height: int
    avg_error_per_pixel: float


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

        (_score, cnt) = best
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        min_r = max(2.0, float(w) * 0.24)
        max_r = min(float(w) * 0.52, float(top_limit) * 0.58)
        if max_r < min_r:
            max_r = min_r
        r = float(_clip(r, min_r, max_r))
        cx = float(_clip(cx, 0.0, float(w - 1)))
        cy = float(_clip(cy, 0.0, float(h - 1)))
        return cx, cy, r

    @staticmethod
    def _fit_ac0811_params_from_image(img: np.ndarray, defaults: dict) -> dict:
        """Fit AC0811 while keeping the vertical stem anchored to the lower edge.

        AC0811 source symbols are noisy for thin vertical lines. Generic stem fitting can
        under-segment the line so the generated SVG misses parts of the lower connector.
        For this family we therefore fit the circle/tones from the image, but keep the stem
        geometry constrained to the semantic template (centered under the circle, extending
        to the image bottom).
        """
        params = Action._fit_semantic_badge_from_image(img, defaults)
        h, w = img.shape[:2]

        raw_stem_width = float(params.get("stem_width", defaults.get("stem_width", max(1.0, float(w) * 0.10))))
        cx = float(params.get("cx", defaults.get("cx", float(w) / 2.0)))
        cy = float(params.get("cy", defaults.get("cy", float(w) / 2.0)))
        r = float(params.get("r", defaults.get("r", float(w) * 0.4)))
        stroke_circle = float(params.get("stroke_circle", defaults.get("stroke_circle", max(0.9, float(w) / 15.0))))

        # Foreground contour estimation helps stem-only badges, but for VOC/CO2
        # labels it can lock onto text blobs and shrink the fitted circle.
        allow_upper_circle_estimate = str(params.get("text_mode", "")).lower() not in {"voc", "co2"}
        upper_circle = Action._estimate_upper_circle_from_foreground(img, defaults) if allow_upper_circle_estimate else None
        if upper_circle is not None:
            ecx, ecy, er = upper_circle
            # Prefer robust foreground estimate for tiny/narrow AC0811 variants.
            trust = 0.85 if w <= 18 else 0.55
            cx = (cx * (1.0 - trust)) + (ecx * trust)
            cy = (cy * (1.0 - trust)) + (ecy * trust)
            r = (r * (1.0 - trust)) + (er * trust)
            params["cx"] = cx
            params["cy"] = cy
            params["r"] = r

        # On tiny AC0811 variants, anti-aliased pixels can pull contour-based center
        # estimates to one side. Keep the semantic template's horizontal center so the
        # stem remains visually centered under the circle.
        if w <= 18 and not bool(params.get("draw_text", True)):
            default_cx = float(defaults.get("cx", float(w) / 2.0))
            default_cy = float(defaults.get("cy", float(w) / 2.0))
            default_r = float(defaults.get("r", float(w) * 0.4))
            cx = default_cx
            cy = float(_clip(cy, default_cy - 0.8, default_cy + 0.8))
            # Keep tiny variants from shrinking due to noisy anti-aliased edge pixels.
            # This preserves the visual diameter expected for AC0811_S.
            r = max(r, default_r * 0.96)

            # Ensure the fitted circle remains fully inside the canvas with stroke taken
            # into account so it is not clipped at the edges.
            radius_limit_x = max(1.0, min(default_cx, float(w) - default_cx) - (stroke_circle / 2.0))
            radius_limit_y = max(1.0, min(default_cy, float(h) - default_cy) - (stroke_circle / 2.0))
            r = float(min(r, radius_limit_x, radius_limit_y))

            params["cx"] = default_cx
            params["cy"] = cy
            params["r"] = r
            # Keep tiny AC0811 variants horizontally anchored; anti-aliased
            # min-rect alignment can otherwise pull circle/stem to one side.
            params["lock_circle_cx"] = True
            params["lock_stem_center_to_circle"] = True

        # Keep text badges close to template radius; otherwise under-estimation
        # shrinks both the circle and text size in variants such as AC0836_L.
        if str(params.get("text_mode", "")).lower() in {"voc", "co2"}:
            default_r = float(defaults.get("r", r))
            r = float(_clip(r, default_r * 0.95, default_r * 1.08))
            params["r"] = r

        # AC0811 stems are intentionally thin. The generic contour fit can over-estimate
        # width when anti-aliased circle pixels bleed into the stem ROI, especially on
        # larger "_L" variants. Keep the fitted value but clamp it to a narrow, plausible
        # band derived from the circle stroke and image width.
        min_stem_width = max(1.0, stroke_circle * 0.72)
        default_stem_width_max = max(min_stem_width, min(float(w) * 0.12, stroke_circle * 1.35))
        max_stem_width = max(
            min_stem_width,
            min(float(defaults.get("stem_width_max", default_stem_width_max)), default_stem_width_max),
        )
        stem_width = max(min_stem_width, min(raw_stem_width, max_stem_width))

        params["stem_enabled"] = True
        params["stem_width"] = stem_width
        params["stem_width_max"] = max_stem_width
        params["stem_x"] = cx - (params["stem_width"] / 2.0)
        min_stem_len = 1.0 if h <= 18 else 2.0
        max_r_for_visible_stem = max(1.0, float(h) - cy - min_stem_len)
        if r > max_r_for_visible_stem:
            r = max_r_for_visible_stem
            params["r"] = r
        stem_top = cy + r
        stem_top = max(0.0, min(float(h) - min_stem_len, stem_top))
        params["stem_top"] = stem_top
        params["stem_bottom"] = float(h)
        params["stem_gray"] = int(round(params.get("stroke_gray", defaults.get("stroke_gray", 152))))
        return Action._normalize_light_circle_colors(params)

    @staticmethod
    def _default_ac0882_params(w: int, h: int) -> dict:
        params = Action._default_ac081x_shared(w, h)
        arm_x2 = params["cx"] - params["r"]
        arm_x1 = max(0.0, arm_x2 - params["stem_or_arm_len"])
        params.update(
            {
                "text_gray": 98,
                "label": "T",
                "text_mode": "path_t",
                "arm_enabled": True,
                "arm_x1": arm_x1,
                "arm_y1": params["cy"],
                "arm_x2": arm_x2,
                "arm_y2": params["cy"],
                "arm_stroke": params["stem_or_arm"],
                "s": 0.0088 * min(1.0, (min(w, h) / 25.0)) if min(w, h) > 0 else 0.0088,
            }
        )
        Action._center_glyph_bbox(params)
        return params

    @staticmethod
    def _apply_co2_label(params: dict) -> dict:
        params["draw_text"] = True
        params["text_mode"] = "co2"
        params["text_gray"] = int(round(params.get("stroke_gray", Action.LIGHT_CIRCLE_STROKE_GRAY)))
        params["co2_font_scale"] = float(params.get("co2_font_scale", 0.82 * Action.SEMANTIC_TEXT_BASE_SCALE))
        params["co2_sub_font_scale"] = float(params.get("co2_sub_font_scale", 66.0))
        params["co2_dx"] = float(params.get("co2_dx", 0.0))
        params["co2_dy"] = float(params.get("co2_dy", 0.0))
        params["co2_inner_padding_px"] = float(params.get("co2_inner_padding_px", 0.35))
        # Keep "CO" as an explicit run so the subscript position remains stable across
        # renderers. The default mode keeps the CO baseline vertically centered, but
        # applies a small left compensation so the overall CO₂ cluster appears
        # horizontally centered in the circle.
        params["co2_anchor_mode"] = str(params.get("co2_anchor_mode", "center_co"))
        return params

    @staticmethod
    def _co2_layout(params: dict) -> dict[str, float | str]:
        """Compute renderer-independent CO₂ text metrics and placement."""
        cx = float(params.get("cx", 0.0))
        cy = float(params.get("cy", 0.0))
        r = max(1.0, float(params.get("r", 1.0)))
        stroke = max(0.8, float(params.get("stroke_circle", 1.0)))
        inner_diameter = max(2.0, (2.0 * r) - stroke)
        requested_font_size = max(4.0, r * float(params.get("co2_font_scale", 0.82)))
        # Keep the main CO run proportionate to the circle interior, even if
        # optimizer steps push co2_font_scale too high for anti-aliased rasters.
        max_font_size = max(
            4.0,
            inner_diameter * float(params.get("co2_max_inner_diameter_ratio", 0.50)),
        )
        inner_padding = max(0.0, float(params.get("co2_inner_padding_px", 0.35)))
        clear_span = max(1.0, inner_diameter - (2.0 * inner_padding))
        sub_scale = float(params.get("co2_sub_font_scale", 66.0))
        sub_ratio = max(0.20, sub_scale / 100.0)
        # Estimate the whole CO₂ cluster width and derive a scale that keeps
        # a small edge margin whenever geometry allows it.
        cluster_factor = 1.04 + 0.03 + (0.62 * sub_ratio)
        width_limited_font = clear_span / max(0.001, cluster_factor)
        # Preserve vertical clear-space as well.
        height_limited_font = clear_span / max(0.95, 0.95 + (0.24 * sub_ratio) + (0.35 * sub_ratio))
        auto_font_size = min(width_limited_font, height_limited_font)
        font_size = min(max_font_size, max(requested_font_size, auto_font_size))
        # Tiny badges can otherwise rasterize the subscript into a barely visible
        # blob or drop it entirely. Keep a conservative minimum pixel height.
        sub_font_px = max(4.0, font_size * (sub_scale / 100.0))
        anchor_mode = str(params.get("co2_anchor_mode", "center_co")).lower()

        co_width = font_size * 1.04
        gap = font_size * 0.03
        sub_w = sub_font_px * 0.62

        if anchor_mode in {"cluster", "co"}:
            # Legacy mode: center the whole CO₂ cluster.
            cluster_shift = (gap + sub_w) / 2.0
            co_x = (cx + float(params.get("co2_dx", 0.0))) - cluster_shift
            x1 = co_x - (co_width / 2.0)
            subscript_x = co_x + (co_width / 2.0) + gap
            x2 = subscript_x + sub_w
        else:
            plateau += 1
            if plateau % 8 == 0:
                scale = max(0.6, scale * 0.8)
        if plateau >= plateau_limit:
            break

    @staticmethod
    def _fit_ac0812_params_from_image(img: np.ndarray, defaults: dict) -> dict:
        """Fit AC0812 while keeping the horizontal arm anchored to the left edge."""
        params = Action._fit_semantic_badge_from_image(img, defaults)
        h, w = img.shape[:2]
        aspect_ratio = (float(w) / float(h)) if h > 0 else 1.0

        raw_arm_stroke = float(params.get("arm_stroke", defaults.get("arm_stroke", max(1.0, float(h) * 0.10))))
        cx = float(params.get("cx", defaults.get("cx", float(w) / 2.0)))
        cy = float(params.get("cy", defaults.get("cy", float(h) / 2.0)))
        r = float(params.get("r", defaults.get("r", float(h) * 0.4)))
        stroke_circle = float(params.get("stroke_circle", defaults.get("stroke_circle", max(0.9, float(h) / 15.0))))

        min_arm_stroke = max(1.0, stroke_circle * 0.75)
        max_arm_stroke = max(min_arm_stroke, min(float(h) * 0.14, stroke_circle * 1.6))
        arm_stroke = max(min_arm_stroke, min(raw_arm_stroke, max_arm_stroke))

        default_r = float(defaults.get("r", float(h) * 0.4))
        # Why circles can become too large here:
        # - AC0812 has a circle touching the right side and an extra left arm.
        # - On anti-aliased rasters, contour/Hough fitting may merge ring edge,
        #   arm and border pixels into one oversized blob.
        # Keep fitting adaptive, but bounded by generic geometric plausibility
        # instead of variant-specific hard caps. This keeps elongated connector
        # symbols (including AC0812_L-like forms) free to grow when needed while
        # still avoiding runaway radii from anti-aliased merged contours.
        canvas_r_limit = Action._max_circle_radius_inside_canvas(cx, cy, w, h, stroke_circle)
        max_r = max(default_r * 1.45, default_r + 3.0)
        max_r = min(max_r, canvas_r_limit)
        r = min(r, max_r)

        if h <= 15 and not bool(params.get("draw_text", True)):
            # Tiny plain connector badges can lose roughly one anti-aliased ring
            # pixel in contour/Hough fitting; keep them close to template size.
            r = max(r, default_r * 0.98)

        # Elongated connector badges are prone to under-estimating the ring when
        # the connector bleeds into the contour mask. Apply a generic floor for
        # broad, no-text forms rather than pinning a single SKU.
        if aspect_ratio >= 1.60 and h >= 20 and not bool(params.get("draw_text", True)):
            r = max(r, default_r * 0.95)

        params["r"] = r

        params["arm_enabled"] = True
        params["arm_stroke"] = arm_stroke
        params["arm_x1"] = 0.0
        params["arm_y1"] = cy
        params["arm_x2"] = max(0.0, cx - r)
        params["arm_y2"] = cy
        current_arm_len = float(math.hypot(params["arm_x2"] - params["arm_x1"], params["arm_y2"] - params["arm_y1"]))
        default_arm_len = max(
            0.0,
            float(defaults.get("cx", float(w) / 2.0)) - float(defaults.get("r", float(h) * 0.4)),
        )
        # Keep AC0812 connector geometry anchored to the semantic template. If we
        # derive the minimum arm length from an already-overgrown fitted circle,
        # later circle optimization can converge to the same unstable large-radius
        # solution. Use the template arm span as the lower bound baseline instead.
        semantic_arm_len_min = max(1.0, default_arm_len * 0.75)
        params["arm_len_min"] = max(1.0, current_arm_len * 0.75, semantic_arm_len_min)
        min_arm_len_ratio = 0.75
        # For elongated AC0812 variants (L-like forms), preserve a visibly long
        # connector arm so circle-fitting noise cannot eat too much horizontal
        # span. This keeps the left arm close to the semantic template.
        if aspect_ratio >= 1.60 and h >= 20 and not bool(params.get("draw_text", True)):
            min_arm_len_ratio = 0.82
        params["arm_len_min_ratio"] = float(max(float(params.get("arm_len_min_ratio", min_arm_len_ratio)), min_arm_len_ratio))
        params["arm_len_min"] = max(
            float(params["arm_len_min"]),
            max(1.0, current_arm_len * float(params["arm_len_min_ratio"]), semantic_arm_len_min),
        )

        # Expose a stable upper radius bound for later stochastic/adaptive circle
        # searches. This prevents left-arm AC0812 variants from re-growing the
        # circle and shortening the mandatory connector arm during optimization.
        max_r_from_arm_span = max(1.0, cx - params["arm_len_min"])
        params["max_circle_radius"] = float(min(canvas_r_limit, max_r_from_arm_span))
        return Action._normalize_light_circle_colors(params)

    @staticmethod
    def _enforce_left_arm_badge_geometry(params: dict, w: int, h: int) -> dict:
        """Ensure AC0812-like badges always keep a visible left connector arm."""
        p = dict(params)
        if not p.get("circle_enabled", True):
            return p
        if "cx" not in p or "cy" not in p or "r" not in p:
            return p

        cx = float(p["cx"])
        cy = float(p["cy"])
        r = float(p["r"])
        arm_x2 = max(0.0, cx - r)

        p["arm_enabled"] = True
        p["arm_x1"] = 0.0
        p["arm_y1"] = cy
        p["arm_x2"] = arm_x2
        p["arm_y2"] = cy
        p["arm_stroke"] = float(max(1.0, p.get("arm_stroke", Action.AC08_STROKE_WIDTH_PX)))

        arm_len = float(max(0.0, arm_x2))
        ratio = float(max(0.0, min(1.0, float(p.get("arm_len_min_ratio", 0.75)))))
        p["arm_len_min_ratio"] = ratio
        p["arm_len_min"] = float(max(1.0, float(p.get("arm_len_min", 1.0)), arm_len * ratio))
        return p

    @staticmethod
    def _default_ac0813_params(w: int, h: int) -> dict:
        """AC0813 is AC0812 rotated 90° clockwise (vertical arm from top to circle)."""
        if w <= 0 or h <= 0:
            return Action._default_ac081x_shared(w, h)

        # AC0813 is a vertically elongated symbol; like AC0811/AC0812 variants,
        # keep the circle sized from the narrow side so the top arm can reach it.
        r = float(w) * 0.4
        stroke_circle = max(0.9, float(w) / 15.0)
        cx = float(w) / 2.0
        cy = float(h) - (float(w) / 2.0)
        arm_stroke = max(1.0, float(w) * 0.10)

        return Action._normalize_light_circle_colors(
            {
                "cx": cx,
                "cy": cy,
                "r": r,
                "stroke_circle": stroke_circle,
                "stroke_gray": Action.LIGHT_CIRCLE_STROKE_GRAY,
                "fill_gray": Action.LIGHT_CIRCLE_FILL_GRAY,
                "draw_text": False,
                "arm_enabled": True,
                "arm_x1": cx,
                "arm_y1": 0.0,
                "arm_x2": cx,
                "arm_y2": max(0.0, cy - r),
                "arm_stroke": arm_stroke,
            }
        )

    @staticmethod
    def _fit_ac0813_params_from_image(img: np.ndarray, defaults: dict) -> dict:
        """Fit AC0813 while keeping the vertical arm anchored to the upper edge."""
        params = Action._fit_semantic_badge_from_image(img, defaults)
        h, w = img.shape[:2]

        raw_arm_stroke = float(params.get("arm_stroke", defaults.get("arm_stroke", max(1.0, float(w) * 0.10))))
        cx = float(params.get("cx", defaults.get("cx", float(w) / 2.0)))
        cy = float(params.get("cy", defaults.get("cy", float(h) - (float(w) / 2.0))))
        r = float(params.get("r", defaults.get("r", float(w) * 0.4)))
        stroke_circle = float(params.get("stroke_circle", defaults.get("stroke_circle", max(0.9, float(w) / 15.0))))

        min_arm_stroke = max(1.0, stroke_circle * 0.75)
        max_arm_stroke = max(min_arm_stroke, min(float(w) * 0.14, stroke_circle * 1.6))
        arm_stroke = max(min_arm_stroke, min(raw_arm_stroke, max_arm_stroke))

        # Tiny vertical badges with text overlays (e.g. AC0833_S / AC0838_S)
        # tend to be over-influenced by anti-aliased text pixels during contour
        # fitting. This can pull the circle downward and shrink its radius, which
        # shortens the visible top connector. Keep small variants close to the
        # semantic template geometry and only allow minimal vertical drift.
        if w <= 15 and bool(params.get("draw_text", False)):
            default_cx = float(defaults.get("cx", float(w) / 2.0))
            default_cy = float(defaults.get("cy", float(h) - (float(w) / 2.0)))
            default_r = float(defaults.get("r", float(w) * 0.4))
            params["cx"] = default_cx
            params["cy"] = float(_clip(cy, default_cy - 0.8, default_cy + 0.8))
            params["r"] = max(r, default_r * 0.94)
            params["lock_circle_cx"] = True
            params["lock_circle_cy"] = True
            params["lock_arm_center_to_circle"] = True
            cx = float(params["cx"])
            cy = float(params["cy"])
            r = float(params["r"])

        params["arm_enabled"] = True
        params["arm_stroke"] = arm_stroke
        params["arm_x1"] = cx
        params["arm_y1"] = 0.0
        params["arm_x2"] = cx
        params["arm_y2"] = max(0.0, cy - r)
        return Action._normalize_light_circle_colors(params)

    @staticmethod
    def _rotate_semantic_badge_clockwise(params: dict, w: int, h: int) -> dict:
        cx = float(w) / 2.0
        cy = float(h) / 2.0

        def rotate_clockwise(x: float, y: float) -> tuple[float, float]:
            # image-space clockwise description maps to mathematically counter-clockwise
            # because y grows downward in raster coordinates.
            return cx - (y - cy), cy + (x - cx)

        rotated = dict(params)
        rotated["cx"], rotated["cy"] = rotate_clockwise(float(params["cx"]), float(params["cy"]))
        rotated["arm_x1"], rotated["arm_y1"] = rotate_clockwise(float(params["arm_x1"]), float(params["arm_y1"]))
        rotated["arm_x2"], rotated["arm_y2"] = rotate_clockwise(float(params["arm_x2"]), float(params["arm_y2"]))
        return rotated

    @staticmethod
    def _default_ac0814_params(w: int, h: int) -> dict:
        """AC0814 is horizontally elongated: circle on the left, arm to the right."""
        if w <= 0 or h <= 0:
            return Action._default_ac081x_shared(w, h)

        # AC0812 source rasters leave a slightly larger vertical margin around the
        # ring than AC0811/AC0813. Using 0.40*h tends to over-size the circle.
        r = float(h) * 0.36
        stroke_circle = max(0.9, float(h) / 15.0)
        cx = float(h) / 2.0
        cy = float(h) / 2.0
        arm_stroke = max(1.0, float(h) * 0.10)

        return Action._normalize_light_circle_colors(
            {
                "cx": cx,
                "cy": cy,
                "r": r,
                "stroke_circle": stroke_circle,
                "stroke_gray": Action.LIGHT_CIRCLE_STROKE_GRAY,
                "fill_gray": Action.LIGHT_CIRCLE_FILL_GRAY,
                "draw_text": False,
                "arm_enabled": True,
                "arm_x1": min(float(w), cx + r),
                "arm_y1": cy,
                "arm_x2": float(w),
                "arm_y2": cy,
                "arm_stroke": arm_stroke,
                "arm_len_min": max(1.0, (float(w) - min(float(w), cx + r)) * 0.75),
                "arm_len_min_ratio": 0.75,
            }
        )

    @staticmethod
    def _fit_ac0814_params_from_image(img: np.ndarray, defaults: dict) -> dict:
        """Fit AC0814 while keeping the horizontal arm anchored to the right edge."""
        params = Action._fit_semantic_badge_from_image(img, defaults)
        h, w = img.shape[:2]

        raw_arm_stroke = float(params.get("arm_stroke", defaults.get("arm_stroke", max(1.0, float(h) * 0.10))))
        cx = float(params.get("cx", defaults.get("cx", float(w) / 2.0)))
        cy = float(params.get("cy", defaults.get("cy", float(h) / 2.0)))
        r = float(params.get("r", defaults.get("r", float(h) * 0.4)))
        stroke_circle = float(params.get("stroke_circle", defaults.get("stroke_circle", max(0.9, float(h) / 15.0))))

        min_arm_stroke = max(1.0, stroke_circle * 0.75)
        max_arm_stroke = max(min_arm_stroke, min(float(h) * 0.14, stroke_circle * 1.6))
        arm_stroke = max(min_arm_stroke, min(raw_arm_stroke, max_arm_stroke))

        cx = float(params.get("cx", defaults.get("cx", float(h) / 2.0)))
        cy = float(params.get("cy", defaults.get("cy", float(h) / 2.0)))
        r = float(params.get("r", defaults.get("r", float(h) * 0.4)))

        params["arm_enabled"] = True
        params["arm_stroke"] = arm_stroke
        params["arm_x1"] = min(float(w), cx + r)
        params["arm_y1"] = cy
        params["arm_x2"] = float(w)
        params["arm_y2"] = cy
        current_arm_len = float(math.hypot(params["arm_x2"] - params["arm_x1"], params["arm_y2"] - params["arm_y1"]))
        params["arm_len_min"] = max(1.0, current_arm_len * 0.75)
        return Action._normalize_light_circle_colors(params)

    @staticmethod
    def _default_ac0810_params(w: int, h: int) -> dict:
        """AC0810 uses the same right-arm geometry as AC0814 (circle on the left)."""
        return Action._default_ac0814_params(w, h)

    @staticmethod
    def _fit_ac0810_params_from_image(img: np.ndarray, defaults: dict) -> dict:
        """Fit AC0810 with the same right-anchored arm behavior as AC0814."""
        return Action._fit_ac0814_params_from_image(img, defaults)

    @staticmethod
    def _glyph_bbox(text_mode: str) -> tuple[int, int, int, int]:
        if text_mode == "path_t":
            return Action.T_XMIN, Action.T_YMIN, Action.T_XMAX, Action.T_YMAX
        return Action.M_XMIN, Action.M_YMIN, Action.M_XMAX, Action.M_YMAX

    @staticmethod
    def _center_glyph_bbox(params: dict) -> None:
        if "s" not in params or "cx" not in params or "cy" not in params:
            return
        xmin, ymin, xmax, ymax = Action._glyph_bbox(params.get("text_mode", "path"))
        glyph_width = (xmax - xmin) * params["s"]
        glyph_height = (ymax - ymin) * params["s"]
        params["tx"] = float(params["cx"] - (glyph_width / 2.0))
        params["ty"] = float(params["cy"] - (glyph_height / 2.0))

    @staticmethod
    def _stabilize_semantic_circle_pose(params: dict, defaults: dict, w: int, h: int) -> dict:
        """Bound fitted circle pose to semantic template geometry.

        Tiny, low-information raster variants are especially sensitive to JPEG
        edge artifacts. For connector-only badges without text, prefer the
        semantic template center and keep radius from collapsing.
        """
        if "r" not in defaults:
            return params

        default_cx = float(defaults.get("cx", float(w) / 2.0))
        default_cy = float(defaults.get("cy", float(h) / 2.0))
        default_r = float(defaults.get("r", 0.0))
        if default_r <= 0.0:
            return params

        has_connector = bool(params.get("arm_enabled") or params.get("stem_enabled"))
        has_text = bool(params.get("draw_text", False))
        if not has_connector:
            return params

        if not has_text and min(w, h) <= 16:
            params["cx"] = default_cx
            params["cy"] = default_cy
            params["r"] = max(float(params.get("r", default_r)), default_r * 0.96)
            params["lock_circle_cx"] = True
            params["lock_circle_cy"] = True
            return params

        # Keep semantic drift bounded, but allow enough travel that larger source
        # variants (especially AC081x line+circle symbols) can still land on the
        # visually correct center when Hough/contours detect a shifted ring.
        cx_tolerance = max(1.5, float(min(w, h)) * 0.18)
        cy_tolerance = max(1.5, float(min(w, h)) * 0.18)
        current_cx = float(params.get("cx", default_cx))
        current_cy = float(params.get("cy", default_cy))
        params["cx"] = float(max(default_cx - cx_tolerance, min(default_cx + cx_tolerance, current_cx)))
        params["cy"] = float(max(default_cy - cy_tolerance, min(default_cy + cy_tolerance, current_cy)))
        min_radius = max(1.0, default_r * 0.80)
        max_radius = max(min_radius, default_r * 1.45)
        current_r = float(params.get("r", default_r))
        params["r"] = float(max(min_radius, min(max_radius, current_r)))
        return params

    def _fit_ac0870_params_from_image(img: np.ndarray, defaults: dict) -> dict:
        params = dict(defaults)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        min_side = float(min(h, w))
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.0,
            minDist=max(8.0, min_side * 0.5),
            param1=100,
            param2=10,
            minRadius=max(4, int(round(min_side * 0.25))),
            maxRadius=max(6, int(round(min_side * 0.48))),
        )


        if circles is not None and circles.size > 0:
            best = None
            template_cx = float(defaults.get("cx", params.get("cx", float(w) / 2.0)))
            template_cy = float(defaults.get("cy", params.get("cy", float(h) / 2.0)))
            template_r = float(defaults.get("r", params.get("r", max(1.0, min_side * 0.35))))
            max_center_offset = max(2.0, min_side * 0.42)
            max_radius_delta = max(2.0, template_r * 0.70)
            for c in circles[0]:
                cx, cy, r = float(c[0]), float(c[1]), float(c[2])
                center_offset = float(math.hypot(cx - template_cx, cy - template_cy))
                # Semantic AC08xx badges follow a fixed layout. Reject detections
                # that drift too far away from the expected template center; on
                # tiny CO₂/VOC symbols those are usually text blobs, not circles.
                if center_offset > max_center_offset:
                    continue
                yy, xx = np.indices(gray.shape)
                dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
                fill_mask = dist <= max(1.0, r * 0.82)
                ring_mask = np.abs(dist - r) <= max(1.0, params.get("stroke_circle", 1.2))
                if not np.any(fill_mask) or not np.any(ring_mask):
                    continue
                fill_gray = float(np.median(gray[fill_mask]))
                ring_gray = float(np.median(gray[ring_mask]))
                score = abs(fill_gray - 220.0) + abs(ring_gray - 152.0)
                # Prefer circles that stay close to the semantic template size/
                # position so all AC08xx variants remain stable across JPEG noise.
                score += (center_offset / max_center_offset) * 9.0
                score += (abs(r - template_r) / max_radius_delta) * 6.0
                if best is None or score < best[0]:
                    best = (score, cx, cy, r, fill_gray, ring_gray)

            if best is not None:
                _, cx, cy, r, fill_gray, ring_gray = best
                params["cx"] = cx
                params["cy"] = cy
                params["r"] = r
                params["fill_gray"] = int(round(fill_gray))
                params["stroke_gray"] = int(round(ring_gray))

        # Keep contour/Hough noise from collapsing circles far below the semantic
        # template size. This was most visible for compact centered badges
        # (e.g. AC0820_M), but the guard is intentionally generic for the full
        # semantic badge family.
        if "r" in defaults and "r" in params:
            default_r = float(defaults.get("r", 0.0))
            if default_r > 0.0:
                has_connector = bool(params.get("arm_enabled") or params.get("stem_enabled"))
                has_text = bool(params.get("draw_text", False))
                min_ratio = 0.80
                if not has_connector:
                    min_ratio = 0.88
                if has_text and not has_connector:
                    min_ratio = 0.92

                cx = float(params.get("cx", defaults.get("cx", float(w) / 2.0)))
                cy = float(params.get("cy", defaults.get("cy", float(h) / 2.0)))
                stroke = max(0.0, float(params.get("stroke_circle", defaults.get("stroke_circle", 1.0))))
                radius_limit_x = max(1.0, min(cx, float(w) - cx) - (stroke / 2.0))
                radius_limit_y = max(1.0, min(cy, float(h) - cy) - (stroke / 2.0))
                max_r = max(1.0, min(radius_limit_x, radius_limit_y))
                min_r = min(max_r, max(1.0, default_r * min_ratio))
                params["r"] = float(_clip(float(params.get("r", default_r)), min_r, max_r))

        if params.get("stem_enabled"):
            dark = gray <= min(225, int(np.percentile(gray, 75)))
            x1 = max(0, int(round(params["cx"] - params["r"] * 0.8)))
            x2 = min(w, int(round(params["cx"] + params["r"] * 0.8)))
            y1 = max(0, int(round(params["cy"] + params["r"] * 0.45)))
            roi = dark[y1:h, x1:x2]
            if roi.size > 0:
                cnts, _ = cv2.findContours(roi.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                best_rect = None
                for cnt in cnts:
                    rx, ry, rw, rh = cv2.boundingRect(cnt)
                    if rw < 1 or rh < 2 or rh <= rw:
                        continue
                    area = rw * rh
                    if best_rect is None or area > best_rect[0]:
                        best_rect = (area, rx, ry, rw, rh)
                if best_rect is not None:
                    _, rx, ry, rw, rh = best_rect
                    params["stem_x"] = float(x1 + rx)
                    params["stem_top"] = float(y1 + ry)
                    params["stem_width"] = float(max(1, rw))
                    params["stem_bottom"] = float(min(h, y1 + ry + rh))
                    stem_mask = np.zeros_like(gray, dtype=bool)
                    sx1 = int(max(0, params["stem_x"]))
                    sx2 = int(min(w, params["stem_x"] + params["stem_width"]))
                    sy1 = int(max(0, params["stem_top"]))
                    sy2 = int(min(h, params["stem_bottom"]))
                    stem_mask[sy1:sy2, sx1:sx2] = True
                    stem_vals = gray[stem_mask]
                    if stem_vals.size > 0:
                        params["stem_gray"] = int(round(np.median(stem_vals)))

        if params.get("arm_enabled"):
            dark = gray <= min(225, int(np.percentile(gray, 75)))
            is_horizontal = abs(params.get("arm_x2", 0.0) - params.get("arm_x1", 0.0)) >= abs(
                params.get("arm_y2", 0.0) - params.get("arm_y1", 0.0)
            )
            if is_horizontal:
                side = -1 if params.get("arm_x2", 0.0) <= params.get("cx", 0.0) else 1
                y1 = max(0, int(round(params["cy"] - params["r"] * 0.6)))
                y2 = min(h, int(round(params["cy"] + params["r"] * 0.6)))
                if side < 0:
                    x1 = max(0, int(round(params["cx"] - params["r"] * 2.0)))
                    x2 = max(0, int(round(params["cx"] - params["r"] * 0.4)))
                else:
                    x1 = min(w, int(round(params["cx"] + params["r"] * 0.4)))
                    x2 = min(w, int(round(params["cx"] + params["r"] * 2.0)))
            else:
                x1 = max(0, int(round(params["cx"] - params["r"] * 0.6)))
                x2 = min(w, int(round(params["cx"] + params["r"] * 0.6)))
                y1 = max(0, int(round(params["cy"] - params["r"] * 2.0)))
                y2 = max(0, int(round(params["cy"] - params["r"] * 0.4)))

            roi = dark[y1:y2, x1:x2] if y2 > y1 and x2 > x1 else None
            if roi is not None and roi.size > 0:
                cnts, _ = cv2.findContours(roi.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                best_rect = None
                for cnt in cnts:
                    rx, ry, rw, rh = cv2.boundingRect(cnt)
                    if rw < 1 or rh < 1:
                        continue
                    elong = (rw / max(1, rh)) if is_horizontal else (rh / max(1, rw))
                    if elong < 1.2:
                        continue
                    area = rw * rh
                    if best_rect is None or area > best_rect[0]:
                        best_rect = (area, rx, ry, rw, rh)
                if best_rect is not None:
                    _, rx, ry, rw, rh = best_rect
                    if is_horizontal:
                        params["arm_x1"] = float(x1 + rx)
                        params["arm_x2"] = float(x1 + rx + rw)
                        y = float(y1 + ry + rh / 2.0)
                        params["arm_y1"] = y
                        params["arm_y2"] = y
                        params["arm_stroke"] = float(max(1.0, rh))
                    else:
                        x = float(x1 + rx + rw / 2.0)
                        params["arm_x1"] = x
                        params["arm_x2"] = x
                        params["arm_y1"] = float(y1 + ry)
                        params["arm_y2"] = float(y1 + ry + rh)
                        params["arm_stroke"] = float(max(1.0, rw))

        params = Action._stabilize_semantic_circle_pose(params, defaults, w, h)

        if params.get("draw_text", True) and params.get("text_mode") in {"path", "path_t"}:
            Action._center_glyph_bbox(params)
        return Action._normalize_light_circle_colors(params)

    @staticmethod
    def make_badge_params(w: int, h: int, base_name: str, img: np.ndarray | None = None) -> dict | None:
        name = base_name.upper()

        if name == "AR0100":
            scale = min(w, h) / 25.0 if min(w, h) > 0 else 1.0
            b = Action.AR0100_BASE
            params = {
                "cx": b["cx"] * scale,
                "cy": b["cy"] * scale,
                "r": b["r"] * scale,
                "stroke_circle": b["stroke_width"] * scale,
                "fill_gray": b["fill_gray"],
                "stroke_gray": b["stroke_gray"],
                "text_gray": b["text_gray"],
                "tx": b["tx"] * scale,
                "ty": b["ty"] * scale,
                "s": b["s"] * scale,
                "label": "M",
                "text_mode": "path",
            }
            Action._center_glyph_bbox(params)
            return params

        if name == "AC0870":
            defaults = Action._default_ac0870_params(w, h)
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_ac0870_params_from_image(img, defaults))

        if name == "AC0800":
            scale = min(w, h) / 30.0 if min(w, h) > 0 else 1.0
            defaults = {
                "cx": 15.0 * scale,
                "cy": 15.0 * scale,
                "r": 12.0 * scale,
                "stroke_circle": 2.0 * scale,
                "fill_gray": 220,
                "stroke_gray": 152,
                "draw_text": False,
            }
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_semantic_badge_from_image(img, defaults))

        if name == "AC0811":
            defaults = Action._default_ac0811_params(w, h)
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_ac0811_params_from_image(img, defaults))

        if name == "AC0810":
            defaults = Action._default_ac0810_params(w, h)
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_ac0810_params_from_image(img, defaults))

        if name == "AC0812":
            defaults = Action._default_ac0812_params(w, h)
            if img is None:
                return Action._enforce_left_arm_badge_geometry(Action._finalize_ac08_style(name, defaults), w, h)
            return Action._enforce_left_arm_badge_geometry(
                Action._finalize_ac08_style(name, Action._fit_ac0812_params_from_image(img, defaults)),
                w,
                h,
            )

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

            if ref_path:
                ref_img = cv2.imread(ref_path)
                ref_h, ref_w = ref_img.shape[:2]
                cut_ratio = 0.55
                cut_y = max(1, int(round(ref_h * cut_ratio)))
                top_half_img = ref_img[0:cut_y, 0:ref_w]
                target_top_h = max(1, int(round(h * cut_ratio)))
                scale_x = w / ref_w if ref_w > 0 else 1.0
                scale_y = target_top_h / cut_y if cut_y > 0 else 1.0
                svg_elements.extend(
                    Action.trace_image_segment(
                        top_half_img,
                        epsilon,
                        scale_x=scale_x,
                        scale_y=scale_y,
                    )
                )

        if params["bottom_shape"] == "square_cross":
            cx = w / 2
            cy = h * 0.75
            s = min(w, h) * 0.15
            sw = w * 0.02
            svg_elements.append(
                f'  <rect x="{cx-s}" y="{cy-s}" width="{s*2}" height="{s*2}" fill="#e6e6e6" stroke="#4d4d4d" stroke-width="{sw}"/>'
            )
            svg_elements.append(
                f'  <line x1="{cx-s}" y1="{cy-s}" x2="{cx+s}" y2="{cy+s}" stroke="#4d4d4d" stroke-width="{sw}"/>'
            )
            svg_elements.append(
                f'  <line x1="{cx+s}" y1="{cy-s}" x2="{cx-s}" y2="{cy+s}" stroke="#4d4d4d" stroke-width="{sw}"/>'
            )

        svg_elements.append("</svg>")
        return "\n".join(svg_elements)

    @staticmethod
    def render_svg_to_numpy(svg_string: str, size_w: int, size_h: int):
        if fitz is None:
            return None
        doc = fitz.open("pdf", svg_string.encode("utf-8"))
        page = doc.load_page(0)
        zoom_x = size_w / page.rect.width if page.rect.width > 0 else 1
        zoom_y = size_h / page.rect.height if page.rect.height > 0 else 1
        mat = fitz.Matrix(zoom_x, zoom_y)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    @staticmethod
    def create_diff_image(
        img_orig: np.ndarray,
        img_svg: np.ndarray,
        focus_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        if img_svg.shape[:2] != img_orig.shape[:2]:
            img_svg = cv2.resize(img_svg, (img_orig.shape[1], img_orig.shape[0]), interpolation=cv2.INTER_AREA)
        gray_orig = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
        gray_svg = cv2.cvtColor(img_svg, cv2.COLOR_BGR2GRAY)

        if focus_mask is not None:
            if focus_mask.shape[:2] != img_orig.shape[:2]:
                focus_mask = cv2.resize(
                    focus_mask.astype(np.uint8),
                    (img_orig.shape[1], img_orig.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                )
            mask = focus_mask > 0
            gray_orig = np.where(mask, gray_orig, 0).astype(np.uint8)
            gray_svg = np.where(mask, gray_svg, 0).astype(np.uint8)

        diff = np.zeros_like(img_orig)
        diff[:, :, 2] = gray_orig
        diff[:, :, 1] = gray_svg
        diff[:, :, 0] = gray_svg
        return diff

    @staticmethod
    def calculate_error(img_orig: np.ndarray, img_svg: np.ndarray) -> float:
        if img_svg is None:
            return float("inf")
        if img_svg.shape[:2] != img_orig.shape[:2]:
            img_svg = cv2.resize(img_svg, (img_orig.shape[1], img_orig.shape[0]), interpolation=cv2.INTER_AREA)
        return float(np.mean(cv2.absdiff(img_orig, img_svg)))

    @staticmethod
    def calculate_delta2_stats(img_orig: np.ndarray, img_svg: np.ndarray) -> tuple[float, float]:
        """Return mean/std of per-pixel squared RGB deltas.

        Per-pixel metric:
            delta2 = (ΔR)^2 + (ΔG)^2 + (ΔB)^2
        """
        if img_svg is None:
            return float("inf"), float("inf")
        if img_svg.shape[:2] != img_orig.shape[:2]:
            img_svg = cv2.resize(img_svg, (img_orig.shape[1], img_orig.shape[0]), interpolation=cv2.INTER_AREA)
        diff = img_orig.astype(np.float32) - img_svg.astype(np.float32)
        delta2 = np.sum(diff * diff, axis=2)
        return float(np.mean(delta2)), float(np.std(delta2))

    @staticmethod
    def _fit_to_original_size(img_orig: np.ndarray, img_svg: np.ndarray | None) -> np.ndarray | None:
        if img_svg is None:
            return None
        if img_svg.shape[:2] == img_orig.shape[:2]:
            return img_svg
        return cv2.resize(img_svg, (img_orig.shape[1], img_orig.shape[0]), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _mask_centroid_radius(mask: np.ndarray) -> tuple[float, float, float] | None:
        ys, xs = np.where(mask)
        if xs.size < 5:
            return None
        cx = float(np.mean(xs))
        cy = float(np.mean(ys))
        r = float(np.sqrt(xs.size / np.pi))
        return cx, cy, r

    @staticmethod
    def _mask_bbox(mask: np.ndarray) -> tuple[float, float, float, float] | None:
        ys, xs = np.where(mask)
        if xs.size < 3:
            return None
        x1, x2 = float(xs.min()), float(xs.max())
        y1, y2 = float(ys.min()), float(ys.max())
        return x1, y1, x2, y2

    @staticmethod
    def _mask_center_size(mask: np.ndarray) -> tuple[float, float, float] | None:
        bbox = Action._mask_bbox(mask)
        if bbox is None:
            return None
        x1, y1, x2, y2 = bbox
        width = max(1.0, (x2 - x1) + 1.0)
        height = max(1.0, (y2 - y1) + 1.0)
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        size = width * height
        return cx, cy, size

    @staticmethod
    def _mask_min_rect_center_diag(mask: np.ndarray) -> tuple[float, float, float] | None:
        mask_u8 = (mask.astype(np.uint8)) * 255
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        cnt = max(contours, key=cv2.contourArea)
        if cv2.contourArea(cnt) < 2.0:
            return None

        (cx, cy), (rw, rh), _angle = cv2.minAreaRect(cnt)
        diag = float(math.hypot(float(rw), float(rh)))
        if not _isfinite(diag) or diag <= 0.0:
            return None
        return float(cx), float(cy), diag

    @staticmethod
    def _element_bbox_change_is_plausible(
        mask_orig: np.ndarray,
        mask_svg: np.ndarray,
    ) -> tuple[bool, str | None]:
        """Reject clearly implausible box drifts between source and converted element."""
        orig_bbox = Action._mask_bbox(mask_orig)
        svg_bbox = Action._mask_bbox(mask_svg)
        if orig_bbox is None or svg_bbox is None:
            return True, None

        ox1, oy1, ox2, oy2 = orig_bbox
        sx1, sy1, sx2, sy2 = svg_bbox

        ow = max(1.0, (ox2 - ox1) + 1.0)
        oh = max(1.0, (oy2 - oy1) + 1.0)
        sw = max(1.0, (sx2 - sx1) + 1.0)
        sh = max(1.0, (sy2 - sy1) + 1.0)

        ocx = (ox1 + ox2) / 2.0
        ocy = (oy1 + oy2) / 2.0
        scx = (sx1 + sx2) / 2.0
        scy = (sy1 + sy2) / 2.0

        center_dist = float(math.hypot(scx - ocx, scy - ocy))
        orig_diag = float(math.hypot(ow, oh))
        max_center_dist = max(2.0, orig_diag * 0.42)

        w_ratio = sw / ow
        h_ratio = sh / oh
        area_ratio = (sw * sh) / max(1.0, ow * oh)

        if center_dist > max_center_dist:
            return (
                False,
                (
                    "Box-Check verworfen "
                    f"(Δcenter={center_dist:.3f} > {max_center_dist:.3f})"
                ),
            )

        if not (0.55 <= w_ratio <= 1.85 and 0.55 <= h_ratio <= 1.85 and 0.40 <= area_ratio <= 2.40):
            return (
                False,
                (
                    "Box-Check verworfen "
                    f"(w_ratio={w_ratio:.3f}, h_ratio={h_ratio:.3f}, area_ratio={area_ratio:.3f})"
                ),
            )

        return True, None

    @staticmethod
    def _apply_element_alignment_step(
        params: dict,
        element: str,
        center_dx: float,
        center_dy: float,
        diag_scale: float,
        w: int,
        h: int,
        apply_circle_geometry_penalty: bool = True,
    ) -> bool:
        changed = False
        scale = float(_clip(diag_scale, 0.85, 1.18))

        if element == "circle" and apply_circle_geometry_penalty:
            old_cx = float(params["cx"])
            old_cy = float(params["cy"])
            old_r = float(params["r"])
            min_r = float(max(1.0, params.get("min_circle_radius", 1.0)))
            if bool(params.get("lock_circle_cx", False)):
                params["cx"] = old_cx
            else:
                params["cx"] = float(_clip(old_cx + center_dx * 0.65, 0.0, float(w - 1)))
            if bool(params.get("lock_circle_cy", False)):
                params["cy"] = old_cy
            else:
                params["cy"] = float(_clip(old_cy + center_dy * 0.65, 0.0, float(h - 1)))
            params["r"] = float(_clip(old_r * scale, min_r, float(min(w, h)) * 0.48))
            changed = (
                abs(params["cx"] - old_cx) > 0.02
                or abs(params["cy"] - old_cy) > 0.02
                or abs(params["r"] - old_r) > 0.02
            )

        elif element == "stem" and params.get("stem_enabled"):
            old_x = float(params["stem_x"])
            old_w = float(params["stem_width"])
            old_top = float(params["stem_top"])
            old_bottom = float(params["stem_bottom"])

            stem_cx = old_x + (old_w / 2.0)
            if bool(params.get("lock_stem_center_to_circle", False)):
                stem_cx = float(params.get("cx", stem_cx))
            else:
                stem_cx = float(_clip(stem_cx + center_dx * 0.75, 0.0, float(w - 1)))
            new_w = float(_clip(old_w * scale, 1.0, float(w) * 0.22))
            params["stem_width"] = new_w
            params["stem_x"] = float(_clip(stem_cx - (new_w / 2.0), 0.0, float(w) - new_w))
            params["stem_top"] = float(_clip(old_top + center_dy * 0.45, 0.0, float(h - 2)))
            params["stem_bottom"] = float(_clip(old_bottom + center_dy * 0.25, params["stem_top"] + 1.0, float(h - 1)))
            changed = (
                abs(params["stem_x"] - old_x) > 0.02
                or abs(params["stem_width"] - old_w) > 0.02
                or abs(params["stem_top"] - old_top) > 0.02
                or abs(params["stem_bottom"] - old_bottom) > 0.02
            )

        elif element == "arm" and params.get("arm_enabled"):
            old_x1 = float(params["arm_x1"])
            old_x2 = float(params["arm_x2"])
            old_y1 = float(params["arm_y1"])
            old_y2 = float(params["arm_y2"])
            old_stroke = float(params.get("arm_stroke", params.get("stem_or_arm", 1.0)))

            ax1 = old_x1 + center_dx * 0.75
            ax2 = old_x2 + center_dx * 0.75
            ay1 = old_y1 + center_dy * 0.75
            ay2 = old_y2 + center_dy * 0.75
            acx = (ax1 + ax2) / 2.0
            acy = (ay1 + ay2) / 2.0
            vx = (ax2 - ax1) * scale
            vy = (ay2 - ay1) * scale

            params["arm_x1"] = float(_clip(acx - (vx / 2.0), 0.0, float(w - 1)))
            params["arm_x2"] = float(_clip(acx + (vx / 2.0), 0.0, float(w - 1)))
            params["arm_y1"] = float(_clip(acy - (vy / 2.0), 0.0, float(h - 1)))
            params["arm_y2"] = float(_clip(acy + (vy / 2.0), 0.0, float(h - 1)))
            params["arm_stroke"] = float(_clip(old_stroke * scale, 1.0, float(min(w, h)) * 0.18))
            changed = (
                abs(params["arm_x1"] - old_x1) > 0.02
                or abs(params["arm_x2"] - old_x2) > 0.02
                or abs(params["arm_y1"] - old_y1) > 0.02
                or abs(params["arm_y2"] - old_y2) > 0.02
                or abs(params["arm_stroke"] - old_stroke) > 0.02
            )

        elif element == "text" and params.get("draw_text", True):
            mode = str(params.get("text_mode", "")).lower()
            r = max(1.0, float(params.get("r", min(w, h) * 0.45)))

            # Keep text alignment iterative on the vertical axis so badges such as
            # AC0820_L can converge against the source when "CO" drifts too high.
            if mode == "co2":
                old_dy = float(params.get("co2_dy", 0.0))
                params["co2_dy"] = float(_clip(old_dy + center_dy * 0.75, -0.45 * r, 0.45 * r))
                changed = abs(params["co2_dy"] - old_dy) > 0.02
            elif mode == "voc":
                old_dy = float(params.get("voc_dy", 0.0))
                params["voc_dy"] = float(_clip(old_dy + center_dy * 0.75, -0.45 * r, 0.45 * r))
                changed = abs(params["voc_dy"] - old_dy) > 0.02
            elif "ty" in params:
                old_ty = float(params.get("ty", 0.0))
                params["ty"] = float(_clip(old_ty + center_dy * 0.75, 0.0, float(h - 1)))
                changed = abs(params["ty"] - old_ty) > 0.02

        return changed

    @staticmethod
    def _estimate_vertical_stem_from_mask(
        mask: np.ndarray,
        expected_cx: float,
        y_start: int,
        y_end: int,
    ) -> tuple[float, float] | None:
        """Estimate stem center/width from foreground mask rows.

        The estimate is intentionally iterative: we repeatedly reject outliers around
        the running median width so anti-aliased pixels at the circle junction do not
        inflate the final width.
        """
        h, w = mask.shape[:2]
        y1 = max(0, min(h, int(y_start)))
        y2 = max(y1, min(h, int(y_end)))
        if y2 <= y1:
            return None

        # The rows directly below the circle/stem junction are frequently widened
        # by anti-aliased ring pixels. Bias the estimator towards the lower stem
        # segment so thin stems (e.g. tall AC0811 variants) are not over-thickened.
        span = y2 - y1
        if span >= 8:
            y1 = min(y2 - 1, y1 + int(round(span * 0.25)))

        widths: list[float] = []
        centers: list[float] = []
        cx_idx = int(round(expected_cx))

        for y in range(y1, y2):
            row = mask[y]
            xs = np.where(row)[0]
            if xs.size == 0:
                continue

            split_points = np.where(np.diff(xs) > 1)[0]
            runs = np.split(xs, split_points + 1)
            if not runs:
                continue

            # Prefer the run that contains the expected center, otherwise nearest run.
            chosen = None
            nearest_dist = float("inf")
            for run in runs:
                rx1, rx2 = int(run[0]), int(run[-1])
                if rx1 <= cx_idx <= rx2:
                    chosen = run
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

        x1 = int(np.floor(min(b[0] for b in boxes)))
        y1 = int(np.floor(min(b[1] for b in boxes)))
        x2 = int(np.ceil(max(b[2] for b in boxes)))
        y2 = int(np.ceil(max(b[3] for b in boxes)))
        return x1, y1, x2, y2

    @staticmethod
    def _masked_union_error_in_bbox(
        img_orig: np.ndarray,
        img_svg: np.ndarray,
        mask_orig: np.ndarray | None,
        mask_svg: np.ndarray | None,
    ) -> float:
        """Symmetric masked error, cropped to the smallest rectangle around both masks."""
        if img_svg is None or mask_orig is None or mask_svg is None:
            return float("inf")
        if img_svg.shape[:2] != img_orig.shape[:2]:
            img_svg = cv2.resize(img_svg, (img_orig.shape[1], img_orig.shape[0]), interpolation=cv2.INTER_AREA)

        bbox = Action._union_bbox_from_masks(mask_orig, mask_svg)
        if bbox is None:
            return float("inf")

        h, w = img_orig.shape[:2]
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(x1, min(w - 1, x2))
        y2 = max(y1, min(h - 1, y2))

        orig_crop = img_orig[y1 : y2 + 1, x1 : x2 + 1]
        svg_crop = img_svg[y1 : y2 + 1, x1 : x2 + 1]
        union_mask = mask_orig[y1 : y2 + 1, x1 : x2 + 1] | mask_svg[y1 : y2 + 1, x1 : x2 + 1]
        if int(np.sum(union_mask)) <= 0:
            return float("inf")

        gray_diff = cv2.cvtColor(cv2.absdiff(orig_crop, svg_crop), cv2.COLOR_BGR2GRAY).astype(np.float32)
        return float(np.sum(gray_diff * union_mask.astype(np.float32)))

    @staticmethod
    def _element_match_error(
        img_orig: np.ndarray,
        img_svg: np.ndarray,
        params: dict,
        element: str,
        *,
        mask_orig: np.ndarray | None = None,
        mask_svg: np.ndarray | None = None,
        apply_circle_geometry_penalty: bool = True,
    ) -> float:
        """Element score for optimization: localization + redraw + symmetric compare.

        The score combines:
        - photometric difference in the union bbox of source/candidate element masks
        - overlap quality (IoU)
        - explicit penalties for missing source pixels and extra candidate pixels

        This keeps exploration broad, but accepts candidates only when the element
        truly matches better (not merely by shrinking or drifting outside the source mask).
        """
        if img_svg is None:
            return float("inf")
        if img_svg.shape[:2] != img_orig.shape[:2]:
            img_svg = cv2.resize(img_svg, (img_orig.shape[1], img_orig.shape[0]), interpolation=cv2.INTER_AREA)

        local_mask_orig = mask_orig if mask_orig is not None else Action.extract_badge_element_mask(img_orig, params, element)
        local_mask_svg = mask_svg if mask_svg is not None else Action.extract_badge_element_mask(img_svg, params, element)
        if local_mask_orig is None or local_mask_svg is None:
            return float("inf")

        orig_area = float(np.sum(local_mask_orig))
        svg_area = float(np.sum(local_mask_svg))
        if orig_area <= 0.0 or svg_area <= 0.0:
            return float("inf")

        photo_err = float(Action._masked_union_error_in_bbox(img_orig, img_svg, local_mask_orig, local_mask_svg))
        if not _isfinite(photo_err):
            return float("inf")

        inter = float(np.sum(local_mask_orig & local_mask_svg))
        union = float(np.sum(local_mask_orig | local_mask_svg))
        if union <= 0.0:
            return float("inf")

        miss = float(np.sum(local_mask_orig & (~local_mask_svg))) / orig_area
        extra = float(np.sum(local_mask_svg & (~local_mask_orig))) / orig_area
        iou = inter / union

        # Normalize photometric term by source element area so comparisons stay
        # meaningful across sizes (S/M/L variants).
        photo_norm = photo_err / max(1.0, orig_area)

        # Circle optimization should prefer concentric matches and avoid shrinking
        # to the smallest ring that still overlaps the arm/label neighborhood.
        # The mask overlap terms above are necessary but can be too permissive
        # when anti-aliased JPEG edges blur circle/connector boundaries.
        if element == "circle" and apply_circle_geometry_penalty:
            src_circle = Action._mask_centroid_radius(local_mask_orig)
            cand_circle = Action._mask_centroid_radius(local_mask_svg)
            if src_circle is not None and cand_circle is not None:
                src_cx, src_cy, src_r = src_circle
                cand_cx, cand_cy, cand_r = cand_circle
                center_dist = float(math.hypot(cand_cx - src_cx, cand_cy - src_cy))
                center_norm = center_dist / max(1.0, src_r)
                # Penalize undersized rings more strongly than oversized ones so
                # AC0812-like badges keep a readable radius in optimization.
                undersize_ratio = max(0.0, (src_r - cand_r) / max(1.0, src_r))
                extra += undersize_ratio * 0.35
                miss += undersize_ratio * 0.45
                iou = max(0.0, iou - min(0.35, undersize_ratio * 0.55))
                photo_norm += center_norm * 2.8

        return float(photo_norm + (38.0 * miss) + (24.0 * extra) + (18.0 * (1.0 - iou)))

    @staticmethod
    def _capture_canonical_badge_colors(params: dict) -> dict:
        p = dict(params)
        p["target_fill_gray"] = int(round(float(p.get("fill_gray", Action.LIGHT_CIRCLE_FILL_GRAY))))
        p["target_stroke_gray"] = int(round(float(p.get("stroke_gray", Action.LIGHT_CIRCLE_STROKE_GRAY))))
        if p.get("stem_enabled"):
            p["target_stem_gray"] = int(round(float(p.get("stem_gray", p["target_stroke_gray"]))))
        if p.get("draw_text", True) and "text_gray" in p:
            p["target_text_gray"] = int(round(float(p.get("text_gray", Action.LIGHT_CIRCLE_TEXT_GRAY))))
        return p

    @staticmethod
    def _apply_canonical_badge_colors(params: dict) -> dict:
        p = dict(params)
        if "target_fill_gray" in p:
            p["fill_gray"] = int(p["target_fill_gray"])
        if "target_stroke_gray" in p:
            p["stroke_gray"] = int(p["target_stroke_gray"])
        if p.get("stem_enabled") and "target_stem_gray" in p:
            p["stem_gray"] = int(p["target_stem_gray"])
        if p.get("draw_text", True) and "target_text_gray" in p:
            p["text_gray"] = int(p["target_text_gray"])
        return p

    @staticmethod
    def _circle_bounds(params: dict, w: int, h: int) -> tuple[float, float, float, float, float, float]:
        min_r = float(max(1.0, params.get("min_circle_radius", 1.0)))
        max_r = max(min_r, float(min(w, h)) * 0.48)
        cx = float(params.get("cx", float(w) / 2.0))
        cy = float(params.get("cy", float(h) / 2.0))
        stroke = float(params.get("stroke_circle", 0.0))
        max_r = min(max_r, Action._max_circle_radius_inside_canvas(cx, cy, w, h, stroke))
        if "max_circle_radius" in params:
            max_r = min(max_r, float(params.get("max_circle_radius", max_r)))
        return 0.0, float(w - 1), 0.0, float(h - 1), min_r, max_r

    @staticmethod
    def _stochastic_survivor_scalar(
        current_value: float,
        low: float,
        high: float,
        evaluate,
        *,
        snap,
        seed: int,
        iterations: int = 20,
    ) -> tuple[float, float, bool]:
        """Random 3-candidate survivor search for a scalar parameter."""
        cur = float(snap(float(_clip(current_value, low, high))))
        best_value = cur
        best_err = float(evaluate(best_value))
        if not _isfinite(best_err):
            return best_value, best_err, False

        rng_seed = int(seed) + int(Action.STOCHASTIC_SEED_OFFSET)
        rng = np.random.default_rng(rng_seed) if np is not None else random.Random(rng_seed)
        span = max(0.5, abs(high - low) * 0.22)
        improved = False
        stable_rounds = 0

        for _ in range(max(1, iterations)):
            candidates = [best_value]
            for _j in range(2):
                if np is not None:
                    raw_sample = float(rng.normal(best_value, span))
                else:
                    raw_sample = float(rng.gauss(best_value, span))
                sample = float(_clip(raw_sample, low, high))
                candidates.append(float(snap(sample)))

            scored: list[tuple[float, float]] = []
            for cand in candidates:
                err = float(evaluate(cand))
                if _isfinite(err):
                    scored.append((cand, err))
            if not scored:
                continue
            scored.sort(key=lambda pair: pair[1])
            cand_best, cand_err = scored[0]
            if cand_err + 0.05 < best_err:
                best_value, best_err = cand_best, cand_err
                improved = True
                stable_rounds = 0
            else:
                stable_rounds += 1

            span = max(0.2, span * 0.90)
            if stable_rounds >= 6:
                break

        return best_value, best_err, improved

    @staticmethod
    def _optimize_circle_pose_stochastic_survivor(
        img_orig: np.ndarray,
        params: dict,
        logs: list[str],
        *,
        iterations: int = 24,
    ) -> bool:
        """Stochastic 3-candidate survivor search for circle pose.

        Draw 3 random candidates per round, discard the worst, and continue from
        the best survivor with shrinking perturbation.
        """
        if not params.get("circle_enabled", True):
            return False

        h, w = img_orig.shape[:2]
        x_low, x_high, y_low, y_high, r_low, r_high = Action._circle_bounds(params, w, h)
        current = (
            Action._snap_half(float(params.get("cx", (w - 1) / 2.0))),
            Action._snap_half(float(params.get("cy", (h - 1) / 2.0))),
            Action._snap_half(float(params.get("r", max(1.0, min(w, h) * 0.3)))),
        )
        lock_cx = bool(params.get("lock_circle_cx", False))
        lock_cy = bool(params.get("lock_circle_cy", False))
        rng = np.random.default_rng(835 + int(Action.STOCHASTIC_RUN_SEED) + int(Action.STOCHASTIC_SEED_OFFSET))

        def eval_pose(candidate: tuple[float, float, float]) -> float:
            cx, cy, rad = candidate
            return float(
                Action._element_error_for_circle_pose(
                    img_orig,
                    params,
                    cx_value=cx,
                    cy_value=cy,
                    radius_value=rad,
                )
            )

        best = current
        best_err = eval_pose(best)
        if not _isfinite(best_err):
            return False

        spread_xy = max(1.0, float(min(w, h)) * 0.10)
        spread_r = max(0.6, float(best[2]) * 0.18)
        improved = False
        stable_rounds = 0

        for _ in range(max(1, iterations)):
            candidates: list[tuple[tuple[float, float, float], float]] = [(best, best_err)]
            for _j in range(2):
                if lock_cx:
                    cx = best[0]
                else:
                    cx = Action._snap_half(float(_clip(rng.normal(best[0], spread_xy), x_low, x_high)))
                if lock_cy:
                    cy = best[1]
                else:
                    cy = Action._snap_half(float(_clip(rng.normal(best[1], spread_xy), y_low, y_high)))
                rad = Action._snap_half(float(_clip(rng.normal(best[2], spread_r), r_low, r_high)))
                cand = (cx, cy, rad)
                candidates.append((cand, eval_pose(cand)))

            finite = [pair for pair in candidates if _isfinite(pair[1])]
            if not finite:
                continue
            finite.sort(key=lambda item: item[1])
            round_best, round_err = finite[0]
            if round_err + 0.05 < best_err:
                best, best_err = round_best, round_err
                improved = True
                stable_rounds = 0
            else:
                stable_rounds += 1

            spread_xy = max(0.4, spread_xy * 0.92)
            spread_r = max(0.35, spread_r * 0.90)
            if stable_rounds >= 7:
                break

        if not improved:
            logs.append("circle: Stochastic-Survivor keine relevante Verbesserung")
            return False

        params["cx"], params["cy"], params["r"] = best
        if params.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(params, best[2])
        if params.get("stem_enabled"):
            params["stem_top"] = float(params.get("cy", 0.0)) + best[2]
        logs.append(
            f"circle: Stochastic-Survivor übernommen (cx={best[0]:.3f}, cy={best[1]:.3f}, r={best[2]:.3f}, err={best_err:.3f})"
        )
        return True

    @staticmethod
    def _optimize_circle_pose_adaptive_domain(
        img_orig: np.ndarray,
        params: dict,
        logs: list[str],
        *,
        rounds: int = 4,
        samples_per_round: int = 18,
    ) -> bool:
        """Adaptive random-domain search with iterative domain shrinking.

        Strategy:
        1) Start from a broad but plausible 3D domain (cx, cy, r).
        2) Evaluate random samples and keep a near-optimal plateau.
        3) Estimate a surrogate minimum from the plateau center and best sample.
        4) Shrink the domain and repeat.
        """
        if not params.get("circle_enabled", True):
            return False

        h, w = img_orig.shape[:2]
        x_low, x_high, y_low, y_high, r_low, r_high = Action._circle_bounds(params, w, h)
        lock_cx = bool(params.get("lock_circle_cx", False))
        lock_cy = bool(params.get("lock_circle_cy", False))

        current = (
            Action._snap_half(float(params.get("cx", (w - 1) / 2.0))),
            Action._snap_half(float(params.get("cy", (h - 1) / 2.0))),
            Action._snap_half(float(params.get("r", max(1.0, min(w, h) * 0.3)))),
        )

        def clamp_pose(candidate: tuple[float, float, float]) -> tuple[float, float, float]:
            cx, cy, rad = candidate
            if lock_cx:
                cx = current[0]
            else:
                cx = Action._snap_half(float(_clip(cx, x_low, x_high)))
            if lock_cy:
                cy = current[1]
            else:
                cy = Action._snap_half(float(_clip(cy, y_low, y_high)))
            rad = Action._snap_half(float(_clip(rad, r_low, r_high)))
            return cx, cy, rad

        cache: dict[tuple[float, float, float], float] = {}

        def eval_pose(candidate: tuple[float, float, float]) -> float:
            pose = clamp_pose(candidate)
            if pose not in cache:
                cache[pose] = float(
                    Action._element_error_for_circle_pose(
                        img_orig,
                        params,
                        cx_value=pose[0],
                        cy_value=pose[1],
                        radius_value=pose[2],
                    )
                )
            return cache[pose]

        best = clamp_pose(current)
        best_err = eval_pose(best)
        if not _isfinite(best_err):
            return False

        domain = {
            "cx_low": x_low,
            "cx_high": x_high,
            "cy_low": y_low,
            "cy_high": y_high,
            "r_low": r_low,
            "r_high": r_high,
        }

        rng_seed = 2027 + int(Action.STOCHASTIC_RUN_SEED) + int(Action.STOCHASTIC_SEED_OFFSET)
        rng = np.random.default_rng(rng_seed) if np is not None else random.Random(rng_seed)
        improved = False
        flat_plateau_hits = 0

        logs.append(
            (
                "circle: Adaptive-Domain-Suche gestartet "
                f"(Möglichkeitsraum: cx=[{domain['cx_low']:.2f},{domain['cx_high']:.2f}], "
                f"cy=[{domain['cy_low']:.2f},{domain['cy_high']:.2f}], "
                f"r=[{domain['r_low']:.2f},{domain['r_high']:.2f}], "
                f"samples_pro_runde={max(8, int(samples_per_round))})"
            )
        )

        for _round in range(max(1, rounds)):
            samples: list[tuple[tuple[float, float, float], float]] = [(best, best_err)]
            for _ in range(max(8, int(samples_per_round))):
                if lock_cx:
                    cx = current[0]
                else:
                    cx = float(rng.uniform(domain["cx_low"], domain["cx_high"]))
                if lock_cy:
                    cy = current[1]
                else:
                    cy = float(rng.uniform(domain["cy_low"], domain["cy_high"]))
                rad = float(rng.uniform(domain["r_low"], domain["r_high"]))
                pose = clamp_pose((cx, cy, rad))
                samples.append((pose, eval_pose(pose)))

            finite = [pair for pair in samples if _isfinite(pair[1])]
            if not finite:
                continue
            finite.sort(key=lambda item: item[1])
            round_best, round_best_err = finite[0]

            # Build a near-optimal plateau and use its center as a smooth surrogate.
            plateau_eps = max(0.06, round_best_err * 0.02)
            plateau = [pose for pose, err in finite if err <= round_best_err + plateau_eps]
            if len(plateau) >= 4:
                flat_plateau_hits += 1

            plateau_points = plateau if plateau else [round_best]
            plateau_min = (
                min(point[0] for point in plateau_points),
                min(point[1] for point in plateau_points),
                min(point[2] for point in plateau_points),
            )
            plateau_max = (
                max(point[0] for point in plateau_points),
                max(point[1] for point in plateau_points),
                max(point[2] for point in plateau_points),
            )
            plateau_mid = clamp_pose(
                (
                    (plateau_min[0] + plateau_max[0]) / 2.0,
                    (plateau_min[1] + plateau_max[1]) / 2.0,
                    (plateau_min[2] + plateau_max[2]) / 2.0,
                )
            )
            plateau_mid_err = eval_pose(plateau_mid)

            candidate_best = round_best
            candidate_err = round_best_err
            if _isfinite(plateau_mid_err) and plateau_mid_err < candidate_err:
                candidate_best = plateau_mid
                candidate_err = plateau_mid_err

            if candidate_err + 0.05 < best_err:
                best = candidate_best
                best_err = candidate_err
                improved = True

            logs.append(
                (
                    f"circle: Runde {_round + 1} random-samples={len(samples) - 1}, "
                    f"Error-Minimum={best_err:.3f} bei "
                    f"(cx={best[0]:.3f}, cy={best[1]:.3f}, r={best[2]:.3f})"
                )
            )

            # Iteratively shrink domain around the stable near-optimal region.
            shrink = 0.58
            if not lock_cx:
                half_span = max(0.5, float((domain["cx_high"] - domain["cx_low"]) * shrink * 0.5))
                focus = float(best[0] if len(plateau) <= 1 else (plateau_min[0] + plateau_max[0]) / 2.0)
                domain["cx_low"] = max(x_low, focus - half_span)
                domain["cx_high"] = min(x_high, focus + half_span)
            if not lock_cy:
                half_span = max(0.5, float((domain["cy_high"] - domain["cy_low"]) * shrink * 0.5))
                focus = float(best[1] if len(plateau) <= 1 else (plateau_min[1] + plateau_max[1]) / 2.0)
                domain["cy_low"] = max(y_low, focus - half_span)
                domain["cy_high"] = min(y_high, focus + half_span)
            half_span_r = max(0.5, float((domain["r_high"] - domain["r_low"]) * shrink * 0.5))
            focus_r = float(best[2] if len(plateau) <= 1 else (plateau_min[2] + plateau_max[2]) / 2.0)
            domain["r_low"] = max(r_low, focus_r - half_span_r)
            domain["r_high"] = min(r_high, focus_r + half_span_r)

            logs.append(
                (
                    f"circle: Runde {_round + 1} Möglichkeitsraum eingegrenzt auf "
                    f"cx=[{domain['cx_low']:.2f},{domain['cx_high']:.2f}], "
                    f"cy=[{domain['cy_low']:.2f},{domain['cy_high']:.2f}], "
                    f"r=[{domain['r_low']:.2f},{domain['r_high']:.2f}]"
                )
            )

        if not improved:
            logs.append("circle: Adaptive-Domain-Suche keine relevante Verbesserung")
            return False

        params["cx"], params["cy"], params["r"] = best
        if params.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(params, best[2])
        if params.get("stem_enabled"):
            params["stem_top"] = float(params.get("cy", 0.0)) + best[2]

        boundary_hit = (
            (not lock_cx and (abs(best[0] - x_low) <= 0.01 or abs(best[0] - x_high) <= 0.01))
            or (not lock_cy and (abs(best[1] - y_low) <= 0.01 or abs(best[1] - y_high) <= 0.01))
            or abs(best[2] - r_low) <= 0.01
            or abs(best[2] - r_high) <= 0.01
        )
        flat_hint = flat_plateau_hits >= 2
        logs.append(
            "circle: Adaptive-Domain-Suche übernommen "
            f"(cx={best[0]:.3f}, cy={best[1]:.3f}, r={best[2]:.3f}, err={best_err:.3f}, "
            f"rand_optimum={'ja' if boundary_hit else 'nein'}, flaches_optimum={'ja' if flat_hint else 'nein'})"
        )
        return True

    @staticmethod
    def _enforce_semantic_connector_expectation(base_name: str, semantic_elements: list[str], params: dict, w: int, h: int) -> dict:
        """Restore mandatory connector geometry for directional semantic badges."""
        normalized_base = get_base_name_from_file(str(base_name)).upper()
        normalized_elements = [str(elem).lower() for elem in (semantic_elements or [])]
        expects_left_arm = any("waagrechter strich links" in elem for elem in normalized_elements)

        # AC0812/AC0837/AC0882 are directional left-arm families. If noisy element
        # extraction temporarily drops arm flags, regenerate canonical connector geometry
        # from the fitted circle before final SVG serialization.
        if normalized_base in {"AC0812", "AC0837", "AC0882"} or expects_left_arm:
            return Action._enforce_left_arm_badge_geometry(params, w, h)
        return params

    @staticmethod
    def _element_width_key_and_bounds(
        element: str, params: dict, w: int, h: int, img_orig: np.ndarray | None = None
    ) -> tuple[str, float, float] | None:
        lock_strokes = bool(params.get("lock_stroke_widths"))
        min_dim = float(min(w, h))
        if element == "stem" and params.get("stem_enabled"):
            if lock_strokes:
                fixed = float(Action.AC08_STROKE_WIDTH_PX)
                if not bool(params.get("allow_stem_width_tuning", False)):
                    return "stem_width", fixed, fixed
                high = min(
                    float(params.get("stem_width_max", fixed + 1.0)),
                    max(fixed, fixed + float(params.get("stem_width_tuning_px", 1.0))),
                )
                return "stem_width", fixed, max(fixed, high)
            low = max(1.0, float(params.get("stroke_circle", 1.0)) * 0.65)
            high = max(low, min(float(w) * 0.25, float(params.get("stem_width_max", float(w) * 0.25))))
            return "stem_width", low, high
        if element == "arm" and params.get("arm_enabled"):
            if lock_strokes:
                fixed = float(Action.AC08_STROKE_WIDTH_PX)
                return "arm_stroke", fixed, fixed
            low = max(1.0, float(params.get("stroke_circle", 1.0)) * 0.65)
            high = max(low, min(float(min(w, h)) * 0.20, float(params.get("r", min(w, h))) * 0.9))
            return "arm_stroke", low, high
        if element == "circle" and params.get("circle_enabled", True):
            if lock_strokes:
                fixed = float(Action.AC08_STROKE_WIDTH_PX)
                return "stroke_circle", fixed, fixed
            low = max(0.8, float(params.get("stroke_circle", 1.0)) * 0.6)
            high = max(low, min(float(min(w, h)) * 0.22, float(params.get("r", min(w, h))) * 0.9))
            return "stroke_circle", low, high
        if element == "text" and params.get("draw_text", True):
            mode = str(params.get("text_mode", "")).lower()
            if mode == "voc":
                cur = float(params.get("voc_font_scale", 0.52))
                if bool(params.get("lock_text_scale", False)):
                    return "voc_font_scale", cur, cur
                # Start with broad generic bounds so the optimizer can follow
                # text-mask error rather than artificial variant caps.
                low = max(0.30, min(cur * 0.60, 0.45))
                # Keep a broad generic search window unless a specific badge
                # family constrains it via explicit min/max overrides.
                high = 1.60
                if "voc_font_scale_min" in params:
                    low = max(low, float(params["voc_font_scale_min"]))
                if "voc_font_scale_max" in params:
                    high = min(high, float(params["voc_font_scale_max"]))
                return "voc_font_scale", low, max(low, high)
            if mode == "co2":
                cur = float(params.get("co2_font_scale", 0.82))
                if bool(params.get("lock_text_scale", False)):
                    return "co2_font_scale", cur, cur
                # CO₂ labels in large variants can require a noticeably larger font
                # than the historical cap of 1.20 to match the source symbol.
                low = max(0.45, cur * 0.72)
                high = min(1.55, cur * 1.45)
                if "co2_font_scale_min" in params:
                    low = max(low, float(params["co2_font_scale_min"]))
                if "co2_font_scale_max" in params:
                    high = min(high, float(params["co2_font_scale_max"]))
                return "co2_font_scale", low, max(low, high)
        return None

    @staticmethod
    def _element_error_for_width(img_orig: np.ndarray, params: dict, element: str, width_value: float) -> float:
        h, w = img_orig.shape[:2]
        probe = dict(params)
        info = Action._element_width_key_and_bounds(element, probe, w, h, img_orig=img_orig)
        if info is None:
            return float("inf")
        key, low, high = info
        probe[key] = float(_clip(width_value, low, high))
        if key == "stem_width" and probe.get("stem_enabled"):
            probe["stem_x"] = float(probe.get("cx", probe.get("stem_x", 0.0))) - (probe["stem_width"] / 2.0)
        elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(probe, element))
        elem_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(elem_svg, w, h))
        if elem_render is None:
            return float("inf")
        mask_orig = Action.extract_badge_element_mask(img_orig, probe, element)
        if mask_orig is None:
            return float("inf")
        return Action._element_match_error(img_orig, elem_render, probe, element, mask_orig=mask_orig)

    @staticmethod
    def _element_error_for_circle_radius(img_orig: np.ndarray, params: dict, radius_value: float) -> float:
        h, w = img_orig.shape[:2]
        if not params.get("circle_enabled", True):
            return float("inf")

        probe = dict(params)
        max_r = max(1.0, (float(min(w, h)) * 0.48))
        probe["r"] = float(_clip(radius_value, 1.0, max_r))

        if probe.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(probe, float(probe["r"]))

        if probe.get("stem_enabled"):
            probe["stem_top"] = float(probe.get("cy", 0.0)) + float(probe["r"])

        elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(probe, "circle"))
        elem_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(elem_svg, w, h))
        if elem_render is None:
            return float("inf")

        # Keep the source mask conservative across radius probes.
        # - For shrink probes, stay anchored to the current radius so we don't
        #   hide missing source pixels (collapse bias, observed on AC0833_L).
        # - For growth probes, expand the source mask context to the larger
        #   radius so underestimated starts (e.g. AC0812_L) can still move up.
        source_mask_params = dict(params)
        source_mask_params["r"] = max(float(params.get("r", 0.0)), float(probe["r"]))
        if source_mask_params.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(source_mask_params, float(source_mask_params["r"]))
        if source_mask_params.get("stem_enabled"):
            source_mask_params["stem_top"] = float(source_mask_params.get("cy", 0.0)) + float(source_mask_params["r"])

        mask_orig = Action.extract_badge_element_mask(img_orig, source_mask_params, "circle")
        if mask_orig is None:
            return float("inf")
        mask_svg = Action.extract_badge_element_mask(elem_render, probe, "circle")
        if mask_svg is None:
            return float("inf")

        return Action._element_match_error(
            img_orig,
            elem_render,
            probe,
            "circle",
            mask_orig=mask_orig,
            mask_svg=mask_svg,
        )


    @staticmethod
    def _element_error_for_circle_pose(
        img_orig: np.ndarray,
        params: dict,
        *,
        cx_value: float,
        cy_value: float,
        radius_value: float,
    ) -> float:
        h, w = img_orig.shape[:2]
        if not params.get("circle_enabled", True):
            return float("inf")

        probe = dict(params)
        max_r = max(1.0, (float(min(w, h)) * 0.48))
        probe["cx"] = Action._snap_half(float(_clip(cx_value, 0.0, float(w - 1))))
        probe["cy"] = Action._snap_half(float(_clip(cy_value, 0.0, float(h - 1))))
        min_r = float(max(1.0, probe.get("min_circle_radius", 1.0)))
        probe["r"] = Action._snap_half(float(_clip(radius_value, min_r, max_r)))

        if probe.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(probe, float(probe["r"]))

        if probe.get("stem_enabled"):
            probe["stem_top"] = float(probe.get("cy", 0.0)) + float(probe["r"])

        elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(probe, "circle"))
        elem_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(elem_svg, w, h))
        if elem_render is None:
            return float("inf")

        # See `_element_error_for_circle_radius`: use a stable source mask that
        # is independent from the tested candidate pose.
        mask_orig = Action.extract_badge_element_mask(img_orig, params, "circle")
        if mask_orig is None:
            return float("inf")
        mask_svg = Action.extract_badge_element_mask(elem_render, probe, "circle")
        if mask_svg is None:
            return float("inf")

        return Action._element_match_error(
            img_orig,
            elem_render,
            probe,
            "circle",
            mask_orig=mask_orig,
            mask_svg=mask_svg,
        )

    @staticmethod
    def _reanchor_arm_to_circle_edge(params: dict, radius: float) -> None:
        """Keep arm orientation but snap the circle-side endpoint to the new radius."""
        if not params.get("arm_enabled"):
            return
        if not all(k in params for k in ("arm_x1", "arm_y1", "arm_x2", "arm_y2", "cx", "cy")):
            return

        cx = float(params.get("cx", 0.0))
        cy = float(params.get("cy", 0.0))
        x1 = float(params.get("arm_x1", cx))
        y1 = float(params.get("arm_y1", cy))
        x2 = float(params.get("arm_x2", cx))
        y2 = float(params.get("arm_y2", cy))

        # Preserve dominant orientation (horizontal vs. vertical).
        is_horizontal = abs(x2 - x1) >= abs(y2 - y1)
        if is_horizontal:
            params["arm_y1"] = cy
            params["arm_y2"] = cy
            p1_dist = abs(x1 - cx)
            p2_dist = abs(x2 - cx)
            if p2_dist <= p1_dist:
                params["arm_x2"] = cx - radius if x1 <= cx else cx + radius
            else:
                params["arm_x1"] = cx - radius if x2 <= cx else cx + radius
        else:
            params["arm_x1"] = cx
            params["arm_x2"] = cx
            p1_dist = abs(y1 - cy)
            p2_dist = abs(y2 - cy)
            if p2_dist <= p1_dist:
                params["arm_y2"] = cy - radius if y1 <= cy else cy + radius
            else:
                params["arm_y1"] = cy - radius if y2 <= cy else cy + radius

    @staticmethod
    def _optimize_circle_center_bracket(img_orig: np.ndarray, params: dict, logs: list[str]) -> bool:
        if not params.get("circle_enabled", True):
            return False

        h, w = img_orig.shape[:2]
        current_cx = float(params.get("cx", -1.0))
        current_cy = float(params.get("cy", -1.0))
        current_r = float(params.get("r", 0.0))
        if current_r <= 0.0 or current_cx < 0.0 or current_cy < 0.0:
            return False

        lock_cx = bool(params.get("lock_circle_cx", False))
        lock_cy = bool(params.get("lock_circle_cy", False))
        if lock_cx and lock_cy:
            return False

        max_shift = max(1.0, float(min(w, h)) * 0.16)
        x_low = Action._snap_half(max(0.0, current_cx - max_shift))
        x_high = Action._snap_half(min(float(w - 1), current_cx + max_shift))
        y_low = Action._snap_half(max(0.0, current_cy - max_shift))
        y_high = Action._snap_half(min(float(h - 1), current_cy + max_shift))

        evaluations: dict[tuple[float, float], float] = {}

        def eval_center(cx_value: float, cy_value: float) -> float:
            cx_snap = Action._snap_half(float(_clip(cx_value, 0.0, float(w - 1))))
            cy_snap = Action._snap_half(float(_clip(cy_value, 0.0, float(h - 1))))
            key = (cx_snap, cy_snap)
            if key not in evaluations:
                probe = dict(params)
                probe["cx"] = cx_snap
                probe["cy"] = cy_snap
                evaluations[key] = float(Action._element_error_for_circle_radius(img_orig, probe, current_r))
            return evaluations[key]

        def optimize_axis(low: float, high: float, fixed: float, axis: str) -> float:
            if high - low < 0.05:
                return Action._snap_half((low + high) / 2.0)
            mid = Action._snap_half((low + high) / 2.0)
            for _ in range(8):
                if axis == "x":
                    low_err = eval_center(low, fixed)
                    mid_err = eval_center(mid, fixed)
                    high_err = eval_center(high, fixed)
                else:
                    low_err = eval_center(fixed, low)
                    mid_err = eval_center(fixed, mid)
                    high_err = eval_center(fixed, high)

                if not all(_isfinite(v) for v in (low_err, mid_err, high_err)):
                    return mid

                if mid_err <= low_err and mid_err <= high_err:
                    if low_err <= high_err:
                        high = mid
                    else:
                        low = mid
                elif low_err <= mid_err and low_err <= high_err:
                    high = mid
                else:
                    low = mid

                if high - low < 0.05:
                    break
                next_mid = Action._snap_half((low + high) / 2.0)
                if abs(next_mid - mid) < 0.02:
                    break
                mid = next_mid
            points = [low, mid, high]
            if axis == "x":
                return min(points, key=lambda v: eval_center(v, fixed))
            return min(points, key=lambda v: eval_center(fixed, v))

        best_cx = current_cx
        best_cy = current_cy
        if not lock_cx:
            best_cx = optimize_axis(x_low, x_high, current_cy, "x")
        if not lock_cy:
            best_cy = optimize_axis(y_low, y_high, best_cx, "y")

        best_err = eval_center(best_cx, best_cy)
        if not _isfinite(best_err):
            logs.append("circle: Mittelpunkt-Bracketing abgebrochen wegen nicht-finitem Fehler")
            return False

        if abs(best_cx - current_cx) < 0.02 and abs(best_cy - current_cy) < 0.02:
            logs.append(
                f"circle: Mittelpunkt-Bracketing keine relevante Änderung (cx={current_cx:.3f}, cy={current_cy:.3f}, best_err={best_err:.3f})"
            )
            return False

        params["cx"] = best_cx
        params["cy"] = best_cy
        if params.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(params, current_r)
        if params.get("stem_enabled"):
            params["stem_top"] = float(params.get("cy", 0.0)) + current_r
            if bool(params.get("lock_stem_center_to_circle", False)):
                stem_w = float(params.get("stem_width", 1.0))
                params["stem_x"] = Action._snap_half(max(0.0, min(float(w) - stem_w, best_cx - (stem_w / 2.0))))

        logs.append(
            f"circle: Mittelpunkt-Bracketing cx {current_cx:.3f}->{best_cx:.3f}, cy {current_cy:.3f}->{best_cy:.3f} (best_err={best_err:.3f})"
        )
        return True

    @staticmethod
    def _optimize_circle_radius_bracket(img_orig: np.ndarray, params: dict, logs: list[str]) -> bool:
        if not params.get("circle_enabled", True):
            return False

        h, w = img_orig.shape[:2]
        current = float(params.get("r", 0.0))
        if current <= 0.0:
            return False

        min_dim = float(min(w, h))
        low_bound = max(1.0, min_dim * 0.14)
        low_bound = max(low_bound, float(params.get("min_circle_radius", 1.0)))
        has_connector = bool(params.get("arm_enabled") or params.get("stem_enabled"))
        if has_connector:
            # Connector badges (AC081x/AC083x families) are geometrically tied to
            # a semantic template. If radius bracketing can dive to the generic
            # min-dimension floor, the circle may detach from that template and
            # the connector degenerates into a tiny corner artifact.
            template_r = float(params.get("template_circle_radius", current))
            low_bound = max(low_bound, template_r * 0.88)
            # Also prevent one-shot collapses from noisy element masks.
            low_bound = max(low_bound, current * 0.90)
        # Tiny badges are especially sensitive to anti-aliasing noise in the
        # circle-only error mask. Prevent aggressive downward jumps that make
        # AC0800_S noticeably smaller than the medium/large variants.
        if min_dim <= 22.0:
            low_bound = max(low_bound, current * 0.9)
        high_bound = min_dim * 0.48
        if not low_bound < high_bound:
            return False

        low = Action._snap_half(low_bound)
        high = Action._snap_half(high_bound)
        mid = Action._snap_half(float(_clip(current, low, high)))
        if high - low < 0.05:
            return False

        evaluations: dict[float, float] = {}

        def eval_radius(radius: float) -> float:
            snapped = Action._snap_half(float(_clip(radius, low_bound, high_bound)))
            if snapped not in evaluations:
                evaluations[snapped] = float(Action._element_error_for_circle_radius(img_orig, params, snapped))
            return evaluations[snapped]

        max_rounds = 12
        for _ in range(max_rounds):
            low_err = eval_radius(low)
            mid_err = eval_radius(mid)
            high_err = eval_radius(high)
            if not all(_isfinite(v) for v in (low_err, mid_err, high_err)):
                logs.append(
                    "circle: Radius-Bracketing abgebrochen wegen nicht-finiten Fehlern "
                    + ", ".join(f"{v:.3f}->{e:.3f}" for v, e in sorted(evaluations.items()))
                )
                return False

            # Drei-Punkt-Bracketing: immer den besten Punkt und seinen besseren Nachbarn behalten.
            if mid_err <= low_err and mid_err <= high_err:
                if low_err <= high_err:
                    high = mid
                else:
                    low = mid
            elif low_err <= mid_err and low_err <= high_err:
                high = mid
            else:
                low = mid

            if high - low < 0.05:
                break
            next_mid = Action._snap_half((low + high) / 2.0)
            if abs(next_mid - mid) < 0.02:
                break
            mid = next_mid

        best_r, best_err = min(evaluations.items(), key=lambda pair: pair[1])
        candidate_dump = ", ".join(f"{v:.3f}->{e:.3f}" for v, e in sorted(evaluations.items()))
        if abs(best_r - current) < 0.02:
            logs.append(
                f"circle: Radius-Bracketing keine relevante Änderung (r: {current:.3f}, best_err={best_err:.3f}); Kandidaten="
                + candidate_dump
            )
            return False

        old_r = current
        params["r"] = best_r
        if params.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(params, best_r)
        if params.get("stem_enabled"):
            params["stem_top"] = float(params.get("cy", 0.0)) + best_r

        logs.append(
            f"circle: Radius-Bracketing r {old_r:.3f}->{best_r:.3f} (best_err={best_err:.3f}); Kandidaten="
            + candidate_dump
        )
        return True

    @staticmethod
    def _optimize_circle_pose_multistart(img_orig: np.ndarray, params: dict, logs: list[str]) -> bool:
        """Jointly optimize circle center+radius via a compact multi-start grid."""
        if not params.get("circle_enabled", True):
            return False

        h, w = img_orig.shape[:2]
        current_cx = float(params.get("cx", -1.0))
        current_cy = float(params.get("cy", -1.0))
        current_r = float(params.get("r", 0.0))
        if current_r <= 0.0 or current_cx < 0.0 or current_cy < 0.0:
            return False

        lock_cx = bool(params.get("lock_circle_cx", False))
        lock_cy = bool(params.get("lock_circle_cy", False))

        shift = max(0.5, float(min(w, h)) * 0.08)
        radius_span = max(0.5, current_r * 0.12)
        _x_low, _x_high, _y_low, _y_high, min_r, max_r = Action._circle_bounds(params, w, h)

        if lock_cx:
            cx_candidates = [Action._snap_half(current_cx)]
        else:
            cx_candidates = [
                Action._snap_half(float(_clip(current_cx + offset, 0.0, float(w - 1))))
                for offset in (-shift, 0.0, shift)
            ]
        if lock_cy:
            cy_candidates = [Action._snap_half(current_cy)]
        else:
            cy_candidates = [
                Action._snap_half(float(_clip(current_cy + offset, 0.0, float(h - 1))))
                for offset in (-shift, 0.0, shift)
            ]

        r_candidates = [
            Action._snap_half(float(_clip(current_r + offset, min_r, max_r)))
            for offset in (-radius_span, -(radius_span * 0.5), 0.0, radius_span * 0.5, radius_span)
        ]

        evaluations: dict[tuple[float, float, float], float] = {}

        def eval_pose(cx: float, cy: float, rad: float) -> float:
            key = (cx, cy, rad)
            if key not in evaluations:
                evaluations[key] = float(
                    Action._element_error_for_circle_pose(
                        img_orig,
                        params,
                        cx_value=cx,
                        cy_value=cy,
                        radius_value=rad,
                    )
                )
            return evaluations[key]

        best = (Action._snap_half(current_cx), Action._snap_half(current_cy), Action._snap_half(current_r))
        best_err = eval_pose(*best)

        for cx in cx_candidates:
            for cy in cy_candidates:
                for rad in r_candidates:
                    err = eval_pose(cx, cy, rad)
                    if _isfinite(err) and err + 0.05 < best_err:
                        best = (cx, cy, rad)
                        best_err = err

        best_cx, best_cy, best_r = best
        if (
            abs(best_cx - current_cx) < 0.02
            and abs(best_cy - current_cy) < 0.02
            and abs(best_r - current_r) < 0.02
        ):
            logs.append(
                f"circle: Joint-Multistart keine relevante Änderung (cx={current_cx:.3f}, cy={current_cy:.3f}, r={current_r:.3f}, best_err={best_err:.3f})"
            )
            return False

        params["cx"] = best_cx
        params["cy"] = best_cy
        params["r"] = best_r
        if params.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(params, best_r)
        if params.get("stem_enabled"):
            params["stem_top"] = float(params.get("cy", 0.0)) + best_r
            if bool(params.get("lock_stem_center_to_circle", False)):
                stem_w = float(params.get("stem_width", 1.0))
                params["stem_x"] = Action._snap_half(max(0.0, min(float(w) - stem_w, best_cx - (stem_w / 2.0))))

        logs.append(
            f"circle: Joint-Multistart cx {current_cx:.3f}->{best_cx:.3f}, cy {current_cy:.3f}->{best_cy:.3f}, r {current_r:.3f}->{best_r:.3f} (best_err={best_err:.3f})"
        )

        at_boundary = (
            (not lock_cx and (best_cx <= 0.01 or best_cx >= float(w - 1) - 0.01))
            or (not lock_cy and (best_cy <= 0.01 or best_cy >= float(h - 1) - 0.01))
            or abs(best_r - min_r) <= 0.01
            or abs(best_r - max_r) <= 0.01
        )
        if at_boundary:
            logs.append("circle: Joint-Multistart liegt am Rand; starte adaptive Domain-Suche")
            improved = Action._optimize_circle_pose_adaptive_domain(img_orig, params, logs)
            if not improved:
                logs.append("circle: Adaptive-Domain-Suche ohne Gewinn; fallback auf stochastic survivor")
                Action._optimize_circle_pose_stochastic_survivor(img_orig, params, logs)
        return True

    @staticmethod
    def _element_error_for_extent(img_orig: np.ndarray, params: dict, element: str, extent_value: float) -> float:
        h, w = img_orig.shape[:2]
        probe = dict(params)

        if element == "stem" and probe.get("stem_enabled"):
            min_len = 1.0
            max_len = float(h)
            new_len = float(_clip(extent_value, min_len, max_len))
            center = (float(probe.get("stem_top", 0.0)) + float(probe.get("stem_bottom", 0.0))) / 2.0
            half = new_len / 2.0
            probe["stem_top"] = float(_clip(center - half, 0.0, float(h - 1)))
            probe["stem_bottom"] = float(_clip(center + half, probe["stem_top"] + 1.0, float(h)))

        elif element == "arm" and probe.get("arm_enabled"):
            x1 = float(probe.get("arm_x1", 0.0))
            y1 = float(probe.get("arm_y1", 0.0))
            x2 = float(probe.get("arm_x2", 0.0))
            y2 = float(probe.get("arm_y2", 0.0))
            dx = x2 - x1
            dy = y2 - y1
            cur_len = float(math.hypot(dx, dy))
            if cur_len <= 1e-6:
                return float("inf")
            new_len = float(_clip(extent_value, 1.0, float(max(w, h))))
            ux = dx / cur_len
            uy = dy / cur_len

            if probe.get("circle_enabled", True) and all(k in probe for k in ("cx", "cy", "r")):
                # Keep the endpoint at the circle edge fixed and optimize the free side
                # length only. Symmetric center-scaling shortens both ends and can make
                # AC0812/AC0814 horizontal connectors visibly too short.
                Action._reanchor_arm_to_circle_edge(probe, float(probe.get("r", 0.0)))
                ax1 = float(probe.get("arm_x1", x1))
                ay1 = float(probe.get("arm_y1", y1))
                ax2 = float(probe.get("arm_x2", x2))
                ay2 = float(probe.get("arm_y2", y2))

                cx = float(probe.get("cx", 0.0))
                cy = float(probe.get("cy", 0.0))
                d1 = float(math.hypot(ax1 - cx, ay1 - cy))
                d2 = float(math.hypot(ax2 - cx, ay2 - cy))

                if d1 <= d2:
                    ix, iy = ax1, ay1
                    probe["arm_x2"] = float(_clip(ix + (ux * new_len), 0.0, float(w - 1)))
                    probe["arm_y2"] = float(_clip(iy + (uy * new_len), 0.0, float(h - 1)))
                else:
                    ix, iy = ax2, ay2
                    probe["arm_x1"] = float(_clip(ix - (ux * new_len), 0.0, float(w - 1)))
                    probe["arm_y1"] = float(_clip(iy - (uy * new_len), 0.0, float(h - 1)))
            else:
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                half = new_len / 2.0
                probe["arm_x1"] = float(_clip(cx - (ux * half), 0.0, float(w - 1)))
                probe["arm_y1"] = float(_clip(cy - (uy * half), 0.0, float(h - 1)))
                probe["arm_x2"] = float(_clip(cx + (ux * half), 0.0, float(w - 1)))
                probe["arm_y2"] = float(_clip(cy + (uy * half), 0.0, float(h - 1)))
        else:
            return float("inf")

        elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(probe, element))
        elem_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(elem_svg, w, h))
        if elem_render is None:
            return float("inf")

        mask_orig = Action.extract_badge_element_mask(img_orig, probe, element)
        if mask_orig is None:
            return float("inf")

        return Action._element_match_error(img_orig, elem_render, probe, element, mask_orig=mask_orig)

    @staticmethod
    def _optimize_element_extent_bracket(img_orig: np.ndarray, params: dict, element: str, logs: list[str]) -> bool:
        h, w = img_orig.shape[:2]
        if element == "stem" and params.get("stem_enabled"):
            current = float(params.get("stem_bottom", 0.0)) - float(params.get("stem_top", 0.0))
            key_label = "stem_len"
            low_bound = 1.0
            high_bound = float(h)
            is_bottom_anchored = float(params.get("stem_bottom", 0.0)) >= float(h) - 0.5
            forced_abs_min = params.get("stem_len_min")
            if forced_abs_min is not None:
                low_bound = max(low_bound, float(forced_abs_min))
            forced_min_ratio = params.get("stem_len_min_ratio")
            if forced_min_ratio is not None:
                min_ratio = float(max(0.0, min(1.0, float(forced_min_ratio))))
                low_bound = max(low_bound, current * min_ratio)
                if is_bottom_anchored and params.get("circle_enabled", True):
                    low_bound = max(low_bound, float(h) * 0.36)
            # Keep bottom-anchored stem variants (e.g. AC0811_S) from collapsing
            # into near-invisible stubs when anti-aliased extraction under-segments
            # thin line pixels in element-only masks.
            if (
                forced_min_ratio is None
                and is_bottom_anchored
                and params.get("circle_enabled", True)
                and all(k in params for k in ("cy", "r"))
            ):
                min_ratio = float(params.get("stem_len_min_ratio", 0.65))
                low_bound = max(low_bound, current * max(0.0, min(1.0, min_ratio)))
                # Keep tiny bottom-anchored stems visibly present even when
                # current fits are already under-estimated by anti-aliasing.
                low_bound = max(low_bound, float(h) * 0.36)
        elif element == "arm" and params.get("arm_enabled"):
            dx = float(params.get("arm_x2", 0.0)) - float(params.get("arm_x1", 0.0))
            dy = float(params.get("arm_y2", 0.0)) - float(params.get("arm_y1", 0.0))
            current = float(math.hypot(dx, dy))
            key_label = "arm_len"
            low_bound = 1.0
            high_bound = float(max(w, h))
            forced_abs_min = params.get("arm_len_min")
            if forced_abs_min is not None:
                low_bound = max(low_bound, float(forced_abs_min))
            forced_min_ratio = params.get("arm_len_min_ratio")
            if forced_min_ratio is not None:
                min_ratio = float(max(0.0, min(1.0, float(forced_min_ratio))))
                low_bound = max(low_bound, current * min_ratio)
            # Keep edge-anchored connector variants (e.g. AC0832_S) from collapsing
            # to tiny stubs when element-only error masks under-segment thin lines.
            is_edge_anchored = any(
                (
                    float(params.get(key, 0.0)) <= 0.5
                    or float(params.get(key, 0.0)) >= float(limit) - 0.5
                )
                for key, limit in (
                    ("arm_x1", w),
                    ("arm_x2", w),
                    ("arm_y1", h),
                    ("arm_y2", h),
                )
            )
            if forced_min_ratio is None and is_edge_anchored and params.get("circle_enabled", True):
                min_ratio = float(params.get("arm_len_min_ratio", 0.75))
                low_bound = max(low_bound, current * max(0.0, min(1.0, min_ratio)))
        else:
            return False

        if current <= 0.0:
            return False

        low = float(low_bound)
        high = float(high_bound)
        if not (low < high):
            logs.append(
                f"{element}: Längen-Bracketing übersprungen ({key_label}: current={current:.3f}, "
                f"Range={low_bound:.3f}..{high_bound:.3f})"
            )
            return False

        candidates = sorted(
            {
                Action._snap_half(low),
                Action._snap_half(low + (high - low) * 0.25),
                Action._snap_half((low + high) / 2.0),
                Action._snap_half(low + (high - low) * 0.75),
                Action._snap_half(high),
                Action._snap_half(current),
            }
        )
        candidate_errors = [Action._element_error_for_extent(img_orig, params, element, v) for v in candidates]
        if not all(_isfinite(e) for e in candidate_errors):
            logs.append(
                f"{element}: Längen-Bracketing abgebrochen ({key_label}) wegen nicht-finiten Fehlern "
                + ", ".join(f"{v:.3f}->{e:.3f}" for v, e in zip(candidates, candidate_errors, strict=False))
            )
            return False

        best_idx = min(range(len(candidate_errors)), key=lambda i: candidate_errors[i])
        best_len = float(candidates[best_idx])

        boundary_best = abs(best_len - low) < 0.02 or abs(best_len - high) < 0.02
        if boundary_best:
            s_best, s_err, s_improved = Action._stochastic_survivor_scalar(
                current,
                low,
                high,
                lambda v: Action._element_error_for_extent(img_orig, params, element, float(v)),
                snap=Action._snap_half,
                seed=1103 if element == "stem" else 1109,
            )
            if s_improved:
                best_len = float(s_best)
                logs.append(
                    f"{element}: Längen-Stochastic-Survivor aktiviert (best_len={best_len:.3f}, err={s_err:.3f})"
                )

        if abs(best_len - current) < 0.02:
            logs.append(
                f"{element}: Längen-Bracketing keine relevante Änderung ({key_label}: {current:.3f}); "
                f"Kandidaten="
                + ", ".join(f"{v:.3f}->{e:.3f}" for v, e in zip(candidates, candidate_errors, strict=False))
            )
            return False

        if element == "stem":
            if params.get("circle_enabled", True) and all(k in params for k in ("cy", "r")):
                # Keep the stem attached to the circle edge and optimize only the free end.
                top = float(_clip(float(params.get("cy", 0.0)) + float(params.get("r", 0.0)), 0.0, float(h - 1)))
                params["stem_top"] = top
                params["stem_bottom"] = float(_clip(top + best_len, top + 1.0, float(h)))
            else:
                center = (float(params.get("stem_top", 0.0)) + float(params.get("stem_bottom", 0.0))) / 2.0
                half = best_len / 2.0
                params["stem_top"] = float(_clip(center - half, 0.0, float(h - 1)))
                params["stem_bottom"] = float(_clip(center + half, params["stem_top"] + 1.0, float(h)))
        else:
            x1 = float(params.get("arm_x1", 0.0))
            y1 = float(params.get("arm_y1", 0.0))
            x2 = float(params.get("arm_x2", 0.0))
            y2 = float(params.get("arm_y2", 0.0))
            dx = x2 - x1
            dy = y2 - y1
            cur_len = float(math.hypot(dx, dy))
            if cur_len <= 1e-6:
                return False
            ux = dx / cur_len
            uy = dy / cur_len

            if params.get("circle_enabled", True) and all(k in params for k in ("cx", "cy", "r")):
                Action._reanchor_arm_to_circle_edge(params, float(params.get("r", 0.0)))
                ax1 = float(params.get("arm_x1", x1))
                ay1 = float(params.get("arm_y1", y1))
                ax2 = float(params.get("arm_x2", x2))
                ay2 = float(params.get("arm_y2", y2))

                cx = float(params.get("cx", 0.0))
                cy = float(params.get("cy", 0.0))
                d1 = float(math.hypot(ax1 - cx, ay1 - cy))
                d2 = float(math.hypot(ax2 - cx, ay2 - cy))

                if d1 <= d2:
                    ix, iy = ax1, ay1
                    params["arm_x2"] = float(_clip(ix + (ux * best_len), 0.0, float(w - 1)))
                    params["arm_y2"] = float(_clip(iy + (uy * best_len), 0.0, float(h - 1)))
                else:
                    ix, iy = ax2, ay2
                    params["arm_x1"] = float(_clip(ix - (ux * best_len), 0.0, float(w - 1)))
                    params["arm_y1"] = float(_clip(iy - (uy * best_len), 0.0, float(h - 1)))
            else:
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                half = best_len / 2.0
                params["arm_x1"] = float(_clip(cx - (ux * half), 0.0, float(w - 1)))
                params["arm_y1"] = float(_clip(cy - (uy * half), 0.0, float(h - 1)))
                params["arm_x2"] = float(_clip(cx + (ux * half), 0.0, float(w - 1)))
                params["arm_y2"] = float(_clip(cy + (uy * half), 0.0, float(h - 1)))

        logs.append(
            f"{element}: Längen-Bracketing {key_label} {current:.3f}->{best_len:.3f}; Kandidaten="
            + ", ".join(f"{v:.3f}->{e:.3f}" for v, e in zip(candidates, candidate_errors, strict=False))
        )
        return True

    @staticmethod
    def _optimize_element_width_bracket(img_orig: np.ndarray, params: dict, element: str, logs: list[str]) -> bool:
        h, w = img_orig.shape[:2]
        info = Action._element_width_key_and_bounds(element, params, w, h, img_orig=img_orig)
        if info is None:
            return False

        key, low_bound, high_bound = info
        current = float(params.get(key, 0.0))
        if current <= 0.0:
            return False

        # Breiteres Mehrpunkt-Bracketing über den gesamten plausiblen Bereich.
        low = float(low_bound)
        high = float(high_bound)
        if not (low < high):
            logs.append(
                f"{element}: Breiten-Bracketing übersprungen ({key}: current={current:.3f}, "
                f"Range={low_bound:.3f}..{high_bound:.3f})"
            )
            return False

        if key.endswith("_font_scale"):
            candidates = sorted(
                {
                    round(low, 3),
                    round(low + (high - low) * 0.15, 3),
                    round(low + (high - low) * 0.30, 3),
                    round(low + (high - low) * 0.50, 3),
                    round(low + (high - low) * 0.70, 3),
                    round(low + (high - low) * 0.85, 3),
                    round(high, 3),
                    round(max(low, min(high, current * 0.85)), 3),
                    round(max(low, min(high, current)), 3),
                    round(max(low, min(high, current * 1.15)), 3),
                }
            )
        else:
            candidates = sorted(
                {
                    Action._snap_half(low),
                    Action._snap_half(low + (high - low) * 0.25),
                    Action._snap_half((low + high) / 2.0),
                    Action._snap_half(low + (high - low) * 0.75),
                    Action._snap_half(high),
                    Action._snap_half(current),
                }
            )
        candidate_errors = [Action._element_error_for_width(img_orig, params, element, v) for v in candidates]
        if not all(_isfinite(e) for e in candidate_errors):
            logs.append(
                f"{element}: Breiten-Bracketing abgebrochen ({key}) wegen nicht-finiten Fehlern "
                + ", ".join(f"{v:.3f}->{e:.3f}" for v, e in zip(candidates, candidate_errors, strict=False))
            )
            return False

        best_idx = min(range(len(candidate_errors)), key=lambda i: candidate_errors[i])
        best_width = candidates[best_idx]

        boundary_best = abs(float(best_width) - low) < 0.02 or abs(float(best_width) - high) < 0.02
        if boundary_best:
            snap_fn = (lambda v: float(round(v, 3))) if key.endswith("_font_scale") else Action._snap_half
            s_best, s_err, s_improved = Action._stochastic_survivor_scalar(
                current,
                low,
                high,
                lambda v: Action._element_error_for_width(img_orig, params, element, float(v)),
                snap=snap_fn,
                seed=1201,
            )
            if s_improved:
                best_width = float(s_best)
                logs.append(
                    f"{element}: Breiten-Stochastic-Survivor aktiviert ({key}={best_width:.3f}, err={s_err:.3f})"
                )

        old = float(params.get(key, current))
        if abs(best_width - old) < 0.02:
            logs.append(
                f"{element}: Breiten-Bracketing keine relevante Änderung ({key}: {old:.3f}); "
                f"Kandidaten="
                + ", ".join(
                    f"{v:.3f}->{e:.3f}" for v, e in zip(candidates, candidate_errors, strict=False)
                )
            )
            return False

    circle = Candidate(shape="circle", cx=sum(xs) / len(xs), cy=sum(ys) / len(ys), w=float(bw), h=float(bh))
    return circle, stem_bbox, stem_direction

    @staticmethod
    def _element_error_for_color(
        img_orig: np.ndarray,
        params: dict,
        element: str,
        color_key: str,
        color_value: int,
        mask_orig: np.ndarray,
    ) -> float:
        probe = dict(params)
        probe[color_key] = int(_clip(color_value, 0, 255))

        h, w = img_orig.shape[:2]
        elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(probe, element))
        elem_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(elem_svg, w, h))
        if elem_render is None:
            return float("inf")

        if element == "circle":
            # Color-only circle probing should be photometric against a stable
            # source region. Do not let threshold-induced mask area changes in
            # candidate renders bias toward darker/larger-looking circles.
            return Action._masked_union_error_in_bbox(img_orig, elem_render, mask_orig, mask_orig)

        return Action._element_match_error(
            img_orig,
            elem_render,
            probe,
            element,
            mask_orig=mask_orig,
        )

    @staticmethod
    def _optimize_element_color_bracket(
        img_orig: np.ndarray,
        params: dict,
        element: str,
        mask_orig: np.ndarray,
        logs: list[str],
    ) -> bool:
        if bool(params.get("lock_colors", False)):
            logs.append(f"{element}: Farb-Bracketing übersprungen (Farben gesperrt)")
            return False
        if mask_orig is None or int(mask_orig.sum()) == 0:
            return False

        changed_any = False
        local_gray = Action._mean_gray_for_mask(img_orig, mask_orig)
        sampled = int(round(local_gray)) if local_gray is not None else None

        for color_key in Action._element_color_keys(element, params):
            current = int(round(float(params.get(color_key, 128))))
            candidates = {
                int(_clip(current - 32, 0, 255)),
                int(_clip(current - 16, 0, 255)),
                int(_clip(current - 8, 0, 255)),
                int(_clip(current, 0, 255)),
                int(_clip(current + 8, 0, 255)),
                int(_clip(current + 16, 0, 255)),
                int(_clip(current + 32, 0, 255)),
            }
            if sampled is not None:
                candidates.add(int(_clip(sampled, 0, 255)))
            if element == "circle" and color_key == "fill_gray":
                candidates.update({200, 210, 220, 230, 240})
            if color_key in {"stroke_gray", "stem_gray", "text_gray"}:
                candidates.update({96, 112, 128, 144, 152, 160, 171})

            values = sorted(candidates)
            errs = [
                Action._element_error_for_color(img_orig, params, element, color_key, v, mask_orig)
                for v in values
            ]
            if not all(_isfinite(e) for e in errs):
                logs.append(
                    f"{element}: Farb-Bracketing abgebrochen ({color_key}) wegen nicht-finiten Fehlern "
                    + ", ".join(f"{v}->{e:.3f}" for v, e in zip(values, errs, strict=False))
                )
                continue

            best_idx = int(np.argmin(errs))
            best_value = int(values[best_idx])

            if best_value == min(values) or best_value == max(values):
                s_best, s_err, s_improved = Action._stochastic_survivor_scalar(
                    float(current),
                    float(min(values)),
                    float(max(values)),
                    lambda v: Action._element_error_for_color(
                        img_orig,
                        params,
                        element,
                        color_key,
                        int(_clip(int(round(v)), 0, 255)),
                        mask_orig,
                    ),
                    snap=lambda v: int(_clip(int(round(v)), 0, 255)),
                    seed=1301,
                )
                if s_improved:
                    best_value = int(_clip(int(round(s_best)), 0, 255))
                    logs.append(
                        f"{element}: Farb-Stochastic-Survivor aktiviert ({color_key}={best_value}, err={s_err:.3f})"
                    )

            if best_value == current:
                logs.append(
                    f"{element}: Farb-Bracketing keine relevante Änderung ({color_key}: {current}); Kandidaten="
                    + ", ".join(f"{v}->{e:.3f}" for v, e in zip(values, errs, strict=False))
                )
                continue

    circle_candidate, (sx0, sy0, sx1, sy1), stem_direction = detected
    stem_w = sx1 - sx0 + 1
    stem_h = sy1 - sy0 + 1

        return changed_any

    @staticmethod
    def _refine_stem_geometry_from_masks(params: dict, mask_orig: np.ndarray, mask_svg: np.ndarray, w: int) -> tuple[bool, str | None]:
        """Refine stem width/position when validation detects a geometric mismatch."""
        orig_bbox = Action._mask_bbox(mask_orig)
        svg_bbox = Action._mask_bbox(mask_svg)
        if orig_bbox is None or svg_bbox is None:
            return False, None

        ox1, _oy1, ox2, _oy2 = orig_bbox
        sx1, _sy1, sx2, _sy2 = svg_bbox
        orig_w = max(1.0, (ox2 - ox1) + 1.0)
        svg_w = max(1.0, (sx2 - sx1) + 1.0)
        ratio = svg_w / orig_w

        expected_cx = float(params.get("cx", (ox1 + ox2) / 2.0))
        stroke = float(params.get("stroke_circle", 1.0))
        # Skip a small band right below the circle edge so anti-aliased ring/fill
        # pixels do not inflate stem width estimation.
        y_start = float(params.get("stem_top", 0.0)) + max(1.0, stroke * 2.0)
        y_end = float(params.get("stem_bottom", mask_orig.shape[0]))
        est = Action._estimate_vertical_stem_from_mask(mask_orig, expected_cx, int(y_start), int(y_end))

        if est is not None:
            est_cx, est_width = est
            min_w = max(1.0, float(params.get("stroke_circle", 1.0)) * 0.70)
            max_w = max(
                min_w,
                min(
                    float(params.get("stem_width_max", float(w) * 0.18)),
                    min(float(w) * 0.18, float(params.get("r", 1.0)) * 0.80),
                ),
            )
            target_width = max(min_w, min(est_width, max_w))
            if bool(params.get("lock_stem_center_to_circle", False)):
                circle_cx = float(params.get("cx", est_cx))
                max_offset = float(params.get("stem_center_lock_max_offset", max(0.35, target_width * 0.75)))
                target_cx = float(_clip(est_cx, circle_cx - max_offset, circle_cx + max_offset))
            else:
                target_cx = est_cx
            estimate_mode = "iter"
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
    if h < 3 or w < 3:
        return None

    row_counts = [sum(row) for row in element.pixels]
    col_counts = [sum(element.pixels[y][x] for y in range(h)) for x in range(w)]
    max_row = max(row_counts) if row_counts else 0
    max_col = max(col_counts) if col_counts else 0
    if max_row < max(2, int(w * 0.45)) or max_col < max(2, int(h * 0.45)):
        return None

    area = sum(sum(row) for row in element.pixels)
    if area <= 0:
        return None
    expected = max_row + max_col - 1
    if area > expected * 2.05:
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

    row_runs = [sum(1 for xx in range(w) if element.pixels[yy][xx] and y0 <= yy <= y1) for yy in range(h) if row_counts[yy]]
    col_runs = [sum(1 for yy in range(h) if element.pixels[yy][xx] and x0 <= xx <= x1) for xx in range(w) if col_counts[xx]]
    base_thickness = min(
        min(row_runs) if row_runs else max_row,
        min(col_runs) if col_runs else max_col,
    )
    thickness = float(max(1, min(base_thickness, max(1, min(w, h) // 2))))
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

    interior_vals: list[tuple[int, int, int]] = []
    diag_vals: list[int] = []
    for y in range(border_band, h - border_band):
        for x in range(border_band, w - border_band):
            if not element.pixels[y][x]:
                continue
            value = grayscale[element.y0 + y][element.x0 + x]
            if abs(x - (a * y + b)) <= max(1.0, thickness * 0.65):
                diag_vals.append(value)
            else:
                interior_vals.append((x, y, value))

    left_cut = border_band + max(1, (w - 2 * border_band) // 3)
    right_cut = w - border_band - max(1, (w - 2 * border_band) // 3)
    left_vals = [value for x, _, value in interior_vals if x < left_cut]
    center_vals = [value for x, _, value in interior_vals if left_cut <= x < right_cut]
    right_vals = [value for x, _, value in interior_vals if x >= right_cut]
    if not left_vals or not center_vals or not right_vals:
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
    if diag_vals:
        diag_hex = gray_to_hex(round(sum(diag_vals) / len(diag_vals)))
    else:
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
    target_w: int,
    target_h: int,
    rotation_deg: int,
    scale: float,
) -> dict[str, object]:
    """Rotate/scale connector geometry around circle center while preserving upright text."""
    p = dict(donor_params)
    cx = float(p.get("cx", target_w / 2.0))
    cy = float(p.get("cy", target_h / 2.0))
    tx = float(target_params.get("cx", target_w / 2.0))
    ty = float(target_params.get("cy", target_h / 2.0))

    # Always carry essential rendering colors from target/donor/defaults.
    p["fill_gray"] = int(round(float(target_params.get("fill_gray", p.get("fill_gray", Action.LIGHT_CIRCLE_FILL_GRAY)))))
    p["stroke_gray"] = int(round(float(target_params.get("stroke_gray", p.get("stroke_gray", Action.LIGHT_CIRCLE_STROKE_GRAY)))))
    if bool(target_params.get("draw_text", p.get("draw_text", False))) or bool(p.get("draw_text", False)):
        p["text_gray"] = int(round(float(target_params.get("text_gray", p.get("text_gray", Action.LIGHT_CIRCLE_TEXT_GRAY)))))
    if bool(target_params.get("stem_enabled", p.get("stem_enabled", False))) or bool(p.get("stem_enabled", False)):
        p["stem_gray"] = int(round(float(target_params.get("stem_gray", p.get("stem_gray", p["stroke_gray"])))))

    # Prefer target anchor so center alignment remains stable between variants.
    p["cx"] = tx
    p["cy"] = ty

    if p.get("circle_enabled", True):
        p["r"] = max(1.0, float(p.get("r", 1.0)) * float(scale))

    angle = math.radians(float(rotation_deg))
    ca = math.cos(angle)
    sa = math.sin(angle)

    def _rot_scale_point(x: float, y: float) -> tuple[float, float]:
        dx = (x - cx) * float(scale)
        dy = (y - cy) * float(scale)
        rx = (dx * ca) - (dy * sa)
        ry = (dx * sa) + (dy * ca)
        return tx + rx, ty + ry

    if p.get("arm_enabled"):
        x1, y1 = _rot_scale_point(float(p.get("arm_x1", tx)), float(p.get("arm_y1", ty)))
        x2, y2 = _rot_scale_point(float(p.get("arm_x2", tx)), float(p.get("arm_y2", ty)))
        p["arm_x1"] = float(_clip(x1, 0.0, max(0.0, float(target_w - 1))))
        p["arm_y1"] = float(_clip(y1, 0.0, max(0.0, float(target_h - 1))))
        p["arm_x2"] = float(_clip(x2, 0.0, max(0.0, float(target_w - 1))))
        p["arm_y2"] = float(_clip(y2, 0.0, max(0.0, float(target_h - 1))))

    if p.get("stem_enabled"):
        stem_x = float(p.get("stem_x", tx)) + (float(p.get("stem_width", 1.0)) / 2.0)
        top = float(p.get("stem_top", ty))
        bottom = float(p.get("stem_bottom", ty))
        x1, y1 = _rot_scale_point(stem_x, top)
        x2, y2 = _rot_scale_point(stem_x, bottom)
        p["stem_x"] = float(_clip((x1 + x2) / 2.0 - (float(p.get("stem_width", 1.0)) / 2.0), 0.0, float(target_w)))
        p["stem_top"] = float(_clip(min(y1, y2), 0.0, float(target_h)))
        p["stem_bottom"] = float(_clip(max(y1, y2), 0.0, float(target_h)))

    # Keep text horizontally readable while preventing aggressive down-scaling
    # during template transfer. The historical sqrt(scale) shrink was often too
    # strong and produced undersized labels in converted outputs.
    if bool(p.get("draw_text", False)):
        text_scale = max(0.5, min(1.8, float(scale)))
        # Gentle response to geometric scale changes: preserve legibility for
        # downscaled transfers while still allowing moderate growth.
        text_adjust = max(0.90, min(1.18, text_scale ** 0.38))
        if "s" in p:
            p["s"] = float(max(1e-4, float(p.get("s", 0.01)) * text_adjust))
        if "co2_font_scale" in p:
            p["co2_font_scale"] = float(max(0.30, float(p.get("co2_font_scale", 0.82)) * text_adjust))
        if "voc_font_scale" in p:
            p["voc_font_scale"] = float(max(0.30, float(p.get("voc_font_scale", 0.52)) * text_adjust))

    symbol_name = str(target_params.get("label") or target_params.get("variant") or target_params.get("base") or "")
    if symbol_name:
        p = Action._finalize_ac08_style(symbol_name, p)
    return p

def _try_template_transfer(
    *,
    max_iter: int,
    plateau_limit: int,
    seed: int,
) -> None:
    min_pixels = max(6, int((len(binary) * len(binary[0])) * 0.0015)) if binary and binary[0] else 6
    elements = find_elements(binary, min_pixels=min_pixels)
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

    line_match = re.search(
        r"<line[^>]*x1=\"([0-9.]+)\"[^>]*y1=\"([0-9.]+)\"[^>]*x2=\"([0-9.]+)\"[^>]*y2=\"([0-9.]+)\"[^>]*stroke-width=\"([0-9.]+)\"",
        text,
    )
    if line_match:
        params["arm_enabled"] = True
        params["arm_x1"] = float(line_match.group(1))
        params["arm_y1"] = float(line_match.group(2))
        params["arm_x2"] = float(line_match.group(3))
        params["arm_y2"] = float(line_match.group(4))
        params["arm_stroke"] = float(line_match.group(5))

    text_tag_match = re.search(r"(<text[^>]*>)", text)
    if text_tag_match:
        text_tag = text_tag_match.group(1)
        fill_match = re.search(r'fill="(#[0-9a-fA-F]{6})"', text_tag)
        if fill_match:
            params["text_gray"] = _gray_from_hex(fill_match.group(1), int(params["text_gray"]))
        text_content_match = re.search(r"<text[^>]*>([^<]+)</text>", text)
        text_content = text_content_match.group(1).strip().upper() if text_content_match else ""
        if text_content == "VOC":
            params["draw_text"] = True
            params["text_mode"] = "voc"
        elif text_content in {"CO", "2"}:
            # CO₂ is emitted as two separate text nodes ("CO" + subscript "2").
            # Preserve text semantics so variant harmonization cannot strip labels.
            params["draw_text"] = True
            params["text_mode"] = "co2"

    text_path_match = re.search(r"(<path[^>]*>)", text)
    if text_path_match:
        path_tag = text_path_match.group(1)
        fill_match = re.search(r'fill="(#[0-9a-fA-F]{6})"', path_tag)
        params["draw_text"] = True
        if fill_match:
            params["text_gray"] = _gray_from_hex(fill_match.group(1), int(params["text_gray"]))
        if Action.T_PATH_D in path_tag:
            params["text_mode"] = "path_t"
        else:
            params["text_mode"] = "path"

    if params.get("draw_text") and params.get("text_mode") in {"path", "path_t"} and (
        "tx" not in params or "ty" not in params or "s" not in params
    ):
        # Fallback for older path-glyph SVGs where we only need compositing geometry
        # during harmonization. Keep native <text>-based modes (CO₂/VOC) intact.
        params["draw_text"] = False

    return w, h, params


def _normalized_geometry_signature(w: int, h: int, params: dict) -> dict[str, float]:
    sig: dict[str, float] = {}
    scale = max(1.0, float(min(w, h)))

    if params.get("circle_enabled"):
        sig["cx"] = float(params["cx"]) / max(1.0, float(w))
        sig["cy"] = float(params["cy"]) / max(1.0, float(h))
        sig["r"] = float(params["r"]) / scale
        sig["stroke_circle"] = float(params["stroke_circle"]) / scale

    if params.get("stem_enabled"):
        sig["stem_x"] = float(params["stem_x"]) / max(1.0, float(w))
        sig["stem_width"] = float(params["stem_width"]) / max(1.0, float(w))
        sig["stem_top"] = float(params["stem_top"]) / max(1.0, float(h))
        sig["stem_bottom"] = float(params["stem_bottom"]) / max(1.0, float(h))

    if params.get("arm_enabled"):
        sig["arm_x1"] = float(params["arm_x1"]) / max(1.0, float(w))
        sig["arm_y1"] = float(params["arm_y1"]) / max(1.0, float(h))
        sig["arm_x2"] = float(params["arm_x2"]) / max(1.0, float(w))
        sig["arm_y2"] = float(params["arm_y2"]) / max(1.0, float(h))
        sig["arm_stroke"] = float(params["arm_stroke"]) / scale

    return sig


def _max_signature_delta(sig_a: dict[str, float], sig_b: dict[str, float]) -> float:
    keys = sorted(set(sig_a.keys()).intersection(sig_b.keys()))
    if not keys:
        return 1.0
    return max(abs(sig_a[k] - sig_b[k]) for k in keys)


def _scale_badge_params(anchor: dict, anchor_w: int, anchor_h: int, target_w: int, target_h: int) -> dict:
    scaled = dict(anchor)
    scale = max(1e-6, float(min(target_w, target_h)) / max(1.0, float(min(anchor_w, anchor_h))))
    scale_x = max(1e-6, float(target_w) / max(1.0, float(anchor_w)))
    scale_y = max(1e-6, float(target_h) / max(1.0, float(anchor_h)))

    if scaled.get("circle_enabled"):
        scaled["cx"] = float(anchor["cx"]) * scale_x
        scaled["cy"] = float(anchor["cy"]) * scale_y
        scaled["r"] = float(anchor["r"]) * scale
        # Intentionally preserve stroke thickness across size variants.
        scaled["stroke_circle"] = float(anchor["stroke_circle"])

    if scaled.get("stem_enabled"):
        scaled["stem_x"] = float(anchor["stem_x"]) * scale_x
        scaled["stem_width"] = float(anchor["stem_width"])
        scaled["stem_top"] = float(anchor["stem_top"]) * scale_y
        scaled["stem_bottom"] = float(anchor["stem_bottom"]) * scale_y

    if scaled.get("arm_enabled"):
        scaled["arm_x1"] = float(anchor["arm_x1"]) * scale_x
        scaled["arm_y1"] = float(anchor["arm_y1"]) * scale_y
        scaled["arm_x2"] = float(anchor["arm_x2"]) * scale_x
        scaled["arm_y2"] = float(anchor["arm_y2"]) * scale_y
        scaled["arm_stroke"] = float(anchor["arm_stroke"])

    if scaled.get("circle_enabled"):
        stroke = max(0.0, float(scaled.get("stroke_circle", 1.0)))
        half_stroke = stroke / 2.0
        cx = float(scaled.get("cx", target_w / 2.0))
        cy = float(scaled.get("cy", target_h / 2.0))
        r = max(1.0, float(scaled.get("r", 1.0)))

        max_fit_r = max(1.0, (min(float(target_w), float(target_h)) / 2.0) - half_stroke)
        if r > max_fit_r:
            r = max_fit_r

        min_cx = r + half_stroke
        max_cx = float(target_w) - r - half_stroke
        min_cy = r + half_stroke
        max_cy = float(target_h) - r - half_stroke

        if min_cx > max_cx:
            cx = float(target_w) / 2.0
        else:
            cx = float(_clip(cx, min_cx, max_cx))

        if min_cy > max_cy:
            cy = float(target_h) / 2.0
        else:
            cy = float(_clip(cy, min_cy, max_cy))

        if scaled.get("stem_enabled") and "stem_width" in scaled:
            stem_width = max(1e-6, float(scaled["stem_width"]))
            scaled["stem_x"] = cx - (stem_width / 2.0)

        scaled["cx"] = cx
        scaled["cy"] = cy
        scaled["r"] = r

    return scaled


def _harmonization_anchor_priority(suffix: str, prefer_large: bool) -> int:
    """Return size-priority rank for L/M/S harmonization anchors."""
    if prefer_large:
        # For connector families we keep L authoritative to avoid undersized
        # large variants caused by propagating medium geometry upwards.
        return {"L": 0, "M": 1, "S": 2}.get(str(suffix), 3)
    # Plain circles remain more stable when M is used as anchor.
    return {"M": 0, "L": 1, "S": 2}.get(str(suffix), 3)


def _harmonize_semantic_size_variants(
    results: list[dict[str, object]],
    folder_path: str,
    svg_out_dir: str,
    reports_out_dir: str,
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


def _hex_to_gray(value: str) -> int:
    value = value.strip().lower()
    if not value.startswith("#"):
        return 0
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    if len(value) != 7:
        return 0
    r = int(value[1:3], 16)
    g = int(value[3:5], 16)
    b = int(value[5:7], 16)
    return int(round(0.299 * r + 0.587 * g + 0.114 * b))


def _rasterize_generated_svg(svg_path: Path, width: int, height: int) -> list[list[int]]:
    img = [[255 for _ in range(width)] for _ in range(height)]
    root = ET.fromstring(svg_path.read_text(encoding="utf-8"))

    for node in root:
        tag = node.tag.rsplit("}", 1)[-1]
        fill = node.attrib.get("fill")
        if not fill or fill.lower() == "none":
            continue
        fill_gray = _hex_to_gray(fill)
        stroke = node.attrib.get("stroke")
        stroke_gray = _hex_to_gray(stroke) if stroke and stroke.lower() != "none" else None
        stroke_width = float(node.attrib.get("stroke-width", "0") or "0")

        if tag == "rect":
            x = float(node.attrib.get("x", "0"))
            y = float(node.attrib.get("y", "0"))
            w = float(node.attrib.get("width", "0"))
            h = float(node.attrib.get("height", "0"))
            x0 = max(0, int(x))
            y0 = max(0, int(y))
            x1 = min(width, int(x + w + 0.999))
            y1 = min(height, int(y + h + 0.999))
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    img[yy][xx] = fill_gray
            continue

        if tag == "circle":
            cx = float(node.attrib.get("cx", "0"))
            cy = float(node.attrib.get("cy", "0"))
            r = float(node.attrib.get("r", "0"))
            rx = r
            ry = r
        elif tag == "ellipse":
            cx = float(node.attrib.get("cx", "0"))
            cy = float(node.attrib.get("cy", "0"))
            rx = float(node.attrib.get("rx", "0"))
            ry = float(node.attrib.get("ry", "0"))
        else:
            continue

        outer_rx = max(0.1, rx + stroke_width / 2.0)
        outer_ry = max(0.1, ry + stroke_width / 2.0)
        inner_rx = max(0.0, rx - stroke_width / 2.0)
        inner_ry = max(0.0, ry - stroke_width / 2.0)

        min_x = max(0, int(cx - outer_rx - 1))
        max_x = min(width - 1, int(cx + outer_rx + 1))
        min_y = max(0, int(cy - outer_ry - 1))
        max_y = min(height - 1, int(cy + outer_ry + 1))
        inv_outer_rx2 = 1.0 / (outer_rx * outer_rx)
        inv_outer_ry2 = 1.0 / (outer_ry * outer_ry)
        inv_inner_rx2 = 1.0 / (inner_rx * inner_rx) if inner_rx > 0 else 0.0
        inv_inner_ry2 = 1.0 / (inner_ry * inner_ry) if inner_ry > 0 else 0.0

        for yy in range(min_y, max_y + 1):
            dy = yy + 0.5 - cy
            dy_outer = dy * dy * inv_outer_ry2
            if dy_outer > 1.0:
                continue
            dy_inner = dy * dy * inv_inner_ry2 if inner_ry > 0 else 0.0
            for xx in range(min_x, max_x + 1):
                dx = xx + 0.5 - cx
                outer = dx * dx * inv_outer_rx2 + dy_outer
                if outer > 1.0:
                    continue
                if stroke_gray is not None and stroke_width > 0 and inner_rx > 0 and inner_ry > 0:
                    inner = dx * dx * inv_inner_rx2 + dy_inner
                    img[yy][xx] = stroke_gray if inner > 1.0 else fill_gray
                else:
                    img[yy][xx] = fill_gray

    return img


def compute_svg_grayscale_mae(reference: list[list[int]], svg_path: Path) -> float:
    height = len(reference)
    width = len(reference[0]) if height else 0
    if width == 0 or height == 0:
        return 0.0
    rendered = _rasterize_generated_svg(svg_path, width, height)
    error_sum = 0.0
    for y in range(height):
        for x in range(width):
            error_sum += abs(reference[y][x] - rendered[y][x])
    return error_sum / (width * height)


def write_quality_list(rows: list[QualityRow], path: Path) -> None:
    ordered = sorted(rows, key=lambda row: row.avg_error_per_pixel)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["image,svg,width,height,avg_error_per_pixel"]
    for row in ordered:
        lines.append(f"{row.image},{row.svg},{row.width},{row.height},{row.avg_error_per_pixel:.6f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

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
    p.add_argument("--quality-list", type=Path, default=Path("artifacts/quality_list.csv"), help="Write converted-image quality ranking CSV (ascending avg error per pixel)")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    images = sorted(iter_images(args.input_dir))
    if not images:
        print(f"No images found in {args.input_dir}")
        return 1

    quality_rows: list[QualityRow] = []

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

    if harmonized_logs:
        with open(os.path.join(reports_out_dir, "variant_harmonization.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(harmonized_logs).rstrip() + "\n")
    if category_logs:
        with open(os.path.join(reports_out_dir, "shape_catalog.csv"), "w", encoding="utf-8") as f:
            f.write("base;category;variants\n")
            f.write("\n".join(category_logs).rstrip() + "\n")


def _write_pixel_delta2_ranking(folder_path: str, svg_out_dir: str, reports_out_dir: str, threshold: float = 18.0) -> None:
    ranking: list[dict[str, float | str]] = []
    for svg_name in sorted(f for f in os.listdir(svg_out_dir) if f.lower().endswith(".svg")):
        stem = os.path.splitext(svg_name)[0]
        orig_path = None
        for ext in (".jpg", ".png", ".bmp"):
            candidate = os.path.join(folder_path, f"{stem}{ext}")
            if os.path.exists(candidate):
                orig_path = candidate
                break
        if orig_path is None:
            continue

        img_orig = cv2.imread(orig_path)
        if img_orig is None:
            continue

        with open(os.path.join(svg_out_dir, svg_name), "r", encoding="utf-8") as f:
            svg_content = f.read()

        h, w = img_orig.shape[:2]
        rendered = Action.render_svg_to_numpy(svg_content, w, h)
        if rendered is None:
            continue

        mean_delta2, std_delta2 = Action.calculate_delta2_stats(img_orig, rendered)
        ranking.append(
            {
                "image": os.path.basename(orig_path),
                "mean_delta2": float(mean_delta2),
                "std_delta2": float(std_delta2),
            }
        )

    ranking.sort(key=lambda row: float(row["mean_delta2"]), reverse=True)
    csv_path = os.path.join(reports_out_dir, "pixel_delta2_ranking.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["image", "mean_delta2", "std_delta2"])
        for row in ranking:
            writer.writerow([row["image"], f"{float(row['mean_delta2']):.6f}", f"{float(row['std_delta2']):.6f}"])

    valid = [row for row in ranking if _isfinite(float(row["mean_delta2"]))]
    count_ok = sum(1 for row in valid if float(row["mean_delta2"]) <= threshold)
    summary_lines = [
        f"images_total={len(valid)}",
        f"threshold_mean_delta2={threshold:.3f}",
        f"images_with_mean_delta2_le_threshold={count_ok}",
    ]
    with open(os.path.join(reports_out_dir, "pixel_delta2_summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder_path", help="Pfad zum Ordner mit den Bildern")
    parser.add_argument("csv_path", help="Pfad zur CSV/Export-Tabelle")
    parser.add_argument("iterations", type=int, help="Anzahl der Iterationen (z.B. 8)")
    parser.add_argument("--start", default="AR0102", help="Start-Referenz (inkl.), default: AR0102")
    parser.add_argument("--end", default="AR0104", help="End-Referenz (inkl.), default: AR0104")
    parser.add_argument(
        "--debug-ac0811-dir",
        default=None,
        help="Optional: Ordner für AC0811 Element-Diff-Dumps pro Runde/Element",
    )
    parser.add_argument(
        "--debug-element-diff-dir",
        default=None,
        help="Optional: Ordner für Element-Diff-Dumps pro Runde/Element für alle Semantic-Badges",
    )
    parser.add_argument(
        "--bootstrap-deps",
        action="store_true",
        help=(
            "Installiert fehlende Bild-Abhängigkeiten (numpy, opencv-python-headless) "
            "automatisch via pip vor der Konvertierung."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.bootstrap_deps:
        try:
            installed = _bootstrap_required_image_dependencies()
        except RuntimeError as exc:
            print(f"[ERROR] {exc}")
            return 2
        if installed:
            print(f"[INFO] Installiert: {', '.join(installed)}")

    out_dir = convert_range(
        args.folder_path,
        args.csv_path,
        args.iterations,
        args.start,
        args.end,
        args.debug_ac0811_dir,
        args.debug_element_diff_dir,
    )
    print(f"\nAbgeschlossen! Ausgaben unter: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
