"""Image-to-composite-SVG conversion pipeline.

Ported from the user-provided prototype and exposed as a Python helper module so
it can be executed directly or via TinyLanguage (`src_tiny/image_composite_converter.tiny`).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import time
import re
import subprocess
import sys
from dataclasses import dataclass

try:
    from src.converter_runtime_bootstrap import configure_converter_runtime
except ModuleNotFoundError:  # Script-Ausführung aus src/-Verzeichnis
    from converter_runtime_bootstrap import configure_converter_runtime

configure_converter_runtime()

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


def _missing_required_image_dependencies() -> list[str]:
    missing: list[str] = []
    if cv2 is None:
        missing.append("opencv-python-headless")
    if np is None:
        missing.append("numpy")
    return missing


def _bootstrap_required_image_dependencies() -> list[str]:
    missing = _missing_required_image_dependencies()
    if not missing:
        return []

    cmd = [sys.executable, "-m", "pip", "install", *missing]
    print(f"[INFO] Fehlende Bild-Abhängigkeiten gefunden: {', '.join(missing)}")
    print(f"[INFO] Installiere via: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Automatische Installation fehlgeschlagen. "
            "Bitte Abhängigkeiten manuell installieren oder Proxy/Netzwerk prüfen."
        ) from exc

    # Re-import in current process so conversion can run without restart.
    global cv2, np
    if "opencv-python-headless" in missing:
        import cv2 as _cv2

        cv2 = _cv2
    if "numpy" in missing:
        import numpy as _np

        np = _np

    return missing


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

        if base_name.upper() in {
            "AR0100",
            "AC0810",
            "AC0812",
            "AC0813",
            "AC0814",
            "AC0820",
            "AC0831",
            "AC0832",
            "AC0833",
            "AC0834",
            "AC0835",
            "AC0836",
            "AC0837",
            "AC0838",
            "AC0839",
            "AC0870",
            "AC0881",
            "AC0882",
        }:
            params["mode"] = "semantic_badge"
            if base_name.upper() in {"AC0810", "AC0812", "AC0813", "AC0814"}:
                params["elements"].append("SEMANTIC: Kreis ohne Buchstabe")
                params["label"] = ""
            elif base_name.upper() in {"AC0820", "AC0831", "AC0832", "AC0833", "AC0834"}:
                params["elements"].append("SEMANTIC: Kreis + Buchstabe CO_2")
                params["label"] = "CO_2"
            elif base_name.upper() in {"AC0835", "AC0836", "AC0837", "AC0838", "AC0839"}:
                params["elements"].append("SEMANTIC: Kreis + Buchstabe VOC")
                params["label"] = "VOC"
            else:
                params["elements"].append("SEMANTIC: Kreis + Buchstabe")
                params["label"] = "M" if base_name.upper() == "AR0100" else "T"
            if base_name.upper() == "AC0810":
                params["elements"].append("SEMANTIC: waagrechter Strich rechts vom Kreis")
            if base_name.upper() == "AC0881":
                params["elements"].append("SEMANTIC: senkrechter Strich hinter dem Kreis")
            if base_name.upper() in {"AC0812", "AC0882"}:
                params["elements"].append("SEMANTIC: waagrechter Strich links vom Kreis")
            if base_name.upper() == "AC0813":
                params["elements"].append("SEMANTIC: senkrechter Strich oben vom Kreis")
            if base_name.upper() == "AC0814":
                params["elements"].append("SEMANTIC: waagrechter Strich rechts vom Kreis")
            if base_name.upper() == "AC0831":
                params["elements"].append("SEMANTIC: senkrechter Strich hinter dem Kreis")
            if base_name.upper() == "AC0832":
                params["elements"].append("SEMANTIC: waagrechter Strich links vom Kreis")
            if base_name.upper() == "AC0833":
                params["elements"].append("SEMANTIC: senkrechter Strich oben vom Kreis")
            if base_name.upper() == "AC0834":
                params["elements"].append("SEMANTIC: waagrechter Strich rechts vom Kreis")
            if base_name.upper() == "AC0836":
                params["elements"].append("SEMANTIC: senkrechter Strich hinter dem Kreis")
            if base_name.upper() == "AC0837":
                params["elements"].append("SEMANTIC: waagrechter Strich links vom Kreis")
            if base_name.upper() == "AC0838":
                params["elements"].append("SEMANTIC: senkrechter Strich oben vom Kreis")
            if base_name.upper() == "AC0839":
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
    STOCHASTIC_SEED_OFFSET = 0
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
    # Einheitliche AC08xx-Grauwerte (entspricht #7F7F7F).
    LIGHT_CIRCLE_STROKE_GRAY = 127
    LIGHT_CIRCLE_TEXT_GRAY = 127
    AC08_STROKE_WIDTH_PX = 1.0

    @staticmethod
    def grayhex(gray: int) -> str:
        g = max(0, min(255, int(round(gray))))
        return f"#{g:02x}{g:02x}{g:02x}"

    @staticmethod
    def _snap_half(value: float) -> float:
        return round(float(value) * 2.0) / 2.0

    @staticmethod
    def _snap_int_px(value: float, minimum: float = 1.0) -> float:
        return float(max(int(round(float(minimum))), int(round(float(value)))))

    @staticmethod
    def _enforce_circle_connector_symmetry(params: dict, w: int, h: int) -> dict:
        """Keep circle+connector "lollipop" geometry centered around the connector axis."""
        p = dict(params)
        if not p.get("circle_enabled", True):
            return p
        if "cx" not in p or "cy" not in p or "r" not in p:
            return p

        cx = float(p["cx"])
        cy = float(p["cy"])
        r = float(p["r"])

        if p.get("stem_enabled") and "stem_width" in p:
            p["stem_x"] = cx - (float(p["stem_width"]) / 2.0)

        if p.get("arm_enabled") and all(k in p for k in ("arm_x1", "arm_y1", "arm_x2", "arm_y2")):
            x1 = float(p["arm_x1"])
            y1 = float(p["arm_y1"])
            x2 = float(p["arm_x2"])
            y2 = float(p["arm_y2"])

            vertical = abs(x2 - x1) <= abs(y2 - y1)
            if vertical:
                p["arm_x1"] = cx
                p["arm_x2"] = cx
                end_is_p2 = abs(y2 - cy) <= abs(y1 - cy)
                if end_is_p2:
                    p["arm_y2"] = cy - r if y1 <= cy else cy + r
                else:
                    p["arm_y1"] = cy - r if y2 <= cy else cy + r
            else:
                p["arm_y1"] = cy
                p["arm_y2"] = cy
                end_is_p2 = abs(x2 - cx) <= abs(x1 - cx)
                if end_is_p2:
                    p["arm_x2"] = cx - r if x1 <= cx else cx + r
                else:
                    p["arm_x1"] = cx - r if x2 <= cx else cx + r

        if "stem_x" in p and "stem_width" in p:
            p["stem_x"] = max(0.0, min(float(w) - float(p["stem_width"]), float(p["stem_x"])))
        for key in ("arm_x1", "arm_x2"):
            if key in p:
                p[key] = max(0.0, min(float(w), float(p[key])))
        for key in ("arm_y1", "arm_y2"):
            if key in p:
                p[key] = max(0.0, min(float(h), float(p[key])))
        return p

    @staticmethod
    def _quantize_badge_params(params: dict, w: int, h: int) -> dict:
        """Quantize geometry for bitmap-like sources.

        - Coordinates/lengths use 0.5px steps.
        - Line widths use integer pixel steps.
        """
        p = dict(params)

        half_keys = (
            "cx",
            "cy",
            "r",
            "stem_x",
            "stem_top",
            "stem_bottom",
            "arm_x1",
            "arm_y1",
            "arm_x2",
            "arm_y2",
            "tx",
            "ty",
            "co2_dy",
        )
        for key in half_keys:
            if key in p:
                p[key] = Action._snap_half(float(p[key]))

        int_width_keys = ("stroke_circle", "arm_stroke", "stem_width")
        for key in int_width_keys:
            if key in p:
                p[key] = Action._snap_int_px(float(p[key]), minimum=1.0)

        if "stem_width_max" in p:
            p["stem_width_max"] = max(1.0, Action._snap_half(float(p["stem_width_max"])))

        if p.get("stem_enabled") and "cx" in p and "stem_width" in p:
            p["stem_x"] = Action._snap_half(float(p["cx"]) - (float(p["stem_width"]) / 2.0))

        if "stem_x" in p and "stem_width" in p:
            p["stem_x"] = max(0.0, min(float(w) - float(p["stem_width"]), float(p["stem_x"])))
        if "stem_top" in p:
            p["stem_top"] = max(0.0, min(float(h), float(p["stem_top"])))
        if "stem_bottom" in p:
            p["stem_bottom"] = max(0.0, min(float(h), float(p["stem_bottom"])))

        p = Action._enforce_circle_connector_symmetry(p, w, h)

        # Symmetry enforcement may reintroduce non-snapped values.
        for key in half_keys:
            if key in p:
                p[key] = Action._snap_half(float(p[key]))

        return p

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
    def _normalize_ac08_line_widths(params: dict) -> dict:
        """For AC08xx symbols: prefer a uniform 1px circle/connector stroke."""
        p = dict(params)
        p["stroke_circle"] = Action.AC08_STROKE_WIDTH_PX
        # Keep semantic AC08xx families on their canonical stroke thickness.
        # The later pixel-error bracketing step can otherwise over-fit anti-aliased
        # ring edges and inflate widths (e.g. 1px -> 6px for tiny circles).
        p["lock_stroke_widths"] = True
        if p.get("arm_enabled"):
            p["arm_stroke"] = Action.AC08_STROKE_WIDTH_PX
        if p.get("stem_enabled"):
            p["stem_width"] = Action.AC08_STROKE_WIDTH_PX
            if "cx" in p:
                p["stem_x"] = float(p["cx"]) - (Action.AC08_STROKE_WIDTH_PX / 2.0)
            p["stem_gray"] = int(p.get("stroke_gray", Action.LIGHT_CIRCLE_STROKE_GRAY))
        return p

    @staticmethod
    def _persist_connector_length_floor(params: dict, element: str, default_ratio: float) -> None:
        """Persist a robust minimum connector length for later validation stages."""
        if element == "stem":
            length = float(params.get("stem_bottom", 0.0)) - float(params.get("stem_top", 0.0))
            min_key = "stem_len_min"
            ratio_key = "stem_len_min_ratio"
        elif element == "arm":
            x1 = float(params.get("arm_x1", 0.0))
            y1 = float(params.get("arm_y1", 0.0))
            x2 = float(params.get("arm_x2", 0.0))
            y2 = float(params.get("arm_y2", 0.0))
            length = float(math.hypot(x2 - x1, y2 - y1))
            min_key = "arm_len_min"
            ratio_key = "arm_len_min_ratio"
        else:
            return

        if length <= 0.0:
            return

        ratio = float(max(0.0, min(1.0, float(params.get(ratio_key, default_ratio)))))
        params[ratio_key] = ratio
        params[min_key] = float(max(float(params.get(min_key, 1.0)), length * ratio, 1.0))

    @staticmethod
    def _finalize_ac08_style(name: str, params: dict) -> dict:
        """Apply AC08xx palette/stroke conventions globally for semantic conversions."""
        canonical_name = str(name).upper()
        symbol_name = canonical_name.split("_", 1)[0]
        if not symbol_name.startswith("AC08"):
            return params
        p = Action._capture_canonical_badge_colors(Action._normalize_light_circle_colors(dict(params)))
        # During geometry fitting we intentionally keep auto-estimated colors.
        # Canonical palette values are re-applied once fitting converged.
        p = Action._normalize_ac08_line_widths(p)
        p["lock_colors"] = True
        if symbol_name != "AC0820":
            p = Action._normalize_centered_co2_label(p)
        if symbol_name == "AC0820" and str(p.get("text_mode", "")).lower() == "co2":
            # AC0820 variants (L/M/S): keep "CO" itself centered and nudge it
            # slightly lower. Centering the whole cluster makes the visually
            # dominant run look too far left in tiny badges.
            p["co2_anchor_mode"] = "center_co"
            p["co2_optical_bias"] = 0.125
            r = max(1.0, float(p.get("r", 1.0)))
            # Keep AC0820 text close to the cap-height used by centered path
            # glyph labels (e.g. single C) so the leading "C" is no longer
            # undersized compared to the original badge family.
            if r >= 10.0:
                p["co2_font_scale"] = 0.94
            elif r >= 6.0:
                p["co2_font_scale"] = 0.95
            else:
                p["co2_font_scale"] = 0.97
            # Keep AC0820_M/S adjustable in validation: the tiny CO run can still
            # be slightly undersized after geometric fitting, but we do not want
            # unconstrained growth that reintroduces prior over-scaling regressions.
            base_scale = float(p["co2_font_scale"])
            p["co2_font_scale_min"] = float(max(0.84, base_scale * 0.92))
            p["co2_font_scale_max"] = float(min(1.12, base_scale * 1.22))
            p["co2_sub_font_scale"] = float(p.get("co2_sub_font_scale", 66.0))
            p["co2_subscript_offset_scale"] = 0.27
        if p.get("circle_enabled", True):
            has_connector = bool(p.get("arm_enabled") or p.get("stem_enabled"))
            has_text = bool(p.get("draw_text", False))

            # For all semantic AC08xx badges, keep a robust radius floor anchored
            # to the template geometry. This prevents degenerate late-stage fits
            # where noisy masks shrink circles far below their known base size.
            template_r = float(p.get("template_circle_radius", p.get("r", 1.0)))
            current_r = float(p.get("r", template_r))
            base_r = max(1.0, template_r, current_r)
            min_ratio = 0.88
            if has_text:
                # Text badges are especially sensitive to circle shrink because
                # the label scales relative to the interior diameter.
                min_ratio = 0.92 if symbol_name == "AC0820" else 0.90
            p["min_circle_radius"] = float(max(float(p.get("min_circle_radius", 1.0)), base_r * min_ratio))

            # Plain centered badges should keep their circle optically centered.
            # Otherwise min-rect alignment may drift the ring into a corner,
            # which also makes CO/VOC labels look far too small.
            if not has_connector:
                p["lock_circle_cx"] = True
                p["lock_circle_cy"] = True

            # Connector-only and connector+text badges can both lose connector
            # extraction in noisy JPEGs. Without geometric anchors the circle
            # optimizer may collapse toward unrelated border blobs (for plain
            # symbols) or text blobs (for labeled symbols). Keep the center and
            # connector alignment locked to template semantics for all connector
            # families so rotations/reflections/scales remain stable.
            if has_connector:
                p["lock_circle_cx"] = True
                p["lock_circle_cy"] = True
                if p.get("stem_enabled"):
                    p["lock_stem_center_to_circle"] = True
                    p["stem_center_lock_max_offset"] = float(max(0.35, float(p.get("stroke_circle", 1.0)) * 0.6))
                    p["allow_stem_width_tuning"] = True
                    p["stem_width_tuning_px"] = 1.0
                if p.get("arm_enabled"):
                    p["lock_arm_center_to_circle"] = True

            if bool(p.get("lock_circle_cx", False)) and "template_circle_cx" in p:
                p["cx"] = float(p["template_circle_cx"])
            if bool(p.get("lock_circle_cy", False)) and "template_circle_cy" in p:
                p["cy"] = float(p["template_circle_cy"])
        if p.get("stem_enabled"):
            Action._persist_connector_length_floor(p, "stem", default_ratio=0.65)
        if p.get("arm_enabled"):
            Action._persist_connector_length_floor(p, "arm", default_ratio=0.75)
        if str(p.get("text_mode", "")).lower() == "co2":
            min_dim = float(min(float(p.get("width", 0.0) or 0.0), float(p.get("height", 0.0) or 0.0)))
            if min_dim <= 0.0:
                # Fallback for call sites that only pass geometry parameters.
                min_dim = max(1.0, float(p.get("r", 1.0)) * 2.0)

            # Keep AC0820 variants tunable (bounded via *_min/*_max overrides).
            # Very small CO₂ badges from other AC08xx families (e.g. AC0833_S)
            # can exhibit the same undersizing behavior after anti-aliased fitting,
            # so unlock bounded tuning for tiny variants in general.
            tiny_co2_variant = min_dim <= 15.5
            p["lock_text_scale"] = not (symbol_name == "AC0820" or tiny_co2_variant)
            if tiny_co2_variant:
                base_scale = float(p.get("co2_font_scale", 0.82))
                p["co2_font_scale_min"] = float(max(0.74, base_scale * 0.90))
                p["co2_font_scale_max"] = float(min(1.18, base_scale * 1.25))
        if str(p.get("text_mode", "")).lower() == "voc":
            min_dim = float(min(float(p.get("width", 0.0) or 0.0), float(p.get("height", 0.0) or 0.0)))
            if min_dim <= 0.0:
                min_dim = max(1.0, float(p.get("r", 1.0)) * 2.0)
            if symbol_name == "AC0835" and min_dim <= 15.5:
                # AC0835_S tends to over-scale VOC during text bracketing,
                # producing a visibly heavy label compared to the source icon.
                base_scale = float(p.get("voc_font_scale", 0.52))
                p["lock_text_scale"] = False
                p["voc_font_scale_min"] = float(max(0.58, base_scale * 0.90))
                p["voc_font_scale_max"] = float(min(0.92, base_scale * 1.05))
        if p.get("draw_text", True) and "text_gray" in p:
            p["text_gray"] = int(p.get("stroke_gray", Action.LIGHT_CIRCLE_STROKE_GRAY))
        return p

    @staticmethod
    def _align_stem_to_circle_center(params: dict) -> dict:
        """Ensure vertical handle/stem extension runs through circle center.

        For vertical connector badges (e.g. AC0811/AC0831/AC0836), force the
        connector start to the circle edge so quantization does not leave a
        visible gap between circle and stem.
        """
        if params.get("stem_enabled") and params.get("circle_enabled", True):
            if "stem_width" in params and "cx" in params:
                params["stem_x"] = float(params["cx"]) - (float(params["stem_width"]) / 2.0)
            if "cy" in params and "r" in params:
                params["stem_top"] = float(params["cy"]) + float(params["r"])
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
        # AC0811 reference symbols use a visually slim vertical handle.
        # Persist an explicit width ceiling so later fitting/validation
        # steps cannot widen the stem beyond the template's intent.
        stem_width_max = max(1.0, float(w) * 0.105)
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
            "stem_width_max": stem_width_max,
            "stem_x": cx - (stem_width / 2.0),
            "stem_top": cy + r,
            "stem_bottom": min(float(h), (cy + r) + stem_len),
            "stem_gray": Action.LIGHT_CIRCLE_STROKE_GRAY,
        })

    @staticmethod
    def _estimate_upper_circle_from_foreground(img: np.ndarray, defaults: dict) -> tuple[float, float, float] | None:
        """Estimate circle geometry from the upper symbol region.

        AC0811_S is very small and Hough-based fitting can drift on anti-aliased
        edges. This fallback uses a simple foreground extraction in the upper part
        of the symbol and derives a robust enclosing circle from the largest blob.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        if h <= 0 or w <= 0:
            return None

        _, fg = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        top_limit = int(round(min(float(h), float(defaults.get("cy", h / 2.0)) + float(defaults.get("r", w / 3.0)) * 1.15)))
        top_limit = max(3, min(h, top_limit))
        roi = fg[:top_limit, :]
        if roi.size == 0:
            return None

        contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        best = None
        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < 8.0:
                continue
            perimeter = float(cv2.arcLength(cnt, True))
            if perimeter <= 0.0:
                continue
            circularity = 4.0 * np.pi * area / max(1e-6, perimeter * perimeter)
            if circularity < 0.35:
                continue
            score = area * (0.5 + circularity)
            if best is None or score > best[0]:
                best = (score, cnt)

        if best is None:
            return None

        (_score, cnt) = best
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        min_r = max(2.0, float(w) * 0.24)
        max_r = min(float(w) * 0.52, float(top_limit) * 0.58)
        if max_r < min_r:
            max_r = min_r
        r = float(np.clip(r, min_r, max_r))
        cx = float(np.clip(cx, 0.0, float(w - 1)))
        cy = float(np.clip(cy, 0.0, float(h - 1)))
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
            cy = float(np.clip(cy, default_cy - 0.8, default_cy + 0.8))
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
            r = float(np.clip(r, default_r * 0.95, default_r * 1.08))
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
        params["co2_font_scale"] = float(params.get("co2_font_scale", 0.82))
        params["co2_sub_font_scale"] = float(params.get("co2_sub_font_scale", 66.0))
        params["co2_dx"] = float(params.get("co2_dx", 0.0))
        params["co2_dy"] = float(params.get("co2_dy", 0.0))
        # Keep "CO" as an explicit run so the subscript position remains stable across
        # renderers. By default we keep "CO" itself centered in the badge and attach
        # the subscript to the right; this avoids visible drift in compact variants.
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
        font_size = min(requested_font_size, max_font_size)
        sub_scale = float(params.get("co2_sub_font_scale", 66.0))
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
            # Default mode: keep the "CO" run itself centered and attach the ₂ rightward.
            # Prioritize matching the main "CO" glyphs first; if space is tight, shrink
            # or tuck the subscript before shifting the dominant "CO" run.
            co_x = cx + float(params.get("co2_dx", 0.0))
            x1 = co_x - (co_width / 2.0)

            local_gap = gap
            local_sub_font_px = sub_font_px
            local_sub_w = sub_w
            subscript_x = co_x + (co_width / 2.0) + local_gap
            x2 = subscript_x + local_sub_w

            stroke = max(0.8, float(params.get("stroke_circle", 1.0)))
            inner_right = cx + max(1.0, r - stroke)
            inner_left = cx - max(1.0, r - stroke)

            overflow = x2 - inner_right
            if overflow > 0.0:
                # Step 1: reduce spacing before moving CO.
                min_gap = font_size * 0.005
                shrink_gap = min(overflow, max(0.0, local_gap - min_gap))
                local_gap -= shrink_gap
                overflow -= shrink_gap

                # Step 2: reduce subscript size (keep readable floor) before moving CO.
                if overflow > 0.0:
                    min_sub_font_px = max(3.6, font_size * 0.42)
                    max_shrink_px = max(0.0, local_sub_font_px - min_sub_font_px)
                    shrink_px = min(max_shrink_px, overflow / 0.62)
                    local_sub_font_px -= shrink_px
                    local_sub_w = local_sub_font_px * 0.62

                # Recompute geometry with adjusted ₂ attachment.
                sub_font_px = local_sub_font_px
                subscript_x = co_x + (co_width / 2.0) + local_gap
                x2 = subscript_x + local_sub_w

                # Step 3: only if still necessary, shift cluster minimally left.
                overflow = x2 - inner_right
                if overflow > 0.0:
                    co_x -= overflow
                    x1 -= overflow
                    subscript_x -= overflow
                    x2 -= overflow

            # Keep the left side inside the inner circle as well.
            left_overflow = inner_left - x1
            if left_overflow > 0.0:
                co_x += left_overflow
                x1 += left_overflow
                subscript_x += left_overflow
                x2 += left_overflow

        # Capital glyphs usually appear slightly high when simply middle-anchored.
        # Apply a proportional optical correction so the label sits visually centered.
        # A stronger correction keeps the "CO" run from looking top-heavy in tiny
        # AC08xx badges where antialiasing exaggerates baseline drift.
        # Large variants (e.g. AC0820_L) can still look top-heavy with a fixed
        # correction. Nudge bigger badges slightly further down while keeping the
        # small-size behavior effectively unchanged.
        optical_bias = float(params.get("co2_optical_bias", 0.090 + (0.015 * min(1.0, r / 12.0))))
        y_base = cy + float(params.get("co2_dy", 0.0)) + (font_size * optical_bias)
        subscript_offset = font_size * float(params.get("co2_subscript_offset_scale", 0.18))
        height = font_size * 0.95

        # Keep text vertically within the circle's clear area.
        stroke = max(0.8, float(params.get("stroke_circle", 1.0)))
        inner_top = cy - max(1.0, r - stroke)
        inner_bottom = cy + max(1.0, r - stroke)
        top = y_base - (height / 2.0)
        bottom = y_base + (height / 2.0)
        if top < inner_top:
            delta = inner_top - top
            y_base += delta
        elif bottom > inner_bottom:
            delta = bottom - inner_bottom
            y_base -= delta

        # Keep the subscript readable and away from the border, but do not let it
        # drive the vertical centering of the main "CO" run.
        min_subscript_offset = font_size * 0.08
        max_subscript_offset = font_size * 0.24
        subscript_offset = float(max(min_subscript_offset, min(max_subscript_offset, subscript_offset)))
        subscript_y = y_base + subscript_offset
        sub_bottom = subscript_y + (sub_font_px * 0.35)
        if sub_bottom > inner_bottom:
            max_offset = inner_bottom - y_base - (sub_font_px * 0.35)
            subscript_offset = float(max(min_subscript_offset, min(max_subscript_offset, max_offset)))
            subscript_y = y_base + subscript_offset

        sub_top = subscript_y - (sub_font_px * 0.60)
        if sub_top < inner_top:
            min_offset = inner_top - y_base + (sub_font_px * 0.60)
            subscript_offset = float(max(min_subscript_offset, min(max_subscript_offset, min_offset)))
            subscript_y = y_base + subscript_offset

        return {
            "anchor_mode": anchor_mode,
            "font_size": font_size,
            "sub_scale": sub_scale,
            "sub_font_px": sub_font_px,
            "co_x": co_x,
            "y_base": y_base,
            "subscript_x": subscript_x,
            "subscript_y": subscript_y,
            "x1": x1,
            "x2": x2,
            "height": height,
        }

    @staticmethod
    def _apply_voc_label(params: dict) -> dict:
        params["draw_text"] = True
        params["text_mode"] = "voc"
        params["text_gray"] = int(round(params.get("stroke_gray", Action.LIGHT_CIRCLE_STROKE_GRAY)))
        params["voc_font_scale"] = float(params.get("voc_font_scale", 0.52))
        params["voc_dy"] = float(params.get("voc_dy", -0.01 * float(params.get("r", 0.0))))
        params["voc_weight"] = int(params.get("voc_weight", 600))
        return params

    @staticmethod
    def _tune_ac0832_co2_badge(params: dict) -> dict:
        """AC0832 has a compact circle; keep CO₂ comfortably inside the ring."""
        p = dict(params)
        r = float(p.get("r", 0.0))
        p["stroke_gray"] = Action.LIGHT_CIRCLE_STROKE_GRAY
        p["arm_stroke"] = Action.AC08_STROKE_WIDTH_PX
        p["stroke_circle"] = Action.AC08_STROKE_WIDTH_PX
        p["co2_font_scale"] = min(float(p.get("co2_font_scale", 0.82)), 0.74)
        p["co2_sub_font_scale"] = min(float(p.get("co2_sub_font_scale", 66.0)), 62.0)
        p["co2_dy"] = float(p.get("co2_dy", 0.0)) - (0.03 * r)
        p["text_gray"] = p["stroke_gray"]
        return p

    @staticmethod
    def _tune_ac0834_co2_badge(params: dict, w: int, h: int) -> dict:
        """Stabilize tiny AC0834 badges where fitting drifts the circle downward."""
        p = dict(params)
        p["stroke_gray"] = Action.LIGHT_CIRCLE_STROKE_GRAY
        p["text_gray"] = p["stroke_gray"]
        p["stroke_circle"] = Action.AC08_STROKE_WIDTH_PX
        p["arm_stroke"] = Action.AC08_STROKE_WIDTH_PX

        if min(w, h) <= 16:
            default_cy = float(h) / 2.0
            default_r = float(h) * 0.4

            p["cy"] = default_cy
            p["r"] = max(default_r * 0.95, float(p.get("r", default_r)))
            cx = float(p.get("cx", float(h) / 2.0))
            p["arm_y1"] = default_cy
            p["arm_y2"] = default_cy
            p["arm_x1"] = min(float(w), cx + float(p["r"]))
            p["arm_x2"] = float(w)

            p["co2_font_scale"] = min(float(p.get("co2_font_scale", 0.82)), 0.86)
            p["co2_sub_font_scale"] = min(float(p.get("co2_sub_font_scale", 66.0)), 64.0)

        return p

    @staticmethod
    def _normalize_centered_co2_label(params: dict) -> dict:
        """Normalize CO₂ label sizing for plain circular badges.

        This keeps CO₂ text proportionate to the inner circle diameter for any
        centered (connector-free) semantic badge instead of tuning a single SKU.
        """
        p = dict(params)
        if str(p.get("text_mode", "")).lower() != "co2":
            return p
        if p.get("arm_enabled") or p.get("stem_enabled"):
            return p
        if not p.get("circle_enabled", True):
            return p

        r = max(1.0, float(p.get("r", 1.0)))
        stroke = max(0.8, float(p.get("stroke_circle", 1.0)))
        inner_diameter = max(2.0, (2.0 * r) - stroke)

        cur_scale = float(p.get("co2_font_scale", 0.82))
        cur_font = max(4.0, r * cur_scale)
        cur_width = cur_font * 1.45
        # Keep centered CO₂ labels clearly readable in small AC0820 badges while
        # still fitting inside the inner ring.
        target_width = inner_diameter * 0.84

        adjusted_scale = cur_scale * (target_width / max(1e-6, cur_width))
        p["co2_font_scale"] = float(max(0.90, min(1.12, adjusted_scale)))
        p["co2_sub_font_scale"] = float(max(60.0, min(68.0, float(p.get("co2_sub_font_scale", 66.0)))))
        p["co2_dx"] = float(max(-0.18 * r, min(0.18 * r, float(p.get("co2_dx", -0.04 * r)))))
        p["co2_dy"] = float(max(-0.20 * r, min(0.20 * r, float(p.get("co2_dy", 0.03 * r)))))
        p["text_gray"] = int(round(p.get("stroke_gray", Action.LIGHT_CIRCLE_STROKE_GRAY)))
        return p

    @staticmethod
    def _default_ac0812_params(w: int, h: int) -> dict:
        """AC0812 is horizontally elongated: left arm, circle on the right."""
        if w <= 0 or h <= 0:
            return Action._default_ac081x_shared(w, h)

        # Like AC0811/AC0813, size from the narrow side so tiny variants keep
        # the intended visual circle diameter.
        r = float(h) * 0.4
        stroke_circle = max(0.9, float(h) / 15.0)
        cx = float(w) - (float(h) / 2.0)
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
                "arm_x1": 0.0,
                "arm_y1": cy,
                "arm_x2": max(0.0, cx - r),
                "arm_y2": cy,
                "arm_stroke": arm_stroke,
                "arm_len_min_ratio": 0.75,
            }
        )

    @staticmethod
    def _fit_ac0812_params_from_image(img: np.ndarray, defaults: dict) -> dict:
        """Fit AC0812 while keeping the horizontal arm anchored to the left edge."""
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

        if h <= 15 and not bool(params.get("draw_text", True)):
            default_r = float(defaults.get("r", float(h) * 0.4))
            # AC0812_S can lose roughly one anti-aliased ring pixel in contour/Hough
            # fitting; keep tiny plain variants close to the semantic template size.
            r = max(r, default_r * 0.98)
            params["r"] = r

        params["arm_enabled"] = True
        params["arm_stroke"] = arm_stroke
        params["arm_x1"] = 0.0
        params["arm_y1"] = cy
        params["arm_x2"] = max(0.0, cx - r)
        params["arm_y2"] = cy
        return Action._normalize_light_circle_colors(params)

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
            params["cy"] = float(np.clip(cy, default_cy - 0.8, default_cy + 0.8))
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

        r = float(h) * 0.4
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
        current_arm_len = float(np.hypot(params["arm_x2"] - params["arm_x1"], params["arm_y2"] - params["arm_y1"]))
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
        if "r" in params and "template_circle_radius" not in params:
            params["template_circle_radius"] = float(params["r"])
        if "cx" in params and "template_circle_cx" not in params:
            params["template_circle_cx"] = float(params["cx"])
        if "cy" in params and "template_circle_cy" not in params:
            params["template_circle_cy"] = float(params["cy"])
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
            minRadius=max(3, int(round(min_side * 0.14))),
            maxRadius=max(6, int(round(min_side * 0.60))),
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
                center_offset = float(np.hypot(cx - template_cx, cy - template_cy))
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
                params["r"] = float(np.clip(float(params.get("r", default_r)), min_r, max_r))

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
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_ac0812_params_from_image(img, defaults))

        if name == "AC0813":
            defaults = Action._default_ac0813_params(w, h)
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_ac0813_params_from_image(img, defaults))

        if name == "AC0814":
            defaults = Action._default_ac0814_params(w, h)
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_ac0814_params_from_image(img, defaults))

        if name == "AC0881":
            defaults = Action._default_ac0881_params(w, h)
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_semantic_badge_from_image(img, defaults))

        if name == "AC0882":
            defaults = Action._default_ac0882_params(w, h)
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._fit_semantic_badge_from_image(img, defaults))

        if name == "AC0820":
            defaults = Action._apply_co2_label(Action._default_ac0870_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._apply_co2_label(Action._fit_semantic_badge_from_image(img, defaults)))

        if name == "AC0831":
            defaults = Action._apply_co2_label(Action._default_ac0881_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._apply_co2_label(Action._fit_ac0811_params_from_image(img, defaults)))

        if name == "AC0832":
            defaults = Action._apply_co2_label(Action._default_ac0812_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, Action._tune_ac0832_co2_badge(defaults))
            return Action._finalize_ac08_style(
                name,
                Action._tune_ac0832_co2_badge(
                    Action._apply_co2_label(Action._fit_ac0812_params_from_image(img, defaults))
                ),
            )

        if name == "AC0833":
            defaults = Action._apply_co2_label(Action._default_ac0813_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._apply_co2_label(Action._fit_ac0813_params_from_image(img, defaults)))

        if name == "AC0834":
            defaults = Action._apply_co2_label(Action._default_ac0814_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, Action._tune_ac0834_co2_badge(defaults, w, h))
            return Action._finalize_ac08_style(
                name,
                Action._tune_ac0834_co2_badge(
                    Action._apply_co2_label(Action._fit_ac0814_params_from_image(img, defaults)),
                    w,
                    h,
                ),
            )

        if name == "AC0835":
            defaults = Action._apply_voc_label(Action._default_ac0870_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._apply_voc_label(Action._fit_semantic_badge_from_image(img, defaults)))

        if name == "AC0836":
            defaults = Action._apply_voc_label(Action._default_ac0881_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._apply_voc_label(Action._fit_ac0811_params_from_image(img, defaults)))

        if name == "AC0837":
            defaults = Action._apply_voc_label(Action._default_ac0812_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._apply_voc_label(Action._fit_ac0812_params_from_image(img, defaults)))

        if name == "AC0838":
            defaults = Action._apply_voc_label(Action._default_ac0813_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._apply_voc_label(Action._fit_ac0813_params_from_image(img, defaults)))

        if name == "AC0839":
            defaults = Action._apply_voc_label(Action._default_ac0814_params(w, h))
            if img is None:
                return Action._finalize_ac08_style(name, defaults)
            return Action._finalize_ac08_style(name, Action._apply_voc_label(Action._fit_ac0814_params_from_image(img, defaults)))

        return None

    @staticmethod
    def generate_badge_svg(w: int, h: int, p: dict) -> str:
        p = Action._align_stem_to_circle_center(dict(p))
        p = Action._quantize_badge_params(p, w, h)
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
            stem_bottom = float(p.get("stem_bottom", 0.0))
            # If the stem should touch the lower border, extend by half a pixel so
            # rasterization keeps the bottom row fully covered after quantization.
            if stem_bottom >= (float(h) - 0.01):
                stem_bottom = float(h) + 0.5
            elements.append(
                (
                    f'  <rect x="{p["stem_x"]:.4f}" y="{p["stem_top"]:.4f}" '
                    f'width="{p["stem_width"]:.4f}" height="{max(0.0, stem_bottom - p["stem_top"]):.4f}" '
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
            elif p.get("text_mode") == "co2":
                layout = Action._co2_layout(p)
                font_size = float(layout["font_size"])
                sub_scale = float(layout["sub_scale"])
                y_text = float(layout["y_base"])
                elements.append(
                    (
                        f'  <text x="{float(layout["co_x"]):.4f}" y="{y_text:.4f}" fill="{Action.grayhex(p["text_gray"])}" '
                        f'font-family="Arial, Helvetica, sans-serif" font-size="{font_size:.4f}" '
                        f'font-style="normal" font-weight="600" text-anchor="middle" dominant-baseline="middle">CO</text>'
                    )
                )
                elements.append(
                    (
                        f'  <text x="{float(layout["subscript_x"]):.4f}" y="{float(layout["subscript_y"]):.4f}" fill="{Action.grayhex(p["text_gray"])}" '
                        f'font-family="Arial, Helvetica, sans-serif" font-size="{float(layout["sub_font_px"]):.4f}" '
                        f'font-style="normal" font-weight="600" text-anchor="start" dominant-baseline="middle">2</text>'
                    )
                )
            elif p.get("text_mode") == "voc":
                radius = p.get("r", min(w, h) * 0.4)
                font_size = max(4.0, radius * p.get("voc_font_scale", 0.52))
                voc_dy = p.get("voc_dy", 0.0)
                voc_weight = int(p.get("voc_weight", 600))
                elements.append(
                    (
                        f'  <text x="{p["cx"]:.4f}" y="{(p["cy"] + voc_dy):.4f}" fill="{Action.grayhex(p["text_gray"])}" '
                        f'font-family="Arial, Helvetica, sans-serif" font-size="{font_size:.4f}" '
                        f'font-style="normal" font-weight="{voc_weight}" letter-spacing="0.01em" '
                        f'text-anchor="middle" dominant-baseline="middle">VOC</text>'
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
        diag = float(np.hypot(float(rw), float(rh)))
        if not np.isfinite(diag) or diag <= 0.0:
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

        center_dist = float(np.hypot(scx - ocx, scy - ocy))
        orig_diag = float(np.hypot(ow, oh))
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
    ) -> bool:
        changed = False
        scale = float(np.clip(diag_scale, 0.85, 1.18))

        if element == "circle":
            old_cx = float(params["cx"])
            old_cy = float(params["cy"])
            old_r = float(params["r"])
            min_r = float(max(1.0, params.get("min_circle_radius", 1.0)))
            if bool(params.get("lock_circle_cx", False)):
                params["cx"] = old_cx
            else:
                params["cx"] = float(np.clip(old_cx + center_dx * 0.65, 0.0, float(w - 1)))
            if bool(params.get("lock_circle_cy", False)):
                params["cy"] = old_cy
            else:
                params["cy"] = float(np.clip(old_cy + center_dy * 0.65, 0.0, float(h - 1)))
            params["r"] = float(np.clip(old_r * scale, min_r, float(min(w, h)) * 0.48))
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
                stem_cx = float(np.clip(stem_cx + center_dx * 0.75, 0.0, float(w - 1)))
            new_w = float(np.clip(old_w * scale, 1.0, float(w) * 0.22))
            params["stem_width"] = new_w
            params["stem_x"] = float(np.clip(stem_cx - (new_w / 2.0), 0.0, float(w) - new_w))
            params["stem_top"] = float(np.clip(old_top + center_dy * 0.45, 0.0, float(h - 2)))
            params["stem_bottom"] = float(np.clip(old_bottom + center_dy * 0.25, params["stem_top"] + 1.0, float(h - 1)))
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

            params["arm_x1"] = float(np.clip(acx - (vx / 2.0), 0.0, float(w - 1)))
            params["arm_x2"] = float(np.clip(acx + (vx / 2.0), 0.0, float(w - 1)))
            params["arm_y1"] = float(np.clip(acy - (vy / 2.0), 0.0, float(h - 1)))
            params["arm_y2"] = float(np.clip(acy + (vy / 2.0), 0.0, float(h - 1)))
            params["arm_stroke"] = float(np.clip(old_stroke * scale, 1.0, float(min(w, h)) * 0.18))
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
                params["co2_dy"] = float(np.clip(old_dy + center_dy * 0.75, -0.45 * r, 0.45 * r))
                changed = abs(params["co2_dy"] - old_dy) > 0.02
            elif mode == "voc":
                old_dy = float(params.get("voc_dy", 0.0))
                params["voc_dy"] = float(np.clip(old_dy + center_dy * 0.75, -0.45 * r, 0.45 * r))
                changed = abs(params["voc_dy"] - old_dy) > 0.02
            elif "ty" in params:
                old_ty = float(params.get("ty", 0.0))
                params["ty"] = float(np.clip(old_ty + center_dy * 0.75, 0.0, float(h - 1)))
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
                dist = min(abs(cx_idx - rx1), abs(cx_idx - rx2))
                if dist < nearest_dist:
                    nearest_dist = dist
                    chosen = run

            if chosen is None:
                continue

            rw = float((chosen[-1] - chosen[0]) + 1)
            rcx = float((chosen[0] + chosen[-1]) / 2.0)
            widths.append(rw)
            centers.append(rcx)

        if not widths:
            return None

        widths_arr = np.array(widths, dtype=np.float32)
        centers_arr = np.array(centers, dtype=np.float32)
        keep = np.ones(widths_arr.shape[0], dtype=bool)

        for _ in range(3):
            sel_w = widths_arr[keep]
            if sel_w.size < 3:
                break
            med = float(np.median(sel_w))
            tol = max(1.0, med * 0.35)
            new_keep = keep & (np.abs(widths_arr - med) <= tol)
            if int(np.sum(new_keep)) == int(np.sum(keep)):
                break
            keep = new_keep

        if int(np.sum(keep)) == 0:
            return None

        est_width = float(np.median(widths_arr[keep]))
        est_cx = float(np.median(centers_arr[keep]))
        est_width = max(1.0, min(est_width, float(w)))
        return est_cx, est_width

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
        context_pad = max(2.0, float(min(h, w)) * 0.12)
        if element == "circle":
            radius_with_context = params["r"] + context_pad
            circle = (xx - params["cx"]) ** 2 + (yy - params["cy"]) ** 2 <= radius_with_context**2
            top = yy <= (params["cy"] + params["r"] + context_pad)
            return circle & top
        if element == "stem" and params.get("stem_enabled"):
            x1 = max(0.0, params["stem_x"] - context_pad)
            x2 = min(float(w), params["stem_x"] + params["stem_width"] + context_pad)
            y1 = max(0.0, params["stem_top"] - context_pad)
            y2 = min(float(h), params["stem_bottom"] + context_pad)
            return (xx >= x1) & (xx <= x2) & (yy >= y1) & (yy <= y2)
        if element == "arm" and params.get("arm_enabled"):
            x1 = max(0.0, min(params.get("arm_x1", 0.0), params.get("arm_x2", 0.0)) - context_pad)
            x2 = min(float(w), max(params.get("arm_x1", 0.0), params.get("arm_x2", 0.0)) + context_pad)
            y1 = max(0.0, min(params.get("arm_y1", 0.0), params.get("arm_y2", 0.0)) - context_pad)
            y2 = min(float(h), max(params.get("arm_y1", 0.0), params.get("arm_y2", 0.0)) + context_pad)
            pad = max(1.0, params.get("arm_stroke", params.get("stem_or_arm", 1.0)) * 0.8)
            return (xx >= (x1 - pad)) & (xx <= (x2 + pad)) & (yy >= (y1 - pad)) & (yy <= (y2 + pad))
        if element == "text" and params.get("draw_text", True):
            x1, y1, x2, y2 = Action._text_bbox(params)
            x1 = max(0.0, x1 - context_pad)
            y1 = max(0.0, y1 - context_pad)
            x2 = min(float(w), x2 + context_pad)
            y2 = min(float(h), y2 + context_pad)
            return (xx >= x1) & (xx <= x2) & (yy >= y1) & (yy <= y2)
        return None

    @staticmethod
    def _text_bbox(params: dict) -> tuple[float, float, float, float]:
        """Approximate text bounding box for semantic badge text modes."""
        cx = float(params.get("cx", 0.0))
        cy = float(params.get("cy", 0.0))
        r = max(1.0, float(params.get("r", 1.0)))
        mode = str(params.get("text_mode", "")).lower()

        if mode == "voc":
            font_size = max(4.0, r * float(params.get("voc_font_scale", 0.52)))
            width = font_size * 1.95
            height = font_size * 0.90
            y = cy + float(params.get("voc_dy", 0.0))
            return (cx - (width / 2.0), y - (height / 2.0), cx + (width / 2.0), y + (height / 2.0))

        if mode == "co2":
            layout = Action._co2_layout(params)
            x1 = float(layout["x1"])
            x2 = float(layout["x2"])
            y = float(layout["y_base"])
            height = float(layout["height"])
            return (x1, y - (height / 2.0), x2, y + (height / 2.0))

        # path/path_t fallback via known glyph bounds.
        s = float(params.get("s", 0.0))
        tx = float(params.get("tx", cx))
        ty = float(params.get("ty", cy))
        xmin, ymin, xmax, ymax = Action._glyph_bbox(params.get("text_mode", "path"))
        x1 = tx + (xmin * s)
        y1 = ty + (ymin * s)
        x2 = tx + (xmax * s)
        y2 = ty + (ymax * s)
        return (x1, y1, x2, y2)

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
        only["draw_text"] = bool(params.get("draw_text", True) and element == "text")
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
        if float(np.sum(valid)) <= 0.0:
            return float("inf")
        weighted = gray_diff * valid
        return float(np.sum(weighted))

    @staticmethod
    def _union_bbox_from_masks(mask_a: np.ndarray | None, mask_b: np.ndarray | None) -> tuple[int, int, int, int] | None:
        boxes: list[tuple[float, float, float, float]] = []
        if mask_a is not None:
            box_a = Action._mask_bbox(mask_a)
            if box_a is not None:
                boxes.append(box_a)
        if mask_b is not None:
            box_b = Action._mask_bbox(mask_b)
            if box_b is not None:
                boxes.append(box_b)
        if not boxes:
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
        if not np.isfinite(photo_err):
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
        cur = float(snap(float(np.clip(current_value, low, high))))
        best_value = cur
        best_err = float(evaluate(best_value))
        if not np.isfinite(best_err):
            return best_value, best_err, False

        rng = np.random.default_rng(int(seed) + int(Action.STOCHASTIC_SEED_OFFSET))
        span = max(0.5, abs(high - low) * 0.22)
        improved = False
        stable_rounds = 0

        for _ in range(max(1, iterations)):
            candidates = [best_value]
            for _j in range(2):
                sample = float(np.clip(rng.normal(best_value, span), low, high))
                candidates.append(float(snap(sample)))

            scored: list[tuple[float, float]] = []
            for cand in candidates:
                err = float(evaluate(cand))
                if np.isfinite(err):
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
        rng = np.random.default_rng(835 + int(Action.STOCHASTIC_SEED_OFFSET))

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
        if not np.isfinite(best_err):
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
                    cx = Action._snap_half(float(np.clip(rng.normal(best[0], spread_xy), x_low, x_high)))
                if lock_cy:
                    cy = best[1]
                else:
                    cy = Action._snap_half(float(np.clip(rng.normal(best[1], spread_xy), y_low, y_high)))
                rad = Action._snap_half(float(np.clip(rng.normal(best[2], spread_r), r_low, r_high)))
                cand = (cx, cy, rad)
                candidates.append((cand, eval_pose(cand)))

            finite = [pair for pair in candidates if np.isfinite(pair[1])]
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
    def _element_width_key_and_bounds(
        element: str, params: dict, w: int, h: int, img_orig: np.ndarray | None = None
    ) -> tuple[str, float, float] | None:
        lock_strokes = bool(params.get("lock_stroke_widths"))
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
                # Large VOC badges can otherwise over-scale the label to the
                # hard cap and look visibly too heavy (e.g. AC0837_L). Keep the
                # tiny-size exploration broad, but tighten larger variants.
                if min_dim > 22.0:
                    high = 1.10
                elif min_dim > 16.0:
                    high = 1.30
                else:
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
        probe[key] = float(np.clip(width_value, low, high))
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
        probe["r"] = float(np.clip(radius_value, 1.0, max_r))

        if probe.get("arm_enabled"):
            Action._reanchor_arm_to_circle_edge(probe, float(probe["r"]))

        if probe.get("stem_enabled"):
            probe["stem_top"] = float(probe.get("cy", 0.0)) + float(probe["r"])

        elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(probe, "circle"))
        elem_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(elem_svg, w, h))
        if elem_render is None:
            return float("inf")

        # Keep the source mask anchored to the current parameter state.
        # If we derive `mask_orig` from the candidate radius itself, a smaller
        # probe can hide mismatching source pixels and bias the optimizer toward
        # collapsing circles (observed on AC0833_L).
        mask_orig = Action.extract_badge_element_mask(img_orig, params, "circle")
        if mask_orig is None:
            return float("inf")
        mask_svg = Action.extract_badge_element_mask(elem_render, probe, "circle")
        if mask_svg is None:
            return float("inf")

        return Action._masked_union_error_in_bbox(img_orig, elem_render, mask_orig, mask_svg)


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
        probe["cx"] = Action._snap_half(float(np.clip(cx_value, 0.0, float(w - 1))))
        probe["cy"] = Action._snap_half(float(np.clip(cy_value, 0.0, float(h - 1))))
        min_r = float(max(1.0, probe.get("min_circle_radius", 1.0)))
        probe["r"] = Action._snap_half(float(np.clip(radius_value, min_r, max_r)))

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

        return Action._masked_union_error_in_bbox(img_orig, elem_render, mask_orig, mask_svg)

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
            cx_snap = Action._snap_half(float(np.clip(cx_value, 0.0, float(w - 1))))
            cy_snap = Action._snap_half(float(np.clip(cy_value, 0.0, float(h - 1))))
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

                if not all(np.isfinite(v) for v in (low_err, mid_err, high_err)):
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
        if not np.isfinite(best_err):
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
        mid = Action._snap_half(float(np.clip(current, low, high)))
        if high - low < 0.05:
            return False

        evaluations: dict[float, float] = {}

        def eval_radius(radius: float) -> float:
            snapped = Action._snap_half(float(np.clip(radius, low_bound, high_bound)))
            if snapped not in evaluations:
                evaluations[snapped] = float(Action._element_error_for_circle_radius(img_orig, params, snapped))
            return evaluations[snapped]

        max_rounds = 12
        for _ in range(max_rounds):
            low_err = eval_radius(low)
            mid_err = eval_radius(mid)
            high_err = eval_radius(high)
            if not all(np.isfinite(v) for v in (low_err, mid_err, high_err)):
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
                Action._snap_half(float(np.clip(current_cx + offset, 0.0, float(w - 1))))
                for offset in (-shift, 0.0, shift)
            ]
        if lock_cy:
            cy_candidates = [Action._snap_half(current_cy)]
        else:
            cy_candidates = [
                Action._snap_half(float(np.clip(current_cy + offset, 0.0, float(h - 1))))
                for offset in (-shift, 0.0, shift)
            ]

        r_candidates = [
            Action._snap_half(float(np.clip(current_r + offset, min_r, max_r)))
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
                    if np.isfinite(err) and err + 0.05 < best_err:
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
            logs.append("circle: Joint-Multistart liegt am Rand; starte stochastic survivor search")
            Action._optimize_circle_pose_stochastic_survivor(img_orig, params, logs)
        return True

    @staticmethod
    def _element_error_for_extent(img_orig: np.ndarray, params: dict, element: str, extent_value: float) -> float:
        h, w = img_orig.shape[:2]
        probe = dict(params)

        if element == "stem" and probe.get("stem_enabled"):
            min_len = 1.0
            max_len = float(h)
            new_len = float(np.clip(extent_value, min_len, max_len))
            center = (float(probe.get("stem_top", 0.0)) + float(probe.get("stem_bottom", 0.0))) / 2.0
            half = new_len / 2.0
            probe["stem_top"] = float(np.clip(center - half, 0.0, float(h - 1)))
            probe["stem_bottom"] = float(np.clip(center + half, probe["stem_top"] + 1.0, float(h)))

        elif element == "arm" and probe.get("arm_enabled"):
            x1 = float(probe.get("arm_x1", 0.0))
            y1 = float(probe.get("arm_y1", 0.0))
            x2 = float(probe.get("arm_x2", 0.0))
            y2 = float(probe.get("arm_y2", 0.0))
            dx = x2 - x1
            dy = y2 - y1
            cur_len = float(np.hypot(dx, dy))
            if cur_len <= 1e-6:
                return float("inf")
            new_len = float(np.clip(extent_value, 1.0, float(max(w, h))))
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
                d1 = float(np.hypot(ax1 - cx, ay1 - cy))
                d2 = float(np.hypot(ax2 - cx, ay2 - cy))

                if d1 <= d2:
                    ix, iy = ax1, ay1
                    probe["arm_x2"] = float(np.clip(ix + (ux * new_len), 0.0, float(w - 1)))
                    probe["arm_y2"] = float(np.clip(iy + (uy * new_len), 0.0, float(h - 1)))
                else:
                    ix, iy = ax2, ay2
                    probe["arm_x1"] = float(np.clip(ix - (ux * new_len), 0.0, float(w - 1)))
                    probe["arm_y1"] = float(np.clip(iy - (uy * new_len), 0.0, float(h - 1)))
            else:
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                half = new_len / 2.0
                probe["arm_x1"] = float(np.clip(cx - (ux * half), 0.0, float(w - 1)))
                probe["arm_y1"] = float(np.clip(cy - (uy * half), 0.0, float(h - 1)))
                probe["arm_x2"] = float(np.clip(cx + (ux * half), 0.0, float(w - 1)))
                probe["arm_y2"] = float(np.clip(cy + (uy * half), 0.0, float(h - 1)))
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
            forced_abs_min = params.get("stem_len_min")
            if forced_abs_min is not None:
                low_bound = max(low_bound, float(forced_abs_min))
            forced_min_ratio = params.get("stem_len_min_ratio")
            if forced_min_ratio is not None:
                min_ratio = float(max(0.0, min(1.0, float(forced_min_ratio))))
                low_bound = max(low_bound, current * min_ratio)
            # Keep bottom-anchored stem variants (e.g. AC0811_S) from collapsing
            # into near-invisible stubs when anti-aliased extraction under-segments
            # thin line pixels in element-only masks.
            is_bottom_anchored = float(params.get("stem_bottom", 0.0)) >= float(h) - 0.5
            if (
                forced_min_ratio is None
                and is_bottom_anchored
                and params.get("circle_enabled", True)
                and all(k in params for k in ("cy", "r"))
            ):
                min_ratio = float(params.get("stem_len_min_ratio", 0.65))
                low_bound = max(low_bound, current * max(0.0, min(1.0, min_ratio)))
        elif element == "arm" and params.get("arm_enabled"):
            dx = float(params.get("arm_x2", 0.0)) - float(params.get("arm_x1", 0.0))
            dy = float(params.get("arm_y2", 0.0)) - float(params.get("arm_y1", 0.0))
            current = float(np.hypot(dx, dy))
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
        if not all(np.isfinite(e) for e in candidate_errors):
            logs.append(
                f"{element}: Längen-Bracketing abgebrochen ({key_label}) wegen nicht-finiten Fehlern "
                + ", ".join(f"{v:.3f}->{e:.3f}" for v, e in zip(candidates, candidate_errors, strict=False))
            )
            return False

        best_idx = int(np.argmin(candidate_errors))
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
                top = float(np.clip(float(params.get("cy", 0.0)) + float(params.get("r", 0.0)), 0.0, float(h - 1)))
                params["stem_top"] = top
                params["stem_bottom"] = float(np.clip(top + best_len, top + 1.0, float(h)))
            else:
                center = (float(params.get("stem_top", 0.0)) + float(params.get("stem_bottom", 0.0))) / 2.0
                half = best_len / 2.0
                params["stem_top"] = float(np.clip(center - half, 0.0, float(h - 1)))
                params["stem_bottom"] = float(np.clip(center + half, params["stem_top"] + 1.0, float(h)))
        else:
            x1 = float(params.get("arm_x1", 0.0))
            y1 = float(params.get("arm_y1", 0.0))
            x2 = float(params.get("arm_x2", 0.0))
            y2 = float(params.get("arm_y2", 0.0))
            dx = x2 - x1
            dy = y2 - y1
            cur_len = float(np.hypot(dx, dy))
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
                d1 = float(np.hypot(ax1 - cx, ay1 - cy))
                d2 = float(np.hypot(ax2 - cx, ay2 - cy))

                if d1 <= d2:
                    ix, iy = ax1, ay1
                    params["arm_x2"] = float(np.clip(ix + (ux * best_len), 0.0, float(w - 1)))
                    params["arm_y2"] = float(np.clip(iy + (uy * best_len), 0.0, float(h - 1)))
                else:
                    ix, iy = ax2, ay2
                    params["arm_x1"] = float(np.clip(ix - (ux * best_len), 0.0, float(w - 1)))
                    params["arm_y1"] = float(np.clip(iy - (uy * best_len), 0.0, float(h - 1)))
            else:
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                half = best_len / 2.0
                params["arm_x1"] = float(np.clip(cx - (ux * half), 0.0, float(w - 1)))
                params["arm_y1"] = float(np.clip(cy - (uy * half), 0.0, float(h - 1)))
                params["arm_x2"] = float(np.clip(cx + (ux * half), 0.0, float(w - 1)))
                params["arm_y2"] = float(np.clip(cy + (uy * half), 0.0, float(h - 1)))

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
        if not all(np.isfinite(e) for e in candidate_errors):
            logs.append(
                f"{element}: Breiten-Bracketing abgebrochen ({key}) wegen nicht-finiten Fehlern "
                + ", ".join(f"{v:.3f}->{e:.3f}" for v, e in zip(candidates, candidate_errors, strict=False))
            )
            return False

        best_idx = int(np.argmin(candidate_errors))
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

        if key in {"stroke_circle", "arm_stroke", "stem_width"}:
            best_width = Action._snap_int_px(best_width, minimum=1.0)
        elif key.endswith("_font_scale"):
            best_width = float(round(best_width, 3))
        else:
            best_width = Action._snap_half(best_width)

        params[key] = best_width
        if key == "stem_width" and params.get("stem_enabled"):
            params["stem_x"] = Action._snap_half(float(params.get("cx", params.get("stem_x", 0.0))) - (params["stem_width"] / 2.0))
        logs.append(
            f"{element}: Breiten-Bracketing {key} {old:.3f}->{best_width:.3f}; "
            f"Kandidaten="
            + ", ".join(f"{v:.3f}->{e:.3f}" for v, e in zip(candidates, candidate_errors, strict=False))
        )
        return True


    @staticmethod
    def _element_color_keys(element: str, params: dict) -> list[str]:
        if element == "circle" and params.get("circle_enabled", True):
            return ["fill_gray", "stroke_gray"]
        if element == "stem" and params.get("stem_enabled"):
            return ["stem_gray"]
        if element == "arm" and params.get("arm_enabled"):
            return ["stroke_gray"]
        if element == "text" and params.get("draw_text", True):
            return ["text_gray"]
        return []

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
        probe[color_key] = int(np.clip(color_value, 0, 255))

        h, w = img_orig.shape[:2]
        elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(probe, element))
        elem_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(elem_svg, w, h))
        if elem_render is None:
            return float("inf")
        return Action._element_match_error(img_orig, elem_render, probe, element, mask_orig=mask_orig)

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
                int(np.clip(current - 32, 0, 255)),
                int(np.clip(current - 16, 0, 255)),
                int(np.clip(current - 8, 0, 255)),
                int(np.clip(current, 0, 255)),
                int(np.clip(current + 8, 0, 255)),
                int(np.clip(current + 16, 0, 255)),
                int(np.clip(current + 32, 0, 255)),
            }
            if sampled is not None:
                candidates.add(int(np.clip(sampled, 0, 255)))
            if element == "circle" and color_key == "fill_gray":
                candidates.update({200, 210, 220, 230, 240})
            if color_key in {"stroke_gray", "stem_gray", "text_gray"}:
                candidates.update({96, 112, 128, 144, 152, 160, 171})

            values = sorted(candidates)
            errs = [
                Action._element_error_for_color(img_orig, params, element, color_key, v, mask_orig)
                for v in values
            ]
            if not all(np.isfinite(e) for e in errs):
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
                        int(np.clip(int(round(v)), 0, 255)),
                        mask_orig,
                    ),
                    snap=lambda v: int(np.clip(int(round(v)), 0, 255)),
                    seed=1301,
                )
                if s_improved:
                    best_value = int(np.clip(int(round(s_best)), 0, 255))
                    logs.append(
                        f"{element}: Farb-Stochastic-Survivor aktiviert ({color_key}={best_value}, err={s_err:.3f})"
                    )

            if best_value == current:
                logs.append(
                    f"{element}: Farb-Bracketing keine relevante Änderung ({color_key}: {current}); Kandidaten="
                    + ", ".join(f"{v}->{e:.3f}" for v, e in zip(values, errs, strict=False))
                )
                continue

            params[color_key] = int(best_value)
            changed_any = True
            logs.append(
                f"{element}: Farb-Bracketing {color_key} {current}->{best_value}; Kandidaten="
                + ", ".join(f"{v}->{e:.3f}" for v, e in zip(values, errs, strict=False))
            )

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
                target_cx = float(np.clip(est_cx, circle_cx - max_offset, circle_cx + max_offset))
            else:
                target_cx = est_cx
            estimate_mode = "iter"
        else:
            if 0.95 <= ratio <= 1.05:
                return False, None
            target_width = float(params.get("stem_width", svg_w)) * (orig_w / svg_w)
            stem_width_cap = float(params.get("stem_width_max", float(w) * 0.20))
            target_width = max(1.0, min(target_width, min(float(w) * 0.20, stem_width_cap)))
            target_cx = (ox1 + ox2) / 2.0
            estimate_mode = "bbox"

        old_width = float(params.get("stem_width", svg_w))
        width_delta = abs(target_width - old_width)
        ratio_after = target_width / max(1.0, orig_w)

        if width_delta < 0.05 and 0.90 <= ratio_after <= 1.12:
            return False, None

        stem_width_cap = float(params.get("stem_width_max", float(w) * 0.20))
        target_width = min(target_width, stem_width_cap)
        target_width = Action._snap_int_px(target_width, minimum=1.0)
        old_x = float(params.get("stem_x", 0.0))
        old_w = float(params.get("stem_width", 1.0))
        new_x = Action._snap_half(max(0.0, min(float(w) - target_width, target_cx - (target_width / 2.0))))
        if abs(target_width - old_w) < 0.05 and abs(new_x - old_x) < 0.05:
            return False, None
        params["stem_width"] = target_width
        params["stem_x"] = new_x
        return True, (
            f"stem: Breitenkorrektur mode={estimate_mode}, ratio={ratio:.3f}, "
            f"alt={old_width:.3f}, neu={target_width:.3f}"
        )

    @staticmethod
    def _expected_semantic_presence(semantic_elements: list[str]) -> dict[str, bool]:
        normalized = [str(elem).lower() for elem in semantic_elements]
        has_text = any("kreis + buchstabe" in elem for elem in normalized)
        return {
            "circle": True,
            "stem": any("senkrechter strich" in elem for elem in normalized),
            "arm": any("waagrechter strich" in elem for elem in normalized),
            "text": has_text,
        }

    @staticmethod
    def _semantic_presence_mismatches(expected: dict[str, bool], observed: dict[str, bool]) -> list[str]:
        labels = {
            "circle": "Kreis",
            "stem": "senkrechter Strich",
            "arm": "waagrechter Strich",
            "text": "Buchstabe/Text",
        }
        issues: list[str] = []
        for key in ("circle", "stem", "arm", "text"):
            exp = bool(expected.get(key, False))
            obs = bool(observed.get(key, False))
            if exp and not obs:
                issues.append(f"Beschreibung erwartet {labels[key]}, im Bild aber nicht robust erkennbar")
            if obs and not exp:
                issues.append(f"Im Bild ist {labels[key]} erkennbar, aber nicht in der Beschreibung enthalten")
        return issues

    @staticmethod
    def validate_semantic_description_alignment(
        img_orig: np.ndarray,
        semantic_elements: list[str],
        badge_params: dict,
    ) -> list[str]:
        expected = Action._expected_semantic_presence(semantic_elements)
        observed = {
            "circle": Action.extract_badge_element_mask(img_orig, badge_params, "circle") is not None,
            "stem": Action.extract_badge_element_mask(img_orig, badge_params, "stem") is not None,
            "arm": Action.extract_badge_element_mask(img_orig, badge_params, "arm") is not None,
            "text": Action.extract_badge_element_mask(img_orig, badge_params, "text") is not None,
        }
        return Action._semantic_presence_mismatches(expected, observed)

    @staticmethod
    def validate_badge_by_elements(
        img_orig: np.ndarray,
        params: dict,
        *,
        max_rounds: int = 6,
        debug_out_dir: str | None = None,
    ) -> list[str]:
        h, w = img_orig.shape[:2]
        logs: list[str] = []
        elements = ["circle"]
        if params.get("stem_enabled"):
            elements.append("stem")
        if params.get("arm_enabled"):
            elements.append("arm")
        if params.get("draw_text", True):
            elements.append("text")

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

            round_changed = False
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

                # Geometrie-Abgleich über Mittelpunkt + Diagonale des kleinsten
                # umschließenden Rechtecks (minAreaRect) auf Element-Ebene.
                rect_orig = Action._mask_min_rect_center_diag(mask_orig)
                rect_svg = Action._mask_min_rect_center_diag(mask_svg)
                if rect_orig is not None and rect_svg is not None:
                    old_params = dict(params)
                    old_elem_err = float(Action._element_match_error(img_orig, elem_render, params, element, mask_orig=mask_orig, mask_svg=mask_svg))
                    ocx, ocy, odiag = rect_orig
                    scx, scy, sdiag = rect_svg
                    dx = ocx - scx
                    dy = ocy - scy
                    scale = odiag / max(1e-6, sdiag)
                    changed = Action._apply_element_alignment_step(params, element, dx, dy, scale, w, h)
                    logs.append(
                        (
                            f"{element}: minRect Δcx={dx:.3f}, Δcy={dy:.3f}, "
                            f"diag={sdiag:.3f}->{odiag:.3f}, scale={scale:.4f}"
                        )
                    )
                    if changed:
                        updated_elem_svg = Action.generate_badge_svg(w, h, Action._element_only_params(params, element))
                        updated_elem_render = Action._fit_to_original_size(
                            img_orig,
                            Action.render_svg_to_numpy(updated_elem_svg, w, h),
                        )
                        updated_err = float("inf")
                        bbox_ok = True
                        bbox_log: str | None = None
                        if updated_elem_render is not None:
                            updated_err = float(Action._element_match_error(img_orig, updated_elem_render, params, element, mask_orig=mask_orig))
                            updated_mask_svg = Action.extract_badge_element_mask(updated_elem_render, params, element)
                            if updated_mask_svg is not None:
                                bbox_ok, bbox_log = Action._element_bbox_change_is_plausible(mask_orig, updated_mask_svg)

                        if np.isfinite(updated_err) and updated_err <= old_elem_err + 0.20 and bbox_ok:
                            round_changed = True
                            logs.append(f"{element}: Parameter nach Mittelpunkt/Diagonale angepasst")
                        else:
                            params.clear()
                            params.update(old_params)
                            reason = f"Fehler {old_elem_err:.3f}->{updated_err:.3f}"
                            if bbox_log:
                                reason = f"{reason}; {bbox_log}"
                            logs.append(
                                (
                                    f"{element}: Mittelpunkt/Diagonale-Update verworfen "
                                    f"({reason})"
                                )
                            )

                elem_err = Action._element_match_error(img_orig, elem_render, params, element, mask_orig=mask_orig, mask_svg=mask_svg)
                logs.append(f"{element}: Fehler={elem_err:.3f}")

                if element == "stem" and params.get("stem_enabled"):
                    changed, refine_log = Action._refine_stem_geometry_from_masks(params, mask_orig, mask_svg, w)
                    if refine_log:
                        logs.append(refine_log)
                    if changed:
                        round_changed = True
                        logs.append("stem: Geometrie nach Elementabgleich aktualisiert")

                width_changed = Action._optimize_element_width_bracket(img_orig, params, element, logs)
                if width_changed:
                    round_changed = True

                extent_changed = Action._optimize_element_extent_bracket(img_orig, params, element, logs)
                if extent_changed:
                    round_changed = True

                if element == "circle":
                    center_changed = Action._optimize_circle_center_bracket(img_orig, params, logs)
                    if center_changed:
                        round_changed = True
                    radius_changed = Action._optimize_circle_radius_bracket(img_orig, params, logs)
                    if radius_changed:
                        round_changed = True
                    joint_changed = Action._optimize_circle_pose_multistart(img_orig, params, logs)
                    if joint_changed:
                        round_changed = True

                # Color fitting is intentionally deferred to the end so
                # geometry convergence is not biased by temporary palette noise.

            full_svg = Action.generate_badge_svg(w, h, params)
            full_render = Action._fit_to_original_size(img_orig, Action.render_svg_to_numpy(full_svg, w, h))
            full_err = Action.calculate_error(img_orig, full_render)
            logs.append(f"Runde {round_idx + 1}: Gesamtfehler={full_err:.3f}")

            if full_err <= 8.0:
                logs.append("Gesamtfehler unter Schwellwert, Validierung beendet")
                break

            if round_idx + 1 >= max_rounds:
                break

            if not round_changed:
                logs.append("Keine Element-Geometrieänderung mehr; Validierung vorzeitig beendet")
                break

        for element in elements:
            if element == "text" and not params.get("draw_text", True):
                continue
            mask_orig = Action.extract_badge_element_mask(img_orig, params, element)
            if mask_orig is None:
                continue
            color_changed = Action._optimize_element_color_bracket(img_orig, params, element, mask_orig, logs)
            if color_changed:
                logs.append(f"{element}: Farboptimierung in Abschlussphase angewendet")

        params.update(Action._apply_canonical_badge_colors(params))

        return logs


def run_iteration_pipeline(
    img_path: str,
    csv_path: str,
    max_iterations: int,
    svg_out_dir: str,
    diff_out_dir: str,
    reports_out_dir: str | None = None,
    debug_ac0811_dir: str | None = None,
    debug_element_diff_dir: str | None = None,
    badge_validation_rounds: int = 6,
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

        semantic_issues = Action.validate_semantic_description_alignment(
            perc.img,
            list(params.get("elements", [])),
            badge_params,
        )
        if semantic_issues:
            print("[ERROR] Semantik-Abgleich fehlgeschlagen:")
            for issue in semantic_issues:
                print(f"  - {issue}")
            return None

        validation_logs: list[str] = []
        debug_dir = None
        if debug_element_diff_dir:
            debug_dir = os.path.join(debug_element_diff_dir, os.path.splitext(filename)[0])
            os.makedirs(debug_dir, exist_ok=True)
        elif debug_ac0811_dir and perc.base_name.upper() == "AC0811":
            debug_dir = os.path.join(debug_ac0811_dir, os.path.splitext(filename)[0])
            os.makedirs(debug_dir, exist_ok=True)
        validation_logs = Action.validate_badge_by_elements(
            perc.img,
            badge_params,
            max_rounds=max(1, int(badge_validation_rounds)),
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




def _conversion_random() -> random.Random:
    """Return run-local RNG (seedable via env) for non-deterministic search order."""
    seed_raw = os.environ.get("TINY_ICC_RANDOM_SEED")
    if seed_raw is not None and str(seed_raw).strip() != "":
        try:
            return random.Random(int(str(seed_raw).strip()))
        except ValueError:
            pass
    return random.Random(time.time_ns())

def _default_converted_symbols_root() -> str:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "artifacts", "converted_symbols")


def _quality_config_path(reports_out_dir: str) -> str:
    return os.path.join(reports_out_dir, "quality_tercile_config.json")


def _load_quality_config(reports_out_dir: str) -> dict[str, object]:
    path = _quality_config_path(reports_out_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_quality_config(
    reports_out_dir: str,
    *,
    allowed_error_per_pixel: float,
    skipped_variants: list[str],
    source: str,
) -> None:
    path = _quality_config_path(reports_out_dir)
    normalized_error_pp = float(allowed_error_per_pixel) if math.isfinite(allowed_error_per_pixel) else 0.0
    payload = {
        "allowed_error_per_pixel": float(max(0.0, normalized_error_pp)),
        "skip_variants": sorted(set(skipped_variants)),
        "notes": (
            "Varianten in skip_variants werden in Folge-Pässen nicht erneut konvertiert. "
            "Loeschen der Datei setzt den Ablauf zurueck, dann werden wieder alle Bitmaps bearbeitet."
        ),
        "source": source,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _quality_sort_key(row: dict[str, object]) -> float:
    value = float(row.get("error_per_pixel", float("inf")))
    if math.isfinite(value):
        return value
    return float("inf")


def _select_middle_lower_tercile(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if len(rows) < 3:
        return []

    ranked = sorted(rows, key=_quality_sort_key)
    first_cut = max(1, len(ranked) // 3)
    return ranked[first_cut:]


def _select_open_quality_cases(
    rows: list[dict[str, object]],
    *,
    allowed_error_per_pixel: float,
    skip_variants: set[str] | None = None,
) -> list[dict[str, object]]:
    """Return unresolved quality cases sorted from worst to best.

    "Open" means the case is finite, not explicitly skipped, and still above the
    accepted quality threshold.
    """
    skips = {str(v).upper() for v in (skip_variants or set()) if str(v).strip()}
    open_rows: list[dict[str, object]] = []
    for row in rows:
        err = float(row.get("error_per_pixel", float("inf")))
        if not math.isfinite(err):
            continue
        variant = str(row.get("variant", "")).upper()
        if variant and variant in skips:
            continue
        if math.isfinite(allowed_error_per_pixel) and err <= allowed_error_per_pixel:
            continue
        open_rows.append(row)

    return sorted(open_rows, key=_quality_sort_key, reverse=True)


def _iteration_strategy_for_pass(pass_idx: int, base_iterations: int) -> tuple[int, int]:
    """Adaptive per-pass search budget for unresolved quality cases."""
    p = max(1, int(pass_idx))
    base = max(1, int(base_iterations))
    phase = (p - 1) % 3

    if phase == 0:
        return base + p, 6 + p
    if phase == 1:
        return base + 24 + (p * 2), 7 + p
    return base + 48 + (p * 3), 8 + p


def _write_quality_pass_report(
    reports_out_dir: str,
    pass_rows: list[dict[str, object]],
) -> None:
    if not pass_rows:
        return

    out_path = os.path.join(reports_out_dir, "quality_tercile_passes.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "pass",
            "filename",
            "old_error_per_pixel",
            "new_error_per_pixel",
            "improved",
            "iteration_budget",
            "badge_validation_rounds",
        ])
        for row in pass_rows:
            writer.writerow([
                row["pass"],
                row["filename"],
                f"{float(row['old_error_per_pixel']):.8f}",
                f"{float(row['new_error_per_pixel']):.8f}",
                "1" if bool(row["improved"]) else "0",
                row["iteration_budget"],
                row["badge_validation_rounds"],
            ])


def _extract_svg_inner(svg_text: str) -> str:
    match = re.search(r"<svg[^>]*>(.*)</svg>", svg_text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return svg_text


def _build_transformed_svg_from_template(
    template_svg_text: str,
    target_w: int,
    target_h: int,
    *,
    rotation_deg: int,
    scale: float,
) -> str:
    inner = _extract_svg_inner(template_svg_text)
    # Keep donor stroke widths visually stable when trying scale-based transfers.
    # This mirrors the "M->S/L while preserving line thickness" workflow that is
    # often needed for noisy small/large bitmap variants.
    inner = re.sub(
        r"<(circle|ellipse|line|path|polygon|polyline|rect)\\b([^>]*)>",
        lambda m: (
            f"<{m.group(1)}{m.group(2)}>"
            if "vector-effect=" in m.group(2)
            else f"<{m.group(1)}{m.group(2)} vector-effect=\"non-scaling-stroke\">"
        ),
        inner,
        flags=re.IGNORECASE,
    )
    cx = float(target_w) / 2.0
    cy = float(target_h) / 2.0
    return (
        f'<svg width="{target_w}" height="{target_h}" viewBox="0 0 {target_w} {target_h}" '
        'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">\n'
        f'  <g transform="translate({cx:.3f} {cy:.3f}) rotate({int(rotation_deg)}) scale({float(scale):.4f}) '
        f'translate({-cx:.3f} {-cy:.3f})">\n'
        f"{inner}\n"
        "  </g>\n"
        "</svg>"
    )


def _template_transfer_scale_candidates(base_scale: float) -> list[float]:
    """Build a compact scale ladder around an estimated best scale."""
    if not math.isfinite(base_scale) or base_scale <= 0.0:
        base_scale = 1.0

    multipliers = (1.00, 0.92, 1.08, 0.84, 1.18, 0.74, 1.35, 1.55)
    scales: list[float] = []
    seen: set[float] = set()
    for mul in multipliers:
        value = float(min(1.90, max(0.65, base_scale * mul)))
        key = round(value, 4)
        if key in seen:
            continue
        seen.add(key)
        scales.append(key)

    for fallback in (0.80, 0.90, 1.00, 1.10, 1.25):
        key = round(float(fallback), 4)
        if key not in seen:
            seen.add(key)
            scales.append(key)
    return scales


def _estimate_template_transfer_scale(
    img_orig: np.ndarray,
    donor_svg_text: str,
    target_w: int,
    target_h: int,
    *,
    rotation_deg: int,
) -> float | None:
    """Estimate donor->target scale from foreground silhouette bboxes."""
    rendered = Action.render_svg_to_numpy(
        _build_transformed_svg_from_template(
            donor_svg_text,
            target_w,
            target_h,
            rotation_deg=rotation_deg,
            scale=1.0,
        ),
        target_w,
        target_h,
    )
    if rendered is None:
        return None

    target_mask = Action._foreground_mask(img_orig)
    donor_mask = Action._foreground_mask(rendered)
    target_bbox = Action._mask_bbox(target_mask)
    donor_bbox = Action._mask_bbox(donor_mask)
    if target_bbox is None or donor_bbox is None:
        return None

    target_w_box = max(1e-6, float(target_bbox[2] - target_bbox[0] + 1.0))
    target_h_box = max(1e-6, float(target_bbox[3] - target_bbox[1] + 1.0))
    donor_w_box = max(1e-6, float(donor_bbox[2] - donor_bbox[0] + 1.0))
    donor_h_box = max(1e-6, float(donor_bbox[3] - donor_bbox[1] + 1.0))

    scale_w = target_w_box / donor_w_box
    scale_h = target_h_box / donor_h_box
    scale = math.sqrt(max(1e-6, scale_w * scale_h))
    if not math.isfinite(scale):
        return None
    return float(min(1.90, max(0.65, scale)))


def _template_transfer_transform_candidates(
    target_variant: str,
    donor_variant: str,
    *,
    estimated_scale_by_rotation: dict[int, float] | None = None,
) -> list[tuple[int, float]]:
    """Return ordered rotation/scale candidates for template-based fallback."""
    del target_variant, donor_variant  # reserved for future metadata-based policies

    candidates: list[tuple[int, float]] = []
    seen: set[tuple[int, float]] = set()
    for rotation in (0, 90, 180, 270):
        estimated = None
        if estimated_scale_by_rotation is not None:
            estimated = estimated_scale_by_rotation.get(rotation)
        for scale in _template_transfer_scale_candidates(estimated if estimated is not None else 1.0):
            candidate = (rotation, float(scale))
            key = (rotation, round(float(scale), 4))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates


def _rank_template_transfer_donors(
    target_row: dict[str, object],
    donor_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Prioritize donors that are already good and geometrically close to target."""
    target_base = str(target_row.get("base", "")).upper()
    target_sig: dict[str, float] | None = None
    target_params = target_row.get("params")
    if isinstance(target_params, dict):
        target_sig = _normalized_geometry_signature(
            int(target_row.get("w", 0)),
            int(target_row.get("h", 0)),
            dict(target_params),
        )

    ranked: list[tuple[tuple[float, float, float], dict[str, object]]] = []
    for donor in donor_rows:
        donor_base = str(donor.get("base", "")).upper()
        donor_error_pp = float(donor.get("error_per_pixel", float("inf")))
        donor_sig: dict[str, float] | None = None
        donor_params = donor.get("params")
        if isinstance(donor_params, dict):
            donor_sig = _normalized_geometry_signature(int(donor.get("w", 0)), int(donor.get("h", 0)), dict(donor_params))

        delta = float("inf")
        if target_sig is not None and donor_sig is not None:
            delta = _max_signature_delta(target_sig, donor_sig)

        key = (0.0 if donor_base == target_base else 1.0, delta, donor_error_pp)
        ranked.append((key, donor))

    ranked.sort(key=lambda item: item[0])
    return [donor for _, donor in ranked]




def _semantic_transfer_rotations(target_params: dict[str, object], donor_params: dict[str, object]) -> tuple[int, ...]:
    """Rotation candidates for semantic transfer while preserving symbol semantics."""
    has_text = bool(target_params.get("draw_text", False) or donor_params.get("draw_text", False))
    has_connector = bool(
        target_params.get("arm_enabled", False)
        or target_params.get("stem_enabled", False)
        or donor_params.get("arm_enabled", False)
        or donor_params.get("stem_enabled", False)
    )
    if has_text or has_connector:
        # Directional semantic badges (e.g. AC0812 left arm) encode orientation in
        # geometry. Rotating donor templates can improve pixel error but flips the
        # meaning of connector-side symbols. Keep transfer upright/unrotated.
        return (0,)
    return (0, 90, 180, 270)




def _semantic_transfer_scale_candidates(base_scale: float) -> list[float]:
    """Broader scale ladder for semantic badge transfer exploration."""
    core = _template_transfer_scale_candidates(base_scale)
    extra = [0.55, 0.65, 0.75, 0.85, 1.00, 1.15, 1.30, 1.50, 1.75, 2.00]
    values = []
    seen: set[float] = set()
    for v in [*core, *extra]:
        value = float(min(2.2, max(0.5, float(v))))
        key = round(value, 4)
        if key in seen:
            continue
        seen.add(key)
        values.append(key)
    return values

def _semantic_transfer_badge_params(
    donor_params: dict[str, object],
    target_params: dict[str, object],
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
        p["arm_x1"] = float(np.clip(x1, 0.0, max(0.0, float(target_w - 1))))
        p["arm_y1"] = float(np.clip(y1, 0.0, max(0.0, float(target_h - 1))))
        p["arm_x2"] = float(np.clip(x2, 0.0, max(0.0, float(target_w - 1))))
        p["arm_y2"] = float(np.clip(y2, 0.0, max(0.0, float(target_h - 1))))

    if p.get("stem_enabled"):
        stem_x = float(p.get("stem_x", tx)) + (float(p.get("stem_width", 1.0)) / 2.0)
        top = float(p.get("stem_top", ty))
        bottom = float(p.get("stem_bottom", ty))
        x1, y1 = _rot_scale_point(stem_x, top)
        x2, y2 = _rot_scale_point(stem_x, bottom)
        p["stem_x"] = float(np.clip((x1 + x2) / 2.0 - (float(p.get("stem_width", 1.0)) / 2.0), 0.0, float(target_w)))
        p["stem_top"] = float(np.clip(min(y1, y2), 0.0, float(target_h)))
        p["stem_bottom"] = float(np.clip(max(y1, y2), 0.0, float(target_h)))

    # Keep text horizontally readable; only scale text size mildly with radius changes.
    if bool(p.get("draw_text", False)):
        if "s" in p:
            p["s"] = float(max(1e-4, float(p.get("s", 0.01)) * math.sqrt(max(0.5, min(1.8, float(scale))))))

    symbol_name = str(target_params.get("label") or target_params.get("variant") or target_params.get("base") or "")
    if symbol_name:
        p = Action._finalize_ac08_style(symbol_name, p)
    return p

def _try_template_transfer(
    *,
    target_row: dict[str, object],
    donor_rows: list[dict[str, object]],
    folder_path: str,
    svg_out_dir: str,
    diff_out_dir: str,
    rng: random.Random | None = None,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    filename = str(target_row.get("filename", ""))
    if not filename:
        return None, None

    img_path = os.path.join(folder_path, filename)
    img_orig = cv2.imread(img_path)
    if img_orig is None:
        return None, None

    h, w = img_orig.shape[:2]
    pixel_count = float(max(1, w * h))
    prev_error_pp = float(target_row.get("error_per_pixel", float("inf")))

    best_svg: str | None = None
    best_error = float(target_row.get("best_error", float("inf")))
    best_error_pp = prev_error_pp
    best_donor = ""
    best_rotation = 0
    best_scale = 1.0

    target_variant = str(target_row.get("variant", "")).upper()
    ordered_donors = _rank_template_transfer_donors(target_row, donor_rows)
    if rng is not None and len(ordered_donors) > 1:
        head = ordered_donors[:3]
        tail = ordered_donors[3:]
        rng.shuffle(head)
        ordered_donors = head + tail
    for donor in ordered_donors:
        donor_variant = str(donor.get("variant", "")).upper()
        if not donor_variant or donor_variant == target_variant:
            continue
        donor_svg_path = os.path.join(svg_out_dir, f"{donor_variant}.svg")
        if not os.path.exists(donor_svg_path):
            continue
        try:
            donor_svg_text = open(donor_svg_path, "r", encoding="utf-8").read()
        except OSError:
            continue

        estimated_scales = {
            rotation: _estimate_template_transfer_scale(
                img_orig,
                donor_svg_text,
                w,
                h,
                rotation_deg=rotation,
            )
            for rotation in (0, 90, 180, 270)
        }

        target_params_raw = target_row.get("params")
        donor_params_raw = donor.get("params")
        if isinstance(target_params_raw, dict) and isinstance(donor_params_raw, dict):
            if str(target_params_raw.get("mode", "")) == "semantic_badge" and str(donor_params_raw.get("mode", "")) == "semantic_badge":
                base_scale = float(min(w, h)) / max(1.0, float(min(int(donor.get("w", w)), int(donor.get("h", h)))))
                semantic_scales = _semantic_transfer_scale_candidates(base_scale)
                if rng is not None:
                    keep = semantic_scales[:2]
                    rest = semantic_scales[2:]
                    rng.shuffle(rest)
                    semantic_scales = keep + rest
                for rotation in _semantic_transfer_rotations(dict(target_params_raw), dict(donor_params_raw)):
                    for scale in semantic_scales:
                        candidate_params = _semantic_transfer_badge_params(
                            dict(donor_params_raw),
                            dict(target_params_raw),
                            target_w=w,
                            target_h=h,
                            rotation_deg=rotation,
                            scale=float(scale),
                        )
                        try:
                            candidate_svg = Action.generate_badge_svg(w, h, candidate_params)
                            rendered = Action.render_svg_to_numpy(candidate_svg, w, h)
                        except Exception:
                            continue
                        error = Action.calculate_error(img_orig, rendered)
                        error_pp = float(error) / pixel_count
                        if error_pp + 1e-9 < best_error_pp:
                            best_error = float(error)
                            best_error_pp = error_pp
                            best_svg = candidate_svg
                            best_donor = donor_variant
                            best_rotation = rotation
                            best_scale = float(scale)

        for rotation, scale in _template_transfer_transform_candidates(
            target_variant,
            donor_variant,
            estimated_scale_by_rotation=estimated_scales,
        ):
            candidate_svg = _build_transformed_svg_from_template(
                donor_svg_text,
                w,
                h,
                rotation_deg=rotation,
                scale=scale,
            )
            rendered = Action.render_svg_to_numpy(candidate_svg, w, h)
            error = Action.calculate_error(img_orig, rendered)
            error_pp = float(error) / pixel_count
            if error_pp + 1e-9 < best_error_pp:
                best_error = float(error)
                best_error_pp = error_pp
                best_svg = candidate_svg
                best_donor = donor_variant
                best_rotation = rotation
                best_scale = scale

    if best_svg is None:
        return None, None

    stem = os.path.splitext(filename)[0]
    svg_path = os.path.join(svg_out_dir, f"{stem}.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(best_svg)

    rendered = Action.render_svg_to_numpy(best_svg, w, h)
    if rendered is not None:
        diff = Action.create_diff_image(img_orig, rendered)
        cv2.imwrite(os.path.join(diff_out_dir, f"{stem}_diff.png"), diff)

    updated_row = dict(target_row)
    updated_row["best_error"] = float(best_error)
    updated_row["error_per_pixel"] = float(best_error_pp)

    detail = {
        "filename": filename,
        "donor_variant": best_donor,
        "rotation_deg": int(best_rotation),
        "scale": float(best_scale),
        "old_error_per_pixel": float(prev_error_pp),
        "new_error_per_pixel": float(best_error_pp),
    }
    return updated_row, detail


def convert_range(
    folder_path: str,
    csv_path: str,
    iterations: int,
    start_ref: str = "AR0102",
    end_ref: str = "AR0104",
    debug_ac0811_dir: str | None = None,
    debug_element_diff_dir: str | None = None,
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
    rng = _conversion_random()
    process_files = list(files)
    rng.shuffle(process_files)

    base_iterations = max(128, int(iterations))
    max_quality_passes = 4
    quality_logs: list[dict[str, object]] = []
    result_map: dict[str, dict[str, object]] = {}

    def _convert_one(filename: str, iteration_budget: int, badge_rounds: int) -> dict[str, object] | None:
        image_path = os.path.join(folder_path, filename)
        res = run_iteration_pipeline(
            image_path,
            csv_path,
            max(1, int(iteration_budget)),
            svg_out_dir,
            diff_out_dir,
            reports_out_dir,
            debug_ac0811_dir,
            debug_element_diff_dir,
            badge_validation_rounds=max(1, int(badge_rounds)),
        )
        if not res:
            return None

        _base, _desc, params, best_iter, best_error = res
        img = cv2.imread(image_path)
        pixel_count = 1.0
        width = 0
        height = 0
        if img is not None:
            height, width = img.shape[:2]
            pixel_count = float(max(1, width * height))

        return {
            "filename": filename,
            "params": params,
            "best_iter": int(best_iter),
            "best_error": float(best_error),
            "error_per_pixel": float(best_error) / pixel_count,
            "w": int(width),
            "h": int(height),
            "base": get_base_name_from_file(os.path.splitext(filename)[0]).upper(),
            "variant": os.path.splitext(filename)[0].upper(),
        }

    # Initial conversion pass for all forms.
    for filename in process_files:
        row = _convert_one(filename, iteration_budget=base_iterations, badge_rounds=6)
        if row is None:
            continue

        donor_rows = [
            prev
            for key, prev in result_map.items()
            if key != filename and math.isfinite(float(prev.get("error_per_pixel", float("inf"))))
        ]
        if donor_rows:
            transferred, _detail = _try_template_transfer(
                target_row=row,
                donor_rows=donor_rows,
                folder_path=folder_path,
                svg_out_dir=svg_out_dir,
                diff_out_dir=diff_out_dir,
                rng=rng,
            )
            if transferred is not None and float(transferred.get("error_per_pixel", float("inf"))) + 1e-9 < float(row.get("error_per_pixel", float("inf"))):
                row = transferred

        result_map[filename] = row

    current_rows = [
        row
        for row in result_map.values()
        if math.isfinite(float(row.get("error_per_pixel", float("inf"))))
    ]
    ranked_rows = sorted(current_rows, key=_quality_sort_key)
    first_cut = max(1, len(ranked_rows) // 3) if ranked_rows else 0
    initial_top_tercile = ranked_rows[:first_cut]
    initial_threshold = float(initial_top_tercile[-1]["error_per_pixel"]) if initial_top_tercile else float("inf")

    cfg = _load_quality_config(reports_out_dir)
    allowed_error_pp = initial_threshold
    cfg_value = cfg.get("allowed_error_per_pixel")
    if cfg_value is not None:
        try:
            allowed_error_pp = max(0.0, float(cfg_value))
        except (TypeError, ValueError):
            allowed_error_pp = initial_threshold

    skip_variants: set[str] = {str(row["variant"]) for row in initial_top_tercile}
    cfg_skips = cfg.get("skip_variants")
    if isinstance(cfg_skips, list):
        skip_variants.update(str(item).upper() for item in cfg_skips)

    if math.isfinite(allowed_error_pp):
        for row in ranked_rows:
            if float(row.get("error_per_pixel", float("inf"))) <= allowed_error_pp:
                skip_variants.add(str(row.get("variant", "")).upper())

    _write_quality_config(
        reports_out_dir,
        allowed_error_per_pixel=allowed_error_pp,
        skipped_variants=sorted(v for v in skip_variants if v),
        source="manual-config" if cfg_value is not None else "initial-first-tercile",
    )

    # Iteratively refine unresolved quality cases while preserving all already
    # successful outputs (replace only when strictly better).
    consecutive_no_improvement = 0
    strategy_switch_after = 2
    strategy_logs: list[dict[str, object]] = []
    for pass_idx in range(1, max_quality_passes + 1):
        Action.STOCHASTIC_SEED_OFFSET = pass_idx
        current_rows = [
            row
            for row in result_map.values()
            if math.isfinite(float(row.get("error_per_pixel", float("inf"))))
        ]
        candidates = _select_open_quality_cases(
            current_rows,
            allowed_error_per_pixel=allowed_error_pp,
            skip_variants=skip_variants,
        )
        # Fallback to the historical selection when no explicit open set exists
        # (e.g. without threshold config).
        if not candidates:
            candidates = _select_middle_lower_tercile(current_rows)
        if not candidates:
            break

        improved_in_pass = False
        iteration_budget, badge_rounds = _iteration_strategy_for_pass(pass_idx, base_iterations)
        if len(candidates) > 1:
            rng.shuffle(candidates)
        for row in candidates:
            filename = str(row["filename"])
            variant = str(row.get("variant", "")).upper()
            if variant in skip_variants:
                continue

            prev_error_pp = float(row["error_per_pixel"])

            new_row = _convert_one(filename, iteration_budget=iteration_budget, badge_rounds=badge_rounds)
            if new_row is None:
                continue

            new_error_pp = float(new_row["error_per_pixel"])
            improved = new_error_pp + 1e-9 < prev_error_pp
            if improved:
                result_map[filename] = new_row
                improved_in_pass = True

            quality_logs.append(
                {
                    "pass": pass_idx,
                    "filename": filename,
                    "old_error_per_pixel": prev_error_pp,
                    "new_error_per_pixel": new_error_pp,
                    "improved": improved,
                    "iteration_budget": iteration_budget,
                    "badge_validation_rounds": badge_rounds,
                }
            )

        if not improved_in_pass:
            consecutive_no_improvement += 1
        else:
            consecutive_no_improvement = 0

        if consecutive_no_improvement >= strategy_switch_after:
            donor_rows = [
                row
                for row in result_map.values()
                if math.isfinite(float(row.get("error_per_pixel", float("inf"))))
                and float(row.get("error_per_pixel", float("inf"))) <= allowed_error_pp
            ]
            fallback_improved = False
            if len(candidates) > 1:
                rng.shuffle(candidates)
            for row in candidates:
                filename = str(row["filename"])
                current = result_map.get(filename)
                if current is None:
                    continue
                prev_error_pp = float(current.get("error_per_pixel", float("inf")))
                if prev_error_pp <= allowed_error_pp:
                    continue

                updated, detail = _try_template_transfer(
                    target_row=current,
                    donor_rows=donor_rows,
                    folder_path=folder_path,
                    svg_out_dir=svg_out_dir,
                    diff_out_dir=diff_out_dir,
                    rng=rng,
                )
                if updated is None or detail is None:
                    continue

                new_error_pp = float(updated["error_per_pixel"])
                improved = new_error_pp + 1e-9 < prev_error_pp
                if improved:
                    result_map[filename] = updated
                    fallback_improved = True
                    strategy_logs.append(detail)

            if fallback_improved:
                consecutive_no_improvement = 0
                continue
            else:
                break

        if not improved_in_pass and consecutive_no_improvement < strategy_switch_after:
            continue

    _write_quality_pass_report(reports_out_dir, quality_logs)
    if strategy_logs:
        strategy_path = os.path.join(reports_out_dir, "strategy_switch_template_transfers.csv")
        with open(strategy_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "filename",
                "donor_variant",
                "rotation_deg",
                "scale",
                "old_error_per_pixel",
                "new_error_per_pixel",
            ])
            for row in strategy_logs:
                writer.writerow([
                    row["filename"],
                    row["donor_variant"],
                    row["rotation_deg"],
                    f"{float(row['scale']):.4f}",
                    f"{float(row['old_error_per_pixel']):.8f}",
                    f"{float(row['new_error_per_pixel']):.8f}",
                ])

    log_path = os.path.join(reports_out_dir, "Iteration_Log.csv")
    semantic_results: list[dict[str, object]] = []
    with open(log_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Dateiname", "Gefundene Elemente", "Beste Iteration", "Diff-Score", "FehlerProPixel"])
        for filename in files:
            row = result_map.get(filename)
            if row is None:
                continue
            params = dict(row["params"])
            writer.writerow([
                filename,
                " + ".join(params.get("elements", [])),
                int(row["best_iter"]),
                f"{float(row['best_error']):.2f}",
                f"{float(row['error_per_pixel']):.8f}",
            ])

            if params.get("mode") == "semantic_badge":
                semantic_results.append(
                    {
                        "filename": filename,
                        "base": row["base"],
                        "variant": row["variant"],
                        "w": int(row.get("w", 0)),
                        "h": int(row.get("h", 0)),
                        "error": float(row["best_error"]),
                    }
                )

    _harmonize_semantic_size_variants(semantic_results, folder_path, svg_out_dir, reports_out_dir)
    _write_pixel_delta2_ranking(folder_path, svg_out_dir, reports_out_dir)

    Action.STOCHASTIC_SEED_OFFSET = 0
    return out_root


def _read_svg_geometry(svg_path: str) -> tuple[int, int, dict] | None:
    if not os.path.exists(svg_path):
        return None

    text = open(svg_path, "r", encoding="utf-8").read()

    svg_match = re.search(r"<svg[^>]*viewBox=\"0 0 (\d+) (\d+)\"", text)
    if not svg_match:
        return None
    w = int(svg_match.group(1))
    h = int(svg_match.group(2))

    def _gray_from_hex(color: str, fallback: int) -> int:
        m = re.match(r"#([0-9a-fA-F]{6})", color.strip())
        if not m:
            return fallback
        hex_value = m.group(1)
        r = int(hex_value[0:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
        return int(round((r + g + b) / 3.0))

    params: dict[str, float | bool | int | str] = {
        "fill_gray": 220,
        "stroke_gray": 152,
        "text_gray": 98,
        "draw_text": False,
        "text_mode": "path",
        "circle_enabled": False,
        "stem_enabled": False,
        "arm_enabled": False,
    }

    circle_match = re.search(
        r"<circle[^>]*cx=\"([0-9.]+)\"[^>]*cy=\"([0-9.]+)\"[^>]*r=\"([0-9.]+)\"[^>]*stroke-width=\"([0-9.]+)\"",
        text,
    )
    if circle_match:
        params["circle_enabled"] = True
        params["cx"] = float(circle_match.group(1))
        params["cy"] = float(circle_match.group(2))
        params["r"] = float(circle_match.group(3))
        params["stroke_circle"] = float(circle_match.group(4))
        circle_tag_match = re.search(r"(<circle[^>]*>)", text)
        if circle_tag_match:
            circle_tag = circle_tag_match.group(1)
            fill_match = re.search(r'fill="(#[0-9a-fA-F]{6})"', circle_tag)
            stroke_match = re.search(r'stroke="(#[0-9a-fA-F]{6})"', circle_tag)
            if fill_match:
                params["fill_gray"] = _gray_from_hex(fill_match.group(1), int(params["fill_gray"]))
            if stroke_match:
                params["stroke_gray"] = _gray_from_hex(stroke_match.group(1), int(params["stroke_gray"]))

    rect_match = re.search(
        r"<rect[^>]*x=\"([0-9.]+)\"[^>]*y=\"([0-9.]+)\"[^>]*width=\"([0-9.]+)\"[^>]*height=\"([0-9.]+)\"",
        text,
    )
    if rect_match:
        x = float(rect_match.group(1))
        y = float(rect_match.group(2))
        width = float(rect_match.group(3))
        height = float(rect_match.group(4))
        params["stem_enabled"] = True
        params["stem_x"] = x
        params["stem_width"] = width
        params["stem_top"] = y
        params["stem_bottom"] = y + height
        rect_tag_match = re.search(r"(<rect[^>]*>)", text)
        if rect_tag_match:
            rect_fill_match = re.search(r'fill="(#[0-9a-fA-F]{6})"', rect_tag_match.group(1))
            if rect_fill_match:
                params["stem_gray"] = _gray_from_hex(rect_fill_match.group(1), int(params["stroke_gray"]))
            else:
                params["stem_gray"] = int(params["stroke_gray"])
        else:
            params["stem_gray"] = int(params["stroke_gray"])

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
            cx = float(np.clip(cx, min_cx, max_cx))

        if min_cy > max_cy:
            cy = float(target_h) / 2.0
        else:
            cy = float(np.clip(cy, min_cy, max_cy))

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
    grouped: dict[str, list[dict[str, object]]] = {}
    for result in results:
        base = str(result.get("base", ""))
        grouped.setdefault(base, []).append(result)

    harmonized_logs: list[str] = []
    category_logs: list[str] = []
    for base, entries in sorted(grouped.items()):
        if len(entries) < 2:
            continue

        variant_rows: list[dict[str, object]] = []
        for entry in entries:
            variant = str(entry["variant"])
            suffix = variant.rsplit("_", 1)[-1] if "_" in variant else ""
            if suffix not in {"L", "M", "S"}:
                continue
            parsed = _read_svg_geometry(os.path.join(svg_out_dir, f"{variant}.svg"))
            if parsed is None:
                continue
            w, h, params = parsed
            variant_rows.append({"entry": entry, "variant": variant, "suffix": suffix, "w": w, "h": h, "params": params})

        if len(variant_rows) < 2:
            continue

        has_text = any(bool(dict(row["params"]).get("draw_text", False)) for row in variant_rows)
        has_stem = any(bool(dict(row["params"]).get("stem_enabled", False)) for row in variant_rows)
        has_arm = any(bool(dict(row["params"]).get("arm_enabled", False)) for row in variant_rows)
        has_connector = has_stem or has_arm
        category = "Kreise mit Buchstaben" if has_text and not has_connector else (
            "Kreise ohne Buchstaben" if (not has_text and not has_connector) else (
                "Kellen mit Buchstaben" if has_text else "Kellen ohne Buchstaben"
            )
        )
        variants_joined = "|".join(sorted(str(r["variant"]) for r in variant_rows))
        category_logs.append(f"{base};{category};{variants_joined}")

        sigs = {
            row["variant"]: _normalized_geometry_signature(int(row["w"]), int(row["h"]), dict(row["params"]))
            for row in variant_rows
        }
        max_delta = 0.0
        for i in range(len(variant_rows)):
            for j in range(i + 1, len(variant_rows)):
                vi = str(variant_rows[i]["variant"])
                vj = str(variant_rows[j]["variant"])
                max_delta = max(max_delta, _max_signature_delta(sigs[vi], sigs[vj]))

        # Do not skip families with one badly fitted outlier variant. We still
        # validate every harmonization candidate against raster error before write.

        def _anchor_rank(row: dict[str, object]) -> tuple[int, float]:
            suffix = str(row.get("suffix", ""))
            # Connector families ("Kellen") tend to under-fit large variants
            # when we derive L from M. Prefer L as harmonization anchor so the
            # largest geometry stays authoritative and M/S scale down from it.
            priority = _harmonization_anchor_priority(suffix, prefer_large=has_connector)
            err = float(dict(row["entry"]).get("error", float("inf")))
            return priority, err

        anchor = min(variant_rows, key=_anchor_rank)
        anchor_variant = str(anchor["variant"])
        anchor_w = int(anchor["w"])
        anchor_h = int(anchor["h"])
        anchor_params = dict(anchor["params"])

        for row in variant_rows:
            if row is anchor:
                continue
            target_variant = str(row["variant"])
            target_w = int(row["w"])
            target_h = int(row["h"])
            scaled = _scale_badge_params(anchor_params, anchor_w, anchor_h, target_w, target_h)
            svg = Action.generate_badge_svg(target_w, target_h, scaled)

            target_filename = str(dict(row["entry"])["filename"])
            target_path = os.path.join(folder_path, target_filename)
            target_img = cv2.imread(target_path)
            if target_img is None:
                harmonized_logs.append(f"{base}: {target_variant} übersprungen (Bild fehlt: {target_filename})")
                continue

            rendered = Action.render_svg_to_numpy(svg, target_w, target_h)
            candidate_error = Action.calculate_error(target_img, rendered)
            baseline_error = float(dict(row["entry"]).get("error", float("inf")))
            if candidate_error > baseline_error + 0.25:
                harmonized_logs.append(
                    (
                        f"{base}: {target_variant} nicht harmonisiert "
                        f"(Fehler {candidate_error:.2f} > Basis {baseline_error:.2f})"
                    )
                )
                continue

            with open(os.path.join(svg_out_dir, f"{target_variant}.svg"), "w", encoding="utf-8") as f:
                f.write(svg)
            harmonized_logs.append(
                (
                    f"{base}: {target_variant} aus {anchor_variant} abgeleitet "
                    f"(max_delta={max_delta:.4f}, Fehler {baseline_error:.2f}->{candidate_error:.2f})"
                )
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

    valid = [row for row in ranking if np.isfinite(float(row["mean_delta2"]))]
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
