"""Regression tests for CO₂ text positioning in semantic badges."""

from __future__ import annotations

from src.image_composite_converter import Action


def test_co2_label_defaults_keep_co_centered() -> None:
    """Default CO₂ layout should center the "CO" run on the circle center."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    layout = Action._co2_layout(params)

    assert layout["anchor_mode"] == "center_co"
    assert abs(float(layout["co_x"]) - float(params["cx"])) < 1e-6


def test_co2_layout_legacy_cluster_mode_still_supported() -> None:
    """Legacy cluster-centered mode should still shift CO left for the subscript."""
    params = Action._apply_co2_label(Action._default_ac0870_params(15, 15))
    params["co2_anchor_mode"] = "cluster"
    layout = Action._co2_layout(params)

    assert layout["anchor_mode"] == "cluster"
    assert float(layout["co_x"]) < float(params["cx"])
