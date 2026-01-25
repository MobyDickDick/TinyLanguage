"""Tests for backend output normalization helpers."""

from __future__ import annotations

import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from output_normalization import NormalizationOptions, normalize_output  # noqa: E402


def test_normalize_line_endings_and_whitespace() -> None:
    """Normalize line endings and trailing whitespace."""
    raw = "line 1 \r\n\r\nline 2\t\r\n"
    normalized = normalize_output(raw)
    assert normalized == "line 1\n\nline 2"


def test_normalize_banners_and_timing_lines() -> None:
    """Strip banner and timing lines from output."""
    raw = "\n".join(
        [
            "TinyLanguage v1.2.3",
            "Interpreter startup",
            "elapsed=12ms",
            "Result: ok",
        ]
    )
    normalized = normalize_output(raw)
    assert normalized == "Result: ok"


def test_normalize_error_prefix_and_paths() -> None:
    """Normalize error prefixes and rewrite absolute paths."""
    root = pathlib.Path("/workspace/TinyLanguage")
    raw = "Error: failure at /workspace/TinyLanguage/src/main.tiny:12"
    normalized = normalize_output(raw, NormalizationOptions(root=root))
    assert normalized == "error: failure at <ROOT>/src/main.tiny:12"


def test_normalize_pid_port_seed_tokens() -> None:
    """Normalize PID/port/seed values into placeholders."""
    raw = "pid=123 port: 8080 seed=999 random_seed 42"
    normalized = normalize_output(raw)
    assert normalized == "pid=<ID> port=<ID> seed=<SEED> random_seed=<SEED>"


def test_strip_stack_traces_by_default() -> None:
    """Drop stack trace lines unless the option requests them."""
    raw = "\n".join(
        [
            "Traceback (most recent call last):",
            "  File \"example.tiny\", line 1, in <module>",
            "RuntimeError: boom",
        ]
    )
    normalized = normalize_output(raw)
    assert normalized == "error: boom"
