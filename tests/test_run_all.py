from __future__ import annotations

import src.run_all as run_all


def test_run_all_uses_current_python_for_pytest() -> None:
    pytest_entries = [cmd for name, cmd in run_all.COMMANDS if name == "pytest (full suite)"]

    assert pytest_entries == [[run_all.PYTHON, "-m", "pytest"]]
