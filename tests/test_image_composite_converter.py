from __future__ import annotations

from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")
ImageDraw = pytest.importorskip("PIL.ImageDraw")
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
