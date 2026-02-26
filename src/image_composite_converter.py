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

import cv2
import numpy as np

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
        desc = self.raw_desc.get(base_name, "").lower()
        desc += " " + self.raw_desc.get(os.path.splitext(img_filename)[0], "").lower()

        params = {
            "mode": "auto",
            "top_source_ref": None,
            "bottom_shape": None,
            "elements": [],
            "label": "M",
        }

        if base_name.upper() == "AR0100":
            params["mode"] = "semantic_badge"
            params["elements"].append("SEMANTIC: Kreis + Buchstabe")
            params["label"] = "M"
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
    M_YMAX = 1493

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

    @staticmethod
    def grayhex(gray: int) -> str:
        g = max(0, min(255, int(round(gray))))
        return f"#{g:02x}{g:02x}{g:02x}"

    @staticmethod
    def make_badge_params(w: int, h: int, base_name: str) -> dict | None:
        if base_name.upper() != "AR0100":
            return None

        scale = min(w, h) / 25.0 if min(w, h) > 0 else 1.0
        b = Action.AR0100_BASE
        return {
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
        }

    @staticmethod
    def generate_badge_svg(w: int, h: int, p: dict) -> str:
        return "\n".join(
            [
                f'<svg width="{w}px" height="{h}px" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">',
                (
                    f'  <circle cx="{p["cx"]:.4f}" cy="{p["cy"]:.4f}" r="{p["r"]:.4f}" '
                    f'fill="{Action.grayhex(p["fill_gray"])}" stroke="{Action.grayhex(p["stroke_gray"])}" '
                    f'stroke-width="{p["stroke_circle"]:.4f}"/>'
                ),
                (
                    f'  <path d="{Action.M_PATH_D}" fill="{Action.grayhex(p["text_gray"])}" '
                    f'transform="translate({p["tx"]:.4f},{p["ty"]:.4f}) '
                    f'scale({p["s"]:.6f},{-p["s"]:.6f}) '
                    f'translate({-Action.M_XMIN},{-Action.M_YMAX})"/>'
                ),
                "</svg>",
            ]
        )

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
    folder_path = os.path.dirname(img_path)
    filename = os.path.basename(img_path)

    perc = Perception(img_path, csv_path)
    if perc.img is None:
        return None
    h, w = perc.img.shape[:2]

    ref = Reflection(perc.raw_desc)
    desc, params = ref.parse_description(perc.base_name, filename)

    print(f"\n--- Verarbeite {filename} ---")
    elements = ", ".join(params["elements"]) if params["elements"] else "Kein Compositing-Befehl gefunden"
    print(f"Befehl erkannt: {elements}")

    if params["mode"] == "semantic_badge":
        badge_params = Action.make_badge_params(w, h, perc.base_name)
        if badge_params is None:
            return None

        svg_content = Action.generate_badge_svg(w, h, badge_params)
        base = os.path.splitext(filename)[0]
        with open(os.path.join(out_dir, f"{base}.svg"), "w", encoding="utf-8") as f:
            f.write(svg_content)

        if fitz is not None:
            svg_rendered = Action.render_svg_to_numpy(svg_content, w, h)
            if svg_rendered is not None:
                diff = Action.create_diff_image(perc.img, svg_rendered)
                cv2.imwrite(os.path.join(out_dir, f"{base}_diff.png"), diff)
                return base, desc, params, 1, Action.calculate_error(perc.img, svg_rendered)

        return base, desc, params, 1, float("inf")

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

        if fitz is not None:
            svg_rendered = Action.render_svg_to_numpy(svg_content, w, h)
            error = Action.calculate_error(perc.img, svg_rendered)
        else:
            error = 0.0
            svg_rendered = np.zeros_like(perc.img)

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


def _extract_ar_number(name: str) -> int | None:
    match = re.match(r"^AR(\d{3,4})$", name.upper())
    if not match:
        return None
    return int(match.group(1))


def _in_requested_range(filename: str, start_ref: str, end_ref: str) -> bool:
    stem = os.path.splitext(filename)[0].upper()
    stem_n = _extract_ar_number(stem)
    start_n = _extract_ar_number(start_ref)
    end_n = _extract_ar_number(end_ref)
    if stem_n is None or start_n is None or end_n is None:
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
