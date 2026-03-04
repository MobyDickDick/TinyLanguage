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


def test_finalize_ac0820_locks_plain_circle_center_and_min_radius() -> None:
    """Plain AC0820 badges should keep a centered ring and preserve readable radius."""
    params = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    params = Action._finalize_ac08_style("AC0820", params)

    assert params["lock_circle_cx"] is True
    assert params["lock_circle_cy"] is True
    assert float(params["min_circle_radius"]) >= float(params["r"]) * 0.88


def test_finalize_ac0820_min_circle_radius_uses_template_baseline() -> None:
    """Radius floor should be anchored to template size, not a shrunken interim fit."""
    params = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    params["template_circle_radius"] = float(params["r"])
    params["r"] = 3.0

    params = Action._finalize_ac08_style("AC0820", params)

    assert float(params["min_circle_radius"]) >= float(params["template_circle_radius"]) * 0.92


def test_finalize_non_ac0820_text_badge_uses_less_strict_radius_floor() -> None:
    """Non-AC0820 text badges should preserve the previous 90%-template floor."""
    params = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    params["template_circle_radius"] = float(params["r"])
    params["r"] = 3.0

    params = Action._finalize_ac08_style("AC0831", params)

    assert float(params["min_circle_radius"]) >= float(params["template_circle_radius"]) * 0.90


def test_finalize_plain_ac08_badge_reanchors_circle_to_template_center() -> None:
    """Plain AC08xx badges should lock to template circle center, not drifted fit center."""
    params = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    params["template_circle_cx"] = 9.5
    params["template_circle_cy"] = 9.5
    params["cx"] = 8.0
    params["cy"] = 7.0

    params = Action._finalize_ac08_style("AC0820_M", params)

    assert float(params["cx"]) == 9.5
    assert float(params["cy"]) == 9.5


def test_fit_semantic_badge_records_template_center_for_finalize_locking() -> None:
    """Semantic fit should persist template center so finalize can restore canonical centering."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    img = np.full((20, 20, 3), 240, dtype=np.uint8)
    defaults = Action._default_ac0870_params(20, 20)

    params = Action._fit_semantic_badge_from_image(img, defaults)

    assert float(params["template_circle_cx"]) == float(defaults["cx"])
    assert float(params["template_circle_cy"]) == float(defaults["cy"])
def test_fit_semantic_badge_prevents_over_shrinking_plain_text_badge_circle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Circle fitting should keep a minimum template-relative radius for plain text badges."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    cv2 = image_composite_converter.cv2
    img = np.full((20, 20, 3), 220, dtype=np.uint8)

    defaults = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    default_r = float(defaults["r"])

    monkeypatch.setattr(
        cv2,
        "HoughCircles",
        lambda *_args, **_kwargs: np.array([[[10.0, 10.0, 2.0]]], dtype=np.float32),
    )

    fitted = Action._fit_semantic_badge_from_image(img, defaults)

    assert float(fitted["r"]) >= (default_r * 0.92) - 1e-6


def test_fit_semantic_badge_allows_lower_floor_when_connector_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connector badges should use a looser minimum-ratio floor than plain centered badges."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    cv2 = image_composite_converter.cv2
    img = np.full((20, 20, 3), 220, dtype=np.uint8)

    defaults = {
        "cx": 10.0,
        "cy": 10.0,
        "r": 6.0,
        "stroke_circle": 1.0,
        "fill_gray": 220,
        "stroke_gray": 152,
        "draw_text": False,
        "arm_enabled": True,
        "arm_x1": 1.0,
        "arm_y1": 10.0,
        "arm_x2": 4.0,
        "arm_y2": 10.0,
    }

    monkeypatch.setattr(
        cv2,
        "HoughCircles",
        lambda *_args, **_kwargs: np.array([[[10.0, 10.0, 2.0]]], dtype=np.float32),
    )

    fitted = Action._fit_semantic_badge_from_image(img, defaults)

    assert float(fitted["r"]) >= (float(defaults["r"]) * 0.80) - 1e-6


def test_fit_semantic_badge_rejects_far_off_hough_center_for_ac08_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hough candidates far from template center should not override semantic circle placement."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    cv2 = image_composite_converter.cv2
    img = np.full((15, 25, 3), 220, dtype=np.uint8)

    defaults = Action._default_ac0812_params(25, 15)

    monkeypatch.setattr(
        cv2,
        "HoughCircles",
        lambda *_args, **_kwargs: np.array([[[6.0, 9.0, 4.4]]], dtype=np.float32),
    )

    fitted = Action._fit_semantic_badge_from_image(img, defaults)

    assert abs(float(fitted["cx"]) - float(defaults["cx"])) <= 1e-6
    assert abs(float(fitted["cy"]) - float(defaults["cy"])) <= 1e-6


def test_fit_semantic_badge_keeps_near_template_hough_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """A near-template Hough hit should still be accepted and applied."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    cv2 = image_composite_converter.cv2
    img = np.full((15, 25, 3), 220, dtype=np.uint8)

    defaults = Action._default_ac0812_params(25, 15)

    monkeypatch.setattr(
        cv2,
        "HoughCircles",
        lambda *_args, **_kwargs: np.array([[[17.4, 7.3, 5.2]]], dtype=np.float32),
    )

    fitted = Action._fit_semantic_badge_from_image(img, defaults)

    assert abs(float(fitted["cx"]) - 17.4) < 1e-6
    assert abs(float(fitted["cy"]) - 7.3) < 1e-6
    assert abs(float(fitted["r"]) - 5.2) < 1e-6


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


def test_finalize_ac0820_keeps_text_scale_tunable_with_bounds() -> None:
    """AC0820 should allow bounded CO₂ scale tuning during validation rounds."""
    params = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    params = Action._finalize_ac08_style("AC0820", params)

    assert params["lock_text_scale"] is False
    assert float(params["co2_font_scale_min"]) < float(params["co2_font_scale"])
    assert float(params["co2_font_scale_max"]) > float(params["co2_font_scale"])


def test_finalize_non_ac0820_co2_keeps_text_scale_locked() -> None:
    """Non-AC0820 CO₂ badges should keep fixed text scale to avoid drift."""
    params = Action._apply_co2_label(Action._default_ac0881_params(20, 20))
    params = Action._finalize_ac08_style("AC0831", params)

    assert params["lock_text_scale"] is True

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
    cv2 = pytest.importorskip("cv2", exc_type=ImportError)
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
    cv2 = pytest.importorskip("cv2", exc_type=ImportError)
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


def test_circle_radius_bracketing_respects_configured_min_radius() -> None:
    """Radius optimization must not shrink below per-symbol min radius floors."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (20, 20, 3)

    img = DummyImg()
    params = {
        "circle_enabled": True,
        "r": 8.0,
        "min_circle_radius": 7.0,
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
    assert float(params["r"]) >= 7.0
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


def test_voc_font_scale_bounds_limit_growth_for_large_badges() -> None:
    """Large VOC badges should avoid overscaling text during width bracketing."""
    params = {
        "draw_text": True,
        "text_mode": "voc",
        "voc_font_scale": 0.52,
    }

    info = Action._element_width_key_and_bounds("text", params, 45, 25)

    assert info is not None
    key, low, high = info
    assert key == "voc_font_scale"
    assert low <= 0.45
    assert high <= 1.10


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


def test_co2_layout_prioritizes_co_alignment_before_subscript_shift() -> None:
    """Centered CO should stay near the circle center even when subscript space is tight."""
    params = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    params = Action._finalize_ac08_style("AC0820_M", params)
    params["co2_sub_font_scale"] = 130.0

    layout = Action._co2_layout(params)

    assert abs(float(layout["co_x"]) - float(params["cx"])) <= 0.20


def test_co2_layout_can_shrink_subscript_before_moving_co() -> None:
    """When space is tight, subscript should shrink to preserve CO placement first."""
    params = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    params = Action._finalize_ac08_style("AC0820_M", params)
    params["co2_sub_font_scale"] = 160.0

    requested_sub_font_px = max(4.0, float(params["r"]) * float(params["co2_font_scale"]) * (float(params["co2_sub_font_scale"]) / 100.0))
    layout = Action._co2_layout(params)

    assert float(layout["sub_font_px"]) < requested_sub_font_px

def test_co2_layout_caps_font_size_to_inner_circle_ratio() -> None:
    """CO font size must stay proportionate even for inflated co2_font_scale values."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820_L", params)
    params["co2_font_scale"] = 1.50
    layout = Action._co2_layout(params)

    r = float(params["r"])
    stroke = float(params["stroke_circle"])
    inner_diameter = (2.0 * r) - stroke
    assert float(layout["font_size"]) <= (inner_diameter * 0.50) + 1e-6


def test_co2_text_width_bracketing_is_bounded_for_ac0820() -> None:
    """AC0820 CO₂ badges should allow bounded text tuning during width bracketing."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820", params)

    key, low, high = Action._element_width_key_and_bounds("text", params, 30, 30)
    assert key == "co2_font_scale"
    assert float(low) <= float(params["co2_font_scale"]) <= float(high)
    assert float(low) >= float(params["co2_font_scale_min"]) - 1e-9
    assert float(high) <= float(params["co2_font_scale_max"]) + 1e-9


def test_finalize_ac0820_locks_palette_against_color_bracketing() -> None:
    """AC08xx semantic badges should keep canonical fill/stroke grayscale values."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820", params)

    assert params["lock_colors"] is True


def test_optimize_element_color_bracket_skips_when_colors_locked() -> None:
    """Color tuning must be skipped when lock_colors is enabled."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    mask = np.ones((8, 8), dtype=np.uint8)
    params = {
        "circle_enabled": True,
        "fill_gray": 242,
        "stroke_gray": 127,
        "lock_colors": True,
    }
    logs: list[str] = []

    changed = Action._optimize_element_color_bracket(img, params, "circle", mask, logs)

    assert changed is False
    assert any("Farben gesperrt" in line for line in logs)

def test_validate_badge_runs_color_bracketing_after_geometry_steps() -> None:
    """Validation should optimize color only after extent/radius geometry updates."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np

    class DummyImg:
        shape = (15, 15, 3)

    img = DummyImg()
    params = {"circle_enabled": True, "draw_text": False}
    call_order: list[str] = []

    original_generate_badge_svg = Action.generate_badge_svg
    original_render_svg_to_numpy = Action.render_svg_to_numpy
    original_fit_to_original_size = Action._fit_to_original_size
    original_extract_badge_element_mask = Action.extract_badge_element_mask
    original_mask_min_rect_center_diag = Action._mask_min_rect_center_diag
    original_masked_error = Action._masked_error
    original_calculate_error = Action.calculate_error
    original_width = Action._optimize_element_width_bracket
    original_extent = Action._optimize_element_extent_bracket
    original_center = Action._optimize_circle_center_bracket
    original_radius = Action._optimize_circle_radius_bracket
    original_joint = Action._optimize_circle_pose_multistart
    original_color = Action._optimize_element_color_bracket

    Action.generate_badge_svg = staticmethod(lambda _w, _h, _params: "<svg/>")
    Action.render_svg_to_numpy = staticmethod(lambda _svg, w, h: np.zeros((h, w, 3), dtype=np.uint8))
    Action._fit_to_original_size = staticmethod(lambda _orig, render: render)
    Action.extract_badge_element_mask = staticmethod(lambda _img, _params, _element: np.ones((15, 15), dtype=np.uint8))
    Action._mask_min_rect_center_diag = staticmethod(lambda _mask: None)
    Action._masked_error = staticmethod(lambda _orig, _render, _mask: 0.0)
    Action.calculate_error = staticmethod(lambda _orig, _render: 0.0)

    Action._optimize_element_width_bracket = staticmethod(
        lambda _img, _params, _element, _logs: call_order.append("width") or False
    )
    Action._optimize_element_extent_bracket = staticmethod(
        lambda _img, _params, _element, _logs: call_order.append("extent") or False
    )
    Action._optimize_circle_center_bracket = staticmethod(
        lambda _img, _params, _logs: call_order.append("center") or False
    )
    Action._optimize_circle_radius_bracket = staticmethod(
        lambda _img, _params, _logs: call_order.append("radius") or False
    )
    Action._optimize_circle_pose_multistart = staticmethod(
        lambda _img, _params, _logs: call_order.append("joint") or False
    )
    Action._optimize_element_color_bracket = staticmethod(
        lambda _img, _params, _element, _mask, _logs: call_order.append("color") or False
    )

    try:
        Action.validate_badge_by_elements(img, params, max_rounds=1)
    finally:
        Action.generate_badge_svg = original_generate_badge_svg
        Action.render_svg_to_numpy = original_render_svg_to_numpy
        Action._fit_to_original_size = original_fit_to_original_size
        Action.extract_badge_element_mask = original_extract_badge_element_mask
        Action._mask_min_rect_center_diag = original_mask_min_rect_center_diag
        Action._masked_error = original_masked_error
        Action.calculate_error = original_calculate_error
        Action._optimize_element_width_bracket = original_width
        Action._optimize_element_extent_bracket = original_extent
        Action._optimize_circle_center_bracket = original_center
        Action._optimize_circle_radius_bracket = original_radius
        Action._optimize_circle_pose_multistart = original_joint
        Action._optimize_element_color_bracket = original_color

    assert call_order == ["width", "extent", "center", "radius", "joint", "color"]


def test_optimize_circle_pose_multistart_can_escape_local_center_radius_plateau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Joint circle pose search should improve cx/cy/r together when independent steps stall."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    params = {
        "circle_enabled": True,
        "cx": 10.0,
        "cy": 10.0,
        "r": 6.0,
        "min_circle_radius": 4.0,
    }
    logs: list[str] = []

    def fake_error(_img, _params, *, cx_value: float, cy_value: float, radius_value: float) -> float:
        return ((cx_value - 11.0) ** 2) + ((cy_value - 9.0) ** 2) + ((radius_value - 6.5) ** 2)

    monkeypatch.setattr(Action, "_element_error_for_circle_pose", staticmethod(fake_error))

    changed = Action._optimize_circle_pose_multistart(img, params, logs)

    assert changed is True
    assert float(params["cx"]) == 11.0
    assert float(params["cy"]) == 9.0
    assert float(params["r"]) == 6.5
    assert any("Joint-Multistart" in line for line in logs)
