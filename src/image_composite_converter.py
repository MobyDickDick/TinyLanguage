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

        if base_name.upper() in {"AR0100", "AC0870", "AC0881", "AC0882"}:
            params["mode"] = "semantic_badge"
            params["elements"].append("SEMANTIC: Kreis + Buchstabe")
            params["label"] = "M" if base_name.upper() == "AR0100" else "T"
            if base_name.upper() == "AC0881":
                params["elements"].append("SEMANTIC: senkrechter Strich hinter dem Kreis")
            if base_name.upper() == "AC0882":
                params["elements"].append("SEMANTIC: waagrechter Strich links vom Kreis")
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

    @staticmethod
    def grayhex(gray: int) -> str:
        g = max(0, min(255, int(round(gray))))
        return f"#{g:02x}{g:02x}{g:02x}"

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
        return params

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
    def _default_ac0882_params(w: int, h: int) -> dict:
        sx = w / 45.0 if w > 0 else 1.0
        sy = h / 25.0 if h > 0 else 1.0
        s = min(sx, sy)

        params = {
            "cx": 18.0 * sx,
            "cy": 12.5 * sy,
            "r": 8.4 * s,
            "stroke_circle": 1.5 * s,
            "fill_gray": 220,
            "stroke_gray": 152,
            "text_gray": 98,
            "label": "T",
            "text_mode": "path_t",
            "arm_enabled": True,
            "arm_x1": 2.0 * sx,
            "arm_y": 12.5 * sy,
            "arm_x2": 10.0 * sx,
            "arm_stroke": 2.0 * s,
            "s": 0.0088 * s,
        }
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
            return {
                "cx": 15.0 * scale,
                "cy": 15.0 * scale,
                "r": 12.0 * scale,
                "stroke_circle": 2.0 * scale,
                "fill_gray": 220,
                "stroke_gray": 152,
                "draw_text": False,
            }

        if name == "AC0811":
            params = Action._default_ac0881_params(w, h)
            params["draw_text"] = False
            params["fill_gray"] = 220
            params["stroke_gray"] = 98
            params["stem_gray"] = 98
            return params

        if name == "AC0881":
            return Action._default_ac0881_params(w, h)

        if name == "AC0882":
            return Action._default_ac0882_params(w, h)

        return None

    @staticmethod
    def generate_badge_svg(w: int, h: int, p: dict) -> str:
        elements = [
            f'<svg width="{w}px" height="{h}px" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'
        ]

        if p.get("arm_enabled"):
            elements.append(
                (
                    f'  <line x1="{p["arm_x1"]:.4f}" y1="{p["arm_y"]:.4f}" '
                    f'x2="{p["arm_x2"]:.4f}" y2="{p["arm_y"]:.4f}" '
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
    def create_diff_image(img_orig: np.ndarray, img_svg: np.ndarray) -> np.ndarray:
        gray_orig = cv2.cvtColor(img_orig, cv2.COLOR_BGR2GRAY)
        gray_svg = cv2.cvtColor(img_svg, cv2.COLOR_BGR2GRAY)
        diff = np.zeros_like(img_orig)
        diff[:, :, 2] = gray_orig
        diff[:, :, 1] = gray_svg
        diff[:, :, 0] = gray_svg
        return diff

    @staticmethod
    def calculate_error(img_orig: np.ndarray, img_svg: np.ndarray) -> float:
        if img_svg is None:
            return float("inf")
        return float(np.mean(cv2.absdiff(img_orig, img_svg)))


def run_iteration_pipeline(img_path: str, csv_path: str, max_iterations: int, out_dir: str):
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

        svg_content = Action.generate_badge_svg(w, h, badge_params)
        base = os.path.splitext(filename)[0]
        with open(os.path.join(out_dir, f"{base}.svg"), "w", encoding="utf-8") as f:
            f.write(svg_content)

        svg_rendered = Action.render_svg_to_numpy(svg_content, w, h)
        if svg_rendered is None:
            raise RuntimeError("SVG rendering failed although fitz is installed.")
        diff = Action.create_diff_image(perc.img, svg_rendered)
        cv2.imwrite(os.path.join(out_dir, f"{base}_diff.png"), diff)
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
    with open(os.path.join(out_dir, f"{base}.svg"), "w", encoding="utf-8") as f:
        f.write(best_svg)
    if best_diff is not None:
        cv2.imwrite(os.path.join(out_dir, f"{base}_diff.png"), best_diff)

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


def convert_range(folder_path: str, csv_path: str, iterations: int, start_ref: str = "AR0102", end_ref: str = "AR0104") -> str:
    out_dir = os.path.join(folder_path, "Iterated_SVGs")
    os.makedirs(out_dir, exist_ok=True)

    files = sorted(
        f
        for f in os.listdir(folder_path)
        if f.lower().endswith((".bmp", ".jpg", ".png")) and _in_requested_range(f, start_ref, end_ref)
    )

    log_path = os.path.join(out_dir, "Iteration_Log.csv")
    with open(log_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Dateiname", "Gefundene Elemente", "Beste Iteration", "Diff-Score"])
        for filename in files:
            res = run_iteration_pipeline(os.path.join(folder_path, filename), csv_path, iterations, out_dir)
            if res:
                _base, _desc, params, best_iter, best_error = res
                writer.writerow([filename, " + ".join(params["elements"]), best_iter, f"{best_error:.2f}"])

    return out_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder_path", help="Pfad zum Ordner mit den Bildern")
    parser.add_argument("csv_path", help="Pfad zur CSV/Export-Tabelle")
    parser.add_argument("iterations", type=int, help="Anzahl der Iterationen (z.B. 8)")
    parser.add_argument("--start", default="AR0102", help="Start-Referenz (inkl.), default: AR0102")
    parser.add_argument("--end", default="AR0104", help="End-Referenz (inkl.), default: AR0104")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = convert_range(args.folder_path, args.csv_path, args.iterations, args.start, args.end)
    print(f"\nAbgeschlossen! Ausgaben unter: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
