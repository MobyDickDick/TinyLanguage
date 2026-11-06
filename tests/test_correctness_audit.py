"""Independent oracles and failure-detection checks for work package 9."""

from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
import json
import hashlib
import random

import pytest

from tiny_language import compile_and_run
from tools.correctness_audit import assess, compare_output, known_gap, stage_evidence, validate_report, worker
from tools.correctness_cases import BACKENDS, CASES


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_interpreter_against_independent_contract(case, tmp_path, monkeypatch):
    """Every corpus program must really exercise its declared reference contract."""
    for key in ("TINYLANG_COPY_ON_CALL", "TINY_ASSERT_NO_HEAP_LEAKS", "TINY_LINT_HEAP"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "result.json"
    worker(case, "interpreter", "clang", tmp_path, path)
    result = json.loads(path.read_text(encoding="utf-8"))
    assert assess(case, result) == "passed", result


@pytest.mark.parametrize("copy_on_call", [False, True])
def test_shared_graph_mutations_against_python_deepcopy_model(copy_on_call):
    """Preserve the graph's alias relation while isolating the caller when opted in.

    Python's standard deepcopy supplies a separately implemented graph model;
    no Tiny copy, parser escape metadata or backend output computes the oracle.
    """
    rng = random.Random(9007)
    for _ in range(12):
        initial, delta, adopted = (rng.randint(-100, 100) for _ in range(3))
        shared = {"value": initial}
        original = {"left": shared, "right": shared}
        parameter = deepcopy(original) if copy_on_call else original
        parameter["left"]["value"] += delta
        expected = [original["left"]["value"], original["right"]["value"],
                    parameter["right"]["value"]]
        parameter["right"]["value"] = adopted
        expected.extend([original["left"]["value"], parameter["left"]["value"]])
        source = f"""
        fn mutate(graph) {{ def left = graph.left; left.value = left.value + {delta}; return graph; }}
        def shared = {{value: {initial}}};
        def original = {{left: shared, right: shared}};
        def result = mutate(original);
        print(original.left.value); print(original.right.value); print(result.right.value);
        def right = result.right; right.value = {adopted};
        print(original.left.value); print(result.left.value);
        """
        actual = compile_and_run(source, stream_output=False, copy_on_call=copy_on_call)
        assert actual == "".join(f"{value}\n" for value in expected)


def test_exact_oracle_rejects_both_historical_interval_defects():
    """Mutation witnesses: neither old expected result is mathematically enclosing."""
    from tests.detailtests.test_interval_enclosure import assert_encloses

    # q=0 is realized by x=0, y=1/2 in [-2,3] / [-5,1/2]. The old exterior
    # [6,-4] excludes it. This witness uses no interval implementation helper.
    with pytest.raises(AssertionError):
        assert_encloses((6, -4, "wrapped_interval"), [Fraction(0, 1)])
    # Both operands are exact binary64 values; [1,1] loses their exact sum.
    with pytest.raises(AssertionError):
        assert_encloses((1, 1, "normal"), [Fraction(1) + Fraction(1, 2**53)])


@pytest.mark.parametrize("actual,expected", [
    ("1\n", "1.0000000000000002\n"), ("1\n", "1.5\n"),
    ("1\n", "true\n"), ("null\n", "Null\n"),
    ("TinyLanguage\n", ""), ("elapsed 2s\n", ""), ("1\n\n", "1\n"),
])
def test_oracle_does_not_normalize_away_semantic_differences(actual, expected):
    assert not compare_output(actual, expected)


def test_decimal_spelling_may_differ_without_losing_any_value():
    assert compare_output("3.000000\r\n0.125000\r\n", "3\n0.125\n")


def success_record(backend="interpreter", output=""):
    stages = {"frontend": "passed"}
    if backend != "interpreter":
        stages["codegen"] = "passed"
    if backend in {"llvm", "c"}:
        stages["compile"] = "passed"
    stages["execute"] = "passed"
    return dict(backend=backend, stages=stages, stdout=output, stderr="", exit_code=0)


def test_emission_only_crashes_skips_and_wrong_stage_are_not_execution():
    case = next(case for case in CASES if case.name == "control-flow")
    record = success_record("llvm", case.expected)
    record["stages"].pop("compile")
    assert not stage_evidence(record)
    assert assess(case, record) == "failed"
    assert assess(case, dict(unavailable="clang absent")) == "unavailable"
    assert assess(case, dict(timeout=True)) == "failed"
    assert assess(case, success_record("interpreter", "")) == "failed"
    error_case = next(case for case in CASES if case.name == "division-error")
    assert assess(error_case, dict(backend="llvm", stages={"frontend": "passed", "codegen": "failed"},
                                  failure_stage="codegen", diagnostic="division by zero", exit_code=1)) == "failed"
    unexpected_effect = success_record("c", "unexpected side effect\ndivision by zero\n")
    unexpected_effect["exit_code"] = 1
    assert assess(error_case, unexpected_effect) == "failed"


def test_known_gap_does_not_hide_a_new_failure_or_count_as_passing():
    case = next(case for case in CASES if case.name == "short-circuit")
    record = success_record("native", "unexpected\nunexpected\n7\n")
    assert assess(case, record) == "failed"
    assert known_gap(case, "native", record) == "AUD-004"
    record["stdout"] = "new corruption\n"
    assert known_gap(case, "native", record) is None
    record["timeout"] = True
    assert known_gap(case, "native", record) is None


def complete_synthetic_report():
    """Synthetic data exercises the verifier; it is never retained as audit evidence."""
    results = []
    for case in CASES:
        for backend in BACKENDS:
            record = success_record(backend, case.expected)
            if case.error:
                stages = {"frontend": "failed"} if case.error_stage == "frontend" else record["stages"]
                if case.error_stage == "execute":
                    stages["execute"] = "failed"
                record.update(stages=stages, failure_stage=case.error_stage, exit_code=1, diagnostic=case.error)
            record.update(case=case.name, oracle=json.loads(json.dumps(asdict(case))),
                          status="not_applicable" if backend not in case.backends else "passed")
            results.append(record)
    identity = {"input": "digest"}
    return {"files_sha256": identity, "results": results,
            "source_sha256": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
            "counts": {status: sum(r["status"] == status for r in results)
                       for status in ("passed", "failed", "unavailable", "not_applicable")}}


def test_report_rejects_stale_partial_duplicated_and_altered_evidence():
    report = complete_synthetic_report()
    assert validate_report(report, {"input": "digest"}) == []
    assert validate_report(report, {"input": "changed"})
    partial = deepcopy(report)
    partial["results"].pop()
    assert validate_report(partial, {"input": "digest"})
    duplicate = deepcopy(report)
    duplicate["results"].append(duplicate["results"][0])
    assert validate_report(duplicate, {"input": "digest"})
    altered = deepcopy(report)
    altered["results"][0]["oracle"]["expected"] = "incorrect\n"
    assert validate_report(altered, {"input": "digest"})
    altered["results"][0]["stdout"] = "incorrect\n"
    assert validate_report(altered, {"input": "digest"})
    altered = deepcopy(report)
    altered["counts"]["passed"] += 1
    assert validate_report(altered, {"input": "digest"})
