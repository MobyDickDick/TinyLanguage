"""Regression tests for the repository-wide test runner."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repository_run_all", ROOT / "src" / "run_all.py")
run_all = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_all)


@pytest.mark.parametrize("smoke", [False, True])
@pytest.mark.parametrize("demo_exit", [0, 1])
def test_runner_selects_language_suite_and_propagates_demo_failure(monkeypatch, smoke, demo_exit):
    """Both runner modes execute their demos and retain failure exit status."""

    calls = []
    pytest_targets = []
    full_commands = [("full demo", [run_all.REPO_PYTHON, "full-demo.tiny"])]
    smoke_commands = [("smoke demo", [run_all.REPO_PYTHON, "smoke-demo.tiny"])]

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=demo_exit)

    monkeypatch.delenv("TINYLANGUAGE_SMOKE", raising=False)
    monkeypatch.setattr(run_all, "parse_args", lambda: SimpleNamespace(smoke=smoke))
    monkeypatch.setattr(run_all, "run_pytest", lambda failures, extra_args: pytest_targets.append(extra_args))
    monkeypatch.setattr(run_all, "COMMANDS", full_commands)
    monkeypatch.setattr(run_all, "SMOKE_COMMANDS", smoke_commands)
    monkeypatch.setattr(run_all.subprocess, "run", fake_run)

    assert run_all.main() == demo_exit
    assert pytest_targets == [run_all.SMOKE_PYTEST_TARGETS if smoke else None]
    selected_commands = smoke_commands if smoke else full_commands
    assert [command for command, _ in calls] == [command for _, command in selected_commands]
    assert calls[0][1]["cwd"] == ROOT
    assert str(ROOT / "src") in calls[0][1]["env"]["PYTHONPATH"].split(run_all.os.pathsep)
