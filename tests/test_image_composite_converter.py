"""Regression tests for CO₂ text positioning in semantic badges."""

from __future__ import annotations

from pathlib import Path

import pytest

import src.image_composite_converter as image_composite_converter
from src.image_composite_converter import Action


def test_co2_label_defaults_use_center_co_anchor_mode() -> None:
    """Default CO₂ layout should keep center_co mode and only shift left if required."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    layout = Action._co2_layout(params)

    assert layout["anchor_mode"] == "center_co"
    assert float(layout["co_x"]) <= float(params["cx"])
    assert float(params["co2_dx"]) == 0.0


def test_co2_layout_legacy_cluster_mode_still_supported() -> None:
    """Legacy cluster-centered mode should still shift CO left for the subscript."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    params["co2_anchor_mode"] = "cluster"
    layout = Action._co2_layout(params)

    assert layout["anchor_mode"] == "cluster"
    assert float(layout["co_x"]) < float(params["cx"])


def test_finalize_ac0820_uses_center_co_anchor_mode() -> None:
    """AC0820 should keep the main CO run centered for better optical balance."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820", params)

    assert params["co2_anchor_mode"] == "center_co"




def test_finalize_ac0820_variant_name_uses_center_co_anchor_mode() -> None:
    """AC0820 variant names (e.g. AC0820_L) should keep center_co alignment."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820_L", params)

    assert params["co2_anchor_mode"] == "center_co"
    assert float(params["co2_optical_bias"]) >= 0.125


def test_finalize_ac0820_increases_optical_bias_for_co_vertical_centering() -> None:
    """AC0820 should nudge CO down so the main run appears vertically centered in-circle."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820", params)
    layout = Action._co2_layout(params)

    assert float(layout["y_base"]) > float(params["cy"])
    assert abs(float(layout["y_base"]) - float(params["cy"])) <= 1.45




def test_co2_layout_keeps_subscript_inside_inner_circle_for_centered_badges() -> None:
    """Centered CO₂ badges should keep the subscript inside the inner circle."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    params = Action._finalize_ac08_style("AC0820", params)
    layout = Action._co2_layout(params)

    cx = float(params["cx"])
    r = float(params["r"])
    stroke = float(params["stroke_circle"])
    inner_right = cx + max(1.0, r - stroke)

    assert float(layout["x2"]) <= inner_right + 1e-6

def test_co2_layout_keeps_text_within_inner_circle_bounds() -> None:
    """CO₂ layout should not let any glyph run outside the inner circle boundary."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    params = Action._finalize_ac08_style("AC0820", params)
    layout = Action._co2_layout(params)

    cx = float(params["cx"])
    cy = float(params["cy"])
    r = float(params["r"])
    stroke = float(params["stroke_circle"])
    inner_left = cx - max(1.0, r - stroke)
    inner_right = cx + max(1.0, r - stroke)
    inner_top = cy - max(1.0, r - stroke)
    inner_bottom = cy + max(1.0, r - stroke)

    text_top = float(layout["y_base"]) - (float(layout["height"]) / 2.0)
    text_bottom = float(layout["subscript_y"]) + (float(layout["sub_font_px"]) * 0.35)

    assert float(layout["x1"]) >= inner_left - 1e-6
    assert float(layout["x2"]) <= inner_right + 1e-6
    assert text_top >= inner_top - 1e-6
    assert text_bottom <= inner_bottom + 1e-6


def test_co2_layout_vertical_centering_ignores_subscript_for_main_text() -> None:
    """The CO run should stay centered even if the subscript is very large."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    params = Action._finalize_ac08_style("AC0820", params)
    params["co2_sub_font_scale"] = 95.0
    layout = Action._co2_layout(params)

    assert abs(float(layout["y_base"]) - float(params["cy"])) <= 0.75


def test_co2_layout_keeps_subscript_inside_circle_without_changing_main_center() -> None:
    """Large subscripts should be constrained by offset, not by shifting the CO baseline."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    params = Action._finalize_ac08_style("AC0820", params)
    params["co2_sub_font_scale"] = 95.0
    layout = Action._co2_layout(params)

    cy = float(params["cy"])
    r = float(params["r"])
    stroke = float(params["stroke_circle"])
    inner_top = cy - max(1.0, r - stroke)
    inner_bottom = cy + max(1.0, r - stroke)

    sub_top = float(layout["subscript_y"]) - (float(layout["sub_font_px"]) * 0.60)
    sub_bottom = float(layout["subscript_y"]) + (float(layout["sub_font_px"]) * 0.35)

    assert sub_top >= inner_top - 1e-6
    assert sub_bottom <= inner_bottom + 1e-6
    assert abs(float(layout["y_base"]) - cy) <= 0.75


def test_co2_layout_enforces_minimum_subscript_pixel_size() -> None:
    """Subscript font should keep a minimum size so the "2" remains visible."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    params["co2_font_scale"] = 0.50
    params["co2_sub_font_scale"] = 40.0
    layout = Action._co2_layout(params)

    assert float(layout["sub_font_px"]) >= 4.0



def test_generate_badge_svg_renders_center_co_as_split_text_nodes() -> None:
    """center_co layout should render CO and subscript as separate positioned text nodes."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    svg = Action.generate_badge_svg(30, 30, params)

    assert ">CO</text>" in svg
    assert ">2</text>" in svg
    assert "<tspan" not in svg


def test_generate_badge_svg_renders_cluster_mode_as_split_text_nodes() -> None:
    """Cluster mode should render CO₂ as explicit CO + subscript nodes."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820", params)
    svg = Action.generate_badge_svg(30, 30, params)

    assert ">CO</text>" in svg
    assert ">2</text>" in svg
    assert "<tspan" not in svg

def test_default_ac0812_uses_height_based_circle_radius() -> None:
    """AC0812 should size its circle from height so tiny variants don't shrink."""
    params = Action._default_ac0812_params(25, 15)

    assert abs(float(params["r"]) - 6.0) < 1e-6
    assert abs(float(params["cx"]) - 17.5) < 1e-6
    assert abs(float(params["arm_x2"]) - 11.5) < 1e-6


def test_validate_badge_can_expand_ac0812_tiny_circle_radius() -> None:
    """Element validation should actively correct a too-small AC0812_S circle radius."""
    img_path = Path("artifacts/images_to_convert/AC0812_S.jpg")
    cv2 = pytest.importorskip("cv2")
    img = cv2.imread(str(img_path))
    if img is None:
        pytest.skip("AC0812_S fixture image not available")

    h, w = img.shape[:2]
    params = Action._finalize_ac08_style("AC0812", Action._default_ac0812_params(w, h))
    params["r"] = 5.0
    params["arm_x2"] = max(0.0, float(params["cx"]) - float(params["r"]))

    logs = Action.validate_badge_by_elements(img, params, max_rounds=2)

    assert float(params["r"]) > 5.0
    assert any("Radius-Bracketing r" in line for line in logs)


def test_validate_badge_logs_extent_bracketing_for_line_elements() -> None:
    """Validation should include explicit extent/length optimization for arm/stem elements."""
    img_path = Path("artifacts/images_to_convert/AC0812_S.jpg")
    cv2 = pytest.importorskip("cv2")
    img = cv2.imread(str(img_path))
    if img is None:
        pytest.skip("AC0812_S fixture image not available")

    h, w = img.shape[:2]
    params = Action._finalize_ac08_style("AC0812", Action._default_ac0812_params(w, h))
    logs = Action.validate_badge_by_elements(img, params, max_rounds=1)

    assert any("arm: Längen-Bracketing" in line for line in logs)




def test_optimize_circle_radius_keeps_ac0813_vertical_arm_orientation() -> None:
    """AC0813 radius optimization must not collapse the vertical arm into a horizontal one."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (25, 15, 3)

    img = DummyImg()
    params = Action._default_ac0813_params(15, 25)
    params = Action._finalize_ac08_style("AC0813", params)
    logs: list[str] = []

    original = Action._element_error_for_circle_radius

    def prefer_smallest_radius(_img: object, _params: dict, radius_value: float) -> float:
        return float(radius_value)

    Action._element_error_for_circle_radius = staticmethod(prefer_smallest_radius)
    try:
        changed = Action._optimize_circle_radius_bracket(img, params, logs)
    finally:
        Action._element_error_for_circle_radius = original

    assert changed is True
    assert abs(float(params["arm_x1"]) - float(params["arm_x2"])) < 1e-6
    assert float(params["arm_y1"]) < float(params["arm_y2"])
    assert abs(float(params["arm_y2"]) - (float(params["cy"]) - float(params["r"]))) < 1e-6

def test_tiny_circle_radius_bracketing_limits_downscale() -> None:
    """Tiny symbols should not shrink circle radius by more than 10% in one step."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")
    class DummyImg:
        shape = (15, 15, 3)

    img = DummyImg()
    params = {
        "circle_enabled": True,
        "r": 5.0,
    }
    logs: list[str] = []

    original = Action._element_error_for_circle_radius

    def prefer_smallest_radius(_img: object, _params: dict, radius_value: float) -> float:
        return float(radius_value)

    Action._element_error_for_circle_radius = staticmethod(prefer_smallest_radius)
    try:
        changed = Action._optimize_circle_radius_bracket(img, params, logs)
    finally:
        Action._element_error_for_circle_radius = original

    assert changed is True
    assert abs(float(params["r"]) - 4.5) < 1e-6
    assert any("Radius-Bracketing" in line for line in logs)


def test_voc_font_scale_bounds_allow_larger_tiny_badge_labels() -> None:
    """Tiny VOC badges should allow expanding text scale beyond the historic cap."""
    params = {
        "draw_text": True,
        "text_mode": "voc",
        "voc_font_scale": 0.52,
    }

    info = Action._element_width_key_and_bounds("text", params, 15, 15)

    assert info is not None
    key, low, high = info
    assert key == "voc_font_scale"
    assert low <= 0.45
    assert high >= 1.60




def test_optimize_arm_extent_keeps_circle_side_anchor_for_horizontal_connectors() -> None:
    """Arm length optimization should keep the circle-side endpoint fixed for AC0812-like arms."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (15, 25, 3)

    img = DummyImg()
    params = Action._default_ac0812_params(25, 15)
    params = Action._finalize_ac08_style("AC0812", params)

    # Intentionally shrink the free-side arm to emulate under-length conversion output.
    params["arm_x1"] = float(params["arm_x2"] - 3.0)

    logs: list[str] = []
    original = Action._element_error_for_extent

    def prefer_longer(_img: object, _params: dict, _element: str, extent_value: float) -> float:
        return abs(float(extent_value) - 10.0)

    Action._element_error_for_extent = staticmethod(prefer_longer)
    try:
        changed = Action._optimize_element_extent_bracket(img, params, "arm", logs)
    finally:
        Action._element_error_for_extent = original

    assert changed is True
    assert abs(float(params["arm_x2"]) - (float(params["cx"]) - float(params["r"]))) < 1e-6
    assert float(params["arm_x1"]) < float(params["arm_x2"])
    assert any("arm: Längen-Bracketing" in line for line in logs)


def test_optimize_stem_extent_keeps_circle_side_anchor() -> None:
    """Stem length optimization should keep stem_top attached to the circle edge."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (25, 15, 3)

    img = DummyImg()
    params = Action._default_ac0811_params(15, 25)
    params = Action._finalize_ac08_style("AC0811", params)
    params["stem_top"] = float(params["cy"] + params["r"] + 2.0)

    logs: list[str] = []
    original = Action._element_error_for_extent

    def prefer_longer(_img: object, _params: dict, _element: str, extent_value: float) -> float:
        return abs(float(extent_value) - 12.0)

    Action._element_error_for_extent = staticmethod(prefer_longer)
    try:
        changed = Action._optimize_element_extent_bracket(img, params, "stem", logs)
    finally:
        Action._element_error_for_extent = original

    assert changed is True
    assert abs(float(params["stem_top"]) - (float(params["cy"]) + float(params["r"]))) < 1e-6
    assert float(params["stem_bottom"]) > float(params["stem_top"])
    assert any("stem: Längen-Bracketing" in line for line in logs)

def test_text_width_bracketing_keeps_fractional_font_scale_precision() -> None:
    """Text scale optimization should not quantize font scale to half-pixel steps."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (30, 30, 3)

    img = DummyImg()
    params = {
        "draw_text": True,
        "text_mode": "voc",
        "voc_font_scale": 0.52,
    }
    logs: list[str] = []

    original = Action._element_error_for_width

    def prefer_target_scale(_img: object, _params: dict, _element: str, width_value: float) -> float:
        return abs(float(width_value) - 0.85)

    Action._element_error_for_width = staticmethod(prefer_target_scale)
    try:
        changed = Action._optimize_element_width_bracket(img, params, "text", logs)
    finally:
        Action._element_error_for_width = original

    assert changed is True
    assert abs(float(params["voc_font_scale"]) - 0.85) < 1e-6
    assert any("Breiten-Bracketing" in line for line in logs)
