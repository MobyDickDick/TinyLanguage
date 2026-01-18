import os
import pathlib
import shutil

import pytest

from tests.utils import execute_tiny_program, run_tiny


def _ensure_test_fixtures() -> None:
    """Guarantee that ``tests/src`` and ``tests/src_tiny`` are present.

    Some environments (e.g., zip archives or partial checkouts) might omit the
    duplicated fixture copies that the detail tests expect under ``tests/``.
    We mirror the canonical sources from the repository root when those folders
    are missing so the suite can still run end-to-end.
    """

    test_root = pathlib.Path(__file__).resolve().parent
    project_root = test_root.parent

    for source_dir, target_dir in (
        (project_root / "src", test_root / "src"),
        (project_root / "src_tiny", test_root / "src_tiny"),
    ):
        if target_dir.exists():
            continue
        if not source_dir.exists():
            continue
        shutil.copytree(source_dir, target_dir)


_ensure_test_fixtures()


@pytest.fixture
def run_program():
    """Run a TinyLanguage program via the CLI and capture output."""

    return execute_tiny_program


@pytest.fixture
def run_tiny_source():
    """Compile and run TinyLanguage source in-process for convenience."""

    return run_tiny


@pytest.fixture(autouse=True)
def assert_no_heap_leaks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable heap leak assertions for in-process TinyLanguage runs."""

    if os.environ.get("TINY_ASSERT_NO_HEAP_LEAKS") is None:
        monkeypatch.setenv("TINY_ASSERT_NO_HEAP_LEAKS", "1")
