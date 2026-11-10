"""Independent workload oracles and counterexamples for work package 11."""

from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys

import pytest

from benchmarks.argument_isolation import (
    ROUTES, counterexamples, decode, make_runner, oracle, validate,
)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("size,rounds", [(1, 1), (3, 3), (16, 2)])
def test_price_preview_against_exact_oracle(route, size, rounds):
    """Protected implementations agree with mathematics; controls expose writes."""
    result = make_runner(route, size, rounds)()
    observed = validate(result, route, size, rounds)
    assert observed["preserves_original"] == (not route.endswith("shared"))


def test_oracle_has_independently_derived_small_example():
    """Three prices total 3003.75; each preview adds exactly 1.5."""
    assert oracle(3, 3, True) == ([Fraction("3005.25")] * 3, True, Fraction("3003.75"))
    assert oracle(3, 3, False) == (
        [Fraction("3005.25"), Fraction("3006.75"), Fraction("3008.25")],
        False, Fraction("3008.25"),
    )


@pytest.mark.parametrize("route", ["tiny_shared", "python_shared"])
def test_negative_controls_cannot_be_counted_as_isolation(route):
    """The isolation oracle must reject actual shared execution results."""
    result = make_runner(route, 3, 3)()
    assert decode(result[0], 3) != oracle(3, 3, True)
    with pytest.raises(AssertionError, match="observed"):
        validate(result, "tiny_copy" if route.startswith("tiny") else "python_deepcopy", 3, 3)


def test_design_counterexamples_execute():
    """Global guards, receivers, nesting, shallow rows and manual cleanup are real."""
    results = counterexamples()
    assert results["global_alias_tiny"] == "protected parameter error"
    assert results["shared_method_receiver_tiny"] == ["1000.75", "1000.75"]
    assert results["nested_python_copy_each_call"] != results["nested_python_outer_copy_only"]
    assert results["discarded_tiny_heap_copy_live_allocations"] == 1


def test_standalone_examples_match(tmp_path):
    """The checked-in examples execute directly with their documented defaults."""
    root = Path(__file__).resolve().parents[1]
    commands = [
        [str(root / "src/tiny_language.py"), "--copy-on-call",
         str(root / "examples/argument_isolation/price_preview.tiny")],
        [str(root / "examples/argument_isolation/price_preview.py"), "--strategy", "deepcopy"],
    ]
    for command in commands:
        result = subprocess.run([sys.executable, *command], cwd=tmp_path,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert decode(result.stdout, 3) == oracle(16, 3, True)


def test_experiment_cli_runs_outside_checkout(tmp_path):
    """Reproduction writes complete evidence from an unrelated working directory."""
    root = Path(__file__).resolve().parents[1]
    report = tmp_path / "evidence.json"
    result = subprocess.run(
        [sys.executable, str(root / "benchmarks/argument_isolation.py"),
         "--sizes", "2", "--rounds", "2", "--repeat", "1", "--output", str(report)],
        cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(report.read_text(encoding="utf-8"))
    assert len(evidence["results"]) == 6
    assert evidence["source_changed_during_run"] is False
    assert evidence["protocol_sha256"] == evidence["source_sha256"]["docs/argument_isolation_protocol.md"]
    for row in evidence["results"]:
        assert len(row["samples_ns"]) == 1
        assert row["traced_peak_bytes"] > 0
