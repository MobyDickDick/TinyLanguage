"""Tests for llvm jit."""

import importlib.util

import pytest

from tiny_language import run_with_llvm_jit


def _llvmlite_available() -> bool:
    """Helper to llvmlite available."""
    if importlib.util.find_spec("llvmlite") is None:
        return False
    return importlib.util.find_spec("llvmlite.binding") is not None


def test_llvm_jit_executes_program(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that llvm jit executes program."""
    if not _llvmlite_available():
        pytest.skip("llvmlite not available")

    run_with_llvm_jit("def x = 40 + 2; print(x);")
    captured = capsys.readouterr()
    assert captured.out.strip() == "42"
