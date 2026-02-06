"""Tests for enforcing the v1-only language profile."""

import pytest

from tiny_language import TinyLangError, _parse_and_lint


def test_v1_only_blocks_experimental_math(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure v1-only mode rejects experimental math syntax flags."""
    monkeypatch.setenv("TINYLANG_V1_ONLY", "1")
    monkeypatch.setenv("TINYLANG_EXPERIMENTAL_MATH_TUPLES", "1")
    source = "def area = (sqrt: 9);"
    with pytest.raises(TinyLangError) as excinfo:
        _parse_and_lint(source)
    assert "v1-only mode forbids experimental math syntax" in str(excinfo.value)


def test_v1_only_allows_core_syntax(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure core syntax still parses when v1-only mode is enabled."""
    monkeypatch.setenv("TINYLANG_V1_ONLY", "1")
    source = "def answer = 42; print(answer);"
    stmts = _parse_and_lint(source)
    assert len(stmts) >= 1
