"""Tests for the stdlib os module."""

from __future__ import annotations

import os
import sys


def _escape_tiny_string(value: str) -> str:
    """Escape a Python string literal for TinyLanguage source."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _expected_platform() -> str:
    """Map Python platform identifiers to TinyLanguage's stable values."""
    platform = sys.platform
    if platform.startswith("linux"):
        return "linux"
    if platform.startswith("darwin"):
        return "darwin"
    if platform.startswith(("win32", "cygwin")):
        return "windows"
    return "unknown"


def test_stdlib_os_environment_and_platform(run_tiny_source, monkeypatch):
    """Validate env helpers plus platform + separator outputs."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")
    missing_key = "TINY_STD_OS_TEST_MISSING"
    value_key = "TINY_STD_OS_TEST_VALUE"
    monkeypatch.delenv(missing_key, raising=False)
    monkeypatch.delenv(value_key, raising=False)

    missing_out = run_tiny_source(
        f'''
        import stdlib.os;

        print(os.getenv("{missing_key}"));
        ''',
    )
    assert missing_out == "Null\n"

    out = run_tiny_source(
        f'''
        import stdlib.os;

        print(os.setenv("{value_key}", "value"));
        print(os.getenv("{value_key}"));
        print(os.unsetenv("{value_key}"));
        print(os.platform());
        print(os.path_separator());
        ''',
    )

    expected = (
        "true\n"
        "value\n"
        "true\n"
        f"{_expected_platform()}\n"
        f"{os.sep}\n"
    )
    assert out == expected


def test_stdlib_os_cwd_chdir_listdir(run_tiny_source, monkeypatch, tmp_path):
    """Validate cwd/chdir round-trip and listdir ordering."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")

    tmp_dir = tmp_path / "os_test"
    tmp_dir.mkdir()
    (tmp_dir / "alpha.txt").write_text("alpha", encoding="utf-8")
    (tmp_dir / "beta").mkdir()
    (tmp_dir / "gamma.txt").write_text("gamma", encoding="utf-8")

    original_cwd = os.getcwd()
    expected_names = sorted(["alpha.txt", "beta", "gamma.txt"])
    normalized_original = original_cwd.replace("\\", "/")
    normalized_tmp = str(tmp_dir).replace("\\", "/")

    out = run_tiny_source(
        f'''
        import stdlib.os;

        print(os.cwd());
        print(os.chdir("{_escape_tiny_string(str(tmp_dir))}"));
        print(os.cwd());

        def entries = os.listdir("{_escape_tiny_string(str(tmp_dir))}");
        print(Collections.len(entries));
        print(heap_get(entries, 0));
        print(heap_get(entries, 1));
        print(heap_get(entries, 2));
        def _cleanup_entries = delete(entries);

        print(os.chdir("{_escape_tiny_string(original_cwd)}"));
        print(os.cwd());
        ''',
    )

    expected = (
        f"{normalized_original}\n"
        "true\n"
        f"{normalized_tmp}\n"
        "3\n"
        f"{expected_names[0]}\n"
        f"{expected_names[1]}\n"
        f"{expected_names[2]}\n"
        "true\n"
        f"{normalized_original}\n"
    )
    assert out == expected
