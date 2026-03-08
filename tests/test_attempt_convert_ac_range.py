from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "tools" / "attempt_convert_ac_range.py"
SPEC = importlib.util.spec_from_file_location("attempt_convert_ac_range", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
attempt_convert = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(attempt_convert)


def test_resolve_runtime_path_prefers_explicit_path() -> None:
    explicit = "/tmp/my_runtime"
    assert attempt_convert._resolve_runtime_path(explicit) == explicit


def test_resolve_runtime_path_uses_repo_vendor_fallback() -> None:
    expected = str((Path(__file__).resolve().parent.parent / "vendor" / "converter_runtime"))
    assert attempt_convert._resolve_runtime_path("") == expected
