from tools.performance.check_performance_budgets import _evaluate_results


def _baseline(min_ratio: float) -> dict:
    return {
        "benchmarks": ["tight_loop"],
        "backends": ["interpreter", "native"],
        "baseline_ms": {
            "interpreter": {"tight_loop": 140.0},
            "native": {"tight_loop": 70.0},
        },
        "budgets": {
            "native": {
                "tight_loop": {"min_ratio": min_ratio},
            }
        },
        "blocked": {},
        "regression": {"max_slowdown_ratio": 1.5},
    }


def _results(interpreter_avg: float, native_avg: float) -> dict:
    return {
        "results": {
            "tight_loop": {
                "interpreter": {"avg_ms": interpreter_avg},
                "native": {"avg_ms": native_avg},
            }
        }
    }


def test_ratio_rounding_guard_avoids_false_regression() -> None:
    # 139.9 / 70.0 ~= 1.99857, which is slightly below 2.0 but still displays
    # as 2.00x; this should not fail budgets.
    issues, warnings = _evaluate_results(
        results=_results(interpreter_avg=139.9, native_avg=70.0),
        baseline=_baseline(min_ratio=2.0),
    )
    assert not warnings
    assert not issues


def test_material_ratio_drop_still_fails_budget() -> None:
    # 138.6 / 70.0 = 1.98 -> should clearly fail a 2.0x budget.
    issues, _warnings = _evaluate_results(
        results=_results(interpreter_avg=138.6, native_avg=70.0),
        baseline=_baseline(min_ratio=2.0),
    )
    assert issues
    assert "ratio 1.98x below budget 2.00x" in issues[0]
