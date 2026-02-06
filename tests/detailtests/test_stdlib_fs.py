"""Tests for the stdlib fs module."""

from __future__ import annotations

import os


def _escape_tiny_string(value: str) -> str:
    """Escape a Python string literal for TinyLanguage source."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _normalize_path(value: str) -> str:
    """Normalize paths to the TinyLanguage forward-slash format."""
    return value.replace("\\", "/")


def test_stdlib_fs_file_roundtrip(run_tiny_source, monkeypatch, tmp_path):
    """Validate fs read/write/exists/remove against Python file behavior."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")

    file_path = tmp_path / "example.txt"
    content = "hello from fs"

    out = run_tiny_source(
        f'''
        import stdlib.fs;

        print(fs.write_text("{_escape_tiny_string(str(file_path))}", "{content}"));
        print(fs.read_text("{_escape_tiny_string(str(file_path))}"));
        print(fs.exists("{_escape_tiny_string(str(file_path))}"));
        print(fs.remove("{_escape_tiny_string(str(file_path))}"));
        print(fs.exists("{_escape_tiny_string(str(file_path))}"));
        ''',
    )

    expected = f"true\n{content}\ntrue\ntrue\nfalse\n"
    assert out == expected
    assert not file_path.exists()


def test_stdlib_fs_listdir_and_cwd(run_tiny_source, monkeypatch, tmp_path):
    """Validate fs listdir/cwd/chdir parity with Python os helpers."""
    monkeypatch.setenv("TINY_LINT_HEAP", "0")

    work_dir = tmp_path / "fs_demo"
    work_dir.mkdir()
    (work_dir / "alpha.txt").write_text("alpha", encoding="utf-8")
    (work_dir / "beta").mkdir()
    (work_dir / "gamma.txt").write_text("gamma", encoding="utf-8")

    original_cwd = os.getcwd()
    expected_names = sorted(os.listdir(work_dir))

    out = run_tiny_source(
        f'''
        import stdlib.fs;

        print(fs.cwd());
        print(fs.chdir("{_escape_tiny_string(str(work_dir))}"));
        print(fs.cwd());

        def entries = fs.listdir("{_escape_tiny_string(str(work_dir))}");
        print(Collections.len(entries));
        print(heap_get(entries, 0));
        print(heap_get(entries, 1));
        print(heap_get(entries, 2));
        def _cleanup_entries = delete(entries);

        print(fs.chdir("{_escape_tiny_string(original_cwd)}"));
        print(fs.cwd());
        print(fs.path_separator());
        ''',
    )

    expected = (
        f"{_normalize_path(original_cwd)}\n"
        "true\n"
        f"{_normalize_path(str(work_dir))}\n"
        "3\n"
        f"{expected_names[0]}\n"
        f"{expected_names[1]}\n"
        f"{expected_names[2]}\n"
        "true\n"
        f"{_normalize_path(original_cwd)}\n"
        f"{os.sep}\n"
    )
    assert out == expected
