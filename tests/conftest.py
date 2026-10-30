"""Pytest fixtures and CLI options for TinyLanguage's test suite."""

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


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CLI flags for test-only configuration."""

    parser.addoption(
        "--require-backend-toolchains",
        action="store_true",
        default=False,
        help="Require clang and reject skips in C/LLVM executable conformance checks.",
    )
    parser.addoption(
        "--assert-no-heap-leaks",
        action="store_true",
        default=False,
        help="Fail tests when heap allocations remain after in-process runs.",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """CI qualification must fail when the promised compiler is absent."""
    if session.config.getoption("--require-backend-toolchains") and not shutil.which("clang"):
        raise pytest.UsageError("platform qualification requires clang on PATH")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A skipped required backend check is missing acceptance evidence."""
    outcome = yield
    report = outcome.get_result()
    if (item.config.getoption("--require-backend-toolchains") and report.skipped
            and item.path.name in {"test_c_backend.py", "test_llvm_conformance_smoke.py",
                                   "test_tiny_language_compiler_cli.py"}):
        report.outcome = "failed"
        report.longrepr = "Required backend qualification skipped: " + str(report.longrepr)


@pytest.fixture
def run_program():
    """Run a TinyLanguage program via the CLI and capture output."""

    return execute_tiny_program


@pytest.fixture
def run_tiny_source():
    """Compile and run TinyLanguage source in-process for convenience."""

    return run_tiny


@pytest.fixture(autouse=True)
def assert_no_heap_leaks(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable heap leak assertions for in-process TinyLanguage runs."""

    if os.environ.get("TINY_ASSERT_NO_HEAP_LEAKS") == "1":
        return
    if not request.config.getoption("--assert-no-heap-leaks"):
        return
    if os.environ.get("TINY_ASSERT_NO_HEAP_LEAKS") is None:
        monkeypatch.setenv("TINY_ASSERT_NO_HEAP_LEAKS", "1")
