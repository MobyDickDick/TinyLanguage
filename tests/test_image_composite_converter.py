from __future__ import annotations

from pathlib import Path

import pytest

conv = pytest.importorskip("src.image_composite_converter")


def test_find_elements_detects_multiple_components() -> None:
    binary = [[0 for _ in range(30)] for _ in range(20)]
    for y in range(2, 7):
        for x in range(2, 7):
            binary[y][x] = 1
    for y in range(10, 17):
        for x in range(20, 27):
            binary[y][x] = 1

    elements = conv.find_elements(binary, min_pixels=5)

    assert len(elements) == 2


def test_optimize_element_improves_or_keeps_score() -> None:
    target = [[0 for _ in range(16)] for _ in range(16)]
    for y in range(16):
        for x in range(16):
            if ((y - 8) ** 2 + (x - 8) ** 2) <= 16:
                target[y][x] = 1

    init = conv.Candidate(shape="circle", cx=8, cy=8, w=5, h=5)
    init_score = conv.score_candidate(target, init)
    best, best_score = conv.optimize_element(target, init, max_iter=80, plateau_limit=25, seed=123)

    assert isinstance(best, conv.Candidate)
    assert best_score >= init_score


def test_convert_image_writes_svg(tmp_path: Path) -> None:
    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")

    image = Image.new("L", (40, 40), 255)
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 24, 24), fill=0)
    draw.ellipse((26, 12, 36, 22), fill=0)

    src = tmp_path / "input.png"
    dst = tmp_path / "output.svg"
    image.save(src)

    conv.convert_image(src, dst, max_iter=60, plateau_limit=20, seed=7)

    text = dst.read_text(encoding="utf-8")
    assert "<svg" in text
    assert "<circle" in text or "<ellipse" in text


def test_estimate_stroke_style_detects_dark_ring() -> None:
    grayscale = [[255 for _ in range(25)] for _ in range(25)]
    pixels = [[0 for _ in range(21)] for _ in range(21)]

    cx = cy = 10
    for y in range(21):
        for x in range(21):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= 100:
                pixels[y][x] = 1
                if d2 >= 72:
                    grayscale[y + 2][x + 2] = 120
                else:
                    grayscale[y + 2][x + 2] = 210

    element = conv.Element(pixels=pixels, x0=2, y0=2, x1=22, y1=22)
    candidate = conv.Candidate(shape="circle", cx=10, cy=10, w=20, h=20)

    fill, stroke, stroke_width = conv.estimate_stroke_style(grayscale, element, candidate)

    assert fill == "#d2d2d2"
    assert stroke is not None
    assert int(stroke[1:3], 16) < int(fill[1:3], 16)
    assert stroke_width is not None and stroke_width >= 1.0




def test_candidate_to_svg_preserves_outer_size_with_stroke() -> None:
    candidate = conv.Candidate(shape="circle", cx=10.0, cy=10.0, w=20.0, h=20.0)

    svg = conv.candidate_to_svg(candidate, 0, 0, "#dbdbdb", "#808080", 2.0)

    assert 'r="9.00"' in svg
    assert 'stroke-width="2.00"' in svg


def test_decompose_circle_with_stem_detects_bottom_stem() -> None:
    size = 25
    grayscale = [[255 for _ in range(size)] for _ in range(size)]
    pixels = [[0 for _ in range(size)] for _ in range(size)]

    cx = cy = 12
    r = 8
    for y in range(size):
        for x in range(size):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= r * r:
                pixels[y][x] = 1
                grayscale[y][x] = 215

    for y in range(20, 24):
        for x in range(11, 14):
            pixels[y][x] = 1
            grayscale[y][x] = 128

    element = conv.Element(pixels=pixels, x0=0, y0=0, x1=24, y1=24)
    candidate = conv.Candidate(shape="circle", cx=12, cy=12, w=16, h=16)

    parts = conv.decompose_circle_with_stem(grayscale, element, candidate)

    assert parts is not None
    assert len(parts) == 2
    assert parts[0].startswith("<rect ")
    assert 'fill="#' in parts[0]
    assert parts[1].startswith("<circle ")


def test_decompose_circle_with_stem_ignores_plain_circle() -> None:
    size = 30
    grayscale = [[255 for _ in range(size)] for _ in range(size)]
    pixels = [[0 for _ in range(size)] for _ in range(size)]

    cx = cy = 14
    r = 12
    for y in range(size):
        for x in range(size):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= r * r:
                pixels[y][x] = 1
                grayscale[y][x] = 180

    element = conv.Element(pixels=pixels, x0=0, y0=0, x1=29, y1=29)
    candidate = conv.Candidate(shape="circle", cx=14, cy=14, w=24, h=24)

    parts = conv.decompose_circle_with_stem(grayscale, element, candidate)

    assert parts is None


def test_decompose_circle_with_stem_recenters_vertical_stem() -> None:
    size = 31
    grayscale = [[255 for _ in range(size)] for _ in range(size)]
    pixels = [[0 for _ in range(size)] for _ in range(size)]

    cx = cy = 15
    r = 9
    for y in range(size):
        for x in range(size):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= r * r:
                pixels[y][x] = 1
                grayscale[y][x] = 210

    for y in range(24, 29):
        for x in range(17, 20):
            pixels[y][x] = 1
            grayscale[y][x] = 120

    element = conv.Element(pixels=pixels, x0=0, y0=0, x1=size - 1, y1=size - 1)
    candidate = conv.Candidate(shape="circle", cx=15, cy=15, w=18, h=18)

    parts = conv.decompose_circle_with_stem(grayscale, element, candidate)

    assert parts is not None
    rect = parts[0]
    assert rect.startswith("<rect ")

    import re

    mx = re.search(r'x="([0-9.]+)"', rect)
    my = re.search(r'y="([0-9.]+)"', rect)
    mw = re.search(r'width="([0-9.]+)"', rect)
    assert mx and my and mw

    stem_x = float(mx.group(1))
    stem_y = float(my.group(1))
    stem_w = float(mw.group(1))
    stem_cx = stem_x + stem_w / 2.0

    assert abs(stem_cx - 15.0) <= 0.2
    assert stem_y <= 24.1


def test_generate_badges_reconverted_svg_contains_text(tmp_path: Path) -> None:
    gen = pytest.importorskip("tools.generate_badge_comparison_set")

    csv_path = tmp_path / "specs.csv"
    csv_path.write_text(
        "id;code;description\n"
        '1;AC0820;Semantisches Badge: Kreis mit dunkelgrauem Rand und hellgrauer Kreisfläche, mit waagrecht geschriebenem Buchstaben "CO".\n'
        '2;AC0831;Semantisches Badge: Kreis mit grauem Rand und hellgrauem Hintergrund, mit waagrecht geschriebenem Buchstaben "CO_2" und Kelle unten.\n',
        encoding="utf-8",
    )

    # Create matching reference JPEGs required by parse_specs/choose_reference_image.
    Image = pytest.importorskip("PIL.Image")
    for code in ("AC0820", "AC0831"):
        im = Image.new("RGB", (30, 30), (255, 255, 255))
        im.save(tmp_path / f"{code}_M.jpg", format="JPEG")

    out = tmp_path / "out"
    # Drive the generation routine via its helpers to avoid CLI monkeypatching.
    specs = gen.parse_specs(csv_path, tmp_path, limit=10)
    svg_out = out / "svg"
    bmp_out = out / "bmp"
    svg_out.mkdir(parents=True, exist_ok=True)
    bmp_out.mkdir(parents=True, exist_ok=True)

    for spec in specs:
        (svg_out / f"{spec.code}.svg").write_text(gen.svg_for_spec(spec), encoding="utf-8")
        bmp_img = gen.rasterize_simple(spec)
        bmp_path = bmp_out / f"{spec.code}.bmp"
        gen.save_bmp24(bmp_path, bmp_img)
        gen.convert_image(bmp_path, svg_out / f"{spec.code}_reconverted.svg", max_iter=120, plateau_limit=36, seed=42)

    reconverted = (svg_out / "AC0831_reconverted.svg").read_text(encoding="utf-8")
    assert "<text" in reconverted
