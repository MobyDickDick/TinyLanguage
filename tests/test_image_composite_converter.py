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


def test_finalize_ac0820_uses_cluster_anchor_mode() -> None:
    """AC0820 should center the full CO₂ cluster horizontally."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820", params)

    assert params["co2_anchor_mode"] == "cluster"


def test_finalize_ac0820_variant_name_uses_cluster_anchor_mode() -> None:
    """AC0820 variant names (e.g. AC0820_L) should center the full CO₂ label."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820_L", params)

    assert params["co2_anchor_mode"] == "cluster"
    assert float(params["co2_optical_bias"]) >= 0.125


def test_parse_semantic_badge_layout_overrides_centers_full_co2_cluster() -> None:
    """Horizontal centering directive should target the full CO₂ cluster."""
    overrides = image_composite_converter.Reflection._parse_semantic_badge_layout_overrides(
        "CO_2 bezüglich des Kreises horizontal zentriert"
    )

    assert overrides["co2_anchor_mode"] == "cluster"
    assert float(overrides["co2_dx"]) == 0.0


def test_parse_description_marks_ac0833_with_right_horizontal_arm() -> None:
    """AC0833 belongs to the right-arm CO₂ family and must include that semantic element."""
    ref = image_composite_converter.Reflection({})

    _desc, params = ref.parse_description("AC0833", "AC0833_S.jpg")

    assert "SEMANTIC: waagrechter Strich rechts vom Kreis" in list(params.get("elements", []))


def test_parse_description_marks_ac0838_with_right_horizontal_arm() -> None:
    """AC0838 belongs to the right-arm VOC family and must include that semantic element."""
    ref = image_composite_converter.Reflection({})

    _desc, params = ref.parse_description("AC0838", "AC0838_L.jpg")

    assert "SEMANTIC: waagrechter Strich rechts vom Kreis" in list(params.get("elements", []))


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


def test_quantize_clamps_circle_radius_to_canvas_bounds() -> None:
    """Quantization should keep the full ring inside the viewport."""
    params = {
        "circle_enabled": True,
        "cx": 32.5,
        "cy": 12.5,
        "r": 15.0,
        "stroke_circle": 1.0,
    }

    quantized = Action._quantize_badge_params(params, w=45, h=25)

    assert float(quantized["r"]) <= 12.0 + 1e-6


def test_circle_bounds_respect_canvas_for_locked_center() -> None:
    """Circle optimization bounds must not permit radii outside canvas limits."""
    params = {
        "cx": 32.5,
        "cy": 12.5,
        "stroke_circle": 1.0,
        "min_circle_radius": 1.0,
    }

    _x_low, _x_high, _y_low, _y_high, _r_low, r_high = Action._circle_bounds(params, w=45, h=25)

    assert float(r_high) <= 12.0 + 1e-6


def test_fit_ac0812_does_not_cap_radius_to_too_small_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC0812 fitting should allow radius growth above small defaults when image fit supports it."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.full((25, 45, 3), 240, dtype=np.uint8)
    defaults = Action._default_ac0812_params(45, 25)

    def fake_fit(_img, _defaults):
        return {
            **_defaults,
            "cx": 32.5,
            "cy": 12.5,
            "r": 12.0,
            "stroke_circle": 1.0,
            "draw_text": False,
            "arm_enabled": True,
        }

    monkeypatch.setattr(Action, "_fit_semantic_badge_from_image", staticmethod(fake_fit))

    fitted = Action._fit_ac0812_params_from_image(img, defaults)

    assert float(fitted["r"]) >= 11.5
    assert float(fitted["max_circle_radius"]) >= 11.5


def test_finalize_ac0820_increases_optical_bias_for_co_vertical_centering() -> None:
    """AC0820 should nudge CO down so the main run appears vertically centered in-circle."""
    params = Action._apply_co2_label(Action._default_ac0870_params(30, 30))
    params = Action._finalize_ac08_style("AC0820", params)
    layout = Action._co2_layout(params)

    assert float(layout["y_base"]) > float(params["cy"])


def test_run_iteration_pipeline_element_validation_log_contains_run_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Element validation logs should always include run metadata per execution."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    cv2 = image_composite_converter.cv2

    img = np.full((12, 20, 3), 240, dtype=np.uint8)
    img_path = tmp_path / "AC0812_L.jpg"
    csv_path = tmp_path / "data.csv"
    svg_dir = tmp_path / "svg"
    diff_dir = tmp_path / "diff"
    reports_dir = tmp_path / "reports"
    csv_path.write_text("Wurzelform;Beschreibung\nAC0812;semantic\n", encoding="utf-8")
    assert cv2.imwrite(str(img_path), img)

    monkeypatch.setattr(
        image_composite_converter.Reflection,
        "parse_description",
        lambda *_args, **_kwargs: (
            "semantic",
            {"mode": "semantic_badge", "elements": ["SEMANTIC: test"], "label": ""},
        ),
    )
    monkeypatch.setattr(
        image_composite_converter.Action,
        "make_badge_params",
        staticmethod(lambda *_args, **_kwargs: image_composite_converter.Action._default_ac0812_params(20, 12)),
    )
    monkeypatch.setattr(
        image_composite_converter.Action,
        "validate_semantic_description_alignment",
        staticmethod(lambda *_args, **_kwargs: []),
    )
    monkeypatch.setattr(
        image_composite_converter.Action,
        "validate_badge_by_elements",
        staticmethod(lambda *_args, **_kwargs: ["ok: element pass"]),
    )
    monkeypatch.setattr(
        image_composite_converter.Action,
        "_enforce_semantic_connector_expectation",
        staticmethod(lambda _base, _elements, p, _w, _h: p),
    )
    monkeypatch.setattr(
        image_composite_converter.Action,
        "generate_badge_svg",
        staticmethod(lambda w, h, _p: f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"/>'),
    )
    monkeypatch.setattr(
        image_composite_converter.Action,
        "render_svg_to_numpy",
        staticmethod(lambda _svg, w, h: np.full((h, w, 3), 240, dtype=np.uint8)),
    )
    monkeypatch.setattr(
        image_composite_converter.Action,
        "create_diff_image",
        staticmethod(lambda a, _b: a.copy()),
    )

    image_composite_converter.Action.STOCHASTIC_RUN_SEED = 123
    image_composite_converter.Action.STOCHASTIC_SEED_OFFSET = 7
    res = image_composite_converter.run_iteration_pipeline(
        str(img_path),
        str(csv_path),
        2,
        str(svg_dir),
        str(diff_dir),
        str(reports_dir),
    )
    assert res is not None

    log_file = reports_dir / "AC0812_L_element_validation.log"
    assert log_file.exists()
    first_line = log_file.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("run-meta: ")
    assert "run_seed=123" in first_line
    assert "pass_seed_offset=7" in first_line
    assert "nonce_ns=" in first_line


def test_convert_range_does_not_skip_variants_in_quality_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global quality passes should keep all variants eligible (no per-variant skip lock)."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    cv2 = image_composite_converter.cv2

    images_dir = tmp_path / "images"
    images_dir.mkdir()
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Wurzelform;Beschreibung\nAC0812;semantic\n", encoding="utf-8")
    for name in ("AC0812_L.jpg", "AC0812_M.jpg"):
        assert cv2.imwrite(str(images_dir / name), np.full((10, 10, 3), 230, dtype=np.uint8))

    monkeypatch.setattr(image_composite_converter, "_in_requested_range", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(image_composite_converter, "_load_quality_config", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(image_composite_converter, "_write_quality_pass_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(image_composite_converter, "_harmonize_semantic_size_variants", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(image_composite_converter, "_write_pixel_delta2_ranking", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(image_composite_converter, "_default_converted_symbols_root", lambda: str(tmp_path / "out"))

    def fake_pipeline(img_path: str, *_args, **_kwargs):
        stem = Path(img_path).stem
        params = {"mode": "semantic_badge", "cx": 5.0, "cy": 5.0, "r": 3.0}
        return stem, "semantic", params, 1, 100.0

    monkeypatch.setattr(image_composite_converter, "run_iteration_pipeline", fake_pipeline)

    captured_cfg: dict[str, object] = {}

    def capture_quality_cfg(_reports_out_dir: str, *, allowed_error_per_pixel: float, skipped_variants: list[str], source: str) -> None:
        captured_cfg["allowed_error_per_pixel"] = allowed_error_per_pixel
        captured_cfg["skipped_variants"] = list(skipped_variants)
        captured_cfg["source"] = source

    monkeypatch.setattr(image_composite_converter, "_write_quality_config", capture_quality_cfg)

    observed_skips: list[set[str]] = []

    def capture_open_cases(rows, allowed_error_per_pixel, skip_variants=None):
        observed_skips.append(set(skip_variants or set()))
        return []

    monkeypatch.setattr(image_composite_converter, "_select_open_quality_cases", capture_open_cases)
    monkeypatch.setattr(image_composite_converter, "_select_middle_lower_tercile", lambda _rows: [])

    image_composite_converter.convert_range(str(images_dir), str(csv_path), iterations=2, start_ref="AC0812", end_ref="AC0812")

    assert captured_cfg["skipped_variants"] == []
    assert observed_skips
    assert all(not skip_set for skip_set in observed_skips)


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


def test_optimize_circle_pose_adaptive_domain_improves_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adaptive domain search should improve pose and report boundary/plateau hints."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.full((20, 20, 3), 220, dtype=np.uint8)
    params = {
        "circle_enabled": True,
        "cx": 3.0,
        "cy": 3.0,
        "r": 2.0,
        "min_circle_radius": 1.0,
    }

    def fake_error(_img: object, _params: dict, *, cx_value: float, cy_value: float, radius_value: float) -> float:
        return float((cx_value - 9.0) ** 2 + (cy_value - 10.0) ** 2 + (radius_value - 5.0) ** 2)

    monkeypatch.setattr(Action, "_element_error_for_circle_pose", staticmethod(fake_error))
    logs: list[str] = []

    changed = Action._optimize_circle_pose_adaptive_domain(img, params, logs, rounds=3, samples_per_round=14)

    assert changed is True
    assert abs(float(params["cx"]) - 9.0) <= 3.0
    assert abs(float(params["cy"]) - 10.0) <= 3.0
    assert abs(float(params["r"]) - 5.0) <= 2.0
    assert any("Adaptive-Domain-Suche übernommen" in line for line in logs)


def test_optimize_circle_pose_adaptive_domain_uses_run_seed_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adaptive domain RNG should incorporate run-seed and pass offset."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.full((20, 20, 3), 220, dtype=np.uint8)
    params = {
        "circle_enabled": True,
        "cx": 9.0,
        "cy": 10.0,
        "r": 5.0,
        "min_circle_radius": 1.0,
    }

    captured: list[int] = []

    class _DummyRng:
        def uniform(self, low: float, high: float) -> float:
            return float((low + high) / 2.0)

    monkeypatch.setattr(Action, "_element_error_for_circle_pose", staticmethod(lambda *_args, **_kwargs: 1.0))

    original_default_rng = np.random.default_rng

    def fake_default_rng(seed: int):
        captured.append(int(seed))
        return _DummyRng()

    monkeypatch.setattr(np.random, "default_rng", fake_default_rng)
    logs: list[str] = []

    Action.STOCHASTIC_RUN_SEED = 41
    Action.STOCHASTIC_SEED_OFFSET = 2
    try:
        Action._optimize_circle_pose_adaptive_domain(img, params, logs, rounds=1, samples_per_round=8)
    finally:
        Action.STOCHASTIC_RUN_SEED = 0
        Action.STOCHASTIC_SEED_OFFSET = 0
        np.random.default_rng = original_default_rng

    assert captured
    assert captured[0] == 2027 + 41 + 2


def test_optimize_circle_pose_adaptive_domain_no_improvement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adaptive domain search should return False when no better sample exists."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.full((20, 20, 3), 220, dtype=np.uint8)
    params = {
        "circle_enabled": True,
        "cx": 9.0,
        "cy": 10.0,
        "r": 5.0,
        "min_circle_radius": 1.0,
    }

    monkeypatch.setattr(
        Action,
        "_element_error_for_circle_pose",
        staticmethod(lambda *_args, **_kwargs: 1.0),
    )
    logs: list[str] = []

    changed = Action._optimize_circle_pose_adaptive_domain(img, params, logs, rounds=2, samples_per_round=10)

    assert changed is False
    assert any("keine relevante Verbesserung" in line for line in logs)


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


def test_finalize_tiny_non_ac0820_co2_unlocks_bounded_text_tuning() -> None:
    """Tiny CO₂ variants should allow bounded text tuning across AC08xx families."""
    params = Action._apply_co2_label(Action._default_ac0813_params(15, 25))
    params = Action._finalize_ac08_style("AC0833_S", params)

    assert params["lock_text_scale"] is False
    assert float(params["co2_font_scale_min"]) < float(params["co2_font_scale"])
    assert float(params["co2_font_scale_max"]) > float(params["co2_font_scale"])

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



def test_make_badge_params_ac0812_family_keeps_left_arm_without_image_fit() -> None:
    """AC0812-family semantic defaults must always preserve a visible left connector."""
    for name in ("AC0812", "AC0882", "AC0832", "AC0837"):
        params = Action.make_badge_params(45, 25, name, img=None)
        assert params is not None
        assert params.get("arm_enabled") is True
        assert abs(float(params["arm_y1"]) - float(params["cy"])) < 1e-6
        assert abs(float(params["arm_y2"]) - float(params["cy"])) < 1e-6
        assert float(params["arm_x1"]) == 0.0
        assert float(params["arm_x2"]) > 0.0
        assert float(params.get("arm_len_min", 0.0)) >= float(params["arm_x2"]) * float(params.get("arm_len_min_ratio", 0.75))


def test_enforce_left_arm_badge_geometry_restores_missing_arm() -> None:
    """Left-arm enforcement should recover connector geometry from circle-only params."""
    params = {"cx": 32.5, "cy": 12.5, "r": 10.0, "circle_enabled": True}

    fixed = Action._enforce_left_arm_badge_geometry(params, 45, 25)

    assert fixed.get("arm_enabled") is True
    assert float(fixed["arm_x1"]) == 0.0
    assert abs(float(fixed["arm_y1"]) - 12.5) < 1e-6
    assert abs(float(fixed["arm_x2"]) - 22.5) < 1e-6
    assert abs(float(fixed["arm_y2"]) - 12.5) < 1e-6
    assert float(fixed["arm_len_min"]) >= 22.5 * 0.75


def test_default_ac0812_uses_height_based_circle_radius() -> None:
    """AC0812 should size its circle from height without overfilling the frame."""
    params = Action._default_ac0812_params(25, 15)

    assert abs(float(params["r"]) - 5.4) < 1e-6
    assert abs(float(params["cx"]) - 17.5) < 1e-6
    assert abs(float(params["arm_x2"]) - 12.1) < 1e-6


def test_fit_ac0812_caps_radius_to_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC0812 fit should not allow radius growth above semantic template."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    monkeypatch.setattr(
        Action,
        "_fit_semantic_badge_from_image",
        staticmethod(
            lambda _img, defaults: {
                **defaults,
                "cx": float(defaults["cx"]),
                "cy": float(defaults["cy"]),
                "r": float(defaults["r"]) * 1.8,
                "arm_enabled": True,
                "draw_text": False,
            }
        ),
    )

    class DummyImg:
        shape = (15, 25, 3)

    defaults = Action._default_ac0812_params(25, 15)
    fitted = Action._fit_ac0812_params_from_image(DummyImg(), defaults)

    assert float(fitted["r"]) <= float(defaults["r"]) + 1e-6


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


def test_element_error_for_circle_radius_uses_expanded_source_mask_for_growth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Circle growth probes should evaluate against an equally expanded source mask."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.zeros((25, 45, 3), dtype=np.uint8)
    params = Action._finalize_ac08_style("AC0812", Action._default_ac0812_params(45, 25))

    recorded_source_radii: list[float] = []

    monkeypatch.setattr(Action, "generate_badge_svg", staticmethod(lambda _w, _h, _p: "<svg/>"))
    monkeypatch.setattr(Action, "render_svg_to_numpy", staticmethod(lambda _svg, w, h: np.zeros((h, w, 3), dtype=np.uint8)))
    monkeypatch.setattr(Action, "_fit_to_original_size", staticmethod(lambda _orig, rendered: rendered))
    monkeypatch.setattr(Action, "_element_match_error", staticmethod(lambda *_args, **_kwargs: 0.0))

    def fake_mask(_img: object, mask_params: dict, _element: str):
        if mask_params is not params:
            recorded_source_radii.append(float(mask_params.get("r", 0.0)))
        return np.ones((25, 45), dtype=bool)

    monkeypatch.setattr(Action, "extract_badge_element_mask", staticmethod(fake_mask))

    start_r = float(params["r"])
    probe_r = start_r + 2.0
    err = Action._element_error_for_circle_radius(img, params, probe_r)

    assert err == 0.0
    assert recorded_source_radii
    assert max(recorded_source_radii) >= probe_r




def test_tune_ac0834_co2_badge_recenters_tiny_variant_and_locks_strokes() -> None:
    """AC0834_S tuning should keep the badge centered and connector geometry stable."""
    params = Action._apply_co2_label(Action._default_ac0814_params(25, 15))
    params["cy"] = 10.0
    params["r"] = 5.0
    params["stroke_circle"] = 1.7
    params["arm_stroke"] = 1.6

    tuned = Action._tune_ac0834_co2_badge(params, 25, 15)

    assert abs(float(tuned["cy"]) - 7.5) < 1e-6
    assert abs(float(tuned["arm_y1"]) - float(tuned["cy"])) < 1e-6
    assert abs(float(tuned["arm_y2"]) - float(tuned["cy"])) < 1e-6
    assert float(tuned["arm_x2"]) == 25.0
    assert float(tuned["stroke_circle"]) == Action.AC08_STROKE_WIDTH_PX
    assert float(tuned["arm_stroke"]) == Action.AC08_STROKE_WIDTH_PX

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



def test_circle_error_uses_stable_source_mask_for_radius_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Circle radius scoring should keep the source mask tied to current params."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (20, 20, 3)

    img = DummyImg()
    params = {
        "circle_enabled": True,
        "r": 8.0,
        "cx": 10.0,
        "cy": 10.0,
    }

    monkeypatch.setattr(Action, "generate_badge_svg", staticmethod(lambda *_args, **_kwargs: "<svg />"))
    monkeypatch.setattr(Action, "render_svg_to_numpy", staticmethod(lambda *_args, **_kwargs: object()))
    monkeypatch.setattr(Action, "_fit_to_original_size", staticmethod(lambda _img, rendered: rendered))

    calls: list[dict] = []

    def fake_extract(_img: object, mask_params: dict, _element: str):
        calls.append(mask_params)
        return image_composite_converter.np.ones((20, 20), dtype=bool)

    monkeypatch.setattr(Action, "extract_badge_element_mask", staticmethod(fake_extract))
    monkeypatch.setattr(Action, "_element_match_error", staticmethod(lambda *_args, **_kwargs: 1.0))

    err = Action._element_error_for_circle_radius(img, params, 3.5)

    assert err == 1.0
    assert len(calls) >= 2
    assert calls[0] is not params
    assert calls[1] is not params


def test_circle_match_error_penalizes_non_concentric_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Circle scoring should prefer concentric candidates when overlap is otherwise similar."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    params = {"cx": 10.0, "cy": 10.0, "r": 6.0}

    src_mask = np.zeros((20, 20), dtype=bool)
    src_mask[6:14, 6:14] = True

    concentric = np.zeros((20, 20), dtype=bool)
    concentric[6:14, 6:14] = True
    shifted = np.zeros((20, 20), dtype=bool)
    shifted[6:14, 7:15] = True

    monkeypatch.setattr(Action, "_masked_union_error_in_bbox", staticmethod(lambda *_args, **_kwargs: 0.0))

    err_concentric = Action._element_match_error(
        img,
        img,
        params,
        "circle",
        mask_orig=src_mask,
        mask_svg=concentric,
    )
    err_shifted = Action._element_match_error(
        img,
        img,
        params,
        "circle",
        mask_orig=src_mask,
        mask_svg=shifted,
    )

    assert err_shifted > err_concentric


def test_circle_match_error_penalizes_undersized_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Circle scoring should discourage candidates that shrink below source radius."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    params = {"cx": 10.0, "cy": 10.0, "r": 6.0}

    src_mask = np.zeros((20, 20), dtype=bool)
    src_mask[4:16, 4:16] = True

    undersized = np.zeros((20, 20), dtype=bool)
    undersized[6:14, 6:14] = True

    monkeypatch.setattr(Action, "_masked_union_error_in_bbox", staticmethod(lambda *_args, **_kwargs: 0.0))

    err_same = Action._element_match_error(
        img,
        img,
        params,
        "circle",
        mask_orig=src_mask,
        mask_svg=src_mask,
    )
    err_under = Action._element_match_error(
        img,
        img,
        params,
        "circle",
        mask_orig=src_mask,
        mask_svg=undersized,
    )

    assert err_under > err_same

def test_circle_pose_error_uses_element_match_scorer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Center/pose probing should go through the unified element match scorer."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    params = {"circle_enabled": True, "cx": 10.0, "cy": 10.0, "r": 6.0}

    monkeypatch.setattr(Action, "generate_badge_svg", staticmethod(lambda *_args, **_kwargs: "<svg />"))
    monkeypatch.setattr(Action, "render_svg_to_numpy", staticmethod(lambda *_args, **_kwargs: object()))
    monkeypatch.setattr(Action, "_fit_to_original_size", staticmethod(lambda _img, rendered: rendered))
    monkeypatch.setattr(
        Action,
        "extract_badge_element_mask",
        staticmethod(lambda *_args, **_kwargs: np.ones((20, 20), dtype=bool)),
    )
    monkeypatch.setattr(Action, "_element_match_error", staticmethod(lambda *_args, **_kwargs: 2.5))

    err = Action._element_error_for_circle_pose(
        img,
        params,
        cx_value=10.5,
        cy_value=9.5,
        radius_value=5.5,
    )

    assert err == 2.5


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


def test_voc_font_scale_bounds_keep_broad_search_for_large_badges() -> None:
    """Large VOC badges should keep enough headroom for text-mask driven fitting."""
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
    assert high >= 1.60


def test_voc_font_scale_bounds_expand_from_original_text_bbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """When original text extents are known, bounds should expand around that estimate."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    params = {
        "draw_text": True,
        "text_mode": "voc",
        "voc_font_scale": 0.52,
        "r": 5.0,
    }
    img = np.zeros((40, 40, 3), dtype=np.uint8)

    mask = np.zeros((40, 40), dtype=np.uint8)
    mask[10:18, 6:34] = 1  # wide/tall enough to imply larger VOC than defaults

    monkeypatch.setattr(Action, "extract_badge_element_mask", staticmethod(lambda *_args, **_kwargs: mask))

    info = Action._element_width_key_and_bounds("text", params, 40, 40, img_orig=img)

    assert info is not None
    key, low, high = info
    assert key == "voc_font_scale"
    assert low <= 0.90
    assert high >= 2.0


def test_finalize_ac08_style_caps_ac0835_s_voc_growth() -> None:
    """AC0835_S should keep VOC scale bounded to avoid heavy-looking labels."""
    params = Action._apply_voc_label(Action._default_ac0870_params(15, 15))

    finalized = Action._finalize_ac08_style("AC0835_S", params)

    assert finalized["lock_text_scale"] is False
    assert abs(float(finalized["voc_font_scale_min"]) - 0.58) < 1e-6
    assert abs(float(finalized["voc_font_scale_max"]) - 0.546) < 1e-6


def test_finalize_ac08_style_boosts_ac0835_m_voc_baseline() -> None:
    """AC0835_M should bias VOC text upward so medium badges remain readable."""
    params = Action._apply_voc_label(Action._default_ac0870_params(20, 20))

    finalized = Action._finalize_ac08_style("AC0835_M", params)

    assert finalized["lock_text_scale"] is False
    assert abs(float(finalized["voc_font_scale"]) - 0.60) < 1e-6
    assert abs(float(finalized["voc_font_scale_min"]) - 0.60) < 1e-6
    assert "voc_font_scale_max" not in finalized


def test_voc_font_scale_bounds_honor_explicit_min_max_overrides() -> None:
    """VOC text bracketing should respect caller-provided scale bounds."""
    params = {
        "draw_text": True,
        "text_mode": "voc",
        "voc_font_scale": 0.52,
        "voc_font_scale_min": 0.58,
        "voc_font_scale_max": 0.546,
    }

    info = Action._element_width_key_and_bounds("text", params, 15, 15)

    assert info is not None
    key, low, high = info
    assert key == "voc_font_scale"
    assert abs(float(low) - 0.58) < 1e-6
    assert abs(float(high) - 0.58) < 1e-6


def test_finalize_ac08_style_caps_ac0835_s_voc_growth() -> None:
    """AC0835_S should keep VOC scale bounded to avoid heavy-looking labels."""
    params = Action._apply_voc_label(Action._default_ac0870_params(15, 15))

    finalized = Action._finalize_ac08_style("AC0835_S", params)

    assert finalized["lock_text_scale"] is False
    assert abs(float(finalized["voc_font_scale_min"]) - 0.58) < 1e-6
    assert abs(float(finalized["voc_font_scale_max"]) - 0.546) < 1e-6


def test_voc_font_scale_bounds_honor_explicit_min_max_overrides() -> None:
    """VOC text bracketing should respect caller-provided scale bounds."""
    params = {
        "draw_text": True,
        "text_mode": "voc",
        "voc_font_scale": 0.52,
        "voc_font_scale_min": 0.58,
        "voc_font_scale_max": 0.546,
    }

    info = Action._element_width_key_and_bounds("text", params, 15, 15)

    assert info is not None
    key, low, high = info
    assert key == "voc_font_scale"
    assert abs(float(low) - 0.58) < 1e-6
    assert abs(float(high) - 0.58) < 1e-6


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






def test_finalize_persists_stem_length_floor_for_ac08_stem_connectors() -> None:
    params = Action._default_ac0881_params(15, 15)
    params = Action._finalize_ac08_style("AC0881_S", params)

    stem_len = float(params["stem_bottom"]) - float(params["stem_top"])
    assert stem_len > 0.0
    assert float(params.get("stem_len_min_ratio", 0.0)) >= 0.65
    assert float(params.get("stem_len_min", 0.0)) >= stem_len * float(params["stem_len_min_ratio"])


def test_finalize_persists_arm_length_floor_for_ac08_arm_connectors() -> None:
    params = Action._default_ac0812_params(15, 15)
    params = Action._finalize_ac08_style("AC0812_S", params)

    arm_len = float(abs(params["arm_x2"] - params["arm_x1"]))
    assert arm_len > 0.0
    assert float(params.get("arm_len_min_ratio", 0.0)) >= 0.75
    assert float(params.get("arm_len_min", 0.0)) >= arm_len * float(params["arm_len_min_ratio"])

def test_optimize_stem_extent_keeps_bottom_anchored_ac0811_stem_from_collapsing() -> None:
    """Bottom-anchored AC0811 stems should retain a minimum visible length during bracketing."""
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (15, 15, 3)

    img = DummyImg()
    params = Action._default_ac0811_params(15, 15)
    params = Action._finalize_ac08_style("AC0811_S", params)

    logs: list[str] = []
    original = Action._element_error_for_extent

    def prefer_tiny(_img: object, _params: dict, _element: str, extent_value: float) -> float:
        # Try to collapse the stem aggressively; guardrails should prevent this.
        return abs(float(extent_value) - 1.0)

    Action._element_error_for_extent = staticmethod(prefer_tiny)
    try:
        changed = Action._optimize_element_extent_bracket(img, params, "stem", logs)
    finally:
        Action._element_error_for_extent = original

    assert changed is True
    stem_len = float(params["stem_bottom"]) - float(params["stem_top"])
    assert stem_len >= 5.5
    assert abs(float(params["stem_top"]) - (float(params["cy"]) + float(params["r"]))) < 1e-6
    assert any("Längen-Bracketing" in line for line in logs)


def test_fit_ac0811_preserves_visible_stem_when_circle_estimate_reaches_bottom() -> None:
    """AC0811 fitting should keep at least a small visible stem segment."""

    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (15, 15, 3)

    img = DummyImg()
    defaults = Action._default_ac0811_params(15, 15)

    original_fit = Action._fit_semantic_badge_from_image
    original_upper = Action._estimate_upper_circle_from_foreground
    try:
        Action._fit_semantic_badge_from_image = staticmethod(
            lambda _img, _defaults: {
                **dict(defaults),
                "cx": float(defaults["cx"]),
                "cy": float(defaults["cy"]),
                # Simulate a noisy fit where the circle radius grows so much
                # that stem_top would otherwise land at/below image bottom.
                "r": float(img.shape[0]),
                "stem_width": float(defaults["stem_width"]),
            }
        )
        Action._estimate_upper_circle_from_foreground = staticmethod(lambda _img, _defaults: None)

        params = Action._fit_ac0811_params_from_image(img, defaults)
    finally:
        Action._fit_semantic_badge_from_image = original_fit
        Action._estimate_upper_circle_from_foreground = original_upper

    assert float(params["stem_bottom"]) == float(img.shape[0])
    assert float(params["stem_top"]) <= float(img.shape[0]) - 1.0
    assert float(params["stem_bottom"]) - float(params["stem_top"]) >= 1.0


def test_estimate_vertical_stem_from_mask_ignores_circle_junction_bulge() -> None:
    """Stem width estimate should prefer the lower stem over top junction bulges."""

    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    np = image_composite_converter.np
    mask = np.zeros((20, 15), dtype=bool)

    # Simulate anti-aliased widening near the circle/stem transition.
    mask[0:6, 4:11] = True   # wide top bulge (7 px)
    mask[6:20, 6:9] = True   # actual slim stem (3 px)

    est = Action._estimate_vertical_stem_from_mask(mask, expected_cx=7.0, y_start=0, y_end=20)
    assert est is not None

    est_cx, est_width = est
    assert abs(float(est_cx) - 7.0) <= 0.6
    assert abs(float(est_width) - 3.0) <= 0.25

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


def test_co2_layout_prioritizes_co_centering_before_cluster_centering() -> None:
    """center_co mode should keep the main CO run centered, even with a large subscript."""
    params = Action._apply_co2_label(Action._default_ac0870_params(20, 20))
    params["co2_anchor_mode"] = "center_co"
    params["co2_sub_font_scale"] = 130.0

    layout = Action._co2_layout(params)
    cx = float(params["cx"])
    r = float(params["r"])
    stroke = float(params["stroke_circle"])
    inner_padding = float(params.get("co2_inner_padding_px", 0.35))

    inner_left = cx - max(1.0, r - stroke) + inner_padding
    inner_right = cx + max(1.0, r - stroke) - inner_padding

    assert abs(float(layout["co_x"]) - cx) <= 0.20
    assert float(layout["x1"]) >= inner_left - 1e-6
    assert float(layout["x2"]) <= inner_right + 1e-6


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
        Action._optimize_element_color_bracket = original_color

    assert call_order == ["width", "extent", "center", "radius", "color"]


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


def test_make_badge_params_supports_ac0810_variants() -> None:
    """AC0810 and variant names should map to the semantic right-arm badge model."""
    params = Action.make_badge_params(25, 15, "AC0810")

    assert params is not None
    assert params.get("arm_enabled") is True
    assert float(params["arm_x2"]) > float(params["arm_x1"])
    assert float(params["arm_x2"]) >= 22.0


def test_parse_description_marks_ac0810_as_semantic_badge() -> None:
    """Reflection parsing should treat AC0810 as a semantic circle+right-arm badge."""
    desc, params = image_composite_converter.Reflection({}).parse_description("AC0810", "AC0810_L.jpg")

    assert desc == ""
    assert params["mode"] == "semantic_badge"
    assert "SEMANTIC: Kreis ohne Buchstabe" in params["elements"]
    assert "SEMANTIC: waagrechter Strich rechts vom Kreis" in params["elements"]


@pytest.mark.parametrize(
    ("symbol", "expected_element"),
    [
        ("AC0814", "SEMANTIC: waagrechter Strich rechts vom Kreis"),
        ("AC0834", "SEMANTIC: waagrechter Strich rechts vom Kreis"),
        ("AC0837", "SEMANTIC: waagrechter Strich links vom Kreis"),
        ("AC0831", "SEMANTIC: senkrechter Strich hinter dem Kreis"),
    ],
)
def test_parse_description_infers_semantic_connectors_for_derived_ac08_badges(symbol: str, expected_element: str) -> None:
    """Derived AC08 badges should carry the same connector semantics as their base geometry."""
    _desc, params = image_composite_converter.Reflection({}).parse_description(symbol, f"{symbol}_L.jpg")

    assert params["mode"] == "semantic_badge"
    assert expected_element in params["elements"]


def test_template_transfer_skips_nonsemantic_donors_for_semantic_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Semantic target badges must not accept generic donor transforms that can drop connector semantics."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    cv2 = image_composite_converter.cv2

    folder = tmp_path / "images"
    svg_dir = tmp_path / "svg"
    diff_dir = tmp_path / "diff"
    folder.mkdir()
    svg_dir.mkdir()
    diff_dir.mkdir()

    img = np.full((25, 45, 3), 240, dtype=np.uint8)
    target_filename = "AC0812_L.jpg"
    cv2.imwrite(str(folder / target_filename), img)

    target_params = Action.make_badge_params(45, 25, "AC0812")
    assert target_params is not None
    target_params["mode"] = "semantic_badge"
    target_svg = Action.generate_badge_svg(45, 25, target_params)
    (svg_dir / "AC0812_L.svg").write_text(target_svg, encoding="utf-8")

    donor_params = Action.make_badge_params(30, 30, "AC0800")
    assert donor_params is not None
    donor_params["mode"] = "auto"
    donor_svg = Action.generate_badge_svg(30, 30, donor_params)
    (svg_dir / "AC0800_S.svg").write_text(donor_svg, encoding="utf-8")

    monkeypatch.setattr(Action, "render_svg_to_numpy", staticmethod(lambda _svg, w, h: np.full((h, w, 3), 240, dtype=np.uint8)))
    monkeypatch.setattr(Action, "calculate_error", staticmethod(lambda _a, _b: 0.0))
    monkeypatch.setattr(Action, "create_diff_image", staticmethod(lambda a, _b: a.copy()))

    target_row = {
        "filename": target_filename,
        "variant": "AC0812_L",
        "base": "AC0812",
        "params": target_params,
        "best_error": 9999.0,
        "error_per_pixel": 1.0,
        "w": 45,
        "h": 25,
    }
    donor_rows = [
        {
            "variant": "AC0800_S",
            "base": "AC0800",
            "params": donor_params,
            "error_per_pixel": 0.01,
            "w": 30,
            "h": 30,
        }
    ]

    updated_row, detail = image_composite_converter._try_template_transfer(
        target_row=target_row,
        donor_rows=donor_rows,
        folder_path=str(folder),
        svg_out_dir=str(svg_dir),
        diff_out_dir=str(diff_dir),
        rng=None,
    )

    assert updated_row is None
    assert detail is None


def test_template_transfer_skips_semantic_but_incompatible_donors_for_connector_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Semantic transfer should reject semantic donors that cannot preserve connector geometry."""
    if image_composite_converter.np is None or image_composite_converter.cv2 is None:
        pytest.skip("numpy/cv2 not available in this environment")

    np = image_composite_converter.np
    cv2 = image_composite_converter.cv2

    folder = tmp_path / "images"
    svg_dir = tmp_path / "svg"
    diff_dir = tmp_path / "diff"
    folder.mkdir()
    svg_dir.mkdir()
    diff_dir.mkdir()

    img = np.full((25, 45, 3), 240, dtype=np.uint8)
    target_filename = "AC0812_L.jpg"
    cv2.imwrite(str(folder / target_filename), img)

    target_params = Action.make_badge_params(45, 25, "AC0812")
    assert target_params is not None
    target_params["mode"] = "semantic_badge"
    (svg_dir / "AC0812_L.svg").write_text(Action.generate_badge_svg(45, 25, target_params), encoding="utf-8")

    # Semantic donor without arm connector (plain circle).
    donor_params = Action.make_badge_params(30, 30, "AC0870")
    assert donor_params is not None
    donor_params["mode"] = "semantic_badge"
    (svg_dir / "AC0870_S.svg").write_text(Action.generate_badge_svg(30, 30, donor_params), encoding="utf-8")

    monkeypatch.setattr(Action, "render_svg_to_numpy", staticmethod(lambda _svg, w, h: np.full((h, w, 3), 240, dtype=np.uint8)))
    monkeypatch.setattr(Action, "calculate_error", staticmethod(lambda _a, _b: 0.0))
    monkeypatch.setattr(Action, "create_diff_image", staticmethod(lambda a, _b: a.copy()))

    target_row = {
        "filename": target_filename,
        "variant": "AC0812_L",
        "base": "AC0812",
        "params": target_params,
        "best_error": 9999.0,
        "error_per_pixel": 1.0,
        "w": 45,
        "h": 25,
    }
    donor_rows = [
        {
            "variant": "AC0870_S",
            "base": "AC0870",
            "params": donor_params,
            "error_per_pixel": 0.01,
            "w": 30,
            "h": 30,
        }
    ]

    updated_row, detail = image_composite_converter._try_template_transfer(
        target_row=target_row,
        donor_rows=donor_rows,
        folder_path=str(folder),
        svg_out_dir=str(svg_dir),
        diff_out_dir=str(diff_dir),
        rng=None,
    )

    assert updated_row is None
    assert detail is None


def test_semantic_transfer_rejects_opposite_arm_directions() -> None:
    """Semantic transfer must not mix right-arm donors into left-arm targets."""
    target = Action.make_badge_params(45, 25, "AC0812")
    donor = Action.make_badge_params(45, 25, "AC0810")

    assert target is not None
    assert donor is not None
    assert target.get("arm_enabled") is True
    assert donor.get("arm_enabled") is True

    assert image_composite_converter._semantic_transfer_is_compatible(target, donor) is False


def test_enforce_semantic_connector_expectation_restores_left_arm_for_ac0812() -> None:
    params = {
        "circle_enabled": True,
        "cx": 32.5,
        "cy": 12.5,
        "r": 8.0,
        "arm_enabled": False,
    }

    restored = Action._enforce_semantic_connector_expectation(
        "AC0812",
        ["SEMANTIC: Kreis ohne Buchstabe", "SEMANTIC: waagrechter Strich links vom Kreis"],
        params,
        45,
        25,
    )

    assert restored["arm_enabled"] is True
    assert float(restored["arm_x1"]) == 0.0
    assert abs(float(restored["arm_x2"]) - (float(restored["cx"]) - float(restored["r"]))) < 1e-6


def test_enforce_semantic_connector_expectation_handles_variant_base_name_for_ac0812() -> None:
    """Variant names (AC0812_L/M/S) should still trigger left-arm semantic guard."""
    params = {
        "circle_enabled": True,
        "cx": 32.5,
        "cy": 12.5,
        "r": 8.0,
        "arm_enabled": False,
    }

    restored = Action._enforce_semantic_connector_expectation(
        "AC0812_L",
        ["SEMANTIC: Kreis ohne Buchstabe", "SEMANTIC: waagrechter Strich links vom Kreis"],
        params,
        45,
        25,
    )

    assert restored["arm_enabled"] is True
    assert float(restored["arm_x1"]) == 0.0
    assert abs(float(restored["arm_x2"]) - (float(restored["cx"]) - float(restored["r"]))) < 1e-6


def test_optimize_circle_pose_adaptive_domain_logs_random_domain_steps() -> None:
    if image_composite_converter.np is None:
        pytest.skip("numpy not available in this environment")

    class DummyImg:
        shape = (25, 45, 3)

    img = DummyImg()
    params = Action._default_ac0812_params(45, 25)
    params = Action._finalize_ac08_style("AC0812", params)

    original_eval = Action._element_error_for_circle_pose

    def paraboloid(_img: object, _params: dict, *, cx_value: float, cy_value: float, radius_value: float) -> float:
        return (
            ((float(cx_value) - 32.5) ** 2)
            + ((float(cy_value) - 12.5) ** 2)
            + ((float(radius_value) - 8.0) ** 2)
        )

    logs: list[str] = []
    Action._element_error_for_circle_pose = staticmethod(paraboloid)
    try:
        changed = Action._optimize_circle_pose_adaptive_domain(
            img,
            params,
            logs,
            rounds=2,
            samples_per_round=8,
        )
    finally:
        Action._element_error_for_circle_pose = original_eval

    assert changed is True
    assert any("Möglichkeitsraum" in line for line in logs)
    assert any("random-samples" in line for line in logs)
    assert any("Möglichkeitsraum eingegrenzt" in line for line in logs)
