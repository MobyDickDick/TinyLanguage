from __future__ import annotations

import importlib.util

import pytest

import src.run_all as run_all


def test_resolve_pytest_command_uses_current_python_when_pytest_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())

    command = run_all.resolve_pytest_command()

    assert command == [run_all.PYTHON, "-m", "pytest"]


def test_resolve_pytest_command_prefers_path_python_when_missing_pytest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(run_all.os, "name", "posix", raising=False)
    monkeypatch.setattr(run_all.shutil, "which", lambda name: "/usr/bin/python")

    command = run_all.resolve_pytest_command()

    assert command == ["/usr/bin/python", "-m", "pytest"]
