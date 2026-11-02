"""Module imports must preserve unchanged summaries across operating systems."""

import os

import pytest

from tiny_language import compile_and_run


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_unchanged_summary_keeps_original_bytes_and_timestamp(tmp_path, newline):
    """Reading a matching LF/CRLF cache must not modify candidate source files."""
    module = tmp_path / "sample.tiny"
    source = "fn value() -> number { return 7; } print(value());"
    module.write_text(source, encoding="utf-8")
    assert compile_and_run(source, module_path=module, module_namespace="sample", stream_output=False) == "7\n"
    summary = module.with_suffix(".tiny.summary")
    expected = summary.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", newline)
    summary.write_bytes(expected)
    # A fixed past timestamp detects writes even on filesystems with coarse clocks.
    os.utime(summary, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    previous = summary.stat().st_mtime_ns
    assert compile_and_run(source, module_path=module, module_namespace="sample", stream_output=False) == "7\n"
    assert summary.read_bytes() == expected
    assert summary.stat().st_mtime_ns == previous


def test_outdated_summary_is_updated_with_lf(tmp_path):
    """A real export change must still replace stale cache contents."""
    module = tmp_path / "sample.tiny"
    source = "fn value() -> number { return 7; } print(value());"
    module.write_text(source, encoding="utf-8")
    summary = module.with_suffix(".tiny.summary")
    summary.write_bytes(b"outdated\r\n")
    assert compile_and_run(source, module_path=module, module_namespace="sample", stream_output=False) == "7\n"
    assert b"fn value(" in summary.read_bytes()
    assert b"\r" not in summary.read_bytes()
