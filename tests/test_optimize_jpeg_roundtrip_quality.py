from __future__ import annotations

import random
import xml.etree.ElementTree as ET

from tools import optimize_jpeg_roundtrip_quality as opt


def test_mutate_svg_tree_structured_mutates_circle_geometry() -> None:
    root = ET.fromstring('<svg><circle cx="10" cy="12" r="5" fill="#808080" stroke="#404040" stroke-width="2.0" /></svg>')

    mutated = opt.mutate_svg_tree_structured(root, width=40, height=40, rng=random.Random(7), sigma=1.0)
    circle = list(mutated)[0]

    assert circle.tag == "circle"
    assert 0.0 <= float(circle.attrib["cx"]) <= 40.0
    assert 0.0 <= float(circle.attrib["cy"]) <= 40.0
    assert float(circle.attrib["r"]) >= 0.6
    assert float(circle.attrib["stroke-width"]) >= 0.2


def test_mutate_svg_tree_structured_mutates_line_geometry() -> None:
    root = ET.fromstring('<svg><line x1="4" y1="8" x2="20" y2="8" stroke="#404040" stroke-width="1.4" /></svg>')

    mutated = opt.mutate_svg_tree_structured(root, width=30, height=30, rng=random.Random(11), sigma=1.2)
    line = list(mutated)[0]

    assert line.tag == "line"
    for key in ("x1", "y1", "x2", "y2"):
        assert 0.0 <= float(line.attrib[key]) <= 30.0
    assert float(line.attrib["stroke-width"]) >= 0.2


