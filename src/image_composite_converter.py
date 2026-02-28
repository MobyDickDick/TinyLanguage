"""Image-to-composite-SVG conversion pipeline.

Ported from the user-provided prototype and exposed as a Python helper module so
it can be executed directly or via TinyLanguage (`src_tiny/image_composite_converter.tiny`).
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass

try:
    import cv2
except ImportError:  # pragma: no cover - optional dependency in constrained environments
    cv2 = None
try:
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency in constrained environments
    np = None

try:
    import fitz  # PyMuPDF for native SVG rendering
except ImportError:  # pragma: no cover - optional dependency
    fitz = None


def rgb_to_hex(rgb: np.ndarray) -> str:
    return "#{:02x}{:02x}{:02x}".format(int(rgb[0]), int(rgb[1]), int(rgb[2]))


def get_base_name_from_file(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = re.sub(r"(-\d+)$", "", name)
    while True:
        prev = name
        name = re.sub(r"_([1-9]|L|M|S|[1-9]S|W|X)$", "", name, flags=re.IGNORECASE)
        if name == prev:
            break
    return name


@dataclass
class Perception:
    img_path: str
    csv_path: str

    def __post_init__(self) -> None:
        self.base_name = get_base_name_from_file(os.path.basename(self.img_path))
        self.img = cv2.imread(self.img_path)
        self.raw_desc = self._load_csv()

    def _load_csv(self) -> dict[str, str]:
        raw_desc: dict[str, str] = {}
        if not os.path.exists(self.csv_path):
            return raw_desc

        with open(self.csv_path, mode="r", encoding="utf-8-sig") as f:
            content = f.read()
            delimiter = ";" if ";" in content.split("\n", 1)[0] else ","
            f.seek(0)
            reader = csv.reader(f, delimiter=delimiter)
            headers = next(reader, None)
            if not headers:
                return raw_desc

            root_idx, desc_idx = -1, -1
            for i, h in enumerate(headers):
                low = h.lower()
                if "wurzelform" in low:
                    root_idx = i
                elif "beschreibung" in low:
                    desc_idx = i
            if root_idx == -1:
                root_idx = 1
            if desc_idx == -1:
                desc_idx = 2

            for row in reader:
                if len(row) > max(root_idx, desc_idx):
                    root_name = row[root_idx].strip()
                    desc = row[desc_idx].strip()
                    if root_name:
                        raw_desc[root_name] = desc
        return raw_desc


class Reflection:
    def __init__(self, raw_desc: dict[str, str]):
        self.raw_desc = raw_desc

    def parse_description(self, base_name: str, img_filename: str):
        desc_raw = self.raw_desc.get(base_name, "")
        desc_raw += " " + self.raw_desc.get(os.path.splitext(img_filename)[0], "")
        desc = desc_raw.lower().strip()

        params = {
            "mode": "auto",
            "top_source_ref": None,
            "bottom_shape": None,
            "elements": [],
            "label": "M",
        }

        if base_name.upper() == "AC0800":
            params["mode"] = "semantic_badge"
            params["elements"].append("SEMANTIC: Kreis ohne Buchstabe")
            params["label"] = ""
            return desc, params

        if base_name.upper() == "AC0811":
            params["mode"] = "semantic_badge"
            params["elements"].append("SEMANTIC: Kreis ohne Buchstabe")
            params["elements"].append("SEMANTIC: senkrechter Strich hinter dem Kreis")
            params["label"] = ""
            return desc, params

        if base_name.upper() in {"AR0100", "AC0812", "AC0813", "AC0814", "AC0870", "AC0881", "AC0882"}:
            params["mode"] = "semantic_badge"
            if base_name.upper() in {"AC0812", "AC0813", "AC0814"}:
                params["elements"].append("SEMANTIC: Kreis ohne Buchstabe")
                params["label"] = ""
            else:
                params["elements"].append("SEMANTIC: Kreis + Buchstabe")
                params["label"] = "M" if base_name.upper() == "AR0100" else "T"
            if base_name.upper() == "AC0881":
                params["elements"].append("SEMANTIC: senkrechter Strich hinter dem Kreis")
            if base_name.upper() in {"AC0812", "AC0882"}:
                params["elements"].append("SEMANTIC: waagrechter Strich links vom Kreis")
            if base_name.upper() == "AC0813":
                params["elements"].append("SEMANTIC: senkrechter Strich oben vom Kreis")
            if base_name.upper() == "AC0814":
                params["elements"].append("SEMANTIC: waagrechter Strich rechts vom Kreis")
            return desc, params

        match = re.search(r"oben .*?wie .*?in ([a-z0-9_]+)", desc)
        if match:
            params["mode"] = "composite"
            params["top_source_ref"] = match.group(1).upper()
            params["elements"].append(
                f"OBEN: Geschnitten aus Originaldatei {params['top_source_ref']}"
            )

        if "unten" in desc and "viereck" in desc and "kreuz" in desc:
            params["mode"] = "composite"
            params["bottom_shape"] = "square_cross"
            params["elements"].append("UNTEN: Parametrisch generiertes Viereck mit Kreuz")

        return desc, params


class Action:
    # DejaVuSans-Bold glyph outline in font units.
    M_PATH_D = "M188 1493H678L1018 694L1360 1493H1849V0H1485V1092L1141 287H897L553 1092V0H188Z"
    M_XMIN = 188
    M_XMAX = 1849
    M_YMIN = 0
    M_YMAX = 1493
    T_PATH_D = "M829 0V1194H381V1493H1636V1194H1188V0H829Z"
    T_XMIN = 381
    T_XMAX = 1636
    T_YMIN = 0
    T_YMAX = 1493

    # AR0100 tuned defaults for 25x25.
    AR0100_BASE = {
        "cx": 12.654,
        "cy": 12.065,
        "r": 11.280,
        "stroke_width": 1.618,
        "fill_gray": 244,
        "stroke_gray": 171,
        "text_gray": 110,
        "tx": 6.249,
        "ty": 5.946,
        "s": 0.007665,
    }

    AC0870_BASE = {
        "cx": 15.0,
        "cy": 15.0,
        "r": 12.0,
        "stroke_width": 2.0,
        "fill_gray": 220,
        "stroke_gray": 152,
        "text_gray": 98,
        "label": "T",
    }

    LIGHT_CIRCLE_FILL_GRAY = 242
    LIGHT_CIRCLE_STROKE_GRAY = 222
    LIGHT_CIRCLE_TEXT_GRAY = 98

    @staticmethod
    def grayhex(gray: int) -> str:
        g = max(0, min(255, int(round(gray))))
        return f"#{g:02x}{g:02x}{g:02x}"

    @staticmethod
    def _normalize_light_circle_colors(params: dict) -> dict:
        params["fill_gray"] = Action.LIGHT_CIRCLE_FILL_GRAY
        params["stroke_gray"] = Action.LIGHT_CIRCLE_STROKE_GRAY
        if params.get("stem_enabled"):
            params["stem_gray"] = Action.LIGHT_CIRCLE_STROKE_GRAY
        if params.get("draw_text", True) and "text_gray" in params:
            params["text_gray"] = Action.LIGHT_CIRCLE_TEXT_GRAY
        return params

    @staticmethod
    def _default_ac0870_params(w: int, h: int) -> dict:
        scale = min(w, h) / 30.0 if min(w, h) > 0 else 1.0
        b = Action.AC0870_BASE
        params = {
            "cx": b["cx"] * scale,
            "cy": b["cy"] * scale,
            "r": b["r"] * scale,
            "stroke_circle": b["stroke_width"] * scale,
            "fill_gray": b["fill_gray"],
            "stroke_gray": b["stroke_gray"],
            "text_gray": b["text_gray"],
            "label": b["label"],
            "tx": 8.7 * scale,
            "ty": 6.5 * scale,
            "s": 0.0100 * scale,
            "text_mode": "path_t",
        }
        Action._center_glyph_bbox(params)
        return Action._normalize_light_circle_colors(params)

    @staticmethod
    def _default_ac0881_params(w: int, h: int) -> dict:
        params = Action._default_ac0870_params(w, h)
        params["stem_enabled"] = True
        params["stem_width"] = max(1.0, params["r"] * 0.30)
        params["stem_x"] = params["cx"] - (params["stem_width"] / 2.0)
        params["stem_top"] = params["cy"] + (params["r"] * 0.60)
        params["stem_bottom"] = float(h)
        params["stem_gray"] = params["stroke_gray"]
        return params

    @staticmethod
    def _default_ac081x_shared(w: int, h: int) -> dict:
        scale = min(1.0, (min(w, h) / 25.0)) if min(w, h) > 0 else 1.0
        cx = float(w) / 2.0
        cy = float(h) / 2.0
        # AC081x reference bitmaps use a slightly larger circle than AR0100/AC0870.
        r = 9.2 * scale
        stroke_circle = 1.5 * scale
        stem_or_arm = 2.0 * scale
        # Keep connector lines long enough to match the raster source symbols.
        stem_or_arm_len = 9.0 * scale
        return {
            "cx": cx,
            "cy": cy,
            "r": r,
            "stroke_circle": stroke_circle,
            "stroke_gray": 152,
            "fill_gray": 220,
            "stem_or_arm": stem_or_arm,
            "stem_or_arm_len": stem_or_arm_len,
        }

    @staticmethod
    def _default_ac0811_params(w: int, h: int) -> dict:
        """AC0811 is vertically elongated: circle sits in the upper square area."""
        if w <= 0 or h <= 0:
            return Action._default_ac081x_shared(w, h)

        r = float(w) * 0.4
        stroke_circle = max(0.9, float(w) / 15.0)
        cx = float(w) / 2.0
        cy = float(w) / 2.0
        stem_width = max(1.0, float(w) * 0.10)
        stem_len = max(2.0, float(h) - (cy + r))

        return Action._normalize_light_circle_colors({
            "cx": cx,
            "cy": cy,
            "r": r,
            "stroke_circle": stroke_circle,
            "stroke_gray": Action.LIGHT_CIRCLE_STROKE_GRAY,
            "fill_gray": Action.LIGHT_CIRCLE_FILL_GRAY,
            "draw_text": False,
            "stem_enabled": True,
            "stem_width": stem_width,
            "stem_x": cx - (stem_width / 2.0),
            "stem_top": cy + r,
            "stem_bottom": min(float(h), (cy + r) + stem_len),
            "stem_gray": Action.LIGHT_CIRCLE_STROKE_GRAY,
        })

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

        # AC0811 stems are intentionally thin. The generic contour fit can over-estimate
        # width when anti-aliased circle pixels bleed into the stem ROI, especially on
        # larger "_L" variants. Keep the fitted value but clamp it to a narrow, plausible
        # band derived from the circle stroke and image width.
        min_stem_width = max(1.0, stroke_circle * 0.75)
        max_stem_width = max(min_stem_width, min(float(w) * 0.14, stroke_circle * 1.6))
        stem_width = max(min_stem_width, min(raw_stem_width, max_stem_width))

        params["stem_enabled"] = True
        params["stem_width"] = stem_width
        params["stem_x"] = cx - (params["stem_width"] / 2.0)
        params["stem_top"] = max(0.0, min(float(h), cy + r))
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
    def _default_ac0813_params(w: int, h: int) -> dict:
        params = Action._default_ac081x_shared(w, h)
        arm_y2 = params["cy"] - params["r"]
        arm_y1 = max(0.0, arm_y2 - params["stem_or_arm_len"])
        params.update(
            {
                "text_gray": 98,
                "label": "T",
                "text_mode": "path_t",
                "arm_enabled": True,
                "arm_x1": params["cx"],
                "arm_y1": arm_y1,
                "arm_x2": params["cx"],
                "arm_y2": arm_y2,
                "arm_stroke": params["stem_or_arm"],
                "s": 0.0088 * min(1.0, (min(w, h) / 25.0)) if min(w, h) > 0 else 0.0088,
            }
        )
        Action._center_glyph_bbox(params)
        return params

    @staticmethod
    def _default_ac0814_params(w: int, h: int) -> dict:
        params = Action._default_ac0813_params(w, h)
        cx0 = float(w) / 2.0
        cy0 = float(h) / 2.0

        def rotate_clockwise(x: float, y: float) -> tuple[float, float]:
            return cx0 + (y - cy0), cy0 - (x - cx0)

        params["cx"], params["cy"] = rotate_clockwise(params["cx"], params["cy"])
        params["arm_x1"], params["arm_y1"] = rotate_clockwise(params["arm_x1"], params["arm_y1"])
        params["arm_x2"], params["arm_y2"] = rotate_clockwise(params["arm_x2"], params["arm_y2"])
        Action._center_glyph_bbox(params)
        return params

    @staticmethod
    def _glyph_bbox(text_mode: str) -> tuple[int, int, int, int]:
        if text_mode == "path_t":
            return Action.T_XMIN, Action.T_YMIN, Action.T_XMAX, Action.T_YMAX
        return Action.M_XMIN, Action.M_YMIN, Action.M_XMAX, Action.M_YMAX

    @staticmethod
    def _center_glyph_bbox(params: dict) -> None:
        xmin, ymin, xmax, ymax = Action._glyph_bbox(params.get("text_mode", "path"))
        glyph_width = (xmax - xmin) * params["s"]
        glyph_height = (ymax - ymin) * params["s"]
        params["tx"] = float(params["cx"] - (glyph_width / 2.0))
        params["ty"] = float(params["cy"] - (glyph_height / 2.0))

    @staticmethod
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
            c = circles[0][0]
            params["cx"] = float(c[0])
            params["cy"] = float(c[1])
            params["r"] = float(c[2])

        yy, xx = np.indices(gray.shape)
        dist = np.sqrt((xx - params["cx"]) ** 2 + (yy - params["cy"]) ** 2)
        inner_mask = dist <= params["r"] * 0.88
        ring_mask = np.abs(dist - params["r"]) <= max(1.0, params["stroke_circle"])

        if np.any(inner_mask):
            inner_vals = gray[inner_mask]
            text_threshold = min(150, int(np.percentile(inner_vals, 20) + 3))
            text_mask = (gray <= text_threshold) & inner_mask

            kernel = np.ones((2, 2), np.uint8)
            text_mask_u8 = cv2.morphologyEx(text_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(text_mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                contour = max(contours, key=cv2.contourArea)
                x, y, tw, th = cv2.boundingRect(contour)
                if tw > 2 and th > 2:
                    t_width_units = 1636 - Action.T_XMIN
                    t_height_units = Action.T_YMAX
                    sx = tw / t_width_units
                    sy = th / t_height_units
                    s = float(max(0.004, min(0.04, (sx + sy) / 2.0)))
                    params["s"] = s
                    params["text_gray"] = int(np.median(gray[text_mask_u8 > 0]))

            Action._center_glyph_bbox(params)

            params["fill_gray"] = int(np.median(inner_vals))

        if np.any(ring_mask):
            params["stroke_gray"] = int(np.median(gray[ring_mask]))

        return params

    @staticmethod
    def _fit_semantic_badge_from_image(img: np.ndarray, defaults: dict) -> dict:
        """Fit common semantic badge primitives (circle/stem/arm) directly from image content."""
        params = dict(defaults)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        min_side = float(min(h, w))
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        circles = cv2.HoughCircles(
            blur,
            cv2.HOUGH_GRADIENT,
            dp=1.0,
            minDist=max(6.0, min_side * 0.35),
            param1=80,
            param2=9,
            minRadius=max(3, int(round(min_side * 0.18))),
            maxRadius=max(5, int(round(min_side * 0.49))),
        )

        if circles is not None and circles.size > 0:
            best = None
            for c in circles[0]:
                cx, cy, r = float(c[0]), float(c[1]), float(c[2])
                yy, xx = np.indices(gray.shape)
                dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
                fill_mask = dist <= max(1.0, r * 0.82)
                ring_mask = np.abs(dist - r) <= max(1.0, params.get("stroke_circle", 1.2))
                if not np.any(fill_mask) or not np.any(ring_mask):
                    continue
                fill_gray = float(np.median(gray[fill_mask]))
                ring_gray = float(np.median(gray[ring_mask]))
                score = abs(fill_gray - 220.0) + abs(ring_gray - 152.0)
                if best is None or score < best[0]:
                    best = (score, cx, cy, r, fill_gray, ring_gray)

            if best is not None:
                _, cx, cy, r, fill_gray, ring_gray = best
                params["cx"] = cx
                params["cy"] = cy
                params["r"] = r
                params["fill_gray"] = int(round(fill_gray))
                params["stroke_gray"] = int(round(ring_gray))

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

        if params.get("draw_text", True):
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
                return defaults
            return Action._fit_ac0870_params_from_image(img, defaults)

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
                return defaults
            return Action._fit_semantic_badge_from_image(img, defaults)

        if name == "AC0811":
            defaults = Action._default_ac0811_params(w, h)
            if img is None:
                return defaults
            return Action._fit_ac0811_params_from_image(img, defaults)

        if name == "AC0812":
            params = Action._default_ac0882_params(w, h)
            params["draw_text"] = False
            params["fill_gray"] = 220
            params["stroke_gray"] = 98
            if img is not None:
                params = Action._fit_semantic_badge_from_image(img, params)
            return params

        if name == "AC0813":
            params = Action._default_ac0813_params(w, h)
            params["draw_text"] = False
            params["fill_gray"] = 220
            params["stroke_gray"] = 98
            if img is not None:
                params = Action._fit_semantic_badge_from_image(img, params)
            return params

        if name == "AC0814":
            params = Action._default_ac0814_params(w, h)
            params["draw_text"] = False
            params["fill_gray"] = 220
            params["stroke_gray"] = 98
            if img is not None:
                params = Action._fit_semantic_badge_from_image(img, params)
            return params

        if name == "AC0881":
            defaults = Action._default_ac0881_params(w, h)
            if img is None:
                return defaults
            return Action._fit_semantic_badge_from_image(img, defaults)

        if name == "AC0882":
            defaults = Action._default_ac0882_params(w, h)
            if img is None:
                return defaults
            return Action._fit_semantic_badge_from_image(img, defaults)

        return None

    @staticmethod
    def generate_badge_svg(w: int, h: int, p: dict) -> str:
        elements = [
            f'<svg width="{w}px" height="{h}px" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
        ]

        if p.get("arm_enabled"):
            arm_y1 = p.get("arm_y1", p.get("arm_y", 0.0))
            arm_y2 = p.get("arm_y2", p.get("arm_y", arm_y1))
            elements.append(
                (
                    f'  <line x1="{p["arm_x1"]:.4f}" y1="{arm_y1:.4f}" '
                    f'x2="{p["arm_x2"]:.4f}" y2="{arm_y2:.4f}" '
                    f'stroke="{Action.grayhex(p.get("stroke_gray", 152))}" '
                    f'stroke-width="{p["arm_stroke"]:.4f}" stroke-linecap="round"/>'
                )
            )

        if p.get("stem_enabled"):
            elements.append(
                (
                    f'  <rect x="{p["stem_x"]:.4f}" y="{p["stem_top"]:.4f}" '
                    f'width="{p["stem_width"]:.4f}" height="{max(0.0, p["stem_bottom"] - p["stem_top"]):.4f}" '
                    f'fill="{Action.grayhex(p.get("stem_gray", p["stroke_gray"]))}"/>'
                )
            )

        if p.get("circle_enabled", True):
            elements.append(
                (
                    f'  <circle cx="{p["cx"]:.4f}" cy="{p["cy"]:.4f}" r="{p["r"]:.4f}" '
                    f'fill="{Action.grayhex(p["fill_gray"])}" stroke="{Action.grayhex(p["stroke_gray"])}" '
                    f'stroke-width="{p["stroke_circle"]:.4f}"/>'
                )
            )

        if p.get("draw_text", True):
            if p.get("text_mode") == "path_t":
                elements.append(
                    (
                        f'  <path d="{Action.T_PATH_D}" fill="{Action.grayhex(p["text_gray"])}" '
                        f'transform="translate({p["tx"]:.4f},{p["ty"]:.4f}) '
                        f'scale({p["s"]:.6f},{-p["s"]:.6f}) '
                        f'translate({-Action.T_XMIN},{-Action.T_YMAX})"/>'
                    )
                )
            else:
                elements.append(
                    (
                        f'  <path d="{Action.M_PATH_D}" fill="{Action.grayhex(p["text_gray"])}" '
                        f'transform="translate({p["tx"]:.4f},{p["ty"]:.4f}) '
                        f'scale({p["s"]:.6f},{-p["s"]:.6f}) '
                        f'translate({-Action.M_XMIN},{-Action.M_YMAX})"/>'
                    )
                )

        elements.append("</svg>")
        return "\n".join(elements)

    @staticmethod
    def trace_image_segment(
        img_segment: np.ndarray,
        epsilon_factor: float,
        *,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> list[str]:
        if img_segment is None or img_segment.size == 0:
            return []

        data = np.float32(img_segment).reshape((-1, 3))
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.001)
        _, labels, centers = cv2.kmeans(data, 4, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        centers = np.uint8(centers)
        img_quant = centers[labels.flatten()].reshape(img_segment.shape)

        unique, counts = np.unique(img_quant.reshape(-1, 3), axis=0, return_counts=True)
        bg_color = unique[np.argmax(counts)]

        paths: list[str] = []
        for color in unique:
            if np.array_equal(color, bg_color):
                continue

            mask = cv2.inRange(img_quant, color, color)
            contours, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
            hex_color = rgb_to_hex(color[::-1])

            for contour in contours:
                if cv2.contourArea(contour) < 10:
                    continue

                epsilon = epsilon_factor * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                path_d = "M " + " L ".join(
                    [
                        (
                            f"{(pt[0][0] * scale_x) + offset_x:.3f},"
                            f"{(pt[0][1] * scale_y) + offset_y:.3f}"
                        )
                        for pt in approx
                    ]
                ) + " Z"
                paths.append(f'  <path d="{path_d}" fill="{hex_color}" stroke="none" />')
        return paths

    @staticmethod
    def generate_composite_svg(w: int, h: int, params: dict, folder_path: str, epsilon: float) -> str:
        svg_elements = [
            (
                f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
                'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">'
            )
        ]

        if params["top_source_ref"]:
            ref_path = None
            for ext in [".jpg", ".JPG", ".jpeg", ".JPEG", ".bmp", ".png", ".PNG"]:
                p = os.path.join(folder_path, params["top_source_ref"] + ext)
                if os.path.exists(p):
                    ref_path = p
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
    def _ring_and_fill_masks(h: int, w: int, params: dict) -> tuple[np.ndarray, np.ndarray]:
        yy, xx = np.indices((h, w))
        dist = np.sqrt((xx - params["cx"]) ** 2 + (yy - params["cy"]) ** 2)
        ring_half = max(0.7, params["stroke_circle"])
        ring = np.abs(dist - params["r"]) <= ring_half
        fill = dist <= max(0.5, params["r"] - ring_half)
        return ring, fill

    @staticmethod
    def _mean_gray_for_mask(img: np.ndarray, mask: np.ndarray) -> float | None:
        if int(mask.sum()) == 0:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        vals = gray[mask]
        if vals.size == 0:
            return None
        return float(np.mean(vals))

    @staticmethod
    def _element_region_mask(h: int, w: int, params: dict, element: str) -> np.ndarray | None:
        yy, xx = np.indices((h, w))
        if element == "circle":
            circle = (xx - params["cx"]) ** 2 + (yy - params["cy"]) ** 2 <= (params["r"] + 2.0) ** 2
            top = yy <= (params["cy"] + params["r"] + 1.0)
            return circle & top
        if element == "stem" and params.get("stem_enabled"):
            x1 = max(0.0, params["stem_x"] - 1.0)
            x2 = min(float(w), params["stem_x"] + params["stem_width"] + 1.0)
            y1 = max(0.0, params["stem_top"] - 1.0)
            y2 = min(float(h), params["stem_bottom"] + 1.0)
            return (xx >= x1) & (xx <= x2) & (yy >= y1) & (yy <= y2)
        if element == "arm" and params.get("arm_enabled"):
            x1 = max(0.0, min(params.get("arm_x1", 0.0), params.get("arm_x2", 0.0)) - 1.0)
            x2 = min(float(w), max(params.get("arm_x1", 0.0), params.get("arm_x2", 0.0)) + 1.0)
            y1 = max(0.0, min(params.get("arm_y1", 0.0), params.get("arm_y2", 0.0)) - 1.0)
            y2 = min(float(h), max(params.get("arm_y1", 0.0), params.get("arm_y2", 0.0)) + 1.0)
            pad = max(1.0, params.get("arm_stroke", params.get("stem_or_arm", 1.0)) * 0.8)
            return (xx >= (x1 - pad)) & (xx <= (x2 + pad)) & (yy >= (y1 - pad)) & (yy <= (y2 + pad))
        return None

    @staticmethod
    def _foreground_mask(img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, fg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return fg > 0

    @staticmethod
    def extract_badge_element_mask(img_orig: np.ndarray, params: dict, element: str) -> np.ndarray | None:
        h, w = img_orig.shape[:2]
        region_mask = Action._element_region_mask(h, w, params, element)
        if region_mask is None:
            return None

        fg_bool = Action._foreground_mask(img_orig)
        mask = fg_bool & region_mask

        if int(mask.sum()) < 3:
            return None
        return mask

    @staticmethod
    def _element_only_params(params: dict, element: str) -> dict:
        only = dict(params)
        only["draw_text"] = False
        only["circle_enabled"] = element == "circle"
        only["stem_enabled"] = bool(params.get("stem_enabled") and element == "stem")
        only["arm_enabled"] = bool(params.get("arm_enabled") and element == "arm")
        return only

    @staticmethod
    def _masked_error(img_orig: np.ndarray, img_svg: np.ndarray, mask: np.ndarray | None) -> float:
        if img_svg is None or mask is None or int(mask.sum()) == 0:
            return float("inf")
        if img_svg.shape[:2] != img_orig.shape[:2]:
            img_svg = cv2.resize(img_svg, (img_orig.shape[1], img_orig.shape[0]), interpolation=cv2.INTER_AREA)
        gray_diff = cv2.cvtColor(cv2.absdiff(img_orig, img_svg), cv2.COLOR_BGR2GRAY).astype(np.float32)
        valid = mask.astype(np.float32)
        denom = float(np.sum(valid))
        if denom <= 0.0:
            return float("inf")
        weighted = gray_diff * valid
        return float(np.sum(weighted) / denom)


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

        if 0.92 <= ratio <= 1.10:
            return False, None

        target_width = float(params.get("stem_width", svg_w)) * (orig_w / svg_w)
        target_width = max(1.0, min(target_width, float(w) * 0.20))

        orig_cx = (ox1 + ox2) / 2.0
        params["stem_width"] = target_width
        params["stem_x"] = max(0.0, min(float(w) - target_width, orig_cx - (target_width / 2.0)))
        return True, f"stem: Breitenkorrektur ratio={ratio:.3f}, neu={target_width:.3f}"

    @staticmethod
    def validate_badge_by_elements(
        img_orig: np.ndarray,
        params: dict,
        *,
        max_rounds: int = 3,
        debug_out_dir: str | None = None,
    ) -> list[str]:
        h, w = img_orig.shape[:2]
        logs: list[str] = []
        elements = ["circle"]
        if params.get("stem_enabled"):
            elements.append("stem")
        if params.get("arm_enabled"):
            elements.append("arm")

        for round_idx in range(max_rounds):
            logs.append(f"Runde {round_idx + 1}: elementweise Validierung gestartet")
            full_svg = Action.generate_badge_svg(w, h, params)
            full_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(full_svg, w, h))
            if full_render is None:
                logs.append("Abbruch: SVG konnte nicht gerendert werden")
                break

            if debug_out_dir:
                full_diff = Action.create_diff_image(img_orig, full_render)
                cv2.imwrite(os.path.join(debug_out_dir, f"round_{round_idx + 1:02d}_full_diff.png"), full_diff)

            for element in elements:
                elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(params, element))
                elem_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(elem_svg, w, h))
                if elem_render is None:
                    logs.append(f"{element}: Element-SVG konnte nicht gerendert werden")
                    continue

                mask_orig = Action.extract_badge_element_mask(img_orig, params, element)
                mask_svg = Action.extract_badge_element_mask(elem_render, params, element)
                if mask_orig is None or mask_svg is None:
                    logs.append(f"{element}: Element konnte nicht extrahiert werden")
                    continue

                if debug_out_dir:
                    elem_focus_mask = Action._element_region_mask(h, w, params, element)
                    elem_diff = Action.create_diff_image(img_orig, elem_render, elem_focus_mask)
                    cv2.imwrite(
                        os.path.join(debug_out_dir, f"round_{round_idx + 1:02d}_{element}_diff.png"),
                        elem_diff,
                    )
                elem_err = Action._masked_error(img_orig, elem_render, mask_orig)
                logs.append(f"{element}: Fehler={elem_err:.3f}")

                if element == "stem" and params.get("stem_enabled"):
                    changed, refine_log = Action._refine_stem_geometry_from_masks(params, mask_orig, mask_svg, w)
                    if refine_log:
                        logs.append(refine_log)
                    if changed:
                        logs.append("stem: Geometrie nach Elementabgleich aktualisiert")

            full_svg = Action.generate_badge_svg(w, h, params)
            full_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(full_svg, w, h))
            full_err = Action.calculate_error(img_orig, full_render)
            logs.append(f"Runde {round_idx + 1}: Gesamtfehler={full_err:.3f}")

            if full_err <= 8.0:
                logs.append("Gesamtfehler unter Schwellwert, Validierung beendet")
                break

            if round_idx + 1 >= max_rounds:
                break

        return logs


def run_iteration_pipeline(
    img_path: str,
    csv_path: str,
    max_iterations: int,
    svg_out_dir: str,
    diff_out_dir: str,
    reports_out_dir: str | None = None,
    debug_ac0811_dir: str | None = None,
):
    if cv2 is None or np is None:
        missing = []
        if cv2 is None:
            missing.append("cv2")
        if np is None:
            missing.append("numpy")
        raise RuntimeError(
            "Required image dependencies are missing: " + ", ".join(missing) + ". "
            "Install dependencies before running the conversion pipeline."
        )
    if fitz is None:
        raise RuntimeError(
            "Required SVG renderer dependency is missing: fitz (PyMuPDF). "
            "Install PyMuPDF before running the conversion pipeline."
        )

    folder_path = os.path.dirname(img_path)
    filename = os.path.basename(img_path)

    perc = Perception(img_path, csv_path)
    if perc.img is None:
        return None
    h, w = perc.img.shape[:2]

    ref = Reflection(perc.raw_desc)
    desc, params = ref.parse_description(perc.base_name, filename)

    if not desc.strip() and params["mode"] != "semantic_badge":
        print("  -> Überspringe Bild, da keine begleitende textliche Beschreibung vorliegt.")
        return None

    print(f"\n--- Verarbeite {filename} ---")
    elements = ", ".join(params["elements"]) if params["elements"] else "Kein Compositing-Befehl gefunden"
    print(f"Befehl erkannt: {elements}")

    if params["mode"] == "semantic_badge":
        badge_params = Action.make_badge_params(w, h, perc.base_name, perc.img)
        if badge_params is None:
            return None

        validation_logs: list[str] = []
        debug_dir = None
        if debug_ac0811_dir and perc.base_name.upper() == "AC0811":
            debug_dir = os.path.join(debug_ac0811_dir, os.path.splitext(filename)[0])
            os.makedirs(debug_dir, exist_ok=True)
        validation_logs = Action.validate_badge_by_elements(
            perc.img,
            badge_params,
            debug_out_dir=debug_dir,
        )
        if reports_out_dir:
            log_path = os.path.join(reports_out_dir, f"{os.path.splitext(filename)[0]}_element_validation.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(validation_logs).rstrip() + "\n")

        svg_content = Action.generate_badge_svg(w, h, badge_params)
        base = os.path.splitext(filename)[0]
        with open(os.path.join(svg_out_dir, f"{base}.svg"), "w", encoding="utf-8") as f:
            f.write(svg_content)

        svg_rendered = Action.render_svg_to_numpy(svg_content, w, h)
        if svg_rendered is None:
            raise RuntimeError("SVG rendering failed although fitz is installed.")
        diff = Action.create_diff_image(perc.img, svg_rendered)
        cv2.imwrite(os.path.join(diff_out_dir, f"{base}_diff.png"), diff)
        return base, desc, params, 1, Action.calculate_error(perc.img, svg_rendered)

    if params["mode"] != "composite":
        print("  -> Überspringe Bild, da keine Zerschneide-Anweisung (Compositing) im Text vorliegt.")
        return None

    best_error = float("inf")
    best_svg = ""
    best_diff = None
    best_iter = 0

    epsilon_factors = np.linspace(0.05, 0.0005, max_iterations)
    for i, eps in enumerate(epsilon_factors):
        svg_content = Action.generate_composite_svg(w, h, params, folder_path, float(eps))

        svg_rendered = Action.render_svg_to_numpy(svg_content, w, h)
        error = Action.calculate_error(perc.img, svg_rendered)

        print(f"  [Iter {i+1}/{max_iterations}] Epsilon={eps:.4f} -> Diff-Fehler: {error:.2f}")

        if error < best_error:
            best_error, best_svg, best_iter = error, svg_content, i + 1
            best_diff = Action.create_diff_image(perc.img, svg_rendered)

    print(f"-> Bester Match in Iteration {best_iter} (Fehler auf {best_error:.2f} reduziert)")

    base = os.path.splitext(filename)[0]
    with open(os.path.join(svg_out_dir, f"{base}.svg"), "w", encoding="utf-8") as f:
        f.write(best_svg)
    if best_diff is not None:
        cv2.imwrite(os.path.join(diff_out_dir, f"{base}_diff.png"), best_diff)

    return base, desc, params, best_iter, best_error


def _extract_ref_parts(name: str) -> tuple[str, int] | None:
    match = re.match(r"^([A-Z]{2})(\d{3,4})$", name.upper())
    if not match:
        return None
    return match.group(1), int(match.group(2))


def _in_requested_range(filename: str, start_ref: str, end_ref: str) -> bool:
    stem = get_base_name_from_file(os.path.splitext(filename)[0]).upper()
    stem_parts = _extract_ref_parts(stem)
    start_parts = _extract_ref_parts(start_ref)
    end_parts = _extract_ref_parts(end_ref)
    if stem_parts is None or start_parts is None or end_parts is None:
        return False

    stem_prefix, stem_n = stem_parts
    start_prefix, start_n = start_parts
    end_prefix, end_n = end_parts

    if start_prefix != end_prefix or stem_prefix != start_prefix:
        return False

    return start_n <= stem_n <= end_n


def _default_converted_symbols_root() -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "artifacts", "converted_symbols")


def convert_range(
    folder_path: str,
    csv_path: str,
    iterations: int,
    start_ref: str = "AR0102",
    end_ref: str = "AR0104",
    debug_ac0811_dir: str | None = None,
) -> str:
    out_root = _default_converted_symbols_root()
    svg_out_dir = os.path.join(out_root, "svg")
    diff_out_dir = os.path.join(out_root, "diff_pngs")
    reports_out_dir = os.path.join(out_root, "reports")

    os.makedirs(svg_out_dir, exist_ok=True)
    os.makedirs(diff_out_dir, exist_ok=True)
    os.makedirs(reports_out_dir, exist_ok=True)

    files = sorted(
        f
        for f in os.listdir(folder_path)
        if f.lower().endswith((".bmp", ".jpg", ".png")) and _in_requested_range(f, start_ref, end_ref)
    )

    log_path = os.path.join(reports_out_dir, "Iteration_Log.csv")
    with open(log_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Dateiname", "Gefundene Elemente", "Beste Iteration", "Diff-Score"])
        for filename in files:
            res = run_iteration_pipeline(
                os.path.join(folder_path, filename),
                csv_path,
                iterations,
                svg_out_dir,
                diff_out_dir,
                reports_out_dir,
                debug_ac0811_dir,
            )
            if res:
                _base, _desc, params, best_iter, best_error = res
                writer.writerow([filename, " + ".join(params["elements"]), best_iter, f"{best_error:.2f}"])

    return out_root


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = convert_range(
        args.folder_path,
        args.csv_path,
        args.iterations,
        args.start,
        args.end,
        args.debug_ac0811_dir,
    )
    print(f"\nAbgeschlossen! Ausgaben unter: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
