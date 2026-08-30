"""Regression tests for the repository-wide test runner."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repository_run_all", ROOT / "src" / "run_all.py")
run_all = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_all)


def test_tiny_cpu_acceptance_failure_fails_containing_run(monkeypatch):
    """The real all-opcode gate must not degrade into an optional check."""

    calls = []

    class Result:
        returncode = 1

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()

    monkeypatch.setattr(run_all.subprocess, "run", fake_run)
    failures = []
    run_all.run_tiny_cpu_acceptance(failures)

    assert calls[0][0] == [str(ROOT / "scripts" / "test-logisim.sh")]
    assert calls[0][1]["cwd"] == ROOT
    assert failures == ["TinyCPU electrical opcode acceptance"]


def test_smoke_mode_still_runs_electrical_opcode_acceptance(monkeypatch):
    """The fast runner must not bypass the complete TinyCPU instruction proof."""

    acceptance_calls = []
    monkeypatch.setattr(run_all, "parse_args", lambda: type("Args", (), {"smoke": True})())
    monkeypatch.setattr(run_all, "run_pytest", lambda failures, extra_args: None)
    monkeypatch.setattr(
        run_all,
        "run_tiny_cpu_acceptance",
        lambda failures: acceptance_calls.append(failures),
    )
    monkeypatch.setattr(run_all, "SMOKE_COMMANDS", [])

    assert run_all.main() == 0
    assert len(acceptance_calls) == 1
