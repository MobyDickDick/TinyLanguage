from __future__ import annotations

import argparse
import csv
import math
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.image_composite_converter import convert_image


DEFAULT_CSV_PATH = Path("artifacts/images_to_convert/nonexistent.csv")
DEFAULT_IMG_DIR = Path("artifacts/images_to_convert")
DEFAULT_OUTPUT_DIR = Path("artifacts/converted_symbols")
LIMIT = 50


@dataclass
class BadgeSpec:
    code: str
    description: str
    width: int
    height: int


def read_jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"{path} is not a JPEG file")

    i = 2
    while i < len(data):
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1

        if marker in (0xD8, 0xD9):
            continue
        if i + 2 > len(data):
            break
        seg_len = struct.unpack(">H", data[i : i + 2])[0]
        if seg_len < 2 or i + seg_len > len(data):
            break

        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if i + 7 > len(data):
                break
            height, width = struct.unpack(">HH", data[i + 3 : i + 7])
            return width, height

        i += seg_len

    raise ValueError(f"Could not read JPEG dimensions from {path}")


def choose_reference_image(code: str, img_dir: Path) -> Path:
    candidates = sorted(img_dir.glob(f"{code}*.jpg")) + sorted(img_dir.glob(f"{code}*.JPG"))
    if not candidates:
        raise FileNotFoundError(f"No reference image found for {code}")

    ranked: list[tuple[int, bool, Path]] = []
    for candidate in candidates:
        width, height = read_jpeg_size(candidate)
        area = width * height
        is_large_variant = "_L" in candidate.stem.upper()
        ranked.append((area, is_large_variant, candidate))

    ranked.sort(key=lambda item: (item[0], item[1], item[2].name))
    return ranked[-1][2]


def color_profile(description: str) -> tuple[str, str, str]:
    d = description.lower()

    if "dunkelgrauem rand" in d:
        stroke = "#666666"
    elif "grauem rand" in d:
        stroke = "#808080"
    else:
        stroke = "#111111"

    if "hellgrauem hintergrund" in d or "hellgrauer kreisfläche" in d:
        fill = "#dbdbdb"
    else:
        fill = "#111111"

    text = stroke
    return fill, stroke, text


def parse_specs(csv_path: Path, img_dir: Path, limit: int) -> list[BadgeSpec]:
    rows = list(csv.reader(csv_path.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))
    specs: list[BadgeSpec] = []
    for row in rows[1:]:
        if len(row) < 3:
            continue
        code = row[1].strip()
        if not code:
            continue
        ref = choose_reference_image(code, img_dir)
        w, h = read_jpeg_size(ref)
        specs.append(BadgeSpec(code=code, description=row[2].strip(), width=w, height=h))
        if len(specs) >= limit:
            break
    return specs


def detect_paddle(description: str) -> str | None:
    d = description.lower()
    if "ohne kelle" in d:
        return None
    if "kelle unten" in d:
        return "bottom"
    if "kelle links" in d:
        return "left"
    if "kelle oben" in d:
        return "top"
    if "kelle rechts" in d:
        return "right"
    if "waagrechtem grauem strich links" in d:
        return "left"
    if "senkrechter grauer strich" in d:
        return "bottom"
    if "senkrechter strich vom kreis nach oben" in d:
        return "top"
    return None


def detect_label(description: str) -> str:
    m = re.search(r'Buchstaben\s+"([^"]+)"', description)
    return m.group(1) if m else ""


def svg_for_spec(spec: BadgeSpec) -> str:
    w, h = spec.width, spec.height
    cx, cy = w / 2.0, h / 2.0
    r = max(4.0, min(w, h) * 0.36)
    stroke = max(1.2, min(w, h) * 0.06)
    paddle = detect_paddle(spec.description)
    label = detect_label(spec.description)

    fill_color, stroke_color, text_color = color_profile(spec.description)
    paddle_color = stroke_color

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="white"/>',
    ]

    paddle_w = max(1.0, min(w, h) * 0.12)
    paddle_len = max(2.0, r * 0.95)
    if paddle == "bottom":
        parts.append(f'<rect x="{cx - paddle_w / 2:.2f}" y="{cy + r - stroke / 2:.2f}" width="{paddle_w:.2f}" height="{paddle_len:.2f}" fill="{paddle_color}"/>')
    elif paddle == "top":
        parts.append(f'<rect x="{cx - paddle_w / 2:.2f}" y="{cy - r - paddle_len + stroke / 2:.2f}" width="{paddle_w:.2f}" height="{paddle_len:.2f}" fill="{paddle_color}"/>')
    elif paddle == "left":
        parts.append(f'<rect x="{cx - r - paddle_len + stroke / 2:.2f}" y="{cy - paddle_w / 2:.2f}" width="{paddle_len:.2f}" height="{paddle_w:.2f}" fill="{paddle_color}"/>')
    elif paddle == "right":
        parts.append(f'<rect x="{cx + r - stroke / 2:.2f}" y="{cy - paddle_w / 2:.2f}" width="{paddle_len:.2f}" height="{paddle_w:.2f}" fill="{paddle_color}"/>')

    parts.append(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke:.2f}"/>'
    )

    if label:
        # Keep text as large as possible while preserving a small visual margin to the inner circle.
        base_size = max(7.0, r * 0.90)
        if label == "CO_2":
            co_size = base_size
            sub_size = base_size * 0.65
            # Horizontal center refers to full CO₂ token; vertical center should align with CO only.
            parts.append(
                f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" dominant-baseline="middle" fill="{text_color}" '
                f'font-size="{co_size:.2f}" font-family="Arial, sans-serif">CO<tspan baseline-shift="sub" font-size="{sub_size:.2f}">2</tspan></text>'
            )
        else:
            parts.append(
                f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" dominant-baseline="middle" fill="{text_color}" '
                f'font-size="{base_size:.2f}" font-family="Arial, sans-serif">{label}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def parse_hex_color(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[1*2:2*2], 16), int(s[2*2:3*2], 16)


def draw_rect(img: list[list[list[int]]], x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    h = len(img)
    w = len(img[0])
    for y in range(max(0, y0), min(h, y1)):
        row = img[y]
        for x in range(max(0, x0), min(w, x1)):
            row[x][0], row[x][1], row[x][2] = color


def draw_circle(img: list[list[list[int]]], cx: float, cy: float, r: float, fill: tuple[int, int, int], stroke: tuple[int, int, int], stroke_width: float) -> None:
    h = len(img)
    w = len(img[0])
    inner = max(0.0, r - stroke_width / 2.0)
    outer = r + stroke_width / 2.0
    inner2 = inner * inner
    outer2 = outer * outer
    for y in range(h):
        dy2 = (y + 0.5 - cy) ** 2
        for x in range(w):
            d2 = (x + 0.5 - cx) ** 2 + dy2
            if d2 <= inner2:
                img[y][x][0], img[y][x][1], img[y][x][2] = fill
            elif d2 <= outer2:
                img[y][x][0], img[y][x][1], img[y][x][2] = stroke




def save_bmp24(path: Path, img: list[list[list[int]]]) -> None:
    height = len(img)
    width = len(img[0]) if height else 0
    row_stride = ((width * 3 + 3) // 4) * 4
    pixel_data_size = row_stride * height
    file_size = 54 + pixel_data_size

    header = bytearray()
    header.extend(b"BM")
    header.extend(struct.pack("<I", file_size))
    header.extend(struct.pack("<HH", 0, 0))
    header.extend(struct.pack("<I", 54))
    header.extend(struct.pack("<I", 40))
    header.extend(struct.pack("<i", width))
    header.extend(struct.pack("<i", height))
    header.extend(struct.pack("<H", 1))
    header.extend(struct.pack("<H", 24))
    header.extend(struct.pack("<I", 0))
    header.extend(struct.pack("<I", pixel_data_size))
    header.extend(struct.pack("<i", 2835))
    header.extend(struct.pack("<i", 2835))
    header.extend(struct.pack("<I", 0))
    header.extend(struct.pack("<I", 0))

    body = bytearray()
    padding = b"\x00" * (row_stride - width * 3)
    for y in range(height - 1, -1, -1):
        row = img[y]
        for x in range(width):
            r, g, b = row[x]
            body.extend((b, g, r))
        body.extend(padding)

    path.write_bytes(header + body)


def rasterize_simple(spec: BadgeSpec) -> list[list[list[int]]]:
    w, h = spec.width, spec.height
    cx, cy = w / 2.0, h / 2.0
    r = max(4.0, min(w, h) * 0.36)
    stroke = max(1.2, min(w, h) * 0.06)
    paddle = detect_paddle(spec.description)

    white = (255, 255, 255)
    fill_hex, stroke_hex, _text_hex = color_profile(spec.description)
    paddle_color = parse_hex_color(stroke_hex)
    fill_color = parse_hex_color(fill_hex)
    stroke_color = parse_hex_color(stroke_hex)

    img = [[[white[0], white[1], white[2]] for _ in range(w)] for _ in range(h)]

    paddle_w = max(1.0, min(w, h) * 0.12)
    paddle_len = max(2.0, r * 0.95)
    if paddle == "bottom":
        draw_rect(img, int(cx - paddle_w / 2), int(cy + r - stroke / 2), int(cx + paddle_w / 2), int(cy + r - stroke / 2 + paddle_len), paddle_color)
    elif paddle == "top":
        draw_rect(img, int(cx - paddle_w / 2), int(cy - r - paddle_len + stroke / 2), int(cx + paddle_w / 2), int(cy - r + stroke / 2), paddle_color)
    elif paddle == "left":
        draw_rect(img, int(cx - r - paddle_len + stroke / 2), int(cy - paddle_w / 2), int(cx - r + stroke / 2), int(cy + paddle_w / 2), paddle_color)
    elif paddle == "right":
        draw_rect(img, int(cx + r - stroke / 2), int(cy - paddle_w / 2), int(cx + r + paddle_len - stroke / 2), int(cy + paddle_w / 2), paddle_color)

    draw_circle(img, cx, cy, r, fill_color, stroke_color, stroke)

    return img




def inject_label_into_reconverted_svg(spec: BadgeSpec, svg_path: Path) -> None:
    label = detect_label(spec.description)
    if not label or not svg_path.exists():
        return

    content = svg_path.read_text(encoding="utf-8")
    if "<text" in content:
        return

    w, h = spec.width, spec.height
    cx, cy = w / 2.0, h / 2.0
    r = max(4.0, min(w, h) * 0.36)
    _fill_color, stroke_color, text_color = color_profile(spec.description)
    base_size = max(7.0, r * 0.90)

    if label == "CO_2":
        co_size = base_size
        sub_size = base_size * 0.65
        text_node = (
            f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" dominant-baseline="middle" fill="{text_color}" '
            f'font-size="{co_size:.2f}" font-family="Arial, sans-serif">CO'
            f'<tspan baseline-shift="sub" font-size="{sub_size:.2f}">2</tspan></text>'
        )
    else:
        text_node = (
            f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" dominant-baseline="middle" fill="{text_color}" '
            f'font-size="{base_size:.2f}" font-family="Arial, sans-serif">{label}</text>'
        )

    content = content.replace("</svg>", text_node + "\n</svg>")
    svg_path.write_text(content, encoding="utf-8")

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate synthetic badge SVG/BMP pairs and reconverted SVGs")
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH, help="CSV file describing badge objects")
    p.add_argument("--images-dir", type=Path, default=DEFAULT_IMG_DIR, help="Reference images directory")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output base directory")
    p.add_argument("--limit", type=int, default=LIMIT, help="Maximum number of objects to process")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()

    svg_out = args.output_dir / "svg"
    bmp_out = args.output_dir / "bmp"

    specs = parse_specs(args.csv, args.images_dir, args.limit)
    svg_out.mkdir(parents=True, exist_ok=True)
    bmp_out.mkdir(parents=True, exist_ok=True)

    for old in svg_out.glob("*.svg"):
        old.unlink()

    for spec in specs:
        svg_text = svg_for_spec(spec)
        (svg_out / f"{spec.code}.svg").write_text(svg_text, encoding="utf-8")

        bmp_img = rasterize_simple(spec)
        bmp_path = bmp_out / f"{spec.code}.bmp"
        save_bmp24(bmp_path, bmp_img)

        reconverted = svg_out / f"{spec.code}_reconverted.svg"
        convert_image(bmp_path, reconverted, max_iter=120, plateau_limit=36, seed=42)
        inject_label_into_reconverted_svg(spec, reconverted)

    print(f"Created {len(specs)} SVGs, {len(specs)} BMPs and {len(specs)} reconverted SVGs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
